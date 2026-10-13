import 'package:flutter/material.dart';

import '../protocol/discovery.dart';
import '../store.dart';
import 'common.dart';
import 'dashboard.dart';

class AddPcScreen extends StatefulWidget {
  final PcEntry? existing;
  const AddPcScreen({super.key, this.existing});

  /// 같은 Wi-Fi PC 찾기 (테스트에서 바꿔 끼운다)
  static Future<List<FoundPc>> Function() discover = discoverPcs;
  @override
  State<AddPcScreen> createState() => _AddPcScreenState();
}

class _AddPcScreenState extends State<AddPcScreen> {
  final _form = GlobalKey<FormState>();
  late final _relay = TextEditingController(text: widget.existing?.relayUrl ?? '');
  late final _id = TextEditingController(text: widget.existing?.deviceId ?? '');
  late final _name = TextEditingController(text: widget.existing?.name ?? '집 PC');
  bool _busy = false;
  late List<String> _lan = List.of(widget.existing?.lan ?? const []);
  List<FoundPc> _found = [];
  bool _scanning = false;

  @override
  void initState() {
    super.initState();
    if (widget.existing == null) _scan();
  }

  Future<void> _scan() async {
    setState(() => _scanning = true);
    final r = await AddPcScreen.discover();
    if (!mounted) return;
    setState(() {
      _found = r;
      _scanning = false;
    });
  }

  /// 찾은 PC 를 누르면 입력칸을 채우고 바로 연결·등록한다.
  void _pick(FoundPc p) {
    _id.text = p.deviceId;
    _name.text = p.name;
    _relay.text = p.publicUrl;
    _lan = p.lanAddress.isEmpty ? [] : [p.lanAddress];
    _submit();
  }

  @override
  void dispose() {
    _relay.dispose();
    _id.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final ex = widget.existing;
    final pc = PcEntry(
      deviceId: normalizeDeviceId(_id.text),
      name: _name.text.trim().isEmpty ? '집 PC' : _name.text.trim(),
      relayUrl: _relay.text.trim().isEmpty ? '' : normalizeRelayUrl(_relay.text),
      fingerprint: ex?.fingerprint ?? '',
      // 수정할 때 PC 공개키·같은 Wi-Fi 주소를 잃지 않도록 이어받는다
      publicKey: ex?.publicKey ?? '',
      lan: _lan,
      dirTs: ex?.dirTs ?? 0,
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
            if (widget.existing == null) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.wifi),
                          const SizedBox(width: 8),
                          const Expanded(child: Text('같은 Wi-Fi 의 PC', style: TextStyle(fontWeight: FontWeight.w600))),
                          if (_scanning)
                            const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                          else
                            TextButton(onPressed: _busy ? null : _scan, child: const Text('다시 찾기')),
                        ],
                      ),
                      if (!_scanning && _found.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8),
                          child: Text(
                            '찾은 PC 가 없습니다. 휴대폰과 PC 가 같은 Wi-Fi 인지 확인하세요. '
                            'PC 의 Windows 방화벽이 HomePilot 을 막고 있으면 찾을 수 없습니다 '
                            '(이 경우에도 아래에 직접 입력하면 인터넷으로 연결됩니다).',
                          ),
                        ),
                      for (final p in _found)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.asset('assets/logo.png', width: 36, height: 36)),
                          title: Text(p.name),
                          subtitle: Text('지문 ${p.fingerprint}'),
                          trailing: FilledButton(onPressed: _busy ? null : () => _pick(p), child: const Text('연결')),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text('또는 직접 입력', style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 12),
            ],
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
                if (v == null || v.trim().isEmpty) return _lan.isEmpty ? '주소를 입력하세요' : null; // 같은 Wi-Fi 만 쓸 때는 비워도 됨
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
