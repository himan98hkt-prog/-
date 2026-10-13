import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/main.dart';
import 'package:homepilot_remote/protocol/discovery.dart';
import 'package:homepilot_remote/screens/add_pc.dart';
import 'package:homepilot_remote/store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('PC 가 없으면 등록 안내와 [PC 추가] 버튼을 보여 준다', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await store.load();
    await tester.pumpWidget(const HomePilotApp());
    expect(find.text('등록된 PC 가 없습니다'), findsOneWidget);
    expect(find.text('PC 추가'), findsOneWidget);
  });

  testWidgets('PC 추가 화면: 잘못된 장치 ID 는 거부', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await store.load();
    AddPcScreen.discover = () async => [];
    await tester.pumpWidget(const HomePilotApp());
    await tester.tap(find.text('PC 추가'));
    await tester.pumpAndSettle();
    expect(find.text('같은 Wi-Fi 의 PC'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(0), 'abc.trycloudflare.com');
    await tester.enterText(find.byType(TextFormField).at(1), '1234');
    await tester.ensureVisible(find.text('연결하고 등록'));
    await tester.tap(find.text('연결하고 등록'));
    await tester.pumpAndSettle();
    expect(find.text('0-9, a-f 로 된 20자리를 입력하세요'), findsOneWidget);
  });

  testWidgets('같은 Wi-Fi 에서 찾은 PC 를 목록으로 보여 준다', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await store.load();
    AddPcScreen.discover = () async => [FoundPc('f685fa3773a954e5b5a1', '거실 PC', 'f685-fa37-73a9-54e5', '192.168.0.5', 8443, '')];
    await tester.pumpWidget(const HomePilotApp());
    await tester.tap(find.text('PC 추가'));
    await tester.pumpAndSettle();
    expect(find.text('거실 PC'), findsOneWidget);
    expect(find.text('지문 f685-fa37-73a9-54e5'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '연결'), findsOneWidget);
  });
}
