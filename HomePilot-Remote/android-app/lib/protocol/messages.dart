// 응용 계층 메시지. 형식은 shared/protocol/src/app.rs 와 같다.
// 평문 첫 바이트: 0x01 = 제어 JSON, 0x02 = 화면 프레임(29바이트 헤더 + JPEG).

import 'dart:convert';
import 'dart:typed_data';

const protocolVersion = 1;
const kindControl = 0x01;
const kindFrame = 0x02;
const kindVideo = 0x03; // 헤더 뒤 플래그 1바이트 + H.264 Annex-B
const _frameHeaderLen = 30; // 종류 1 + 헤더 29

Uint8List encodeControl(Map<String, Object?> msg) => Uint8List.fromList([kindControl, ...utf8.encode(jsonEncode(msg))]);

class FrameHeader {
  final int frameId, monitor, width, height, srcWidth, srcHeight, capturedMs;
  FrameHeader(this.frameId, this.monitor, this.width, this.height, this.srcWidth, this.srcHeight, this.capturedMs);
}

/// PC 에서 온 메시지: 제어(JSON) 또는 화면 프레임.
sealed class AgentEvent {}

class ControlEvent extends AgentEvent {
  final Map<String, dynamic> msg;
  ControlEvent(this.msg);
  String get type => msg['type'] as String? ?? '';
  @override
  String toString() => 'ControlEvent($msg)';
}

class FrameEvent extends AgentEvent {
  final FrameHeader header;
  final Uint8List jpeg;
  FrameEvent(this.header, this.jpeg);
}

/// H.264 동영상 프레임 (key = 키프레임: 디코더가 여기서부터 시작할 수 있음)
class VideoEvent extends AgentEvent {
  final FrameHeader header;
  final bool key;
  final Uint8List data;
  VideoEvent(this.header, this.key, this.data);
}

AgentEvent decodeAgentMessage(Uint8List pt) {
  if (pt.isEmpty) throw const FormatException('빈 메시지');
  switch (pt[0]) {
    case kindControl:
      return ControlEvent(jsonDecode(utf8.decode(pt.sublist(1))) as Map<String, dynamic>);
    case kindFrame || kindVideo:
      final video = pt[0] == kindVideo;
      if (pt.length < _frameHeaderLen + (video ? 1 : 0)) throw const FormatException('프레임 헤더 잘림');
      final b = ByteData.sublistView(pt);
      final h = FrameHeader(
        b.getUint32(1, Endian.little),
        b.getUint8(5),
        b.getUint32(6, Endian.little),
        b.getUint32(10, Endian.little),
        b.getUint32(14, Endian.little),
        b.getUint32(18, Endian.little),
        b.getUint32(22, Endian.little) + b.getUint32(26, Endian.little) * 0x100000000,
      );
      if (video) return VideoEvent(h, pt[_frameHeaderLen] & 1 != 0, Uint8List.sublistView(pt, _frameHeaderLen + 1));
      return FrameEvent(h, Uint8List.sublistView(pt, _frameHeaderLen));
    default:
      throw FormatException('알 수 없는 메시지 종류 ${pt[0]}');
  }
}

/// 휴대폰 → PC 메시지 생성 도우미.
class Msg {
  static Map<String, Object?> hello(String name, String version) => {
    'type': 'hello',
    'client_name': name,
    'app_version': version,
    'protocol': protocolVersion,
  };
  static const getStatus = {'type': 'get_status'};
  static const listMonitors = {'type': 'list_monitors'};
  static Map<String, Object?> startStream(int monitor, int quality, int scalePct, int maxFps, {String codec = 'jpeg', int bitrateKbps = 0}) => {
    'type': 'start_stream',
    'monitor': monitor,
    'quality': quality,
    'scale_pct': scalePct,
    'max_fps': maxFps,
    'codec': codec,
    'bitrate_kbps': bitrateKbps,
  };
  static const stopStream = {'type': 'stop_stream'};
  static const requestKeyframe = {'type': 'request_keyframe'};
  static Map<String, Object?> frameAck(int id) => {'type': 'frame_ack', 'frame_id': id};
  static Map<String, Object?> mouseMove(double x, double y) => {'type': 'mouse_move', 'x': x, 'y': y};
  static Map<String, Object?> mouseButton(String button, bool down) => {'type': 'mouse_button', 'button': button, 'down': down};
  static Map<String, Object?> mouseClick(String button, {bool double = false}) => {
    'type': 'mouse_click',
    'button': button,
    'double': double,
  };
  static Map<String, Object?> wheel(double dx, double dy) => {'type': 'wheel', 'dx': dx, 'dy': dy};
  static Map<String, Object?> keyText(String text) => {'type': 'key_text', 'text': text};
  static Map<String, Object?> keyCombo(List<String> keys) => {'type': 'key_combo', 'keys': keys};
  static Map<String, Object?> ping(int t) => {'type': 'ping', 't': t};
  static const bye = {'type': 'bye'};
}
