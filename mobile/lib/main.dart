import 'package:flutter/material.dart';

import 'app_root.dart';
import 'src/pages/home_shell.dart';
import 'src/pages/devices_page.dart';
import 'src/pages/login_page.dart';
import 'src/pages/settings_page.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GpsStore',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo)),
      routes: {
        '/': (_) => const AppRoot(),
        '/login': (_) => const LoginPage(),
        '/home': (_) => const HomeShell(),
        '/devices': (_) => const DevicesPage(),
        '/settings': (_) => const SettingsPage(isFirstRun: false),
      },
    );
  }
}
