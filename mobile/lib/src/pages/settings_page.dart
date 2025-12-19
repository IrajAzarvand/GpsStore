import 'package:flutter/material.dart';

import '../storage/app_config_repository.dart';

class SettingsPage extends StatefulWidget {
  final bool isFirstRun;

  const SettingsPage({super.key, required this.isFirstRun});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _repo = AppConfigRepository();
  final _controller = TextEditingController();
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final baseUrl = await _repo.getBaseUrl();
    if (!mounted) return;
    setState(() {
      _controller.text = baseUrl ?? '';
    });
  }

  String? _validate(String v) {
    final value = v.trim();
    if (value.isEmpty) return 'آدرس سرور را وارد کنید.';

    final uri = Uri.tryParse(value);
    if (uri == null || uri.host.isEmpty || (uri.scheme != 'http' && uri.scheme != 'https')) {
      return 'فرمت آدرس معتبر نیست. نمونه: http://192.168.1.10:8000';
    }

    return null;
  }

  Future<void> _save() async {
    final error = _validate(_controller.text);
    if (error != null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error)));
      return;
    }

    setState(() {
      _saving = true;
    });

    try {
      await _repo.setBaseUrl(_controller.text);
      if (!mounted) return;

      if (widget.isFirstRun) {
        Navigator.of(context).pushReplacementNamed('/login');
      } else {
        Navigator.of(context).pop(true);
      }
    } finally {
      if (!mounted) return;
      setState(() {
        _saving = false;
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('تنظیمات سرور'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                labelText: 'Server Base URL',
                hintText: 'http://192.168.1.10:8000',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _save(),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('ذخیره'),
            ),
          ],
        ),
      ),
    );
  }
}
