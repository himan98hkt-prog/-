// 파일 주고받기. PC 쪽: windows-agent/src/files.rs, 휴대폰 기능: android/.../FileBridge.kt

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/services.dart';

import 'protocol/connection.dart';
import 'protocol/messages.dart';

const _ch = MethodChannel('homepilot/files');
const _chunk = 192 * 1024;
const _window = 4;
int _nextId = Random().nextInt(1 << 20);

class PickedFile {
  final String path, name;
  final int size;
  PickedFile(this.path, this.name, this.size);
}

/// 파일 고르기·전송 중인 개수. 0 보다 크면 앱이 잠시 백그라운드로 가도(파일 선택 화면 등)
/// 연결을 끊지 않는다 (대시보드는 원래 백그라운드에서 연결을 닫음).
int transfersInProgress = 0;

Future<T> keepConnection<T>(Future<T> Function() f) async {
  transfersInProgress++;
  try {
    return await f();
  } finally {
    transfersInProgress--;
  }
}

/// 휴대폰에서 보낼 파일 고르기 (취소하면 null)
Future<PickedFile?> pickFile() => keepConnection(() async {
  final m = await _ch.invokeMapMethod<String, Object?>('pickFile');
  if (m == null) return null;
  return PickedFile(m['path'] as String, m['name'] as String, (m['size'] as num).toInt());
});

/// 받은 파일 열기 (열 수 있는 앱이 없으면 false)
Future<bool> openSaved(String uri, String name) async => await _ch.invokeMethod<bool>('open', {'uri': uri, 'name': name}) ?? false;

class TransferException implements Exception {
  final String message;
  TransferException(this.message);
  @override
  String toString() => message;
}

Stream<ControlEvent> _fileEvents(RemoteConnection c, int id) => c.events
    .where((e) => e is ControlEvent && (e.msg['id'] == id || e.type == 'error'))
    .cast<ControlEvent>();

/// PC 파일 받기 → 휴대폰 다운로드/HomePilot 에 저장. 돌려주는 값은 열 수 있는 주소.
Future<String> downloadFile(RemoteConnection c, String path, String name, {void Function(int got, int total)? onProgress, Completer<void>? cancel}) async {
  final id = _nextId++;
  final tmp = File('${Directory.systemTemp.path}/hp_dl_$id');
  final sink = tmp.openWrite();
  var ok = false;
  try {
    final done = Completer<void>();
    final sub = _fileEvents(c, id).listen((e) async {
      switch (e.type) {
        case 'file_chunk':
          sink.add(base64Decode(e.msg['data'] as String));
          final off = (e.msg['offset'] as num).toInt();
          c.send(Msg.fileAck(id, off));
          onProgress?.call(off + _chunk, (e.msg['total'] as num).toInt());
          if (e.msg['eof'] == true && !done.isCompleted) done.complete();
        case 'file_error' || 'error':
          if (!done.isCompleted) done.completeError(TransferException(e.msg['message'] as String? ?? '오류'));
      }
    }, onDone: () {
      if (!done.isCompleted) done.completeError(TransferException(c.closeReason ?? '연결이 끊겼습니다'));
    });
    cancel?.future.then((_) {
      c.send(Msg.fileCancel(id));
      if (!done.isCompleted) done.completeError(TransferException('취소했습니다'));
    });
    c.send(Msg.fileDownload(id, path));
    try {
      await done.future;
    } finally {
      await sub.cancel();
    }
    await sink.close();
    ok = true;
    return await _ch.invokeMethod<String>('saveToDownloads', {'src': tmp.path, 'name': name}) ?? '';
  } finally {
    if (!ok) {
      await sink.close();
      if (tmp.existsSync()) tmp.deleteSync();
    }
  }
}

/// 휴대폰 파일 → PC (PC 의 다운로드\HomePilot). 돌려주는 값은 PC 의 저장 경로.
Future<String> uploadFile(RemoteConnection c, PickedFile f, {void Function(int sent, int total)? onProgress, Completer<void>? cancel}) async {
  final id = _nextId++;
  final raf = await File(f.path).open();
  final done = Completer<String>();
  var sent = 0; // 보낸 바이트
  var acked = -1; // PC 가 저장했다고 확인한 바이트 (-1 = 시작 확인 전)
  var ended = false;

  Future<void> pump() async {
    // 확인 안 된 조각이 _window 개 이하가 되도록 보낸다
    while (acked >= 0 && sent < f.size && sent - acked < _chunk * _window && !done.isCompleted) {
      final n = min(_chunk, f.size - sent);
      final off = sent;
      sent += n;
      await raf.setPosition(off);
      final data = await raf.read(n);
      c.send(Msg.fileUploadChunk(id, off, base64Encode(data)));
    }
    if (acked == f.size && !ended) {
      ended = true;
      c.send(Msg.fileUploadEnd(id));
    }
  }

  final sub = _fileEvents(c, id).listen((e) async {
    switch (e.type) {
      case 'file_ack':
        acked = (e.msg['offset'] as num).toInt();
        onProgress?.call(acked, f.size);
        await pump();
      case 'file_saved':
        if (!done.isCompleted) done.complete(e.msg['path'] as String? ?? '');
      case 'file_error' || 'error':
        if (!done.isCompleted) done.completeError(TransferException(e.msg['message'] as String? ?? '오류'));
    }
  }, onDone: () {
    if (!done.isCompleted) done.completeError(TransferException(c.closeReason ?? '연결이 끊겼습니다'));
  });
  cancel?.future.then((_) {
    c.send(Msg.fileCancel(id));
    if (!done.isCompleted) done.completeError(TransferException('취소했습니다'));
  });
  try {
    c.send(Msg.fileUploadStart(id, f.name, f.size));
    return await done.future;
  } finally {
    await sub.cancel();
    await raf.close();
  }
}
