import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../protocol/connection.dart';
import '../protocol/messages.dart';

/// AI 작업: PC 의 Claude Code·Ollama 에 일을 시키고 결과를 본다.
/// 작업은 PC 에서 계속 실행되므로 앱을 닫았다가 나중에 다시 확인할 수 있다.
class AiScreen extends StatefulWidget {
  final RemoteConnection conn;
  final String pcName;
  const AiScreen({super.key, required this.conn, required this.pcName});
  @override
  State<AiScreen> createState() => _AiScreenState();
}

class _AiScreenState extends State<AiScreen> {
  RemoteConnection get c => widget.conn;
  StreamSubscription<AgentEvent>? _sub;
  List<Map<String, dynamic>> _tools = [];
  List<Map<String, dynamic>> _tasks = [];
  String? _tool;
  bool _allowEdits = false;
  bool _loading = true;
  String? _error;
  final _prompt = TextEditingController();
  final _folder = TextEditingController();

  @override
  void initState() {
    super.initState();
    _sub = c.events.listen((e) {
      if (e is! ControlEvent) return;
      if (e.type == 'ai_task_update') {
        final t = (e.msg['task'] as Map).cast<String, dynamic>();
        setState(() {
          _tasks.removeWhere((x) => x['id'] == t['id']);
          _tasks.insert(0, t);
        });
      }
    });
    SharedPreferences.getInstance().then((p) => _folder.text = p.getString('ai_folder') ?? '');
    _load();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _prompt.dispose();
    _folder.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // 처음 요청 때 PC 화면에 허용 확인창이 뜨므로 넉넉히 기다린다
      final t = await request(c, Msg.aiTools, 'ai_tools', timeout: const Duration(seconds: 90));
      final l = await request(c, Msg.aiList, 'ai_tasks');
      if (!mounted) return;
      setState(() {
        _tools = (t['tools'] as List).cast<Map<String, dynamic>>();
        _tasks = (l['tasks'] as List).cast<Map<String, dynamic>>();
        _tool ??= _tools.where((x) => x['available'] == true).map((x) => x['id'] as String).firstOrNull;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  bool get _isClaude => _tool == 'claude';

  Future<void> _run() async {
    final p = _prompt.text.trim();
    if (p.isEmpty || _tool == null) return;
    (await SharedPreferences.getInstance()).setString('ai_folder', _folder.text.trim());
    c.send(Msg.aiRun(_tool!, p, _isClaude ? _folder.text.trim() : '', _isClaude && _allowEdits));
    _prompt.clear();
    FocusManager.instance.primaryFocus?.unfocus();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PC 에서 작업을 시작했습니다. 앱을 닫아도 계속 실행됩니다.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 작업'),
        actions: [IconButton(tooltip: '새로 고침', icon: const Icon(Icons.refresh), onPressed: _load)],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.smart_toy_outlined, size: 48),
                    const SizedBox(height: 12),
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    FilledButton(onPressed: _load, child: const Text('다시 시도')),
                  ],
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _tool,
                  decoration: const InputDecoration(labelText: 'AI 도구', border: OutlineInputBorder()),
                  items: [
                    for (final t in _tools)
                      DropdownMenuItem(
                        value: t['id'] as String,
                        enabled: t['available'] == true,
                        child: Text(t['name'] as String),
                      ),
                  ],
                  onChanged: (v) => setState(() => _tool = v),
                ),
                if (_isClaude) ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: _folder,
                    decoration: const InputDecoration(
                      labelText: '작업 폴더 (PC)',
                      hintText: r'예: C:\Projects\my-app  (비우면 사용자 폴더)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('파일 수정 허용'),
                    subtitle: const Text('끄면 읽기·답변만 합니다 (안전)'),
                    value: _allowEdits,
                    onChanged: (v) => setState(() => _allowEdits = v),
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: _prompt,
                  minLines: 3,
                  maxLines: 8,
                  decoration: const InputDecoration(labelText: '무엇을 시킬까요?', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _tool == null ? null : _run,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('PC 에서 실행'),
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                ),
                const SizedBox(height: 24),
                Text('작업 목록', style: Theme.of(context).textTheme.titleMedium),
                if (_tasks.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Text('아직 작업이 없습니다.')),
                for (final t in _tasks)
                  Card(
                    child: ListTile(
                      leading: _statusIcon(t['status'] as String, cs),
                      title: Text(t['prompt'] as String, maxLines: 2, overflow: TextOverflow.ellipsis),
                      subtitle: Text('${t['tool_name']} · ${_statusText(t['status'] as String)}'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AiTaskScreen(conn: c, task: t))),
                    ),
                  ),
              ],
            ),
    );
  }
}

