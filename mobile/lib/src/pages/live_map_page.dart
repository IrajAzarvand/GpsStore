import 'package:flutter/material.dart';
import '../widgets/app_logo.dart';

class LiveMapPage extends StatelessWidget {
  const LiveMapPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            AppLogo(height: 28),
            SizedBox(width: 8),
            Text('نقشه زنده'),
          ],
        ),
      ),
      body: const Center(
        child: Text('این بخش در حال توسعه است.'),
      ),
    );
  }
}
