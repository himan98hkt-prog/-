import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../protocol/messages.dart';

/// 게임 키패드 버튼 하나. keys 가 비어 있으면 mouse 버튼('left'/'right').
class PadButton {
  final String label;
  final String? key;
  final String? mouse;
  const PadButton(this.label, {this.key, this.mouse});
}

/// 게임 종류별 배치.
class PadLayout {
  final String name, desc;

  /// 왼쪽 조이스틱이 누를 키 [위, 왼쪽, 아래, 오른쪽]. null 이면 조이스틱 없음.
  final List<String>? stick;

  /// 오른쪽 '시점' 패드 (마우스 상대 이동, FPS 카메라)
  final bool look;
  final List<PadButton> buttons;
  const PadLayout(this.name, this.desc, {this.stick, this.look = false, required this.buttons});

  static const presets = [
    PadLayout(
      'FPS·액션',
      'WASD 이동 + 시점 패드 + 사격/조준',
      stick: ['w', 'a', 's', 'd'],
      look: true,
      buttons: [
        PadButton('사격', mouse: 'left'),
        PadButton('조준', mouse: 'right'),
        PadButton('점프', key: 'space'),
        PadButton('앉기', key: 'ctrl'),
        PadButton('달리기', key: 'shift'),
        PadButton('R', key: 'r'),
        PadButton('E', key: 'e'),
        PadButton('F', key: 'f'),
        PadButton('Q', key: 'q'),
        PadButton('1', key: '1'),
        PadButton('2', key: '2'),
        PadButton('3', key: '3'),
        PadButton('Tab', key: 'tab'),
        PadButton('Esc', key: 'escape'),
      ],
    ),
    PadLayout(
      '레이싱·방향키',
      '방향키 이동 + 자주 쓰는 키',
      stick: ['up', 'left', 'down', 'right'],
      buttons: [
        PadButton('Space', key: 'space'),
        PadButton('Shift', key: 'shift'),
        PadButton('Ctrl', key: 'ctrl'),
        PadButton('Z', key: 'z'),
        PadButton('X', key: 'x'),
        PadButton('C', key: 'c'),
        PadButton('Enter', key: 'enter'),
        PadButton('Esc', key: 'escape'),
      ],
    ),
    PadLayout(
      'RPG·MOBA',
      '스킬 키 (클릭은 화면 직접 터치)',
      buttons: [
        PadButton('Q', key: 'q'),
        PadButton('W', key: 'w'),
        PadButton('E', key: 'e'),
        PadButton('R', key: 'r'),
        PadButton('D', key: 'd'),
        PadButton('F', key: 'f'),
        PadButton('1', key: '1'),
        PadButton('2', key: '2'),
        PadButton('3', key: '3'),
        PadButton('4', key: '4'),
        PadButton('B', key: 'b'),
        PadButton('Space', key: 'space'),
        PadButton('Tab', key: 'tab'),
        PadButton('Esc', key: 'escape'),
      ],
    ),
  ];
}

/// 원격 화면 위에 겹쳐 그리는 게임 키패드.
/// 버튼은 누르는 동안 키를 누르고 있고(down), 떼면 뗀다(up) — 게임이 '꾹 누르기'로 인식한다.
class GamePadOverlay extends StatefulWidget {
  final PadLayout layout;
  final double opacity;
  final double sensitivity;
  final void Function(Map<String, Object?> msg) send;
  const GamePadOverlay({super.key, required this.layout, required this.opacity, required this.sensitivity, required this.send});
  @override
  State<GamePadOverlay> createState() => _GamePadOverlayState();
}

class _GamePadOverlayState extends State<GamePadOverlay> {
  // 지금 누르고 있는 키/마우스 버튼 (화면을 벗어나거나 패드를 끌 때 모두 뗀다)
  final _heldKeys = <String>{};
  final _heldMouse = <String>{};
  final _pressed = <int>{}; // 눌린 버튼 번호 (그리기용)

  // 조이스틱
  Offset _stick = Offset.zero; // -1~1
  int? _stickPointer;

  // 시점 패드: 손가락 이동을 모아서 약 60회/초로 보낸다
  int? _lookPointer;
  double _lookX = 0, _lookY = 0;
  Timer? _lookTimer;

