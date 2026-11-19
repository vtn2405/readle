import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:hive/hive.dart';

import '../models/article_bundle.dart';
import '../models/article_card.dart';
import '../services/remote_store.dart';
import 'article_repository.dart';

class ArticleNotFoundException implements Exception {
  final String message;
  ArticleNotFoundException(this.message);

  @override
  String toString() => 'ArticleNotFoundException: $message';
}

/// Hiện thực ArticleRepository sử dụng RemoteStore (Supabase).
/// Tự động cache danh sách bài (article_cards_cache) và nội dung bundle (bundle_cache)
/// vào Hive để phục vụ đọc offline khi mất mạng.
class SupabaseArticleRepository implements ArticleRepository {
  final RemoteStore remoteStore;
  final Box<Map>? bundleCacheBox;
  final Box<Map>? articleCardsCacheBox;

  SupabaseArticleRepository({
    required this.remoteStore,
    this.bundleCacheBox,
    this.articleCardsCacheBox,
  });

  @override
  Future<List<ArticleCard>> list() async {
    final cardsBox = articleCardsCacheBox;
    try {
      final cards = await remoteStore.listCards();
      // Cache danh sách bài vào Hive
      if (cardsBox != null) {
        await cardsBox.clear();
        final mapToSave = {
          for (final card in cards) card.id: card.toJson(),
        };
        await cardsBox.putAll(mapToSave);
      }
      return cards;
    } catch (e) {
      debugPrint('[SupabaseArticleRepository] list() lỗi mạng: $e. Thử đọc từ cache...');
      if (cardsBox != null && cardsBox.isNotEmpty) {
        final cached = cardsBox.values
            .map((raw) =>
                ArticleCard.fromJson(Map<String, dynamic>.from(raw)))
            .toList();
        cached.sort((a, b) => a.processingOrder.compareTo(b.processingOrder));
        return cached;
      }
      rethrow;
    }
  }

  @override
  Future<ArticleBundle> get(String id) async {
    final bundleBox = bundleCacheBox;
    try {
      final data = await remoteStore.fetchBundle(id);
      if (data == null) {
        throw ArticleNotFoundException('Không tìm thấy bài viết với id: $id');
      }
      final bundle = ArticleBundle.fromJson(data);
      // Cache bundle bài viết vào Hive
      if (bundleBox != null) {
        await bundleBox.put(id, bundle.toJson());
      }
      return bundle;
    } catch (e) {
      debugPrint('[SupabaseArticleRepository] get($id) lỗi: $e. Thử đọc từ cache...');
      if (bundleBox != null && bundleBox.containsKey(id)) {
        final cached = bundleBox.get(id);
        if (cached != null) {
          // Dùng jsonDecode(jsonEncode) để ép kiểu đệ quy toàn bộ Map<dynamic, dynamic>
          // lồng nhau từ Hive sang Map<String, dynamic> chuẩn
          final map = jsonDecode(jsonEncode(cached)) as Map<String, dynamic>;
          return ArticleBundle.fromJson(map);
        }
      }
      rethrow;
    }
  }
}
