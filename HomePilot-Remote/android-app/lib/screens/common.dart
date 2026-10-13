import 'dart:convert';

import 'package:flutter/material.dart';

import '../protocol/connection.dart';
import '../protocol/directory.dart';
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
    final c = await connectSmart(pc, onPairing: (code) => sas.value = code);
    if (dialogOpen) nav.pop();
    return c;
  } catch (e) {
    if (dialogOpen) nav.pop();
    messenger.showSnackBar(SnackBar(content: Text('$e'), duration: const Duration(seconds: 6)));
    return null;
  }
}

/// 가장 빠른 경로부터 시도한다: 같은 Wi-Fi → 저장된 외부 주소 → (실패 시) 주소 안내판에서 새 주소를 받아 다시.
/// 차단·미등록·승인 거절은 네트워크 문제가 아니므로 다른 경로를 시도하지 않는다.
/// 성공하면 PC 공개키·경로를 저장한다.
Future<RemoteConnection> connectSmart(PcEntry pc, {void Function(String sas)? onPairing}) async {
  final keys = await store.keys();
  Future<RemoteConnection> tryUrl(String url, Duration t) => RemoteConnection.connect(
    relayUrl: url,
    deviceId: pc.deviceId,
    keys: keys,
    clientName: store.clientName,
    onPairing: onPairing,
    timeout: t,
  );

  Object? lastError;
  Future<RemoteConnection?> attempt() async {
    for (final a in pc.lan) {
      try {
        final c = await tryUrl('ws://$a', const Duration(seconds: 2));
        pc.lastRoute = 'lan';
        return c;
      } on ConnectException catch (e) {
        if (!e.network) rethrow;
        lastError = e;
      }
    }
    if (pc.relayUrl.isNotEmpty) {
      try {
        final c = await tryUrl(pc.relayUrl, const Duration(seconds: 12));
        pc.lastRoute = 'internet';
        return c;
      } on ConnectException catch (e) {
        if (!e.network) rethrow;
        lastError = e;
      }
    }
    return null;
  }

  var c = await attempt();
  if (c == null && pc.publicKey.isNotEmpty) {
    // 주소가 바뀌었을 수 있다 → 주소 안내판에서 최신 주소를 받아 다시 시도
    final rec = await fetchLatest(base64Decode(pc.publicKey), pc.deviceId);
    if (rec != null && rec.ts > pc.dirTs) {
      pc.dirTs = rec.ts;
      pc.lan = rec.lan;
      if (rec.url.isNotEmpty) pc.relayUrl = normalizeRelayUrl(rec.url);
      await store.upsert(pc);
      c = await attempt();
    }
  }
  if (c == null) throw lastError ?? ConnectException('PC 에 연결할 수 없습니다', network: true);
  pc.publicKey = base64Encode(c.welcome.pcPublic);
  // PC 가 알려 준 최신 주소로 갱신 (다음 연결은 같은 Wi-Fi 부터 바로 시도)
  if (c.welcome.lan.isNotEmpty) pc.lan = c.welcome.lan;
  if (c.welcome.publicUrl.isNotEmpty) pc.relayUrl = normalizeRelayUrl(c.welcome.publicUrl);
  if (store.pcs.any((p) => p.deviceId == pc.deviceId)) await store.upsert(pc);
  return c;
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