  @override
  void didUpdateWidget(GamePadOverlay old) {
    super.didUpdateWidget(old);
    if (old.layout != widget.layout) _releaseAll();
  }

  @override
  void dispose() {
    _releaseAll();
    _lookTimer?.cancel();
    super.dispose();
  }

  void _releaseAll() {
    for (final k in _heldKeys) {
      widget.send(Msg.key(k, false));
    }
    for (final m in _heldMouse) {
      widget.send(Msg.mouseButton(m, false));
    }
    _heldKeys.clear();
    _heldMouse.clear();
    _pressed.clear();
    _stick = Offset.zero;
    _stickPointer = null;
  }

  void _keyDown(String k) {
    if (_heldKeys.add(k)) widget.send(Msg.key(k, true));
  }

  void _keyUp(String k) {
    if (_heldKeys.remove(k)) widget.send(Msg.key(k, false));
  }

  // ---------- 버튼 ----------

  void _button(int i, bool down) {
    final b = widget.layout.buttons[i];
    if (down) {
      HapticFeedback.selectionClick();
      _pressed.add(i);
      if (b.mouse != null) {
        if (_heldMouse.add(b.mouse!)) widget.send(Msg.mouseButton(b.mouse!, true));
      } else {
        _keyDown(b.key!);
      }
    } else {
      _pressed.remove(i);
      if (b.mouse != null) {
        if (_heldMouse.remove(b.mouse!)) widget.send(Msg.mouseButton(b.mouse!, false));
      } else {
        _keyUp(b.key!);
      }
    }
    setState(() {});
  }

  // ---------- 조이스틱 ----------

  void _stickMove(Offset local, double radius) {
    var v = (local - Offset(radius, radius)) / radius;
    if (v.distance > 1) v = v / v.distance;
    final keys = widget.layout.stick!;
    // 0.35 이상 기울이면 그 방향 키를 누른다 (대각선 = 두 키)
    const t = 0.35;
    final want = {if (v.dy < -t) keys[0], if (v.dx < -t) keys[1], if (v.dy > t) keys[2], if (v.dx > t) keys[3]};
    for (final k in keys) {
      if (want.contains(k)) {
        _keyDown(k);
      } else {
        _keyUp(k);
      }
    }
    setState(() => _stick = v);
  }

  void _stickEnd() {
    for (final k in widget.layout.stick!) {
      _keyUp(k);
    }
    setState(() {
      _stick = Offset.zero;
      _stickPointer = null;
    });
  }

  // ---------- 시점 ----------

  void _lookFlush() {
    final dx = _lookX.truncate(), dy = _lookY.truncate();
    if (dx == 0 && dy == 0) return;
    _lookX -= dx;
    _lookY -= dy;
    widget.send(Msg.mouseDelta(dx, dy));
  }

