// Noise_XX_25519_ChaChaPoly_BLAKE2s 핸드셰이크 (휴대폰 = initiator).
//
// PC 에이전트(Rust, snow 라이브러리)와 바이트 단위로 호환되어야 한다.
// 규격: https://noiseprotocol.org/noise.html  (rev 34)
// 핸드셰이크 후에는 split 키로 메시지 단위 ChaCha20-Poly1305 (secure_channel.dart).

import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:crypto/crypto.dart' as crypto;

const _protocolName = 'Noise_XX_25519_ChaChaPoly_BLAKE2s';
const _prologue = 'HomePilot-Remote/1';
const _hashLen = 32;
const _blockLen = 64;

final _blake2s = Blake2s();
final _x25519 = X25519();
final _aead = Chacha20.poly1305Aead();

class NoiseException implements Exception {
  final String message;
  NoiseException(this.message);
  @override
  String toString() => 'NoiseException: $message';
}

Future<Uint8List> blake2s(List<int> data) async {
  final h = await _blake2s.hash(data);
  return Uint8List.fromList(h.bytes);
}

/// HMAC-BLAKE2s (RFC 2104, 블록 64바이트).
Future<Uint8List> hmacBlake2s(List<int> key, List<int> data) async {
  var k = key;
  if (k.length > _blockLen) k = await blake2s(k);
  final kp = Uint8List(_blockLen)..setRange(0, k.length, k);
  final ipad = Uint8List(_blockLen);
  final opad = Uint8List(_blockLen);
  for (var i = 0; i < _blockLen; i++) {
    ipad[i] = kp[i] ^ 0x36;
    opad[i] = kp[i] ^ 0x5c;
  }
  final inner = await blake2s([...ipad, ...data]);
  return blake2s([...opad, ...inner]);
}

/// Noise HKDF: 출력 2개.
Future<List<Uint8List>> hkdf2(List<int> ck, List<int> ikm) async {
  final temp = await hmacBlake2s(ck, ikm);
  final o1 = await hmacBlake2s(temp, [1]);
  final o2 = await hmacBlake2s(temp, [...o1, 2]);
  return [o1, o2];
}

/// Noise nonce: 4바이트 0 + 카운터 u64 리틀엔디언.
Uint8List noiseNonce(int n) {
  final b = ByteData(12);
  b.setUint32(4, n & 0xffffffff, Endian.little);
  b.setUint32(8, (n ~/ 0x100000000) & 0xffffffff, Endian.little);
  return b.buffer.asUint8List();
}

Future<Uint8List> aeadEncrypt(List<int> key, int n, List<int> ad, List<int> plaintext) async {
  final box = await _aead.encrypt(plaintext, secretKey: SecretKey(key), nonce: noiseNonce(n), aad: ad);
  return Uint8List.fromList([...box.cipherText, ...box.mac.bytes]);
}

Future<Uint8List> aeadDecrypt(List<int> key, int n, List<int> ad, List<int> ciphertext) async {
  if (ciphertext.length < 16) throw NoiseException('암호문이 너무 짧음');
  final ct = ciphertext.sublist(0, ciphertext.length - 16);
  final mac = Mac(ciphertext.sublist(ciphertext.length - 16));
  try {
    final pt = await _aead.decrypt(
      SecretBox(ct, nonce: noiseNonce(n), mac: mac),
      secretKey: SecretKey(key),
      aad: ad,
    );
    return Uint8List.fromList(pt);
  } on SecretBoxAuthenticationError {
    throw NoiseException('복호화 실패 (변조되었거나 키가 다름)');
  }
}

/// X25519 고정 키쌍.
class StaticKeys {
  final Uint8List private;
  final Uint8List public;
  StaticKeys(this.private, this.public);

  static Future<StaticKeys> generate() async {
    final kp = await _x25519.newKeyPair();
    final priv = await kp.extractPrivateKeyBytes();
    final pub = await kp.extractPublicKey();
    return StaticKeys(Uint8List.fromList(priv), Uint8List.fromList(pub.bytes));
  }

  static Future<StaticKeys> fromPrivate(List<int> private) async {
    final kp = await _x25519.newKeyPairFromSeed(private);
    final pub = await kp.extractPublicKey();
    return StaticKeys(Uint8List.fromList(private), Uint8List.fromList(pub.bytes));
  }

  Future<Uint8List> dh(List<int> remotePublic) async {
    final kp = await _x25519.newKeyPairFromSeed(private);
    final s = await _x25519.sharedSecretKey(
      keyPair: kp,
      remotePublicKey: SimplePublicKey(remotePublic, type: KeyPairType.x25519),
    );
    return Uint8List.fromList(await s.extractBytes());
  }
}

