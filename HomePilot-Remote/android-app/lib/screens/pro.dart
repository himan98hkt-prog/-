import 'package:flutter/material.dart';

import '../billing.dart';

/// Pro 소개·구매 화면. [reason] 이 있으면 왜 이 화면이 열렸는지 위에 보여 준다.
class ProScreen extends StatelessWidget {
  final String? reason;
  const ProScreen({super.key, this.reason});

  /// Pro 가 필요한 기능 앞에서 호출. 쓸 수 있으면 true.
  static Future<bool> require(BuildContext context, String feature) async {
    if (billing.isPro) return true;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ProScreen(reason: '$feature 은(는) Pro 기능입니다')));
    return billing.isPro;
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('HomePilot Pro')),
      body: ListenableBuilder(
        listenable: billing,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.all(20),
          children: [
            if (reason != null)
              Card(color: cs.secondaryContainer, child: ListTile(leading: const Icon(Icons.lock_outline), title: Text(reason!))),
            const SizedBox(height: 8),
            Center(child: ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.asset('assets/logo.png', width: 88))),
            const SizedBox(height: 12),
            Text(billing.isPro ? 'Pro 를 쓰고 있습니다. 감사합니다!' : '커피 한 잔보다 싼 가격으로 모든 기능을', textAlign: TextAlign.center, style: t.titleLarge),
            const SizedBox(height: 20),
            const _Compare(),
            const SizedBox(height: 20),
            if (!billing.isPro) ...[
              _Plan(id: productYearly, title: '1년', badge: '35% 할인'),
              _Plan(id: productMonthly, title: '1개월'),
              _Plan(id: productLifetime, title: '평생 이용', badge: '구독 없음'),
              const SizedBox(height: 8),
              TextButton(onPressed: billing.restore, child: const Text('구매 복원 (다른 기기·재설치)')),
            ],
            if (billing.lastError != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(billing.lastError!, style: TextStyle(color: cs.error))),
            const SizedBox(height: 12),
            Text(
              '• 결제는 Google Play 로 처리되며, 구독은 Play 스토어 › 결제 및 구독에서 언제든 해지할 수 있습니다.\n'
              '• HomePilot 은 화면·파일 내용을 서버에 저장하지 않습니다 (휴대폰↔PC 종단간 암호화).',
              style: t.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _Compare extends StatelessWidget {
  const _Compare();
  @override
  Widget build(BuildContext context) {
    Widget row(String f, bool free) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(f)),
          SizedBox(width: 56, child: Icon(free ? Icons.check : Icons.remove, size: 20, color: free ? null : Colors.grey)),
          const SizedBox(width: 56, child: Icon(Icons.check, size: 20)),
        ],
      ),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Row(
              children: [
                Expanded(child: Text('기능', style: TextStyle(fontWeight: FontWeight.bold))),
                SizedBox(width: 56, child: Text('무료', textAlign: TextAlign.center)),
                SizedBox(width: 56, child: Text('Pro', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold))),
              ],
            ),
            const Divider(),
            row('원격 화면·마우스·키보드', true),
            row('HD 동영상 전송', true),
            row('파일·클립보드 주고받기', true),
            row('주소가 바뀌어도 자동 연결', true),
            row('종단간 암호화·긴급 차단', true),
            row('PC 여러 대', false),
            row('선명 화질 (원본 해상도·30fps)', false),
            row('PC 소리 듣기', false),
            row('AI 작업 관리 (Claude Code·Ollama)', false),
          ],
        ),
      ),
    );
  }
}

class _Plan extends StatelessWidget {
  final String id, title;
  final String? badge;
  const _Plan({required this.id, required this.title, this.badge});
  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Row(
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
            if (badge != null) ...[const SizedBox(width: 8), Chip(label: Text(badge!), visualDensity: VisualDensity.compact)],
          ],
        ),
        subtitle: Text(billing.priceOf(id)),
        trailing: FilledButton(onPressed: billing.busy ? null : () => billing.buy(id), child: const Text('선택')),
      ),
    );
  }
}
