class ArticleCard {
  final String id;
  final String title;
  final String category;
  final String cefrLevel;
  final String sourceName;
  final int wordCount;
  final int sectionCount;
  final int processingOrder;

  const ArticleCard({
    required this.id,
    required this.title,
    required this.category,
    required this.cefrLevel,
    required this.sourceName,
    required this.wordCount,
    required this.sectionCount,
    this.processingOrder = 0,
  });

  factory ArticleCard.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['title'] == null ||
        json['category'] == null ||
        json['cefr_level'] == null ||
        json['source_name'] == null ||
        json['word_count'] == null ||
        json['section_count'] == null) {
      throw FormatException('ArticleCard missing required fields: $json');
    }
    return ArticleCard(
      id: json['id'] as String,
      title: json['title'] as String,
      category: json['category'] as String,
      cefrLevel: json['cefr_level'] as String,
      sourceName: json['source_name'] as String,
      wordCount: json['word_count'] as int,
      sectionCount: json['section_count'] as int,
      processingOrder: (json['processing_order'] as int?) ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'category': category,
        'cefr_level': cefrLevel,
        'source_name': sourceName,
        'word_count': wordCount,
        'section_count': sectionCount,
        'processing_order': processingOrder,
      };
}

