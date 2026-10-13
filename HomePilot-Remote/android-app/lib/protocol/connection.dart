// PC 와의 연결: 중계 서버 접속 → Noise XX → Hello → (등록 확인) → Welcome.
// Flutter 를 쓰지 않으므로 명령줄 테스트(tool/)에서도 그대로 쓸 수 있다.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'messages.dart';
import 'noise.dart';
import 'secure_channel.dart';

class ConnectException implements Exception {
  final String message;

  /// 네트워크 문제(주소 오래됨·PC 꺼짐·시간 초과)면 true → 다른 경로로 다시 시도할 만하다.
  /// 거부(차단·미등록·승인 거절)는 false → 다른 경로로 시도하지 않는다.
  final bool network;
  ConnectException(this.message, {this.network = false});
  @override
  String toString() => message;
}

class WelcomeInfo {
  final String deviceName;
  final String agentVersion;
  final Map<String, dynamic> permissions;
  final String pcFingerprint;

  /// PC 공개키 (주소 안내판 주제·키를 만들 때 사용)
  final Uint8List pcPublic;

  /// PC 가 알려 준 같은 Wi-Fi 주소들과 현재 외부 주소 (저장해 두고 다음 연결에 사용)
  final List<String> lan;
  final String publicUrl;
  WelcomeInfo(this.deviceName, this.agentVersion, this.permissions, this.pcFingerprint, this.pcPublic, {this.lan = const [], this.publicUrl = ''});
  bool get canControl => permissions['control'] == true;
}

class RemoteConnection {
  final WebSocket _ws;
  final SecureChannel _ch;
  final StreamIterator<dynamic> _in;
  final WelcomeInfo welcome;
  final _events = StreamController<AgentEvent>.broadcast();
  Future<void> _sendChain = Future.value();
  bool _closed = false;
  String? closeReason;

  RemoteConnection._(this._ws, this._ch, this._in, this.welcome) {
    _pump();
  }

  Stream<AgentEvent> get events => _events.stream;
  bool get isClosed => _closed;

