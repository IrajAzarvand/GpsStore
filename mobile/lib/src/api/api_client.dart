import 'dart:convert';
import 'dart:developer' as developer;

import 'package:http/http.dart' as http;

import '../storage/app_config_repository.dart';
import '../storage/auth_storage.dart';

class ApiClient {
  final AppConfigRepository _config;
  final AuthStorage _auth;
  final http.Client _http;

  void _debug(String message) {
    assert(() {
      developer.log(message, name: 'ApiClient');
      return true;
    }());
  }

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
    var headers = await _headers();
    _debug('GET $uri  auth=${headers.containsKey('Authorization')}');
    var res = await _http.get(uri, headers: headers);
    _debug('GET $uri  status=${res.statusCode}  bytes=${res.bodyBytes.length}');
    if (res.statusCode == 401 && await _tryRefreshToken()) {
      headers = await _headers();
      _debug('GET(retry) $uri  auth=${headers.containsKey('Authorization')}');
      res = await _http.get(uri, headers: headers);
      _debug('GET(retry) $uri  status=${res.statusCode}  bytes=${res.bodyBytes.length}');
    }
    return res;
  }

  Future<http.Response> postJson(String path, Map<String, dynamic> body) async {
    final uri = await _uri(path);
    var headers = await _headers();
    _debug('POST $uri  auth=${headers.containsKey('Authorization')}');
    var res = await _http.post(uri, headers: headers, body: jsonEncode(body));
    _debug('POST $uri  status=${res.statusCode}  bytes=${res.bodyBytes.length}');
    if (res.statusCode == 401 && await _tryRefreshToken()) {
      headers = await _headers();
      _debug('POST(retry) $uri  auth=${headers.containsKey('Authorization')}');
      res = await _http.post(uri, headers: headers, body: jsonEncode(body));
      _debug('POST(retry) $uri  status=${res.statusCode}  bytes=${res.bodyBytes.length}');
    }
    return res;
  }

  Future<bool> _tryRefreshToken() async {
    final refresh = await _auth.readRefreshToken();
    _debug('token_refresh: has_refresh=${(refresh ?? '').isNotEmpty}');
    if (refresh == null || refresh.isEmpty) return false;

    try {
      final uri = await _uri('/api/v1/auth/token/refresh/');
      _debug('token_refresh: POST $uri');
      final res = await _http.post(
        uri,
        headers: const {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: jsonEncode({'refresh': refresh}),
      );

      _debug('token_refresh: status=${res.statusCode}  bytes=${res.bodyBytes.length}');

      if (res.statusCode != 200) return false;

      final decoded = jsonDecode(res.body);
      if (decoded is! Map<String, dynamic>) return false;

      final accessNew = (decoded['access'] as String?) ?? '';
      final refreshNew = (decoded['refresh'] as String?) ?? refresh;
      if (accessNew.isEmpty) return false;

      await _auth.saveTokens(access: accessNew, refresh: refreshNew);
      _debug('token_refresh: saved access_prefix=${accessNew.substring(0, accessNew.length < 12 ? accessNew.length : 12)}');
      return true;
    } catch (_) {
      _debug('token_refresh: exception');
      return false;
    }
  }

  Future<Map<String, String>> _headers() async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    final token = await _auth.readAccessToken();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
      _debug('headers: access_prefix=${token.substring(0, token.length < 12 ? token.length : 12)}');
    } else {
      _debug('headers: no access token');
    }

    return headers;
  }
}
