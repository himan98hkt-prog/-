// 앱 저장소: 휴대폰 고유 키(보안 저장소), 등록한 PC 목록, 설정.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'protocol/noise.dart';

class PcEntry {
  final String deviceId;
  String name;
  String relayUrl;
  String fingerprint;

  /// PC 공개키(base64). 첫 연결 때 저장 → 주소 안내판에서 바뀐 주소를 찾는 데 쓴다.
  String publicKey;

  /// 같은 Wi-Fi 바로 접속 주소 ("192.168.0.5:8443")
  List<String> lan;

  /// 마지막으로 받아들인 주소 안내판 기록 시각 (더 오래된 기록은 무시)
  int dirTs;

  /// 마지막 연결 경로: 'lan' | 'internet'
  String lastRoute;

  PcEntry({
    required this.deviceId,
    required this.name,
    required this.relayUrl,
    this.fingerprint = '',
    this.publicKey = '',
    List<String>? lan,
    this.dirTs = 0,
    this.lastRoute = '',
  }) : lan = lan ?? [];

  Map<String, Object?> toJson() => {
    'id': deviceId,
    'name': name,
    'relay': relayUrl,
    'fp': fingerprint,
    'pk': publicKey,
    'lan': lan,
    'dir_ts': dirTs,
    'route': lastRoute,
  };
  factory PcEntry.fromJson(Map<String, dynamic> j) => PcEntry(
    deviceId: j['id'] as String,
    name: j['name'] as String? ?? 'PC',
    relayUrl: j['relay'] as String? ?? '',
    fingerprint: j['fp'] as String? ?? '',
    publicKey: j['pk'] as String? ?? '',
    lan: ((j['lan'] as List?) ?? []).cast<String>(),
    dirTs: (j['dir_ts'] as num?)?.toInt() ?? 0,
    lastRoute: j['route'] as String? ?? '',
  );
}

/// 화질 설정 묶음.
class Quality {
  final String label;
  final int quality, scalePct, maxFps;
  const Quality(this.label, this.quality, this.scalePct, this.maxFps);
  // 실기 측정(Cloudflare 터널 경유): 50% 크기 15fps ≈ 6 Mbps, 100% 크기 27fps ≈ 39 Mbps.
  // 예전 기본값(45%·40%·8fps)은 PC 글씨를 읽을 수 없어 기본을 '보통'으로 올렸다.
  static const presets = [Quality('절약 (모바일 데이터)', 50, 50, 10), Quality('보통', 65, 70, 20), Quality('선명 (Wi-Fi)', 80, 100, 30)];
  static const defaultIndex = 1;
}

class AppStore {
  static const _pcsKey = 'pcs';
  static const _nameKey = 'client_name';
  static const _qualityKey = 'quality';
  static const _keyKey = 'client_private_key';
  final _secure = const FlutterSecureStorage();
  late SharedPreferences _prefs;
  StaticKeys? _keys;
  List<PcEntry> pcs = [];

  Future<void> load() async {
    _prefs = await SharedPreferences.getInstance();
    final raw = _prefs.getString(_pcsKey);
    if (raw != null) {
      pcs = (jsonDecode(raw) as List).map((e) => PcEntry.fromJson(e as Map<String, dynamic>)).toList();
    }
  }

  Future<void> savePcs() => _prefs.setString(_pcsKey, jsonEncode(pcs.map((e) => e.toJson()).toList()));

  Future<void> upsert(PcEntry pc) async {
    pcs.removeWhere((p) => p.deviceId == pc.deviceId);
    pcs.add(pc);
    await savePcs();
  }

  Future<void> remove(String deviceId) async {
    pcs.removeWhere((p) => p.deviceId == deviceId);
    await savePcs();
  }

  String get clientName => _prefs.getString(_nameKey) ?? '내 휴대폰';
  Future<void> setClientName(String v) => _prefs.setString(_nameKey, v.trim().isEmpty ? '내 휴대폰' : v.trim());

  /// 동영상(H.264) 전송 사용 (기본 켜짐). 끄면 예전 JPEG 방식.
  bool get videoEnabled => _prefs.getBool('video_h264') ?? true;
  Future<void> setVideoEnabled(bool v) => _prefs.setBool('video_h264', v);

  int get qualityIndex => (_prefs.getInt(_qualityKey) ?? Quality.defaultIndex).clamp(0, Quality.presets.length - 1);
  Future<void> setQualityIndex(int i) => _prefs.setInt(_qualityKey, i);

  /// 휴대폰 고유 키. Android Keystore 로 보호되는 보안 저장소에 둔다.
  Future<StaticKeys> keys() async {
    if (_keys != null) return _keys!;
    final saved = await _secure.read(key: _keyKey);
    if (saved != null) {
      _keys = await StaticKeys.fromPrivate(base64Decode(saved));
    } else {
      _keys = await StaticKeys.generate();
      await _secure.write(key: _keyKey, value: base64Encode(_keys!.private));
    }
    return _keys!;
  }

  /// 키를 새로 만든다 → 모든 PC 에서 다시 등록해야 한다.
  Future<void> resetKeys() async {
    await _secure.delete(key: _keyKey);
    _keys = null;
  }
}

final store = AppStore();

/// 장치 ID 정규화: 공백·하이픈 제거, 소문자.
String normalizeDeviceId(String s) => s.replaceAll(RegExp(r'[\s-]'), '').toLowerCase();
bool isValidDeviceId(String s) => RegExp(r'^[0-9a-f]{20}$').hasMatch(s);

/// 중계 주소 정규화: https:// → wss://, 주소만 입력하면 wss:// 를 붙인다.
String normalizeRelayUrl(String s) {
  var u = s.trim().replaceAll(RegExp(r'/+$'), '');
  if (u.startsWith('https://')) u = 'wss://${u.substring(8)}';
  if (u.startsWith('http://')) u = 'ws://${u.substring(7)}';
  if (!u.startsWith('ws://') && !u.startsWith('wss://')) u = 'wss://$u';
  return u;
}