  /// 연결. [onPairing] 은 미등록 기기일 때 확인 코드와 함께 호출된다.
  static Future<RemoteConnection> connect({
    required String relayUrl,
    required String deviceId,
    required StaticKeys keys,
    required String clientName,
    String appVersion = '1.0.0',
    void Function(String sas)? onPairing,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    final base = relayUrl.trim().replaceAll(RegExp(r'/+$'), '');
    final WebSocket ws;
    try {
      ws = await WebSocket.connect('$base/v1/client/$deviceId').timeout(timeout);
    } catch (e) {
      throw ConnectException('중계 서버에 연결할 수 없습니다 ($e)', network: true);
    }
    ws.pingInterval = const Duration(seconds: 20);
    final it = StreamIterator<dynamic>(ws);
    Future<dynamic> next(Duration t) async {
      if (!await it.moveNext().timeout(t)) throw ConnectException(_closeText(ws), network: true);
      return it.current;
    }

    try {
      // 1) 중계 서버 응답
      while (true) {
        final m = await next(timeout);
        if (m is String) {
          final t = (jsonDecode(m) as Map)['t'];
          if (t == 'connected') break;
          if (t == 'offline') throw ConnectException('PC 가 꺼져 있거나 HomePilot 이 실행 중이 아닙니다', network: true);
          if (t == 'agent_gone') throw ConnectException('PC 연결이 끊겼습니다', network: true);
        }
      }
      // 2) Noise XX
      final hs = XXInitiator(keys);
      ws.add(await hs.writeMessage1());
      dynamic m2;
      do {
        m2 = await next(timeout);
      } while (m2 is! List<int>);
      await hs.readMessage2(m2);
      ws.add(await hs.writeMessage3());
      final r = await hs.finish();
      // 장치 ID 는 PC 공개키의 해시 → 다르면 중간자
      if (deviceIdFromPublic(r.remoteStatic) != deviceId) {
        throw ConnectException('보안 경고: PC 의 키가 장치 ID 와 다릅니다. 중간자 공격 가능성이 있어 연결을 중단했습니다.');
      }
      final ch = SecureChannel(r);
      ws.add(await ch.seal(encodeControl(Msg.hello(clientName, appVersion))));
      // 3) 등록 확인 / 환영
      while (true) {
        final raw = await next(const Duration(seconds: 150));
        if (raw is! List<int>) continue;
        final ev = decodeAgentMessage(await ch.open(raw));
        if (ev is! ControlEvent) continue;
        switch (ev.type) {
          case 'pairing_pending':
            onPairing?.call(ev.msg['sas'] as String);
          case 'denied':
            throw ConnectException(ev.msg['reason'] as String? ?? '접속이 거부되었습니다');
          case 'welcome':
            final info = WelcomeInfo(
              ev.msg['device_name'] as String? ?? 'PC',
              ev.msg['agent_version'] as String? ?? '',
              (ev.msg['permissions'] as Map?)?.cast<String, dynamic>() ?? {},
              fingerprint(r.remoteStatic),
              bytes(r.remoteStatic),
              lan: ((ev.msg['lan'] as List?) ?? const []).cast<String>(),
              publicUrl: ev.msg['public_url'] as String? ?? '',
            );
            return RemoteConnection._(ws, ch, it, info);
        }
      }
    } on TimeoutException {
      await ws.close();
      throw ConnectException('응답 시간이 초과되었습니다', network: true);
    } catch (e) {
      await ws.close();
      rethrow;
    }
  }

  static String _closeText(WebSocket ws) => ws.closeCode == null ? '연결이 끊겼습니다' : '연결이 끊겼습니다 (${ws.closeCode})';

  Future<void> _pump() async {
    try {
      while (await _in.moveNext()) {
        final raw = _in.current;
        if (raw is String) {
          final t = (jsonDecode(raw) as Map)['t'];
          if (t == 'agent_gone') {
            closeReason = 'PC 연결이 끊겼습니다';
            break;
          }
          continue;
        }
        final ev = decodeAgentMessage(await _ch.open(raw as List<int>));
        if (ev is ControlEvent && (ev.type == 'session_ended' || ev.type == 'denied')) {
          closeReason = ev.msg['reason'] as String?;
          _events.add(ev);
          break;
        }
        _events.add(ev);
      }
    } catch (e) {
      closeReason ??= '연결 오류: $e';
    }
    closeReason ??= '연결이 종료되었습니다';
    _closed = true;
    await _ws.close();
    await _events.close();
  }

  /// 순서를 지키며 암호화해서 보낸다.
  Future<void> send(Map<String, Object?> msg) {
    if (_closed) return Future.value();
    _sendChain = _sendChain
        .then((_) async {
          if (_closed) return;
          final ct = await _ch.seal(encodeControl(msg));
          if (!_closed) _ws.add(ct);
        })
        .catchError((_) {});
    return _sendChain;
  }

  Future<void> close() async {
    if (_closed) return;
    await send(Msg.bye);
    _closed = true;
    await _ws.close();
  }
}

/// 요청 하나 보내고 특정 종류의 응답을 기다린다.
Future<Map<String, dynamic>> request(
  RemoteConnection c,
  Map<String, Object?> msg,
  String replyType, {
  Duration timeout = const Duration(seconds: 10),
}) async {
  final f = c.events
      .where((e) => e is ControlEvent && (e.type == replyType || e.type == 'error'))
      .cast<ControlEvent>()
      .first
      .timeout(timeout);
  await c.send(msg);
  final e = await f;
  if (e.type == 'error') throw ConnectException(e.msg['message'] as String? ?? '오류');
  return e.msg;
}

Uint8List bytes(List<int> l) => l is Uint8List ? l : Uint8List.fromList(l);
