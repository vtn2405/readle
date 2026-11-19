import '../../../data/models/article_bundle.dart';

enum TapKind {
  none,
  tooltip,
  item,
  phrase,
}

class TapResult {
  final TapKind kind;
  final Token token;
  final List<Occurrence> phrases; // Sắp xếp cụm dài trước
  final Occurrence? item; // Sheet mục từ (single_word)
  final bool showWordRow; // Sheet cụm có kèm dòng từ đơn hay không
  final Occurrence? wordRowItem; // Khi dòng từ đơn chính là một mục từ single_word

  const TapResult(
    this.kind,
    this.token, {
    this.phrases = const [],
    this.item,
    this.showWordRow = false,
    this.wordRowItem,
  });

  /// Giá trị `result` cho event word_tapped (CONTRACTS mục 4).
  /// Trả về null với TapKind.none (không phát event khi chạm dấu câu).
  String? get eventResult => switch (kind) {
        TapKind.none => null,
        TapKind.item => 'item',
        TapKind.phrase => showWordRow ? 'phrase_plus_word' : 'phrase_only',
        TapKind.tooltip => token.vi == null ? 'missing_meaning' : 'tooltip',
      };
}

