import 'package:flutter/material.dart';

import '../store.dart';
import 'add_pc.dart';
import 'dashboard.dart';
import 'pro.dart';
import 'settings.dart';

class PcListScreen extends StatefulWidget {
  const PcListScreen({super.key});
  @override
  State<PcListScreen> createState() => _PcListScreenState();
}

class _PcListScreenState extends State<PcListScreen> {
  Future<void> _add() async {
    // 무료는 PC 1대
    if (store.pcs.isNotEmpty && !await ProScreen.require(context, 'PC 여러 대 등록')) return;
    if (!mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AddPcScreen()));
    setState(() {});
  }

  Future<void> _menu(PcEntry pc) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(leading: const Icon(Icons.edit), title: const Text('이름·주소 수정'), onTap: () => Navigator.pop(ctx, 'edit')),
            ListTile(
              leading: const Icon(Icons.delete_outline),
              title: const Text('목록에서 삭제'),
              subtitle: const Text('PC 쪽 등록 해제는 PC 의 트레이 메뉴에서 하세요'),
              onTap: () => Navigator.pop(ctx, 'delete'),
            ),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (action == 'edit') {
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => AddPcScreen(existing: pc)));
    } else if (action == 'delete') {
      await store.remove(pc.deviceId);
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final pcs = store.pcs;
    return Scaffold(
      appBar: AppBar(
        title: const Text('HomePilot'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: '설정',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(onPressed: _add, icon: const Icon(Icons.add), label: const Text('PC 추가')),
      body: pcs.isEmpty
          ? const _EmptyGuide()
          : ListView(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 96),
              children: [
                for (final pc in pcs)
                  Card(
                    child: ListTile(
                      leading: ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.asset('assets/logo.png', width: 40, height: 40)),
                      title: Text(pc.name),
                      subtitle: Text(pc.relayUrl, maxLines: 1, overflow: TextOverflow.ellipsis),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () async {
                        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => DashboardScreen(pc: pc)));
                        setState(() {});
                      },
                      onLongPress: () => _menu(pc),
                    ),
                  ),
              ],
            ),
    );
  }
}

class _EmptyGuide extends StatelessWidget {
  const _EmptyGuide();
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 24),
        Center(child: Image.asset('assets/logo.png', width: 112, height: 112)),
        const SizedBox(height: 16),
        Text('등록된 PC 가 없습니다', textAlign: TextAlign.center, style: t.titleLarge),
        const SizedBox(height: 24),
        Text('1. 집 PC 에 HomePilot 에이전트를 설치하고 실행하세요.', style: t.bodyLarge),
        const SizedBox(height: 8),
        Text('2. PC 트레이 아이콘 → "PC 정보" 에서 중계 주소와 장치 ID 를 확인하세요.', style: t.bodyLarge),
        const SizedBox(height: 8),
        Text('3. 아래 [PC 추가] 를 눌러 입력한 뒤, PC 에 뜨는 확인창에서 [예]를 누르세요.', style: t.bodyLarge),
      ],
    );
  }
}
