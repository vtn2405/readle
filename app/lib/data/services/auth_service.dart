import 'package:flutter/foundation.dart';

import 'remote_store.dart';

class AuthService {
  final RemoteStore _remoteStore;

  AuthService(this._remoteStore);

  /// Khởi tạo đăng nhập ẩn danh và đảm bảo profile tồn tại.
  /// Chạy ngầm trong background, bắt lỗi an toàn nếu offline để app mở ngay.
  Future<String?> initAuth() async {
    try {
      final userId = await _remoteStore.signInAnonymously();
      if (userId != null) {
        await _remoteStore.ensureProfile(userId);
      }
      return userId;
    } catch (e) {
      debugPrint('[AuthService] Chưa có mạng hoặc lỗi đăng nhập ẩn danh: $e');
      return null;
    }
  }

  String? get currentUserId => _remoteStore.currentUserId;
}

