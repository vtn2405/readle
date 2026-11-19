import '../../../data/models/article_bundle.dart';

enum HighlightKind {
  none,
  singleWord,
  collocation,
}

Map<int, HighlightKind> computeHighlights({
  required String sectionId,
  required List<Occurrence> occurrences,
  required List<LexiconEntry> lexicon,
}) {
  final sectionOccurrences =
      occurrences.where((o) => o.sectionId == sectionId).toList();
  final lexiconMap = {for (final e in lexicon) e.id: e};

  // ADR-018: Trong mỗi card, mỗi lexiconEntryId chỉ giữ occurrence có tokenStart nhỏ nhất
  final Map<String, Occurrence> firstOccurrenceByLexicon = {};
  for (final occ in sectionOccurrences) {
    final existing = firstOccurrenceByLexicon[occ.lexiconEntryId];
    if (existing == null || occ.tokenStart < existing.tokenStart) {
      firstOccurrenceByLexicon[occ.lexiconEntryId] = occ;
    }
  }
  final uniqueOccurrences = firstOccurrenceByLexicon.values.toList();

  // Sort: single words first, then shorter collocations, then longer collocations
  uniqueOccurrences.sort((a, b) {
    final aIsColloc = lexiconMap[a.lexiconEntryId]?.type == 'collocation';
    final bIsColloc = lexiconMap[b.lexiconEntryId]?.type == 'collocation';
    if (!aIsColloc && bIsColloc) return -1;
    if (aIsColloc && !bIsColloc) return 1;
    final aLen = a.tokenEnd - a.tokenStart;
    final bLen = b.tokenEnd - b.tokenStart;
    return aLen.compareTo(bLen);
  });

  final Map<int, HighlightKind> result = {};

  for (final occ in uniqueOccurrences) {
    final entry = lexiconMap[occ.lexiconEntryId];
    final isCollocation = entry?.type == 'collocation';

    for (int i = occ.tokenStart; i <= occ.tokenEnd; i++) {
      final current = result[i];
      if (current == null || current == HighlightKind.none) {
        result[i] = isCollocation
            ? HighlightKind.collocation
            : HighlightKind.singleWord;
      } else if (isCollocation) {
        result[i] = HighlightKind.collocation;
      }
    }
  }

  return result;
}

