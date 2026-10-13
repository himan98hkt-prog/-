import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/protocol/messages.dart';
import 'package:homepilot_remote/protocol/noise.dart';
import 'package:homepilot_remote/protocol/secure_channel.dart';
import 'package:homepilot_remote/screens/view_math.dart';
import 'package:homepilot_remote/store.dart';

void main() {
  test('장치 ID·지문은 Rust 구현과 같다 (SHA-256 기반)', () {
    final pk = List<int>.filled(32, 7);
    expect(deviceIdFromPublic(pk), '4bb06f8e4e3a7715d201');
    expect(fingerprint(pk), '4bb0-6f8e-4e3a-7715');
  });

  test('확인 코드 형식', () {
    expect(sasFromHash([0, 0, 0x30, 0x39, ...List.filled(28, 0)]), '012 345');
  });

  test('Noise nonce: 4바이트 0 + u64 LE', () {
    expect(noiseNonce(1), [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]);
    expect(noiseNonce(0x100000001), [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]);
  });

  test('암호화 채널: 순서·변조 검사', () async {
    final k1 = Uint8List.fromList(List.filled(32, 1));
    final k2 = Uint8List.fromList(List.filled(32, 2));
    final a = SecureChannel(HandshakeResult(k1, k2, Uint8List(32), ''));
    final b = SecureChannel(HandshakeResult(k2, k1, Uint8List(32), ''));
    final c1 = await a.seal([1, 2, 3]);
    final c2 = await a.seal([4]);
    expect(await b.open(c1), [1, 2, 3]);
    expect(() => b.open(c1), throwsA(isA<NoiseException>()), reason: '재전송 거부');
    expect(await b.open(c2), [4]);
  });

  test('화면 프레임 헤더 해석', () {
    final b = ByteData(30 + 2);
    b.setUint8(0, kindFrame);
    b.setUint32(1, 9, Endian.little);
    b.setUint8(5, 1);
    b.setUint32(6, 960, Endian.little);
    b.setUint32(10, 540, Endian.little);
    b.setUint32(14, 1920, Endian.little);
    b.setUint32(18, 1080, Endian.little);
    b.setUint32(22, 1234567, Endian.little);
    b.setUint8(30, 0xff);
    b.setUint8(31, 0xd8);
    final e = decodeAgentMessage(b.buffer.asUint8List()) as FrameEvent;
    expect([e.header.frameId, e.header.monitor, e.header.width, e.header.srcHeight, e.header.capturedMs], [9, 1, 960, 1080, 1234567]);
    expect(e.jpeg, [0xff, 0xd8]);
  });

  test('주소·장치 ID 정규화', () {
    expect(normalizeRelayUrl('https://abc.trycloudflare.com/'), 'wss://abc.trycloudflare.com');
    expect(normalizeRelayUrl('abc.example.com'), 'wss://abc.example.com');
    expect(normalizeRelayUrl('ws://192.168.0.10:8443'), 'ws://192.168.0.10:8443');
    expect(normalizeDeviceId('4BB0 6F8E-4E3A7715D201'), '4bb06f8e4e3a7715d201');
  });

  test('터치 좌표 → PC 비율 좌표 (화면 맞춤 + 확대)', () {
    final v = ViewTransform();
    const box = Size(1000, 1000), frame = Size(1920, 1080);
    // 가로 꽉 참, 세로 가운데 정렬: 이미지 높이 562.5, 위쪽 여백 218.75
    final c = v.toNormalized(const Offset(500, 500), box, frame)!;
    expect(c.dx, closeTo(0.5, 1e-9));
    expect(c.dy, closeTo(0.5, 1e-9));
    expect(v.toNormalized(const Offset(500, 100), box, frame), isNull, reason: '이미지 밖');
    // 화면 중앙 기준 2배 확대 후 중앙은 여전히 PC 화면 중앙
    v.zoom(1, 2, const Offset(500, 500), const Offset(500, 500), Offset.zero, box);
    expect(v.scale, 2);
    final p = v.toNormalized(const Offset(500, 500), box, frame)!;
    expect(p.dx, closeTo(0.5, 1e-9));
    expect(p.dy, closeTo(0.5, 1e-9));
  });
}
