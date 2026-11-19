import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../core/config.dart';
import '../models/article_card.dart';
import '../services/auth_service.dart';
import '../services/remote_store.dart';
import '../services/sync_service.dart';
import 'local_providers.dart';

final remoteStoreProvider = Provider<RemoteStore>((ref) {
  if (AppConfig.shouldInitializeSupabase && AppConfig.isSupabaseInitialized) {
    try {
      return SupabaseRemoteStore(Supabase.instance.client);
    } catch (e) {
      debugPrint('[sync_providers] Lỗi truy cập Supabase client: $e');
    }
  }
  return _NoopRemoteStore();
});

final authServiceProvider = Provider<AuthService>((ref) {
  final remoteStore = ref.watch(remoteStoreProvider);
  return AuthService(remoteStore);
});

final consentProvider = StateProvider<bool>((ref) => false);

final syncServiceProvider = Provider<SyncService>((ref) {
  final useSupabase =
      AppConfig.shouldInitializeSupabase && AppConfig.isSupabaseInitialized;
  final remoteStore = ref.watch(remoteStoreProvider);

  return SyncService(
    remoteStore: remoteStore,
    progressRepo: ref.watch(readingProgressRepositoryProvider),
    wordsRepo: ref.watch(savedWordsRepositoryProvider),
    queueRepo: ref.watch(eventQueueRepositoryProvider),
    hasConsent: () => ref.read(consentProvider),
    enabled: useSupabase,
  );
});

class _NoopRemoteStore implements RemoteStore {
  @override
  String? get currentUserId => null;

  @override
  Future<void> deleteSavedWord({required String userId, required String lemmaKey}) async {}

  @override
  Future<void> ensureProfile(String userId) async {}

  @override
  Future<Map<String, dynamic>?> fetchBundle(String articleId) async => null;

  @override
  Future<void> insertEvents(List<Map<String, dynamic>> rows) async {}

  @override
  Future<List<ArticleCard>> listCards() async => [];

  @override
  Future<String?> signInAnonymously() async => null;

  @override
  Future<void> upsertReadingHistory(List<Map<String, dynamic>> rows) async {}

  @override
  Future<void> upsertSavedWords(List<Map<String, dynamic>> rows) async {}
}

