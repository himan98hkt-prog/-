import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../protocol/connection.dart';
import '../protocol/messages.dart';
import '../store.dart';
import 'view_math.dart';

/// 원격 화면. 닫힐 때 종료 사유(있으면)를 돌려준다.
class RemoteScreen extends StatefulWidget {
  final RemoteConnection conn;
  final String pcName;
  final List<Map<String, dynamic>> monitors;
  const RemoteScreen({super.key, required this.conn, required this.pcName, required this.monitors});
  @override
  State<RemoteScreen> createState() => _RemoteScreenState();
}

enum _Mode { touchpad, direct }

class _RemoteScreenState extends State<RemoteScreen> {
  RemoteConnection get c => widget.conn;
  StreamSubscription<AgentEvent>? _sub;
  Uint8List? _jpeg;
  Size _frameSize = const Size(16, 9);
  int _monitor = 0;
  late int _quality = store.qualityIndex;
  _Mode _mode = _Mode.touchpad;
  bool _dragLock = false; // 다음 손가락 이동을 왼쪽 버튼 누른 채로
  bool _scrollMode = false;
  bool _showKeys = false;

  // 보기 확대/이동
  final view = ViewTransform();
  double _scaleStart = 1;
  Offset _focalStart = Offset.zero;
  Offset _translateStart = Offset.zero;
  int _pointers = 0;

  // 원격 커서 (0~1 비율)
  Offset _cursor = const Offset(0.5, 0.5);
  bool _buttonDown = false;
  DateTime _lastMove = DateTime.fromMillisecondsSinceEpoch(0);
  double _scrollAccum = 0;

  // 상태 표시
  int _framesThisSec = 0;
  int _fps = 0;
  int? _rttMs;
  Timer? _tick;
  int _secs = 0;