  @override
  Widget build(BuildContext context) {
    final l = widget.layout;
    final a = widget.opacity;
    return LayoutBuilder(
      builder: (ctx, cons) {
        final short = math.min(cons.maxWidth, cons.maxHeight);
        final stickR = (short * 0.22).clamp(52.0, 90.0);
        final btn = (short * 0.13).clamp(40.0, 60.0);
        final cols = l.buttons.length > 8 ? 4 : 3;
        return Stack(
          children: [
            // 시점 패드: 화면 오른쪽 위 영역 (버튼 위쪽)
            if (l.look)
              Positioned(
                right: 8,
                top: 8,
                width: cons.maxWidth * 0.42,
                height: cons.maxHeight * 0.42,
                child: Listener(
                  behavior: HitTestBehavior.opaque,
                  onPointerDown: (e) {
                    _lookPointer ??= e.pointer;
                    _lookTimer ??= Timer.periodic(const Duration(milliseconds: 16), (_) => _lookFlush());
                    setState(() {});
                  },
                  onPointerMove: (e) {
                    if (e.pointer != _lookPointer) return;
                    _lookX += e.delta.dx * widget.sensitivity;
                    _lookY += e.delta.dy * widget.sensitivity;
                  },
                  onPointerUp: (e) => _lookEnd(e.pointer),
                  onPointerCancel: (e) => _lookEnd(e.pointer),
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: (_lookPointer != null ? 0.18 : 0.06) * a / 0.6),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.35 * a)),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    alignment: Alignment.center,
                    child: Text('시점 (밀어서 돌리기)', style: TextStyle(color: Colors.white.withValues(alpha: 0.7 * a), fontSize: 12)),
                  ),
                ),
              ),
            // 왼쪽 아래 조이스틱
            if (l.stick != null)
              Positioned(
                left: 16,
                bottom: 16,
                width: stickR * 2,
                height: stickR * 2,
                child: Listener(
                  behavior: HitTestBehavior.opaque,
                  onPointerDown: (e) {
                    _stickPointer ??= e.pointer;
                    if (e.pointer == _stickPointer) _stickMove(e.localPosition, stickR);
                  },
                  onPointerMove: (e) {
                    if (e.pointer == _stickPointer) _stickMove(e.localPosition, stickR);
                  },
                  onPointerUp: (e) {
                    if (e.pointer == _stickPointer) _stickEnd();
                  },
                  onPointerCancel: (e) {
                    if (e.pointer == _stickPointer) _stickEnd();
                  },
                  child: CustomPaint(painter: _StickPainter(_stick, a, l.stick!)),
                ),
              ),
            // 오른쪽 아래 버튼 묶음
            Positioned(
              right: 12,
              bottom: 12,
              width: cols * (btn + 8),
              child: Wrap(
                alignment: WrapAlignment.end,
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (var i = 0; i < l.buttons.length; i++)
                    Listener(
                      behavior: HitTestBehavior.opaque,
                      onPointerDown: (_) => _button(i, true),
                      onPointerUp: (_) => _button(i, false),
                      onPointerCancel: (_) => _button(i, false),
                      child: Container(
                        width: btn,
                        height: btn,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: (_pressed.contains(i) ? const Color(0xFF2E7DFF) : Colors.black).withValues(alpha: _pressed.contains(i) ? 0.9 : 0.45 * a / 0.6),
                          border: Border.all(color: Colors.white.withValues(alpha: 0.7 * a), width: 1.5),
                        ),
                        child: Text(
                          l.buttons[i].label,
                          style: TextStyle(color: Colors.white.withValues(alpha: math.min(1, 0.4 + a)), fontSize: l.buttons[i].label.length > 2 ? 11 : 15, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  void _lookEnd(int pointer) {
    if (pointer != _lookPointer) return;
    _lookFlush();
    _lookTimer?.cancel();
    _lookTimer = null;
    setState(() => _lookPointer = null);
  }
}

class _StickPainter extends CustomPainter {
  final Offset v;
  final double a;
  final List<String> keys;
  _StickPainter(this.v, this.a, this.keys);

  @override
  void paint(Canvas canvas, Size size) {
    final r = size.width / 2;
    final c = Offset(r, r);
    canvas.drawCircle(c, r, Paint()..color = Colors.black.withValues(alpha: 0.35 * a / 0.6));
    canvas.drawCircle(
      c,
      r - 1,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = Colors.white.withValues(alpha: 0.6 * a),
    );
    // 방향 글자 (W A S D / ↑ ← ↓ →)
    const arrows = {'up': '↑', 'left': '←', 'down': '↓', 'right': '→'};
    final pos = [Offset(r, r * 0.25), Offset(r * 0.25, r), Offset(r, r * 1.75), Offset(r * 1.75, r)];
    for (var i = 0; i < 4; i++) {
      final tp = TextPainter(
        text: TextSpan(
          text: arrows[keys[i]] ?? keys[i].toUpperCase(),
          style: TextStyle(color: Colors.white.withValues(alpha: 0.75 * a), fontSize: 13, fontWeight: FontWeight.w600),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, pos[i] - Offset(tp.width / 2, tp.height / 2));
    }
    canvas.drawCircle(c + v * r * 0.6, r * 0.38, Paint()..color = const Color(0xFF2E7DFF).withValues(alpha: v == Offset.zero ? 0.5 * a : 0.9));
  }

  @override
  bool shouldRepaint(_StickPainter old) => old.v != v || old.a != a || old.keys != keys;
}
