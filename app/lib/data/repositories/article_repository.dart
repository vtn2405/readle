import '../models/article_bundle.dart';
import '../models/article_card.dart';

abstract class ArticleRepository {
  Future<List<ArticleCard>> list();
  Future<ArticleBundle> get(String id);
}

