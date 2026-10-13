import 'dart:async';

import 'package:flutter/material.dart';

import '../file_transfer.dart';
import '../protocol/connection.dart';
import '../protocol/messages.dart';
import 'common.dart';

/// PC 파일 보기·받기·보내기.
class FilesScreen extends StatefulWidget {
  final RemoteConnection conn;
  final String pcName;
  const FilesScreen({super.key, required this.conn, required this.pcName});
  @override
  State<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends State<FilesScreen> {
  RemoteConnection get c => widget.conn;
  String _path = '';
  String _parent = '';
  List<Map<String, dynamic>> _entries = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _open('');
  }

  Future<void> _open(String path) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // 처음 파일 요청 때 PC 화면에 허용 확인창이 뜨므로 넉넉히 기다린다
      final m = await request(c, Msg.fsList(path), 'fs_listing', timeout: const Duration(seconds: 90));
      if (!mounted) return;
      setState(() {
        _path = m['path'] as String? ?? '';
        _parent = m['parent'] as String? ?? '';
        _entries = (m['entries'] as List).cast<Map<String, dynamic>>();
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

  Future<void> _download(Map<String, dynamic> e) async {
    final name = e['name'] as String;
    final progress = ValueNotifier<double?>(null);
    final cancel = Completer<void>();
    final dialog = _progressDialog('받는 중: $name', progress, cancel);
    try {
      final uri = await keepConnection(
        () => downloadFile(c, e['path'] as String, name, cancel: cancel, onProgress: (got, total) {
          progress.value = total == 0 ? null : (got / total).clamp(0, 1);
        }),
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('휴대폰 다운로드/HomePilot 에 저장했습니다: $name'),
        action: SnackBarAction(label: '열기', onPressed: () => openSaved(uri, name)),
        duration: const Duration(seconds: 8),
      ));
    } catch (err) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('받기 실패: $err')));
    }
    await dialog;
  }

  Future<void> _upload() async {
    PickedFile? picked;
    try {
      picked = await pickFile();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('파일을 열 수 없습니다: $e')));
      return;
    }
    final f = picked;
    debugPrint('HomePilot 파일 선택: ${f?.name} ${f?.size} 연결=${!c.isClosed}');
    if (f == null || !mounted) return;
    if (c.isClosed) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PC 연결이 끊겼습니다. 뒤로 가서 다시 연결한 뒤 보내 주세요.')));
      return;
    }
    final progress = ValueNotifier<double?>(0);
    final cancel = Completer<void>();
    final dialog = _progressDialog('보내는 중: ${f.name}', progress, cancel);
    try {
      final saved = await keepConnection(() => uploadFile(c, f, cancel: cancel, onProgress: (s, t) => progress.value = t == 0 ? 1 : s / t));
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('PC 에 저장했습니다: $saved'), duration: const Duration(seconds: 6)));
      if (_path.isNotEmpty) unawaited(_open(_path)); // 보낸 파일이 목록에 보이도록
    } catch (err) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('보내기 실패: $err')));
    }
    await dialog;
  }

  Future<void> _progressDialog(String title, ValueNotifier<double?> p, Completer<void> cancel) => showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis),
      content: ValueListenableBuilder<double?>(
        valueListenable: p,
        builder: (_, v, _) => Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            LinearProgressIndicator(value: v),
            const SizedBox(height: 8),
            Text(v == null ? '' : '${(v * 100).round()}%'),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () {
            if (!cancel.isCompleted) cancel.complete();
          },
          child: const Text('취소'),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final root = _path.isEmpty;
    return PopScope(
      canPop: root,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _open(_parent.isEmpty || _parent == _path ? '' : _parent);
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(root ? '${widget.pcName} 파일' : _path, maxLines: 1, overflow: TextOverflow.ellipsis),
          actions: [IconButton(tooltip: '새로 고침', icon: const Icon(Icons.refresh), onPressed: () => _open(_path))],
        ),
        floatingActionButton: FloatingActionButton.extended(onPressed: _upload, icon: const Icon(Icons.upload_file), label: const Text('PC 로 보내기')),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.folder_off_outlined, size: 48),
                      const SizedBox(height: 12),
                      Text(_error!, textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      FilledButton(onPressed: () => _open(_path), child: const Text('다시 시도')),
                    ],
                  ),
                ),
              )
            : ListView.builder(
                padding: const EdgeInsets.only(bottom: 96),
                itemCount: _entries.length + (root ? 0 : 1),
                itemBuilder: (_, i) {
                  if (!root && i == 0) {
                    return ListTile(
                      leading: const Icon(Icons.arrow_upward),
                      title: const Text('상위 폴더'),
                      onTap: () => _open(_parent == _path ? '' : _parent),
                    );
                  }
                  final e = _entries[i - (root ? 0 : 1)];
                  final dir = e['is_dir'] == true;
                  return ListTile(
                    leading: Icon(dir ? Icons.folder : _iconFor(e['name'] as String), color: dir ? Theme.of(context).colorScheme.primary : null),
                    title: Text(e['name'] as String),
                    subtitle: dir ? null : Text('${formatBytes(e['size'] as num)} · ${_date(e['modified'] as num)}'),
                    trailing: dir ? const Icon(Icons.chevron_right) : const Icon(Icons.download_outlined),
                    onTap: () => dir ? _open(e['path'] as String) : _download(e),
                  );
                },
              ),
      ),
    );
  }

  static IconData _iconFor(String name) {
    final ext = name.contains('.') ? name.split('.').last.toLowerCase() : '';
    return switch (ext) {
      'jpg' || 'jpeg' || 'png' || 'gif' || 'webp' || 'heic' => Icons.image_outlined,
      'mp4' || 'mov' || 'mkv' || 'avi' => Icons.movie_outlined,
      'mp3' || 'wav' || 'm4a' || 'flac' => Icons.audiotrack_outlined,
      'pdf' => Icons.picture_as_pdf_outlined,
      'zip' || '7z' || 'rar' => Icons.archive_outlined,
      'txt' || 'md' || 'log' => Icons.description_outlined,
      _ => Icons.insert_drive_file_outlined,
    };
  }

  static String _date(num s) {
    final d = DateTime.fromMillisecondsSinceEpoch(s.toInt() * 1000);
    String two(int v) => v.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
  }
}
