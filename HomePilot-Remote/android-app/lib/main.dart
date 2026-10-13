import 'dart:async';

import 'package:flutter/material.dart';

import 'billing.dart';
import 'screens/pc_list.dart';
import 'store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await store.load();
  unawaited(billing.init()); // 상점 연결은 화면을 막지 않고 뒤에서
  runApp(const HomePilotApp());
}

class HomePilotApp extends StatelessWidget {
  const HomePilotApp({super.key});

  @override
  Widget build(BuildContext context) {
    // 앱 아이콘(보라→청록 그라데이션)의 중간 색
    const seed = Color(0xFF4F5BF0);
    return MaterialApp(
      title: 'HomePilot',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark, useMaterial3: true),
      home: const PcListScreen(),
    );
  }
}
