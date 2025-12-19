import 'dart:convert';

import '../storage/auth_storage.dart';
import 'api_client.dart';

class AuthApi {
  final ApiClient _client;
  final AuthStorage _storage;

  AuthApi({ApiClient? client, AuthStorage? storage})
      : _client = client ?? ApiClient(),
        _storage = storage ?? AuthStorage();

  Future<void> login({required String username, required String password}) async {
    final res = await _client.postJson(
      '/api/v1/auth/token/',
      {
        'username': username,
        'password': password,
      },
    );

    if (res.statusCode != 200) {
      throw AuthException('login_failed', statusCode: res.statusCode);
    }

    final json = jsonDecode(res.body);
    final access = (json['access'] as String?) ?? '';
    final refresh = (json['refresh'] as String?) ?? '';

    if (access.isEmpty || refresh.isEmpty) {
      throw const AuthException('invalid_token_response');
    }

    await _storage.saveTokens(access: access, refresh: refresh);
  }

  Future<void> logout() => _storage.clear();
}

class AuthException implements Exception {
  final String code;
  final int? statusCode;

  const AuthException(this.code, {this.statusCode});

  @override
  String toString() => 'AuthException($code, statusCode: $statusCode)';
}
