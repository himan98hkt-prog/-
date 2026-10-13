// 같은 Wi-Fi 의 HomePilot PC 찾기: UDP 방송으로 묻고 응답을 모은다.
// PC 쪽: windows-agent/src/discovery.rs (UDP 47830)

import 'dart:async';
import 'dart:convert';
import 'dart:io';

const discoveryPort = 47830;
const discoveryQuery = 'HOMEPILOT_DISCOVER_V1';

class FoundPc {
  final String deviceId, name, fingerprint, ip, publicUrl;
  final int port;
  FoundPc(this.deviceId, this.name, this.fingerprint, this.ip, this.port, this.publicUrl);

  /// 같은 Wi-Fi 바로 접속 주소 (PC 가 집 네트워크 접속을 꺼 두었으면 빈 문자열)
  String get lanAddress => port > 0 ? '$ip:$port' : '';
}

Future<List<FoundPc>> discoverPcs({Duration wait = const Duration(seconds: 2)}) async {
  final found = <String, FoundPc>{};
  RawDatagramSocket? sock;
  try {
    sock = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    sock.broadcastEnabled = true;
    final done = Completer<void>();
    final sub = sock.listen((ev) {
      if (ev != RawSocketEvent.read) return;
      final d = sock!.receive();
      if (d == null) return;
      try {
        final m = jsonDecode(utf8.decode(d.data)) as Map<String, dynamic>;
        if (m['t'] != 'homepilot_pc') return;
        final id = m['id'] as String;
        found[id] = FoundPc(
          id,
          m['name'] as String? ?? 'PC',
          m['fp'] as String? ?? '',
          d.address.address,
          (m['port'] as num?)?.toInt() ?? 0,
          m['url'] as String? ?? '',
        );
      } catch (_) {}
    });
    final q = utf8.encode(discoveryQuery);
    // 몇 번 반복해서 보낸다 (Wi-Fi 에서 방송 패킷이 가끔 사라짐)
    for (var i = 0; i < 3; i++) {
      sock.send(q, InternetAddress('255.255.255.255'), discoveryPort);
      await Future<void>.delayed(wait ~/ 3);
    }
    if (!done.isCompleted) done.complete();
    await sub.cancel();
  } catch (_) {
    // Wi-Fi 가 아니거나 방송이 막힌 네트워크: 빈 목록
  } finally {
    sock?.close();
  }
  return found.values.toList();
}
