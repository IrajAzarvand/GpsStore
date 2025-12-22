import 'package:flutter/material.dart';

import '../storage/app_config_repository.dart';

class AppLogo extends StatelessWidget {
  final double height;

  const AppLogo({super.key, this.height = 28});

  @override
  Widget build(BuildContext context) {
    final repo = AppConfigRepository();

    return FutureBuilder<String?>(
      future: repo.getBaseUrl(),
      builder: (context, snapshot) {
        final baseUrl = (snapshot.data ?? '').trim();
        if (baseUrl.isEmpty) {
          return _fallback();
        }

        final base = Uri.tryParse(baseUrl);
        if (base == null) {
          return _fallback();
        }

        // Some deployments are hosted under a path prefix (e.g. https://example.com/app/)
        // In that case, '/static/..' may be wrong and 'static/..' is correct.
        final logoUriRelative = base.resolve('static/img/logo.png');
        final logoUriRoot = base.resolve('/static/img/logo.png');

        return Image.network(
          logoUriRelative.toString(),
          height: height,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            return Image.network(
              logoUriRoot.toString(),
              height: height,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) => _fallback(),
            );
          },
        );
      },
    );
  }

  Widget _fallback() {
    return Icon(Icons.image_outlined, size: height);
  }
}
