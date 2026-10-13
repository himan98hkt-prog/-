import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:homepilot_remote/main.dart';
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
    await tester.pumpWidget(const HomePilotApp());
    await tester.tap(find.text('PC 추가'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).at(0), 'abc.trycloudflare.com');
    await tester.enterText(find.byType(TextFormField).at(1), '1234');
    await tester.tap(find.text('연결하고 등록'));
    await tester.pumpAndSettle();
    expect(find.text('0-9, a-f 로 된 20자리를 입력하세요'), findsOneWidget);
  });
}
