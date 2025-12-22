import 'package:flutter/material.dart';

import 'devices_page.dart';
import 'live_map_page.dart';
import 'reports_page.dart';
import 'settings_home_page.dart';
import '../widgets/app_logo.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      const _HomeLogoPage(),
      const DevicesPage(),
      const LiveMapPage(),
      const ReportsPage(),
      const SettingsHomePage(),
    ];

    return Scaffold(
      body: pages[_index],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        type: BottomNavigationBarType.fixed,
        onTap: (i) {
          setState(() {
            _index = i;
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home_outlined),
            label: 'خانه',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.directions_car_filled_outlined),
            label: 'دستگاه‌ها',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.map_outlined),
            label: 'نقشه',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.assessment_outlined),
            label: 'گزارشات',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings_outlined),
            label: 'تنظیمات',
          ),
        ],
      ),
    );
  }
}

class _HomeLogoPage extends StatelessWidget {
  const _HomeLogoPage();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: AppLogo(height: 140),
    );
  }
}
