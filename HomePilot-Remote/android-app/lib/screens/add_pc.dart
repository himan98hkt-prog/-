import 'package:flutter/material.dart';

import '../store.dart';
import 'common.dart';
import 'dashboard.dart';

class AddPcScreen extends StatefulWidget {
  final PcEntry? existing;
  const AddPcScreen({super.key, this.existing});
  @override
  State<AddPcScreen> createState() => _AddPcScreenState();
}

class _AddPcScreenState extends State<AddPcScreen> {
  final _form = GlobalKey<FormState>();
  late final _relay = TextEditingController(text: widget.existing?.relayUrl ?? '');
  late final _id = TextEditingController(text: widget.existing?.deviceId ?? '');
  late final _name = TextEditingController(text: widget.existing?.name ?? '집 PC');
  bool _busy = false;

  @override
  void dispose() {
    _relay.dispose();
    _id.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final pc = PcEntry(
      deviceId: normalizeDeviceId(_id.text),
      name: _name.text.trim().isEmpty ? '집 PC' : _name.text.trim(),
      relayUrl: normalizeRelayUrl(_relay.text),
      fingerprint: widget.existing?.fingerprint ?? '',
    );
    if (widget.existing != null && widget.existing!.deviceId == pc.deviceId) {
      await store.upsert(pc);
      if (mounted) Navigator.pop(context);
      return;
    }
    setState(() => _busy = true);
    final c = await connectWithUi(context, pc);
    if (!mounted) return;
    setState(() => _busy = false);
    if (c == null) return;
    pc.fingerprint = c.welcome.pcFingerprint;
    if (pc.name == '집 PC' && c.welcome.deviceName.isNotEmpty) pc.name = c.welcome.deviceName;
    await store.upsert(pc);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => DashboardScreen(pc: pc, initial: c),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.existing == null ? 'PC 추가' : 'PC 수정')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              controller: _relay,
              decoration: const InputDecoration(
                labelText: '중계 서버 주소',
                hintText: '예: https://xxxx.trycloudflare.com',
                helperText: 'PC 의 "PC 정보" 에 표시된 주소',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.url,
              autocorrect: false,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return '주소를 입력하세요';
                final u = Uri.tryParse(normalizeRelayUrl(v));
                return (u == null || u.host.isEmpty) ? '주소 형식이 올바르지 않습니다' : null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _id,
              decoration: const InputDecoration(
                labelText: '장치 ID (20자리)',
                helperText: '장치 ID 는 PC 의 암호 키에서 만들어지므로, 정확히 입력하면 가짜 PC 에 연결될 수 없습니다',
                helperMaxLines: 2,
                border: OutlineInputBorder(),
              ),
              autocorrect: false,
              enabled: widget.existing == null,
              validator: (v) => isValidDeviceId(normalizeDeviceId(v ?? '')) ? null : '0-9, a-f 로 된 20자리를 입력하세요',
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'PC 이름', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _busy ? null : _submit,
              icon: Icon(widget.existing == null ? Icons.link : Icons.save),
              label: Text(widget.existing == null ? '연결하고 등록' : '저장'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            ),
          ],
        ),
      ),
    );
  }
}
