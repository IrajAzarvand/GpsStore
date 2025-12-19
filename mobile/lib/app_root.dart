import 'package:flutter/material.dart';

import 'src/pages/devices_page.dart';
import 'src/pages/login_page.dart';
import 'src/pages/settings_page.dart';
import 'src/storage/app_config_repository.dart';
import 'src/storage/auth_storage.dart';

class AppRoot extends StatefulWidget {
  const AppRoot({super.key});

  @override
  State<AppRoot> createState() => _AppRootState();
}

class _AppRootState extends State<AppRoot> {
  final _configRepo = AppConfigRepository();
  final _authStorage = AuthStorage();

  Future<_BootstrapState> _bootstrap() async {
    final baseUrl = await _configRepo.getBaseUrl();
    final accessToken = await _authStorage.readAccessToken();

    final normalized = (baseUrl ?? '').trim();
    if (normalized.isEmpty) {
      return const _BootstrapState.needsBaseUrl();
    }

    if ((accessToken ?? '').isEmpty) {
      return const _BootstrapState.needsLogin();
    }

    return _BootstrapState.ready(normalized);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_BootstrapState>(
      future: _bootstrap(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        final state = snapshot.data!;
        switch (state.kind) {
          case _BootstrapKind.needsBaseUrl:
            return const SettingsPage(isFirstRun: true);
          case _BootstrapKind.needsLogin:
            return const LoginPage();
          case _BootstrapKind.ready:
            return const DevicesPage();
        }
      },
    );
  }
}

enum _BootstrapKind { needsBaseUrl, needsLogin, ready }

class _BootstrapState {
  final _BootstrapKind kind;
  final String? baseUrl;

  const _BootstrapState._(this.kind, {this.baseUrl});

  const _BootstrapState.needsBaseUrl() : this._(_BootstrapKind.needsBaseUrl);

  const _BootstrapState.needsLogin() : this._(_BootstrapKind.needsLogin);

  const _BootstrapState.ready(String baseUrl)
      : this._(_BootstrapKind.ready, baseUrl: baseUrl);
}