/// 장치 ID = 공개키 SHA-256 앞 10바이트 16진수 (Rust device_id_from_public 과 동일).
String deviceIdFromPublic(List<int> public) {
  final d = crypto.sha256.convert(public).bytes;
  return d.sublist(0, 10).map((b) => b.toRadixString(16).padLeft(2, '0')).join();
}

/// 사용자에게 보여 주는 지문 "abcd-ef01-2345-6789".
String fingerprint(List<int> public) {
  final d = crypto.sha256.convert(public).bytes;
  final hex = d.sublist(0, 8).map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return [for (var i = 0; i < 16; i += 4) hex.substring(i, i + 4)].join('-');
}

/// 핸드셰이크 해시 → 6자리 확인 코드 "123 456".
String sasFromHash(List<int> h) {
  final n = ByteData.sublistView(Uint8List.fromList(h.sublist(0, 4))).getUint32(0, Endian.big) % 1000000;
  return '${(n ~/ 1000).toString().padLeft(3, '0')} ${(n % 1000).toString().padLeft(3, '0')}';
}

class HandshakeResult {
  final Uint8List sendKey; // 휴대폰 → PC
  final Uint8List recvKey; // PC → 휴대폰
  final Uint8List remoteStatic;
  final String sas;
  HandshakeResult(this.sendKey, this.recvKey, this.remoteStatic, this.sas);
}

/// XX initiator 상태 기계. write1 → read2 → write3 → finish.
class XXInitiator {
  final StaticKeys s;
  late StaticKeys _e;
  late Uint8List _h;
  late Uint8List _ck;
  Uint8List? _k;
  int _n = 0;
  Uint8List? _re;
  Uint8List? _rs;
  int _step = 0;

  XXInitiator(this.s, {StaticKeys? ephemeralForTest}) {
    if (ephemeralForTest != null) _e = ephemeralForTest;
  }

  Future<void> _init(bool hasTestEphemeral) async {
    final name = Uint8List.fromList(_protocolName.codeUnits);
    _h = name.length <= _hashLen ? (Uint8List(_hashLen)..setRange(0, name.length, name)) : await blake2s(name);
    _ck = Uint8List.fromList(_h);
    await _mixHash(Uint8List.fromList(_prologue.codeUnits));
    if (!hasTestEphemeral) _e = await StaticKeys.generate();
  }

  Future<void> _mixHash(List<int> data) async => _h = await blake2s([..._h, ...data]);

  Future<void> _mixKey(List<int> ikm) async {
    final o = await hkdf2(_ck, ikm);
    _ck = o[0];
    _k = o[1];
    _n = 0;
  }

  Future<Uint8List> _encryptAndHash(List<int> pt) async {
    if (_k == null) {
      await _mixHash(pt);
      return Uint8List.fromList(pt);
    }
    final ct = await aeadEncrypt(_k!, _n++, _h, pt);
    await _mixHash(ct);
    return ct;
  }

  Future<Uint8List> _decryptAndHash(List<int> ct) async {
    if (_k == null) {
      await _mixHash(ct);
      return Uint8List.fromList(ct);
    }
    final pt = await aeadDecrypt(_k!, _n++, _h, ct);
    await _mixHash(ct);
    return pt;
  }

  /// -> e
  Future<Uint8List> writeMessage1({bool testEphemeral = false}) async {
    if (_step != 0) throw NoiseException('순서 오류');
    await _init(testEphemeral);
    await _mixHash(_e.public);
    final payload = await _encryptAndHash([]);
    _step = 1;
    return Uint8List.fromList([..._e.public, ...payload]);
  }

  /// <- e, ee, s, es
  Future<void> readMessage2(List<int> msg) async {
    if (_step != 1) throw NoiseException('순서 오류');
    if (msg.length < 32 + 48 + 16) throw NoiseException('핸드셰이크 메시지 길이 오류');
    _re = Uint8List.fromList(msg.sublist(0, 32));
    await _mixHash(_re!);
    await _mixKey(await _e.dh(_re!));
    _rs = await _decryptAndHash(msg.sublist(32, 80));
    await _mixKey(await _e.dh(_rs!));
    await _decryptAndHash(msg.sublist(80));
    _step = 2;
  }

  /// -> s, se
  Future<Uint8List> writeMessage3() async {
    if (_step != 2) throw NoiseException('순서 오류');
    final encS = await _encryptAndHash(s.public);
    await _mixKey(await s.dh(_re!));
    final payload = await _encryptAndHash([]);
    _step = 3;
    return Uint8List.fromList([...encS, ...payload]);
  }

  Future<HandshakeResult> finish() async {
    if (_step != 3) throw NoiseException('핸드셰이크 미완료');
    final o = await hkdf2(_ck, []);
    return HandshakeResult(o[0], o[1], _rs!, sasFromHash(_h));
  }
}
