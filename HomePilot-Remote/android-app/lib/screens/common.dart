import 'package:flutter/material.dart';

import '../protocol/connection.dart';
import '../store.dart';

/// PC 연결 + (미등록이면) 확인 코드 대화상자. 성공하면 연결을, 취소/실패하면 null.
Future<RemoteConnection?> connectWithUi(BuildContext context, PcEntry pc) async {
  final nav = Navigator.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final sas = ValueNotifier<String?>(null);
  var dialogOpen = true;
  showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => ValueListenableBuilder<String?>(
      valueListenable: sas,
      builder: (ctx, code, _) => AlertDialog(
        title: Text(code == null ? '${pc.name} 연결 중' : 'PC 에서 등록을 승인하세요'),
        content: code == null
            ? const Row(
                children: [
                  CircularProgressIndicator(),
                  SizedBox(width: 20),
                  Expanded(child: Text('잠시만 기다려 주세요…')),
                ],
              )
            : Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('PC 화면에 확인창이 떴습니다. 아래 숫자가 PC 에 표시된 숫자와 같으면 PC 에서 [예]를 누르세요.'),
                  const SizedBox(height: 16),
                  Center(
                    child: Text(code, style: Theme.of(ctx).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.bold, letterSpacing: 4)),
                  ),
                  const SizedBox(height: 12),
                  const Text('숫자가 다르면 PC 에서 [아니요]를 누르세요.', style: TextStyle(fontSize: 12)),
                ],
              ),
      ),
    ),
  ).then((_) => dialogOpen = false);
  try {
    final keys = await store.keys();
    final c = await RemoteConnection.connect(
      relayUrl: pc.relayUrl,
      deviceId: pc.deviceId,
      keys: keys,
      clientName: store.clientName,
      onPairing: (code) => sas.value = code,
    );
    if (dialogOpen) nav.pop();
    return c;
  } catch (e) {
    if (dialogOpen) nav.pop();
    messenger.showSnackBar(SnackBar(content: Text('$e'), duration: const Duration(seconds: 6)));
    return null;
  }
}

String formatBytes(num b) {
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  var v = b.toDouble();
  var i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return '${v.toStringAsFixed(v >= 100 || i == 0 ? 0 : 1)} ${u[i]}';
}