Widget _statusIcon(String s, ColorScheme cs) => switch (s) {
  'running' => const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5)),
  'done' => Icon(Icons.check_circle, color: cs.primary),
  'cancelled' => const Icon(Icons.cancel_outlined),
  _ => Icon(Icons.error_outline, color: cs.error),
};

String _statusText(String s) => switch (s) {
  'running' => '실행 중',
  'done' => '완료',
  'cancelled' => '취소됨',
  _ => '실패',
};

/// 작업 하나의 출력 (실시간)
class AiTaskScreen extends StatefulWidget {
  final RemoteConnection conn;
  final Map<String, dynamic> task;
  const AiTaskScreen({super.key, required this.conn, required this.task});
  @override
  State<AiTaskScreen> createState() => _AiTaskScreenState();
}

class _AiTaskScreenState extends State<AiTaskScreen> {
  late Map<String, dynamic> _task = widget.task;
  final _out = StringBuffer();
  StreamSubscription<AgentEvent>? _sub;
  final _scroll = ScrollController();

  int get _id => _task['id'] as int;

  @override
  void initState() {
    super.initState();
    _sub = widget.conn.events.listen((e) {
      if (e is! ControlEvent || e.msg['id'] != _id && e.type != 'ai_task_update') return;
      switch (e.type) {
        case 'ai_full_output':
          setState(() {
            _out
              ..clear()
              ..write(e.msg['text'] as String? ?? '');
          });
        case 'ai_output':
          final kind = e.msg['kind'] as String? ?? 'text';
          final text = e.msg['text'] as String? ?? '';
          setState(() => _out.write(kind == 'text' ? text : '\n${kind == 'tool' ? '▶' : '⚠'} $text\n'));
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
          });
        case 'ai_task_update':
          final t = (e.msg['task'] as Map).cast<String, dynamic>();
          if (t['id'] == _id) setState(() => _task = t);
      }
    });
    widget.conn.send(Msg.aiGetOutput(_id));
  }

  @override
  void dispose() {
    _sub?.cancel();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final running = _task['status'] == 'running';
    return Scaffold(
      appBar: AppBar(
        title: Text(_task['tool_name'] as String),
        actions: [
          IconButton(
            tooltip: '결과 복사',
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: _out.toString()));
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('복사했습니다')));
            },
          ),
          if (running)
            IconButton(tooltip: '작업 취소', icon: const Icon(Icons.stop_circle_outlined), onPressed: () => widget.conn.send(Msg.aiCancel(_id))),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_task['prompt'] as String, style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text('${_statusText(_task['status'] as String)} · ${_task['folder']}${_task['allow_edits'] == true ? ' · 수정 허용' : ''}',
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          if (running) const LinearProgressIndicator(),
          Expanded(
            child: SingleChildScrollView(
              controller: _scroll,
              padding: const EdgeInsets.all(12),
              child: SelectableText(_out.isEmpty ? (running ? '작업 중…' : '(출력 없음)') : _out.toString(), style: const TextStyle(fontFamily: 'monospace', height: 1.4)),
            ),
          ),
        ],
      ),
    );
  }
}
