import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/screens/game_pad.dart';

void main() {
  Future<List<Map<String, Object?>>> pump(WidgetTester t, PadLayout layout) async {
    final sent = <Map<String, Object?>>[];
    await t.binding.setSurfaceSize(const Size(800, 400));
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GamePadOverlay(layout: layout, opacity: 0.6, sensitivity: 1, send: sent.add),
        ),
      ),
    );
    return sent;
  }

  testWidgets('버튼을 누르는 동안 키가 눌려 있고, 떼면 뗀다', (t) async {
    final sent = await pump(t, PadLayout.presets[0]);
    final g = await t.startGesture(t.getCenter(find.text('점프')));
    await t.pump();
    expect(sent, [
      {'type': 'key', 'key': 'space', 'down': true},
    ]);
    await g.up();
    await t.pump();
    expect(sent.last, {'type': 'key', 'key': 'space', 'down': false});
  });

  testWidgets('조이스틱을 위로 밀면 W, 놓으면 W 뗌', (t) async {
    final sent = await pump(t, PadLayout.presets[0]);
    final w = t.getCenter(find.byType(CustomPaint).last);
    final g = await t.startGesture(w);
    await g.moveBy(const Offset(0, -60));
    await t.pump();
    expect(sent.where((m) => m['down'] == true).map((m) => m['key']), ['w']);
    await g.up();
    await t.pump();
    expect(sent.last, {'type': 'key', 'key': 'w', 'down': false});
  });

  testWidgets('사격 버튼은 마우스 왼쪽 버튼', (t) async {
    final sent = await pump(t, PadLayout.presets[0]);
    final g = await t.startGesture(t.getCenter(find.text('사격')));
    await g.up();
    await t.pump();
    expect(sent, [
      {'type': 'mouse_button', 'button': 'left', 'down': true},
      {'type': 'mouse_button', 'button': 'left', 'down': false},
    ]);
  });
}
