// ignore_for_file: avoid_print
// 앱의 프로토콜 코드(lib/protocol)가 실제 Rust 에이전트와 통하는지 확인하는 명령줄 도구.
//   dart run tool/interop_client.dart <중계주소> <장치ID> <키파일>
// tests/app-interop.sh 가 중계 서버·에이전트를 띄운 뒤 실행한다.

import 'dart:convert';
import 'dart:io';

import 'package:homepilot_remote/protocol/connection.dart';
import 'package:homepilot_remote/protocol/messages.dart';
import 'package:homepilot_remote/protocol/noise.dart';

Future<void> main(List<String> args) async {
  final keyFile = File(args[2]);
  final StaticKeys keys;
  if (keyFile.existsSync()) {
    keys = await StaticKeys.fromPrivate(base64Decode(keyFile.readAsStringSync()));
  } else {
    keys = await StaticKeys.generate();
    keyFile.writeAsStringSync(base64Encode(keys.private));
  }
  final c = await RemoteConnection.connect(
    relayUrl: args[0],
    deviceId: args[1],
    keys: keys,
    clientName: 'Dart앱',
    onPairing: (sas) => print('PAIRING $sas'),
  );
  print('WELCOME ${c.welcome.deviceName} control=${c.welcome.canControl} fp=${c.welcome.pcFingerprint}');
  final st = await request(c, Msg.getStatus, 'status');
  print('STATUS cpu=${st['cpu_percent']} mem=${st['mem_total_bytes']}');
  final mons = await request(c, Msg.listMonitors, 'monitors');
  print('MONITORS ${(mons['monitors'] as List).length}');
  var frames = 0;
  var bytes = 0;
  final sub = c.events.listen((e) {
    if (e is FrameEvent) {
      frames++;
      bytes += e.jpeg.length;
      if (frames == 1) {
        print('FIRST_FRAME ${e.header.width}x${e.header.height} soi=${e.jpeg[0].toRadixString(16)}${e.jpeg[1].toRadixString(16)}');
      }
      c.send(Msg.frameAck(e.header.frameId));
    }
  });
  await request(c, Msg.startStream(0, 60, 50, 10), 'stream_started');
  await Future.delayed(const Duration(seconds: 3));
  await c.send(Msg.stopStream);
  print('FRAMES $frames avgKB=${frames == 0 ? 0 : bytes ~/ frames ~/ 1024}');
  await c.send(Msg.keyText('앱에서 한글 입력'));
  await c.send(Msg.mouseMove(0.25, 0.75));
  await c.send(Msg.mouseClick('left', double: true));
  final t = DateTime.now().millisecondsSinceEpoch;
  await request(c, Msg.ping(t), 'pong');
  print('PING ${DateTime.now().millisecondsSinceEpoch - t}ms');
  await sub.cancel();
  await c.close();
  print('DONE');
  exit(0);
}
