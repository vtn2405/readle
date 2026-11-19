import 'dart:convert';
import 'package:flutter/services.dart';

import '../models/article_bundle.dart';
import '../models/article_card.dart';
import 'article_repository.dart';

class FixtureArticleRepository implements ArticleRepository {
  final AssetBundle _assetBundle;

  FixtureArticleRepository({AssetBundle? assetBundle})
      : _assetBundle = assetBundle ?? rootBundle;

  static const String eatingWellPath =
      'assets/fixtures/article_eating_well.json';

  @override
  Future<List<ArticleCard>> list() async {
    final bundle = await get('art_eating_well');
    final meta = bundle.article;

    return [
      ArticleCard(
        id: meta.id,
        title: meta.title,
        category: meta.category,
        cefrLevel: meta.cefrLevel,
        sourceName: meta.source.name,
        wordCount: meta.wordCount,
        sectionCount: meta.sectionCount,
        processingOrder: 1,
      ),
    ];
  }

  @override
  Future<ArticleBundle> get(String id) async {
    final String path;
    if (id == 'art_eating_well' || id == 'article_eating_well') {
      path = eatingWellPath;
    } else {
      path = 'assets/fixtures/$id.json';
    }

    final jsonString = await _assetBundle.loadString(path);
    final Map<String, dynamic> jsonMap =
        jsonDecode(jsonString) as Map<String, dynamic>;
    return ArticleBundle.fromJson(jsonMap);
  }
}

