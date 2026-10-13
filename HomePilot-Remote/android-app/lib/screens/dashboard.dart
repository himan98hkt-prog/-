import 'dart:async';

import 'package:flutter/material.dart';

import '../file_transfer.dart';
import '../protocol/connection.dart';
import '../protocol/messages.dart';
import '../store.dart';
import 'common.dart';
import 'files.dart';
import 'remote.dart';

class DashboardScreen extends StatefulWidget {
  final PcEntry pc;
  final RemoteConnection? initial;
  const DashboardScreen({super.key, required this.pc, this.initial});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> with WidgetsBindingObserver {
  RemoteConnection? _conn;
  Map<String, dynamic>? _status;
  List<Map<String, dynamic>> _monitors = [];
  Timer? _poll;
  StreamSubscription<AgentEvent>? _sub;
  bool _connecting = false;
  String? _lastError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.initial != null) {
      _attach(widget.initial!);
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) => _connect());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poll?.cancel();
    _sub?.cancel();
    _conn?.close();
    super.dispose();
  }

  // 백그라운드로 가면 연결을 닫고(배터리·보안), 돌아오면 다시 연결한다.
  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    // 파일 선택 화면이 열리거나 전송 중일 때는 연결을 유지한다
    if (s == AppLifecycleState.paused && transfersInProgress == 0) {
      _poll?.cancel();
      _conn?.close();
    } else if (s == AppLifecycleState.resumed && (_conn == null || _conn!.isClosed) && ModalRoute.of(context)?.isCurrent == true) {
      _connect();
    }
  }

  Future<void> _connect() async {
    if (_connecting) return;
    setState(() => _connecting = true);
    final c = await connectWithUi(context, widget.pc);
    if (!mounted) {
      await c?.close();
      return;
    }
    setState(() => _connecting = false);
    if (c != null) _attach(c);
  }

  void _attach(RemoteConnection c) {
    _conn = c;
    _lastError = null;
    _sub?.cancel();
    _sub = c.events.listen(
      (e) {
        if (e is ControlEvent && e.type == 'status') setState(() => _status = e.msg);
      },
      onDone: () {
        if (mounted) setState(() => _lastError = c.closeReason);
      },
    );
    c.send(Msg.getStatus);
    request(c, Msg.listMonitors, 'monitors')
        .then((m) {
          if (mounted) setState(() => _monitors = (m['monitors'] as List).cast<Map<String, dynamic>>());
        })
        .catchError((_) {});
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 3), (_) => c.send(Msg.getStatus));
    setState(() {});
  }

  Future<void> _openRemote() async {
    final c = _conn;
    if (c == null || c.isClosed) return;
    _poll?.cancel();
    final reason = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => RemoteScreen(conn: c, pcName: widget.pc.name, monitors: _monitors),
      ),
    );
    if (!mounted) return;
    if (reason != null) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(reason)));
    if (c.isClosed) {
      setState(() => _lastError = c.closeReason);
    } else {
      _poll = Timer.periodic(const Duration(seconds: 3), (_) => c.send(Msg.getStatus));
    }
  }

  @override
  Widget build(BuildContext context) {
    final online = _conn != null && !_conn!.isClosed;
    final s = _status;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.pc.name),
        actions: [
          if (online)
            IconButton(
              tooltip: '연결 끊기',
              icon: const Icon(Icons.link_off),
              onPressed: () async {
                await _conn?.close();
                setState(() => _lastError = '연결을 끊었습니다');
              },
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => online ? _conn!.send(Msg.getStatus) : _connect(),
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            _ConnectionBanner(online: online, connecting: _connecting, error: _lastError, onRetry: _connect, conn: _conn),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: online ? _openRemote : null,
              icon: const Icon(Icons.screen_share_outlined),
              label: Text(_conn?.welcome.canControl == false ? '원격 화면 보기 (보기 전용)' : '원격 화면 · 조작'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            ),
            const SizedBox(height: 12),
            if (s != null) ...[
              Row(
                children: [
                  Expanded(child: _Meter('CPU', (s['cpu_percent'] as num).toDouble())),
                  Expanded(
                    child: _Meter(
                      '메모리',
                      100 * (s['mem_used_bytes'] as num) / ((s['mem_total_bytes'] as num) == 0 ? 1 : (s['mem_total_bytes'] as num)),
                      sub: '${formatBytes(s['mem_used_bytes'] as num)} / ${formatBytes(s['mem_total_bytes'] as num)}',
                    ),
                  ),
                  Expanded(
                    child: s['gpu_percent'] == null
                        ? const _Meter('GPU', null, sub: '측정 불가')
                        : _Meter('GPU', (s['gpu_percent'] as num).toDouble()),
                  ),
                ],
              ),
              Card(
                child: Column(
                  children: [
                    for (final d in (s['disks'] as List).cast<Map<String, dynamic>>())
                      ListTile(
                        dense: true,
                        leading: const Icon(Icons.storage),
                        title: Text(d['mount'] as String),
                        subtitle: LinearProgressIndicator(
                          value: 1 - (d['available_bytes'] as num) / ((d['total_bytes'] as num) == 0 ? 1 : (d['total_bytes'] as num)),
                        ),
                        trailing: Text('여유 ${formatBytes(d['available_bytes'] as num)}'),
                      ),
                  ],
                ),
              ),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: Text('${s['hostname']} · ${s['os']}'),
                  subtitle: Text(
                    '켜진 시간 ${Duration(seconds: (s['uptime_secs'] as num).toInt()).inHours}시간 · 모니터 ${_monitors.length}개'
                    ' · 원격 접속 ${s['active_sessions']}개',
                  ),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Card(
              child: Column(
                children: [
                  const ListTile(
                    enabled: false,
                    leading: Icon(Icons.smart_toy_outlined),
                    title: Text('AI 프로그램 관리'),
                    subtitle: Text('다음 단계(Phase 4)에서 제공 예정'),
                  ),
                  ListTile(
                    enabled: online,
                    leading: const Icon(Icons.folder_outlined),
                    title: const Text('파일'),
                    subtitle: const Text('PC 파일 보기·받기·보내기 (처음 한 번 PC 에서 허용)'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => FilesScreen(conn: _conn!, pcName: widget.pc.name))),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConnectionBanner extends StatelessWidget {
  final bool online, connecting;
  final String? error;
  final VoidCallback onRetry;
  final RemoteConnection? conn;
  const _ConnectionBanner({required this.online, required this.connecting, required this.error, required this.onRetry, this.conn});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (online) {
      final w = conn!.welcome;
      return Card(
        color: cs.primaryContainer,
        child: ListTile(
          leading: const Icon(Icons.lock_outline),
          title: const Text('암호화 연결됨'),
          subtitle: Text('PC 지문 ${w.pcFingerprint} · 에이전트 ${w.agentVersion}'),
        ),
      );
    }
    return Card(
      color: cs.errorContainer,
      child: ListTile(
        leading: Icon(connecting ? Icons.sync : Icons.cloud_off),
        title: Text(connecting ? '연결 중…' : '연결되지 않음'),
        subtitle: error == null ? null : Text(error!),
        trailing: connecting ? null : TextButton(onPressed: onRetry, child: const Text('다시 연결')),
      ),
    );
  }
}

class _Meter extends StatelessWidget {
  final String label;
  final double? percent;
  final String? sub;
  const _Meter(this.label, this.percent, {this.sub});

  @override
  Widget build(BuildContext context) {
    final p = percent;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            SizedBox(
              width: 64,
              height: 64,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CircularProgressIndicator(value: p == null ? 0 : (p / 100).clamp(0, 1), strokeWidth: 7),
                  Text(p == null ? '-' : '${p.round()}%', style: const TextStyle(fontWeight: FontWeight.bold)),
                ],
              ),
            ),
            const SizedBox(height: 6),
            Text(label),
            if (sub != null) Text(sub!, style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
