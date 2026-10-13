// H.264 화면 디코더 (Android MediaCodec, 네이티브 코드: android/.../VideoDecoder.kt).
// 디코딩된 화면은 Flutter Texture 로 바로 그려진다.

import 'dart:async';

import 'package:flutter/services.dart';

class H264Decoder {
  static const _ch = MethodChannel('homepilot/video');
  static final _needKey = <int, void Function()>{};
  static bool _handlerSet = false;
  static bool? _supported;

  final int textureId;
  int _w, _h;
  H264Decoder._(this.textureId, this._w, this._h);

  /// 이 휴대폰에 H.264 하드웨어 디코더가 있는지 (한 번만 확인)
  static Future<bool> supported() async {
    try {
      return _supported ??= await _ch.invokeMethod<bool>('supported') ?? false;
    } catch (_) {
      return _supported = false;
    }
  }

  /// [onNeedKeyframe]: 디코더가 처음 시작하거나 오류에서 회복할 때 → PC 에 키프레임 요청
  static Future<H264Decoder> create(int width, int height, {required void Function() onNeedKeyframe}) async {
    if (!_handlerSet) {
      _handlerSet = true;
      _ch.setMethodCallHandler((call) async {
        if (call.method == 'needKeyframe') _needKey[(call.arguments as num).toInt()]?.call();
      });
    }
    final id = (await _ch.invokeMethod<num>('create', {'width': width, 'height': height}))!.toInt();
    _needKey[id] = onNeedKeyframe;
    return H264Decoder._(id, width, height);
  }

  /// 화면 크기가 바뀌면(모니터 전환 등) 디코더를 다시 설정한다.
  void decode(Uint8List data, bool key, int width, int height) {
    if (width != _w || height != _h) {
      _w = width;
      _h = height;
      unawaited(_ch.invokeMethod('configure', {'id': textureId, 'width': width, 'height': height}));
    }
    unawaited(_ch.invokeMethod('decode', {'id': textureId, 'data': data, 'key': key}));
  }

  Future<void> dispose() async {
    _needKey.remove(textureId);
    await _ch.invokeMethod('dispose', {'id': textureId});
  }
}
