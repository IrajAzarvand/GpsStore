import 'package:flutter/material.dart';

import '../api/auth_api.dart';
import '../storage/app_config_repository.dart';
import 'settings_page.dart';
import '../widgets/app_logo.dart';

class SettingsHomePage extends StatefulWidget {
  const SettingsHomePage({super.key});

  @override
  State<SettingsHomePage> createState() => _SettingsHomePageState();
}

class _SettingsHomePageState extends State<SettingsHomePage> {
  final _auth = AuthApi();
  final _config = AppConfigRepository();

  Future<void> _openServerSettings() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const SettingsPage(isFirstRun: false)),
    );
    if (!mounted) return;
    setState(() {});
  }

  Future<void> _logout() async {
    await _auth.logout();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/login', (_) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            AppLogo(height: 28),
            SizedBox(width: 8),
            Text('تنظیمات'),
          ],
        ),
      ),
      body: ListView(
        children: [
          FutureBuilder<String?>(
            future: _config.getBaseUrl(),
            builder: (context, snapshot) {
              final baseUrl = snapshot.data ?? '';
              return ListTile(
                leading: const Icon(Icons.dns_outlined),
                title: const Text('سرور'),
                subtitle: baseUrl.isEmpty ? const Text('تنظیم نشده') : Text(baseUrl),
                trailing: const Icon(Icons.chevron_right),
                onTap: _openServerSettings,
              );
            },
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('خروج از حساب'),
            onTap: _logout,
          ),
        ],
      ),
    );
  }
}
