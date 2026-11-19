import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

import '../../core/config.dart';
import '../local/hive_boxes.dart';
import '../models/article_card.dart';
import '../repositories/article_repository.dart';
import '../repositories/fixture_article_repository.dart';
import '../repositories/supabase_article_repository.dart';
import 'sync_providers.dart';

final articleRepositoryProvider = Provider<ArticleRepository>((ref) {
  if (!AppConfig.shouldInitializeSupabase || !AppConfig.isSupabaseInitialized) {
    return FixtureArticleRepository();
  }

  final remoteStore = ref.watch(remoteStoreProvider);
  return SupabaseArticleRepository(
    remoteStore: remoteStore,
    bundleCacheBox: Hive.isBoxOpen(bundleCacheBoxName)
        ? Hive.box<Map>(bundleCacheBoxName)
        : null,
    articleCardsCacheBox: Hive.isBoxOpen(articleCardsCacheBoxName)
        ? Hive.box<Map>(articleCardsCacheBoxName)
        : null,
  );
});

final articleListProvider = FutureProvider<List<ArticleCard>>((ref) async {
  final repo = ref.watch(articleRepositoryProvider);
  return repo.list();
});
