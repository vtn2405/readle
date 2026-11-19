import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_bundle.dart';
import '../../../data/models/local_models.dart';
import '../../../data/providers/local_providers.dart';
import '../../../data/repositories/local_storage_repository.dart';

/// Kết quả tạo Cloze và câu ví dụ từ tokens xung quanh một từ đơn glossary.
class TooltipClozeResult {
  final Cloze cloze;
  final String exampleSentence;

  const TooltipClozeResult({
    required this.cloze,
    required this.exampleSentence,
  });
}

/// Helper trích xuất Cloze và câu ví dụ tự động cho từ đơn hiển thị trên Tooltip.
TooltipClozeResult buildTooltipCloze({
  required List<Token> tokens,
  required int targetTokenIndex,
}) {
  if (tokens.isEmpty ||
      targetTokenIndex < 0 ||
      targetTokenIndex >= tokens.length) {
    return const TooltipClozeResult(
      cloze: Cloze(textBefore: '', answer: '', textAfter: ''),
      exampleSentence: '',
    );
  }

  // 1. Tìm đầu câu: từ token đầu tiên hoặc ngay sau token kết thúc câu trước
  int startIndex = 0;
  for (int i = targetTokenIndex - 1; i >= 0; i--) {
    final text = tokens[i].text.trim();
    final ws = tokens[i].ws;
    if (text.endsWith('.') ||
        text.endsWith('!') ||
        text.endsWith('?') ||
        ws.contains('\n')) {
      startIndex = i + 1;
      break;
    }
  }

  // 2. Tìm cuối câu: token có dấu ngắt câu hoặc trước ngắt dòng
  int endIndex = tokens.length - 1;
  for (int i = targetTokenIndex; i < tokens.length; i++) {
    final text = tokens[i].text.trim();
    final ws = tokens[i].ws;
    if (text.endsWith('.') ||
        text.endsWith('!') ||
        text.endsWith('?') ||
        ws.contains('\n')) {
      endIndex = i;
      break;
    }
  }

  // textBefore: từ startIndex tới trước targetTokenIndex
  final beforeBuf = StringBuffer();
  for (int i = startIndex; i < targetTokenIndex; i++) {
    beforeBuf.write(tokens[i].text);
    beforeBuf.write(tokens[i].ws);
  }

  final answer = tokens[targetTokenIndex].text;

  // textAfter: khoảng trắng của target token + các tokens tiếp theo tới endIndex
  final afterBuf = StringBuffer();
  afterBuf.write(tokens[targetTokenIndex].ws);
  for (int i = targetTokenIndex + 1; i <= endIndex; i++) {
    afterBuf.write(tokens[i].text);
    if (i < endIndex) {
      afterBuf.write(tokens[i].ws);
    }
  }

  final cleanBefore =
      beforeBuf.toString().replaceFirst(RegExp(r'^[”"”\s]+'), '');
  final cleanAfter = afterBuf.toString().trimRight();
  final fullSentence = '$cleanBefore$answer$cleanAfter'.trim();

  return TooltipClozeResult(
    cloze: Cloze(
      textBefore: cleanBefore,
      answer: answer,
      textAfter: cleanAfter,
    ),
    exampleSentence: fullSentence,
  );
}

/// StateNotifier quản lý danh sách từ đã lưu (`Set<String>` lemmaKey) và các thao tác
/// lưu / bỏ lưu / cập nhật snapshot theo ADR-019 và Contract 1.4.
class SavedWordsNotifier extends StateNotifier<Set<String>> {
  final SavedWordsRepository savedWordsRepo;
  final EventQueueRepository eventQueueRepo;

  SavedWordsNotifier({
    required this.savedWordsRepo,
    required this.eventQueueRepo,
  }) : super(const {}) {
    _loadInitial();
  }

  Future<void> _loadInitial() async {
    final words = await savedWordsRepo.getAllWords(includeDeleted: false);
    state = words.map((w) => w.lemmaKey).toSet();
  }

  bool isSaved(String lemmaKey) {
    return state.contains(lemmaKey);
  }

  /// Bỏ lưu một từ hoặc cụm từ (soft delete + event word_unsaved + gỡ khỏi state).
  /// Khi gọi từ màn đọc, truyền `articleId` và `sectionId` tương ứng.
  /// Khi gọi từ Tab Đã lưu, để `articleId: null, sectionId: null` để BE-08 biết event xảy ra ngoài màn đọc.
  Future<void> unsaveWord(
    String lemmaKey, {
    String? articleId,
    String? sectionId,
  }) async {
    final now = DateTime.now().toUtc();
    await savedWordsRepo.deleteWord(lemmaKey);
    await eventQueueRepo.enqueue(
      QueuedEvent(
        eventType: 'word_unsaved',
        articleId: articleId,
        sectionId: sectionId,
        payload: buildWordUnsavedPayload(lemmaKey: lemmaKey),
        clientTs: now,
      ),
    );
    state = {...state}..remove(lemmaKey);
  }

