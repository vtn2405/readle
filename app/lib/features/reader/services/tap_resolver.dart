import '../../../data/models/article_bundle.dart';
import '../models/tap_result.dart';

TapResult resolveTap({
  required List<Token> tokens,
  required int i,
  required List<Occurrence> sectionOccurrences,
  required Map<String, LexiconEntry> lexiconById,
  bool inKeyIdea = false,
}) {
  if (i < 0 || i >= tokens.length) {
    throw ArgumentError(
      'Token index $i is out of bounds (0..${tokens.length - 1})',
    );
  }

  final token = tokens[i];
  if (!token.isWord) {
    return TapResult(TapKind.none, token);
  }

  // Token trong Key idea không bao giờ gắn occurrence -> luôn trả về tooltip
  if (inKeyIdea) {
    return TapResult(TapKind.tooltip, token);
  }

  final covering = sectionOccurrences
      .where((o) => o.tokenStart <= i && i <= o.tokenEnd)
      .toList();

  bool isColl(Occurrence o) {
    final entry = lexiconById[o.lexiconEntryId];
    return entry != null && entry.type == 'collocation';
  }

  final phrases = covering.where(isColl).toList()
    ..sort((a, b) {
      final byLen =
          (b.tokenEnd - b.tokenStart).compareTo(a.tokenEnd - a.tokenStart);
      return byLen != 0 ? byLen : a.tokenStart.compareTo(b.tokenStart);
    });

  final singles = covering.where((o) => !isColl(o)).toList();
  final singleItem = singles.isEmpty ? null : singles.first;

  if (phrases.isNotEmpty) {
    return TapResult(
      TapKind.phrase,
      token,
      phrases: phrases,
      showWordRow: !token.isFn,
      wordRowItem: singleItem,
    );
  }

  if (singleItem != null) {
    return TapResult(TapKind.item, token, item: singleItem);
  }

  return TapResult(TapKind.tooltip, token);
}

