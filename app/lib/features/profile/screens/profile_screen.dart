import 'package:flutter/material.dart';

/// Tab Hồ sơ người dùng theo ADR-020 (không số liệu, không streak).
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Hồ sơ',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 20),
        children: [
          // Header hồ sơ người dùng khách
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 32,
                  backgroundColor: theme.colorScheme.surface,
                  child: Icon(
                    Icons.person_outline,
                    size: 36,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Khách',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Đăng nhập để đồng bộ nhiều máy — sẽ có sau',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Divider(),

          // 2 mục chuyển từ Cài đặt cũ sang
          const ListTile(
            leading: Icon(Icons.notifications_none),
            title: Text('Nhắc nhở đọc bài'),
            subtitle: Text('Tùy chọn nhẹ nhàng, không áp lực'),
          ),
          const Divider(),
          const ListTile(
            leading: Icon(Icons.help_outline),
            title: Text('Hướng dẫn sử dụng'),
            subtitle: Text('Xem lại các mẹo và hướng dẫn đọc'),
          ),
        ],
      ),
    );
  }
}
