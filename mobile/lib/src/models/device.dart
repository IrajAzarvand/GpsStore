class Device {
  final int? id;
  final String? name;
  final String? imei;
  final String? status;
  final String? driverName;
  final String? simNo;
  final String? expiresAt;

  final String? modelName;
  final String? modelManufacturer;

  Device({
    required this.id,
    required this.name,
    required this.imei,
    required this.status,
    required this.driverName,
    required this.simNo,
    required this.expiresAt,
    required this.modelName,
    required this.modelManufacturer,
  });

  factory Device.fromJson(Map<String, dynamic> json) {
    final model = json['model'];
    String? modelName;
    String? modelManufacturer;

    if (model is Map<String, dynamic>) {
      modelName = model['model_name']?.toString();
      modelManufacturer = model['manufacturer']?.toString();
    }

    return Device(
      id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}'),
      name: json['name']?.toString(),
      imei: json['imei']?.toString(),
      status: json['status']?.toString(),
      driverName: json['driver_name']?.toString(),
      simNo: json['sim_no']?.toString(),
      expiresAt: json['expires_at']?.toString(),
      modelName: modelName,
      modelManufacturer: modelManufacturer,
    );
  }
}
