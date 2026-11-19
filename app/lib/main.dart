import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app.dart';
import 'core/config.dart';
import 'data/local/hive_boxes.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initHive();

  if (AppConfig.shouldInitializeSupabase) {
    try {
      await Supabase.initialize(
        url: AppConfig.supabaseUrl,
        // ignore: deprecated_member_use
        anonKey: AppConfig.supabaseAnonKey,
      );
      AppConfig.isSupabaseInitialized = true;
    } catch (e) {
      debugPrint('[main] Lỗi khởi tạo Supabase client: $e');
    }
  }

  runApp(
    const ProviderScope(
      child: ReadleApp(),
    ),
  );
}