  final _keyInput = TextEditingController(text: _sentinel);
  final _keyFocus = FocusNode();
  static const _sentinel = '​';

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    final primary = widget.monitors.where((m) => m['primary'] == true).toList();
    _monitor = primary.isEmpty ? 0 : (primary.first['index'] as int);
    _sub = c.events.listen(
      _onEvent,
      onDone: () {
        if (mounted) Navigator.of(context).pop(c.closeReason ?? '연결이 끊겼습니다');
      },
    );
    _start();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      _secs++;
      if (_secs % 2 == 0) c.send(Msg.ping(DateTime.now().millisecondsSinceEpoch));
      setState(() {
        _fps = _framesThisSec;
        _framesThisSec = 0;
      });
    });
  }

  @override
  void dispose() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    _tick?.cancel();
    _sub?.cancel();
    if (_buttonDown) c.send(Msg.mouseButton('left', false));
    c.send(Msg.stopStream);
    _keyInput.dispose();
    _keyFocus.dispose();
    super.dispose();
  }

  void _start() {
    final q = Quality.presets[_quality];
    c.send(Msg.startStream(_monitor, q.quality, q.scalePct, q.maxFps));
  }

  void _onEvent(AgentEvent e) {
    if (e is FrameEvent) {
      c.send(Msg.frameAck(e.header.frameId));
      _framesThisSec++;
      setState(() {
        _jpeg = e.jpeg;
        _frameSize = Size(e.header.srcWidth.toDouble(), e.header.srcHeight.toDouble());
      });
    } else if (e is ControlEvent) {
      switch (e.type) {
        case 'pong':
          setState(() => _rttMs = DateTime.now().millisecondsSinceEpoch - (e.msg['t'] as num).toInt());
        case 'error':
          _toast(e.msg['message'] as String? ?? '오류');
      }
    }
  }

  void _toast(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m), duration: const Duration(seconds: 2)));

  // ---------- 마우스 ----------

  void _sendMove({bool force = false}) {
    final now = DateTime.now();
    if (!force && now.difference(_lastMove).inMilliseconds < 25) return; // 초당 40회로 제한
    _lastMove = now;
    c.send(Msg.mouseMove(_cursor.dx, _cursor.dy));
  }

  Offset? _toRemote(Offset local, Size box) => view.toNormalized(local, box, _frameSize);

  void _onTapUp(TapUpDetails d, Size box) {
    if (_mode == _Mode.direct) {
      final p = _toRemote(d.localPosition, box);
      if (p == null) return;
      _cursor = p;
      _sendMove(force: true);
    }
    c.send(Msg.mouseClick('left'));
    setState(() {});
  }

  void _onLongPress(LongPressStartDetails d, Size box) {
    if (_mode == _Mode.direct) {
      final p = _toRemote(d.localPosition, box);
      if (p == null) return;
      _cursor = p;
      _sendMove(force: true);
    }
    HapticFeedback.mediumImpact();
    c.send(Msg.mouseClick('right'));
    setState(() {});
  }

  void _onScaleStart(ScaleStartDetails d, Size box) {
    _pointers = d.pointerCount;
    _scaleStart = view.scale;
    _focalStart = d.localFocalPoint;
    _translateStart = view.translate;
    _scrollAccum = 0;
    if (_pointers == 1 && _dragLock && !_scrollMode) {
      if (_mode == _Mode.direct) {
        final p = _toRemote(d.localFocalPoint, box);
        if (p != null) {
          _cursor = p;
          _sendMove(force: true);
        }
      }
      _buttonDown = true;
      c.send(Msg.mouseButton('left', true));
    }
  }

  void _onScaleUpdate(ScaleUpdateDetails d, Size box) {
    if (d.pointerCount >= 2 || _pointers >= 2) {
      // 두 손가락: 화면 확대·이동 (PC 로는 아무것도 보내지 않음)
      _pointers = 2;
      setState(() => view.zoom(_scaleStart, d.scale, _focalStart, d.localFocalPoint, _translateStart, box));
      return;
    }
    final delta = d.focalPointDelta;
    if (_scrollMode) {
      _scrollAccum += delta.dy;
      const step = 40.0; // 손가락 40px = 휠 한 칸
      if (_scrollAccum.abs() >= step) {
        final n = (_scrollAccum / step).truncateToDouble();
        _scrollAccum -= n * step;
        c.send(Msg.wheel(0, n)); // 손가락을 내리면 위로 스크롤 (휴대폰과 같은 방향)
      }
      return;
    }
    if (_mode == _Mode.touchpad) {
      final img = view.imageRect(box, _frameSize);
      const sensitivity = 1.6;
      _cursor = Offset(
        (_cursor.dx + delta.dx * sensitivity / img.width).clamp(0.0, 1.0),
        (_cursor.dy + delta.dy * sensitivity / img.height).clamp(0.0, 1.0),
      );
    } else {
      final p = _toRemote(d.localFocalPoint, box);
      if (p == null) return;
      _cursor = p;
    }
    _sendMove();
    setState(() {});
  }

  void _onScaleEnd(ScaleEndDetails d) {
    if (_buttonDown) {
      _sendMove(force: true);
      c.send(Msg.mouseButton('left', false));
      _buttonDown = false;
      setState(() => _dragLock = false);
    }
    if (_pointers < 2) _sendMove(force: true);
    _pointers = 0;
  }

  // ---------- 키보드 ----------

  void _openKeyboard() {
    setState(() => _showKeys = true);
    _keyInput.value = const TextEditingValue(text: _sentinel, selection: TextSelection.collapsed(offset: 1));
    _keyFocus.requestFocus();
    SystemChannels.textInput.invokeMethod('TextInput.show');
  }

  /// 한글 조합이 끝난 글자만 PC 로 보낸다. 지우기는 감시 문자(sentinel)가 지워졌는지로 판단.
  void _onKeyChanged(TextEditingValue v) {
    final text = v.text;
    if (!text.startsWith(_sentinel)) {
      // 감시 문자까지 지워짐 = 백스페이스
      c.send(Msg.keyCombo(['backspace']));
      _keyInput.value = const TextEditingValue(text: _sentinel, selection: TextSelection.collapsed(offset: 1));
      return;
    }
    final composing = v.composing;
    final committedEnd = composing.isValid && !composing.isCollapsed ? composing.start : text.length;
    if (committedEnd <= 1) return;
    final committed = text.substring(1, committedEnd);
    final rest = text.substring(committedEnd);
    c.send(Msg.keyText(committed));
    final newText = _sentinel + rest;
    _keyInput.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: newText.length),
      composing: rest.isEmpty ? TextRange.empty : TextRange(start: 1, end: newText.length),
    );
  }

  void _combo(List<String> keys) {
    HapticFeedback.selectionClick();
    c.send(Msg.keyCombo(keys));
  }

  // ---------- 설정 ----------

  Future<void> _settings() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text('화질', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            for (var i = 0; i < Quality.presets.length; i++)
              ListTile(
                leading: Icon(i == _quality ? Icons.radio_button_checked : Icons.radio_button_off),
                title: Text(Quality.presets[i].label),
                onTap: () {
                  Navigator.pop(ctx);
                  setState(() => _quality = i);
                  _start();
                },
              ),
            if (widget.monitors.length > 1) ...[
              const Divider(),
              const ListTile(
                title: Text('모니터', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
              for (final m in widget.monitors)
                ListTile(
                  leading: Icon(m['index'] == _monitor ? Icons.radio_button_checked : Icons.radio_button_off),
                  title: Text('모니터 ${(m['index'] as int) + 1}${m['primary'] == true ? ' (주 모니터)' : ''}'),
                  subtitle: Text('${m['width']}×${m['height']}'),
                  onTap: () {
                    Navigator.pop(ctx);
                    setState(() {
                      _monitor = m['index'] as int;
                      _jpeg = null;
                      view.reset();
                    });
                    _start();
                  },
                ),
            ],
          ],
        ),
      ),
    );
  }

  // ---------- 화면 ----------

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final canControl = c.welcome.canControl;
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            _toolbar(cs, canControl),
            Expanded(
              child: LayoutBuilder(
                builder: (ctx, cons) {
                  final box = Size(cons.maxWidth, cons.maxHeight);
                  final img = view.imageRect(box, _frameSize);
                  return GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTapUp: canControl ? (d) => _onTapUp(d, box) : null,
                    onLongPressStart: canControl ? (d) => _onLongPress(d, box) : null,
                    onScaleStart: (d) => _onScaleStart(d, box),
                    onScaleUpdate: (d) => canControl || d.pointerCount >= 2 ? _onScaleUpdate(d, box) : null,
                    onScaleEnd: _onScaleEnd,
                    child: ClipRect(
                      child: Stack(
                        children: [
                          if (_jpeg == null)
                            const Center(child: CircularProgressIndicator())
                          else
                            Positioned.fromRect(
                              rect: img,
                              child: Image.memory(_jpeg!, gaplessPlayback: true, fit: BoxFit.fill, filterQuality: FilterQuality.medium),
                            ),
                          if (_mode == _Mode.touchpad && canControl && _jpeg != null)
                            Positioned(
                              left: img.left + _cursor.dx * img.width - 6,
                              top: img.top + _cursor.dy * img.height - 6,
                              child: IgnorePointer(
                                child: Container(
                                  width: 12,
                                  height: 12,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: (_dragLock ? Colors.orange : cs.primary).withValues(alpha: 0.85),
                                    border: Border.all(color: Colors.white, width: 2),
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            if (_showKeys) _keyBar(),
            // 화면 밖에 두는 입력칸 (소프트 키보드 연결용)
            SizedBox(
              height: 1,
              child: Opacity(
                opacity: 0,
                child: TextField(
                  controller: _keyInput,
                  focusNode: _keyFocus,
                  autocorrect: false,
                  enableSuggestions: false,
                  keyboardType: TextInputType.text,
                  textInputAction: TextInputAction.send,
                  onChanged: (_) => _onKeyChanged(_keyInput.value),
                  onSubmitted: (_) {
                    _combo(['enter']);
                    _keyFocus.requestFocus();
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _toolbar(ColorScheme cs, bool canControl) {
    final status = '$_fps fps${_rttMs == null ? '' : ' · ${_rttMs}ms'}';
    final slow = (_rttMs ?? 0) > 300;
    Widget btn(IconData i, String tip, VoidCallback? f, {bool on = false}) => IconButton(
      icon: Icon(i),
      tooltip: tip,
      color: on ? cs.primary : Colors.white,
      style: on ? IconButton.styleFrom(backgroundColor: Colors.white24) : null,
      onPressed: f,
    );
    return Container(
      color: Colors.black87,
      height: 48,
      child: Row(
        children: [
          btn(Icons.close, '세션 종료', () => Navigator.of(context).pop()),
          Expanded(
            child: Text(
              '${widget.pcName}  ·  $status',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: slow ? Colors.orangeAccent : Colors.white70, fontSize: 13),
            ),
          ),
          if (canControl) ...[
            btn(
              _mode == _Mode.touchpad ? Icons.touch_app_outlined : Icons.ads_click,
              _mode == _Mode.touchpad ? '터치패드 모드' : '직접 터치 모드',
              () => setState(() => _mode = _mode == _Mode.touchpad ? _Mode.direct : _Mode.touchpad),
            ),
            btn(Icons.pan_tool_alt_outlined, '드래그 (다음 이동 동안 왼쪽 버튼 누름)', () => setState(() => _dragLock = !_dragLock), on: _dragLock),
            btn(Icons.swap_vert, '스크롤 모드', () => setState(() => _scrollMode = !_scrollMode), on: _scrollMode),
            btn(Icons.keyboard_outlined, '키보드', () => _showKeys ? setState(() => _showKeys = false) : _openKeyboard(), on: _showKeys),
          ],
          btn(Icons.zoom_out_map, '화면 맞춤', () => setState(view.reset)),
          btn(Icons.tune, '화질·모니터', _settings),
        ],
      ),
    );
  }

  Widget _keyBar() {
    Widget k(String label, List<String> keys) => Padding(
      padding: const EdgeInsets.symmetric(horizontal: 2),
      child: ActionChip(label: Text(label), onPressed: () => _combo(keys), visualDensity: VisualDensity.compact),
    );
    return Container(
      color: Colors.black87,
      height: 48,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        children: [
          k('한/영', ['hangul']),
          k('Enter', ['enter']),
          k('⌫', ['backspace']),
          k('Esc', ['escape']),
          k('Tab', ['tab']),
          k('←', ['left']),
          k('↑', ['up']),
          k('↓', ['down']),
          k('→', ['right']),
          k('Del', ['delete']),
          k('Ctrl+C', ['ctrl', 'c']),
          k('Ctrl+V', ['ctrl', 'v']),
          k('Ctrl+Z', ['ctrl', 'z']),
          k('Ctrl+A', ['ctrl', 'a']),
          k('Ctrl+S', ['ctrl', 's']),
          k('Alt+Tab', ['alt', 'tab']),
          k('Win', ['win']),
          k('F5', ['f5']),
          k('Home', ['home']),
          k('End', ['end']),
        ],
      ),
    );
  }
}
