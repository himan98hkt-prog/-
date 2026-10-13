// 주소 안내판(directory): PC 가 무료 공개 게시판(기본 ntfy.sh)에 암호화해 올린 현재 접속 주소를 읽는다.
// 규격은 Rust 쪽 shared/protocol/src/directory.rs 와 같다.
//
// - 주제와 암호 키는 PC 공개키에서 만든다 (등록된 휴대폰만 앎).
// - 위조 기록이 와도 Noise 핸드셰이크에서 장치 ID 를 확인하므로 가짜 PC 에는 연결되지 않는다.

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart' as crypto;
import 'package:cryptography/cryptography.dart';

const defaultDirectory = 'https://ntfy.sh';
final _aead = Chacha20.poly1305Aead();

class DirectoryRecord {
  final String id;
  final String url;
  final List<String> lan;
  final int ts;
  DirectoryRecord(this.id, this.url, this.lan, this.ts);
}

List<int> _hash(String label, List<int> pcPublic) => crypto.sha256.convert([...utf8.encode(label), ...pcPublic]).bytes;

String directoryTopic(List<int> pcPublic) {
  final h = _hash('homepilot-dir-topic-v1', pcPublic);
  return 'hp${h.sublist(0, 15).map((b) => b.toRadixString(16).padLeft(2, '0')).join()}';
}

Future<DirectoryRecord?> openRecord(List<int> pcPublic, String text) async {
  try {
    final raw = base64Url.decode(base64Url.normalize(text.trim()));
    if (raw.length < 12 + 16) return null;
    final topic = directoryTopic(pcPublic);
    final ct = raw.sublist(12, raw.length - 16);
    final mac = Mac(raw.sublist(raw.length - 16));
    final pt = await _aead.decrypt(
      SecretBox(ct, nonce: raw.sublist(0, 12), mac: mac),
      secretKey: SecretKey(_hash('homepilot-dir-key-v1', pcPublic)),
      aad: utf8.encode(topic),
    );
    final j = jsonDecode(utf8.decode(pt)) as Map<String, dynamic>;
    return DirectoryRecord(
      j['id'] as String,
      j['url'] as String? ?? '',
      ((j['lan'] as List?) ?? []).cast<String>(),
      (j['ts'] as num).toInt(),
    );
  } catch (_) {
    return null; // 위조·손상 기록은 무시
  }
}

/// 게시판에서 가장 최신 기록을 읽는다. 장치 ID 가 맞는 것만.
Future<DirectoryRecord?> fetchLatest(Uint8List pcPublic, String deviceId, {String base = defaultDirectory}) async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
  try {
    final req = await client.getUrl(Uri.parse('$base/${directoryTopic(pcPublic)}/json?poll=1&since=all'));
    final res = await req.close().timeout(const Duration(seconds: 10));
    if (res.statusCode != 200) return null;
    final body = await res.transform(utf8.decoder).join();
    DirectoryRecord? best;
    for (final line in const LineSplitter().convert(body)) {
      if (line.trim().isEmpty) continue;
      final m = jsonDecode(line) as Map<String, dynamic>;
      if (m['event'] != 'message') continue;
      final r = await openRecord(pcPublic, m['message'] as String? ?? '');
      if (r == null || r.id != deviceId) continue;
      if (best == null || r.ts > best.ts) best = r;
    }
    return best;
  } catch (_) {
    return null;
  } finally {
    client.close(force: true);
  }
}
