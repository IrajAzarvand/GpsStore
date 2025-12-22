import 'package:flutter/material.dart';
import '../widgets/app_logo.dart';

class ReportsPage extends StatelessWidget {
  const ReportsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            AppLogo(height: 28),
            SizedBox(width: 8),
            Text('گزارشات'),
          ],
        ),
      ),
      body: const Center(
        child: Text('این بخش در حال توسعه است.'),
      ),
    );
  }
}
