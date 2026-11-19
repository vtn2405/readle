import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/article_card.dart';

/// Interface trừu tượng cho các thao tác với tầng lưu trữ từ xa (Supabase).
/// Giúp phân tách logic mạng khỏi repository và sync service,
/// đồng thời giúp viết unit test cực kỳ đơn giản qua FakeRemoteStore mà không cần mocktail.
abstract class RemoteStore {
  /// Lấy danh sách tóm tắt bài viết từ view `article_cards`
  Future<List<ArticleCard>> listCards();

  /// Lấy toàn bộ bundle của bài viết qua RPC `get_article_bundle`
  /// Trả về null nếu không tìm thấy bài
  Future<Map<String, dynamic>?> fetchBundle(String articleId);

  /// Đẩy danh sách tiến trình đọc lên bảng `reading_history`
  Future<void> upsertReadingHistory(List<Map<String, dynamic>> rows);

  /// Đẩy danh sách từ vựng lên bảng `user_saved_words`
  Future<void> upsertSavedWords(List<Map<String, dynamic>> rows);

  /// Xóa từ vựng khỏi bảng `user_saved_words`
  Future<void> deleteSavedWord({required String userId, required String lemmaKey});

  /// Đẩy sự kiện sử dụng theo lô lên bảng `usage_events`
  Future<void> insertEvents(List<Map<String, dynamic>> rows);

  /// Đảm bảo người dùng có bản ghi trong bảng `profiles`
  /// Dùng ignoreDuplicates: true để không ghi đè consent_at đã có
  Future<void> ensureProfile(String userId);

  /// Lấy ID người dùng hiện tại (nếu đã đăng nhập)
  String? get currentUserId;

  /// Đăng nhập ẩn danh nếu chưa có session
  Future<String?> signInAnonymously();
}

/// Hiện thực thật của RemoteStore kết nối với Supabase
class SupabaseRemoteStore implements RemoteStore {
  final SupabaseClient _client;

  SupabaseRemoteStore(this._client);

  @override
  String? get currentUserId => _client.auth.currentUser?.id;

  @override
  Future<String?> signInAnonymously() async {
    if (_client.auth.currentSession == null) {
      final res = await _client.auth.signInAnonymously();
      return res.user?.id;
    }
    return _client.auth.currentUser?.id;
  }

  @override
  Future<List<ArticleCard>> listCards() async {
    final response = await _client
        .from('article_cards')
        .select()
        .order('processing_order', ascending: true);
    final list = (response as List<dynamic>)
        .map((e) => ArticleCard.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return list;
  }

  @override
  Future<Map<String, dynamic>?> fetchBundle(String articleId) async {
    final res = await _client.rpc(
      'get_article_bundle',
      params: {'p_article_id': articleId},
    );
    if (res == null) return null;
    return Map<String, dynamic>.from(res as Map);
  }

  @override
  Future<void> upsertReadingHistory(List<Map<String, dynamic>> rows) async {
    if (rows.isEmpty) return;
    await _client.from('reading_history').upsert(
          rows,
          onConflict: 'user_id,article_id',
        );
  }

  @override
  Future<void> upsertSavedWords(List<Map<String, dynamic>> rows) async {
    if (rows.isEmpty) return;
    await _client.from('user_saved_words').upsert(
          rows,
          onConflict: 'user_id,lemma_key',
        );
  }

  @override
  Future<void> deleteSavedWord({
    required String userId,
    required String lemmaKey,
  }) async {
    await _client
        .from('user_saved_words')
        .delete()
        .eq('user_id', userId)
        .eq('lemma_key', lemmaKey);
  }

  @override
  Future<void> insertEvents(List<Map<String, dynamic>> rows) async {
    if (rows.isEmpty) return;
    await _client.from('usage_events').insert(rows);
  }

  @override
  Future<void> ensureProfile(String userId) async {
    await _client.from('profiles').upsert(
      {'user_id': userId},
      onConflict: 'user_id',
      ignoreDuplicates: true,
    );
  }
}

