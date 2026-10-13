import 'package:flutter/material.dart';

import '../billing.dart';
import '../protocol/noise.dart';
import '../store.dart';
import 'pro.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _name = TextEditingController(text: store.clientName);
  String? _fp;

  @override
  void initState() {
    super.initState();
    store.keys().then((k) => setState(() => _fp = fingerprint(k.public)));
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.workspace_premium_outlined),
              title: Text(billing.isPro ? 'HomePilot Pro 사용 중' : 'HomePilot Pro'),
              subtitle: const Text('PC 여러 대 · 선명 화질 · PC 소리 · AI 작업'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ProScreen())),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            decoration: const InputDecoration(labelText: '이 휴대폰 이름', helperText: 'PC 의 등록 확인창과 접속 기록에 표시됩니다', border: OutlineInputBorder()),
            onChanged: store.setClientName,
          ),
          const SizedBox(height: 24),
          Text('기본 화질', style: Theme.of(context).textTheme.titleMedium),
          RadioGroup<int>(
            groupValue: store.qualityIndex,
            onChanged: (v) => setState(() => store.setQualityIndex(v ?? 0)),
            child: Column(
              children: [
                for (var i = 0; i < Quality.presets.length; i++) RadioListTile<int>(value: i, title: Text(Quality.presets[i].label)),
              ],
            ),
          ),
          SwitchListTile(
            title: const Text('HD 동영상 전송 (권장)'),
            subtitle: const Text('데이터를 1/10 이하로 쓰면서 더 부드럽고 선명합니다. 화면이 이상하면 끄세요.'),
            value: store.videoEnabled,
            onChanged: (v) => setState(() => store.setVideoEnabled(v)),
          ),
          const Divider(height: 32),
          ListTile(leading: const Icon(Icons.fingerprint), title: const Text('이 휴대폰의 기기 지문'), subtitle: Text(_fp ?? '…')),
          ListTile(
            leading: const Icon(Icons.key_off_outlined),
            title: const Text('기기 키 초기화'),
            subtitle: const Text('분실·유출이 의심될 때. 모든 PC 에 다시 등록해야 합니다.'),
            onTap: () async {
              final ok = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('기기 키를 초기화할까요?'),
                  content: const Text('등록된 모든 PC 에서 이 휴대폰이 더 이상 인식되지 않습니다. PC 쪽 등록 목록에서도 이전 기기를 해제하세요.'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('취소')),
                    FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('초기화')),
                  ],
                ),
              );
              if (ok == true) {
                await store.resetKeys();
                final k = await store.keys();
                setState(() => _fp = fingerprint(k.public));
              }
            },
          ),
          const AboutListTile(
            icon: Icon(Icons.info_outline),
            applicationName: 'HomePilot Remote',
            applicationVersion: '1.0.0',
            aboutBoxChildren: [Text('이 소프트웨어는 일부 Independent JPEG Group 의 작업에 기반합니다.')],
          ),
        ],
      ),
    );
  }
}