  /// Toggle lưu / bỏ lưu cho mục từ trong Lexicon (từ sheet mục từ hoặc sheet cụm).
  Future<void> toggleSaveOccurrence({
    required Occurrence occ,
    required LexiconEntry entry,
    required String articleId,
    required WordSavedFrom from,
  }) async {
    final lemmaKey = entry.lemmaKey;
    final now = DateTime.now().toUtc();

    if (state.contains(lemmaKey)) {
      // 1. Đang lưu -> Bỏ lưu (soft delete)
      await unsaveWord(
        lemmaKey,
        articleId: articleId,
        sectionId: occ.sectionId,
      );
    } else {
      // 2. Chưa lưu -> Lưu mới hoặc kích hoạt lại từ đã xóa mềm
      final existing = await savedWordsRepo.getWord(lemmaKey);
      final SavedWord wordToSave;

      if (existing != null) {
        wordToSave = existing.copyWith(
          lexiconEntryId: entry.id,
          entryType: entry.type,
          displayText: entry.canonicalForm,
          vi: occ.vi,
          exampleSentence: occ.exampleSentence,
          cloze: occ.cloze.toJson(),
          // Giữ nguyên sourceArticleId ban đầu theo Contract 3.3
          deleted: false,
          dirty: true,
        );
      } else {
        wordToSave = SavedWord(
          id: generateUuidV4(),
          lemmaKey: lemmaKey,
          lexiconEntryId: entry.id,
          entryType: entry.type,
          displayText: entry.canonicalForm,
          vi: occ.vi,
          exampleSentence: occ.exampleSentence,
          cloze: occ.cloze.toJson(),
          sourceArticleId: articleId,
          savedAt: now,
          dueDate: DateTime(now.year, now.month, now.day),
          isNew: true,
          dirty: true,
          deleted: false,
        );
      }

      await savedWordsRepo.saveWord(wordToSave);
      await eventQueueRepo.enqueue(
        QueuedEvent(
          eventType: 'word_saved',
          articleId: articleId,
          sectionId: occ.sectionId,
          payload: buildWordSavedPayload(
            lemmaKey: lemmaKey,
            kind: 'lexicon',
            from: from,
          ),
          clientTs: now,
        ),
      );
      state = {...state, lemmaKey};
    }
  }

  /// Toggle lưu / bỏ lưu cho từ đơn glossary trên Tooltip.
  Future<void> toggleSaveTooltip({
    required Token token,
    required List<Token> tokens,
    required int tokenIndex,
    required String articleId,
    String? sectionId,
  }) async {
    final lemmaKey = token.lemma.toLowerCase().trim();
    final now = DateTime.now().toUtc();

    if (state.contains(lemmaKey)) {
      // Bỏ lưu
      await unsaveWord(
        lemmaKey,
        articleId: articleId,
        sectionId: sectionId,
      );
    } else {
      // Lưu mới từ glossary
      final clozeResult = buildTooltipCloze(
        tokens: tokens,
        targetTokenIndex: tokenIndex,
      );

      final existing = await savedWordsRepo.getWord(lemmaKey);
      final SavedWord wordToSave;
      final lemmaLower = token.lemma.toLowerCase().trim();

      if (existing != null) {
        wordToSave = existing.copyWith(
          entryType: 'single_word',
          displayText: lemmaLower,
          vi: token.vi ?? existing.vi,
          exampleSentence: clozeResult.exampleSentence,
          cloze: clozeResult.cloze.toJson(),
          // Giữ nguyên sourceArticleId ban đầu
          deleted: false,
          dirty: true,
        );
      } else {
        wordToSave = SavedWord(
          id: generateUuidV4(),
          lemmaKey: lemmaKey,
          lexiconEntryId: null, // Glossary token không thuộc lexicon
          entryType: 'single_word',
          displayText: lemmaLower,
          vi: token.vi ?? '',
          exampleSentence: clozeResult.exampleSentence,
          cloze: clozeResult.cloze.toJson(),
          sourceArticleId: articleId,
          savedAt: now,
          dueDate: DateTime(now.year, now.month, now.day),
          isNew: true,
          dirty: true,
          deleted: false,
        );
      }

      await savedWordsRepo.saveWord(wordToSave);
      await eventQueueRepo.enqueue(
        QueuedEvent(
          eventType: 'word_saved',
          articleId: articleId,
          sectionId: sectionId,
          payload: buildWordSavedPayload(
            lemmaKey: lemmaKey,
            kind: 'glossary',
            from: WordSavedFrom.tooltip,
          ),
          clientTs: now,
        ),
      );
      state = {...state, lemmaKey};
    }
  }

  /// Cập nhật snapshot khi mở sheet của từ đã lưu ở bài viết khác (CONTRACTS 3.3).
  Future<void> updateSnapshotIfSaved({
    required Occurrence occ,
    required LexiconEntry entry,
  }) async {
    final lemmaKey = entry.lemmaKey;
    final existing = await savedWordsRepo.getWord(lemmaKey);
    if (existing != null && !existing.deleted) {
      final newClozeMap = occ.cloze.toJson();
      final isDifferent = existing.vi != occ.vi ||
          existing.exampleSentence != occ.exampleSentence ||
          existing.lexiconEntryId != entry.id ||
          existing.entryType != entry.type ||
          !mapEquals(existing.cloze, newClozeMap);

      if (isDifferent) {
        final updated = existing.copyWith(
          lexiconEntryId: entry.id,
          entryType: entry.type,
          vi: occ.vi,
          exampleSentence: occ.exampleSentence,
          cloze: newClozeMap,
          // Không thay đổi sourceArticleId theo CONTRACTS 3.3
          dirty: true,
        );
        await savedWordsRepo.saveWord(updated);
      }
    }
  }
}

final savedWordsNotifierProvider =
    StateNotifierProvider<SavedWordsNotifier, Set<String>>((ref) {
  final savedWordsRepo = ref.watch(savedWordsRepositoryProvider);
  final eventQueueRepo = ref.watch(eventQueueRepositoryProvider);
  return SavedWordsNotifier(
    savedWordsRepo: savedWordsRepo,
    eventQueueRepo: eventQueueRepo,
  );
});
