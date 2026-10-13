// 핸드셰이크 이후의 암호화 채널. 방향별 카운터 nonce, 순서가 어긋나면 복호화 실패.

import 'dart:typed_data';

import 'noise.dart';

class SecureChannel {
  final Uint8List _sendKey;
  final Uint8List _recvKey;
  int _sendN = 0;
  int _recvN = 0;

  SecureChannel(HandshakeResult r) : _sendKey = r.sendKey, _recvKey = r.recvKey;

  Future<Uint8List> seal(List<int> plaintext) => aeadEncrypt(_sendKey, _sendN++, const [], plaintext);

  Future<Uint8List> open(List<int> ciphertext) async {
    final pt = await aeadDecrypt(_recvKey, _recvN, const [], ciphertext);
    _recvN++;
    return pt;
  }
}
