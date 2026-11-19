import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/services/remote_store.dart';

/// Lớp giả lập RemoteStore in-memory phục vụ cho unit test
/// mà không cần mocktail hay phụ thuộc vào network/Supabase thật.
class FakeRemoteStore implements RemoteStore {
  @override
  String? currentUserId;

  bool shouldThrowOnNetwork = false;

  final List<ArticleCard> cards = [];
  final Map<String, Map<String, dynamic>> bundles = {};
  final List<Map<String, dynamic>> readingHistoryRows = [];
  final List<Map<String, dynamic>> savedWordsRows = [];
  final List<Map<String, dynamic>> usageEventsRows = [];
  final List<String> ensuredProfiles = [];

  FakeRemoteStore({this.currentUserId});

  void _checkNetwork() {
    if (shouldThrowOnNetwork) {
      throw Exception('Fake Network Error: Mất kết nối mạng');
    }
  }

  @override
  Future<String?> signInAnonymously() async {
    _checkNetwork();
    currentUserId ??= 'mock-user-12345678-1234-1234-1234-123456789abc';
    return currentUserId;
  }

  @override
  Future<List<ArticleCard>> listCards() async {
    _checkNetwork();
    return List.from(cards);
  }

  @override
  Future<Map<String, dynamic>?> fetchBundle(String articleId) async {
    _checkNetwork();
    return bundles[articleId];
  }

  @override
  Future<void> upsertReadingHistory(List<Map<String, dynamic>> rows) async {
    _checkNetwork();
    for (final row in rows) {
      final idx = readingHistoryRows.indexWhere(
        (r) =>
            r['user_id'] == row['user_id'] &&
            r['article_id'] == row['article_id'],
      );
      if (idx != -1) {
        readingHistoryRows[idx] = Map.from(row);
      } else {
        readingHistoryRows.add(Map.from(row));
      }
    }
  }

  @override
  Future<void> upsertSavedWords(List<Map<String, dynamic>> rows) async {
    _checkNetwork();
    for (final row in rows) {
      final idx = savedWordsRows.indexWhere(
        (r) =>
            r['user_id'] == row['user_id'] &&
            r['lemma_key'] == row['lemma_key'],
      );
      if (idx != -1) {
        savedWordsRows[idx] = Map.from(row);
      } else {
        savedWordsRows.add(Map.from(row));
      }
    }
  }

  @override
  Future<void> deleteSavedWord({
    required String userId,
    required String lemmaKey,
  }) async {
    _checkNetwork();
    savedWordsRows.removeWhere(
      (r) => r['user_id'] == userId && r['lemma_key'] == lemmaKey,
    );
  }

  @override
  Future<void> insertEvents(List<Map<String, dynamic>> rows) async {
    _checkNetwork();
    usageEventsRows.addAll(rows.map((r) => Map<String, dynamic>.from(r)));
  }

  @override
  Future<void> ensureProfile(String userId) async {
    _checkNetwork();
    if (!ensuredProfiles.contains(userId)) {
      ensuredProfiles.add(userId);
    }
  }
}

