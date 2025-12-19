import 'package:flutter/material.dart';

import '../api/auth_api.dart';
import '../api/devices_api.dart';
import '../models/device.dart';
import 'login_page.dart';

class DevicesPage extends StatefulWidget {
  const DevicesPage({super.key});

  @override
  State<DevicesPage> createState() => _DevicesPageState();
}

class _DevicesPageState extends State<DevicesPage> {
  final _api = DevicesApi();
  final _auth = AuthApi();

  Future<List<Device>>? _future;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() {
      _future = _api.listDevices();
    });
  }

  Future<void> _logout() async {
    await _auth.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginPage()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('دستگاه‌ها'),
        actions: [
          IconButton(
            onPressed: _reload,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            onPressed: _logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: FutureBuilder<List<Device>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('خطا: ${snapshot.error}'),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: _reload,
                      child: const Text('تلاش مجدد'),
                    ),
                  ],
                ),
              ),
            );
          }

          final devices = snapshot.data ?? const [];
          if (devices.isEmpty) {
            return const Center(child: Text('هیچ دستگاهی یافت نشد.'));
          }

          return ListView.separated(
            itemCount: devices.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final d = devices[index];
              final subtitle = <String>[
                if ((d.imei ?? '').isNotEmpty) 'IMEI: ${d.imei}',
                if ((d.status ?? '').isNotEmpty) 'Status: ${d.status}',
                if ((d.modelManufacturer ?? '').isNotEmpty || (d.modelName ?? '').isNotEmpty)
                  'Model: ${(d.modelManufacturer ?? '').trim()} ${(d.modelName ?? '').trim()}'.trim(),
              ].join('  |  ');

              return ListTile(
                title: Text(d.name ?? '(بدون نام)'),
                subtitle: subtitle.isEmpty ? null : Text(subtitle),
              );
            },
          );
        },
      ),
    );
  }
}
