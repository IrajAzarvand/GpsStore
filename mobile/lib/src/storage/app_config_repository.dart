import 'package:shared_preferences/shared_preferences.dart';

class AppConfigRepository {
  static const _keyBaseUrl = 'base_url';

  Future<String?> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final v = prefs.getString(_keyBaseUrl);
    return v;
  }

  Future<void> setBaseUrl(String baseUrl) async {
    final prefs = await SharedPreferences.getInstance();
    final normalized = baseUrl.trim().replaceAll(RegExp(r'/*$'), '');
    await prefs.setString(_keyBaseUrl, normalized);
  }

  Future<void> clearBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyBaseUrl);
  }
}
