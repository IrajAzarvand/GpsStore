import 'dart:convert';

import '../models/device.dart';
import 'api_client.dart';

class DevicesApi {
  final ApiClient _client;

  DevicesApi({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<Device>> listDevices() async {
    final res = await _client.get('/api/v1/devices/');
    if (res.statusCode != 200) {
      throw DevicesException('devices_list_failed', statusCode: res.statusCode);
    }

    final decoded = jsonDecode(res.body);
    if (decoded is List) {
      return decoded
          .whereType<Map<String, dynamic>>()
          .map(Device.fromJson)
          .toList(growable: false);
    }

    if (decoded is Map<String, dynamic> && decoded['results'] is List) {
      final items = (decoded['results'] as List)
          .whereType<Map<String, dynamic>>()
          .map(Device.fromJson)
          .toList(growable: false);
      return items;
    }

    throw const DevicesException('unexpected_response');
  }
}

class DevicesException implements Exception {
  final String code;
  final int? statusCode;

  const DevicesException(this.code, {this.statusCode});

  @override
  String toString() => 'DevicesException($code, statusCode: $statusCode)';
}
