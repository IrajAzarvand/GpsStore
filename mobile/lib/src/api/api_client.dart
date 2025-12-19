import 'dart:convert';

import 'package:http/http.dart' as http;

import '../storage/app_config_repository.dart';
import '../storage/auth_storage.dart';

class ApiClient {
  final AppConfigRepository _config;
  final AuthStorage _auth;
  final http.Client _http;

  ApiClient({
    AppConfigRepository? config,
    AuthStorage? auth,
    http.Client? httpClient,
  })  : _config = config ?? AppConfigRepository(),
        _auth = auth ?? AuthStorage(),
        _http = httpClient ?? http.Client();

  Future<Uri> _uri(String path) async {
    final baseUrl = (await _config.getBaseUrl()) ?? '';
    final normalized = baseUrl.trim().replaceAll(RegExp(r'/*$'), '');
    return Uri.parse('$normalized$path');
  }

  Future<http.Response> get(String path) async {
    final uri = await _uri(path);
    final headers = await _headers();
    return _http.get(uri, headers: headers);
  }

  Future<http.Response> postJson(String path, Map<String, dynamic> body) async {
    final uri = await _uri(path);
    final headers = await _headers();
    return _http.post(uri, headers: headers, body: jsonEncode(body));
  }

  Future<Map<String, String>> _headers() async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    final token = await _auth.readAccessToken();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }

    return headers;
  }
}
