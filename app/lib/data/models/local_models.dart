import 'dart:math' as math;

final _uuidRegex = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
);

/// Tạo chuỗi UUID v4 ngẫu nhiên tuân theo RFC 4122
String generateUuidV4() {
  final random = math.Random();
  final values = List<int>.generate(16, (i) => random.nextInt(256));
  values[6] = (values[6] & 0x0f) | 0x40; // version 4
  values[8] = (values[8] & 0x3f) | 0x80; // variant RFC 4122
  final hex = values.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

/// Kiểm tra một chuỗi có phải UUID hợp lệ không
bool isValidUuid(String? str) {
  if (str == null) return false;
  return _uuidRegex.hasMatch(str.trim());
}

/// Trả về chuỗi UUID đã chuẩn hóa, hoặc null nếu rỗng hoặc không phải UUID
String? sanitizeUuidOrNull(String? str) {
  if (str == null) return null;
  final trimmed = str.trim();
  if (trimmed.isEmpty || !isValidUuid(trimmed)) return null;
  return trimmed;
}

/// Model tiến trình đọc bài viết, lưu trong box `reading_progress`.
/// Phục vụ khôi phục vị trí đọc dở (đọc tiếp) và đồng bộ với bảng `reading_history`.
class ReadingProgress {
  final String articleId;
  final String lastReadSectionId;
  final int lastSectionIndex;
  final int maxIndexReached;
  final int progressPercent;
  final bool completed;
  final DateTime lastReadAt;
  final bool dirty;

  const ReadingProgress({
    required this.articleId,
    required this.lastReadSectionId,
    required this.lastSectionIndex,
    required this.maxIndexReached,
    required this.progressPercent,
    required this.completed,
    required this.lastReadAt,
    this.dirty = true,
  });

  ReadingProgress copyWith({
    String? articleId,
    String? lastReadSectionId,
    int? lastSectionIndex,
    int? maxIndexReached,
    int? progressPercent,
    bool? completed,
    DateTime? lastReadAt,
    bool? dirty,
  }) {
    return ReadingProgress(
      articleId: articleId ?? this.articleId,
      lastReadSectionId: lastReadSectionId ?? this.lastReadSectionId,
      lastSectionIndex: lastSectionIndex ?? this.lastSectionIndex,
      maxIndexReached: maxIndexReached ?? this.maxIndexReached,
      progressPercent: progressPercent ?? this.progressPercent,
      completed: completed ?? this.completed,
      lastReadAt: lastReadAt ?? this.lastReadAt,
      dirty: dirty ?? this.dirty,
    );
  }

  Map<String, dynamic> toMap() => {
        'article_id': articleId,
        'last_read_section_id': lastReadSectionId,
        'last_section_index': lastSectionIndex,
        'max_index_reached': maxIndexReached,
        'progress_percent': progressPercent,
        'completed': completed,
        'last_read_at': lastReadAt.toUtc().toIso8601String(),
        'dirty': dirty,
      };

  /// Chuyển thành hàng dữ liệu gửi lên bảng `reading_history` của Supabase (CONTRACTS 3.2).
  /// Trả về null nếu `article_id` không phải UUID hợp lệ (ví dụ dữ liệu fixture cũ).
  Map<String, dynamic>? toRemoteRow({required String userId}) {
    final validArticleId = sanitizeUuidOrNull(articleId);
    if (validArticleId == null) {
      return null;
    }
    return {
      'user_id': userId,
      'article_id': validArticleId,
      'last_read_section_id': sanitizeUuidOrNull(lastReadSectionId),
      'progress_percent': progressPercent,
      'completed': completed,
      'last_read_at': lastReadAt.toUtc().toIso8601String(),
    };
  }

  factory ReadingProgress.fromMap(Map raw) {
    final map = Map<String, dynamic>.from(raw);
    return ReadingProgress(
      articleId: map['article_id'] as String,
      lastReadSectionId: (map['last_read_section_id'] ?? '') as String,
      lastSectionIndex: (map['last_section_index'] ?? 0) as int,
      maxIndexReached: (map['max_index_reached'] ?? 0) as int,
      progressPercent: (map['progress_percent'] ?? 0) as int,
      completed: (map['completed'] ?? false) as bool,
      lastReadAt: map['last_read_at'] != null
          ? DateTime.parse(map['last_read_at'] as String)
          : DateTime.now().toUtc(),
      dirty: (map['dirty'] ?? false) as bool,
    );
  }
}

/// Nguồn gốc vị trí lưu từ theo Contract 1.4 (ADR-019).
enum WordSavedFrom {
  itemSheet('item_sheet'),
  phraseRow('phrase_row'),
  tooltip('tooltip');

  final String value;
  const WordSavedFrom(this.value);
}

/// Payload cho event word_saved (CONTRACTS mục 4).
Map<String, dynamic> buildWordSavedPayload({
  required String lemmaKey,
  required String kind, // 'lexicon' | 'glossary'
  required WordSavedFrom from,
}) =>
    {
      'lemma_key': lemmaKey,
      'kind': kind,
      'from': from.value,
    };

/// Payload cho event word_unsaved (CONTRACTS mục 4).
Map<String, dynamic> buildWordUnsavedPayload({
  required String lemmaKey,
}) =>
    {
      'lemma_key': lemmaKey,
    };

/// Model từ vựng người dùng đã lưu, lưu trong box `saved_words`.
/// Khóa theo `lemma_key` (ADR-003). Hỗ trợ soft delete (tombstone)
/// để FE-06 biết gọi delete() trên Supabase thay vì bị sống lại khi đồng bộ.
class SavedWord {
  final String id;
  final String lemmaKey;
  final String? lexiconEntryId;
  final String entryType; // 'single_word' | 'collocation' (Contract 1.4 / ADR-019)
  final String displayText;
  final String vi;
  final String exampleSentence;
  final Map<String, dynamic> cloze;
  final String sourceArticleId;
  final DateTime savedAt;
  final bool isNew;
  final DateTime? firstReviewedAt;
  final int reps;
  final int intervalDays;
  final double ease;
  final DateTime dueDate;
  final bool dirty;
  final bool deleted;

  const SavedWord({
    required this.id,
    required this.lemmaKey,
    this.lexiconEntryId,
    this.entryType = 'single_word',
    required this.displayText,
    required this.vi,
    required this.exampleSentence,
    required this.cloze,
    required this.sourceArticleId,
    required this.savedAt,
    this.isNew = true,
    this.firstReviewedAt,
    this.reps = 0,
    this.intervalDays = 0,
    this.ease = 2.5,
    required this.dueDate,
    this.dirty = true,
    this.deleted = false,
  });

  SavedWord copyWith({
    String? id,
    String? lemmaKey,
    String? lexiconEntryId,
    String? entryType,
    String? displayText,
    String? vi,
    String? exampleSentence,
    Map<String, dynamic>? cloze,
    String? sourceArticleId,
    DateTime? savedAt,
    bool? isNew,
    DateTime? firstReviewedAt,
    int? reps,
    int? intervalDays,
    double? ease,
    DateTime? dueDate,
    bool? dirty,
    bool? deleted,
  }) {
    return SavedWord(
      id: id ?? this.id,
      lemmaKey: lemmaKey ?? this.lemmaKey,
      lexiconEntryId: lexiconEntryId ?? this.lexiconEntryId,
      entryType: entryType ?? this.entryType,
      displayText: displayText ?? this.displayText,
      vi: vi ?? this.vi,
      exampleSentence: exampleSentence ?? this.exampleSentence,
      cloze: cloze ?? this.cloze,
      sourceArticleId: sourceArticleId ?? this.sourceArticleId,
      savedAt: savedAt ?? this.savedAt,
      isNew: isNew ?? this.isNew,
      firstReviewedAt: firstReviewedAt ?? this.firstReviewedAt,
      reps: reps ?? this.reps,
      intervalDays: intervalDays ?? this.intervalDays,
      ease: ease ?? this.ease,
      dueDate: dueDate ?? this.dueDate,
      dirty: dirty ?? this.dirty,
      deleted: deleted ?? this.deleted,
    );
  }

  Map<String, dynamic> toMap() => {
        'id': id,
        'lemma_key': lemmaKey,
        'lexicon_entry_id': lexiconEntryId,
        'entry_type': entryType,
        'display_text': displayText,
        'vi': vi,
        'example_sentence': exampleSentence,
        'cloze': cloze,
        'source_article_id': sourceArticleId,
        'saved_at': savedAt.toUtc().toIso8601String(),
        'is_new': isNew,
        'first_reviewed_at': firstReviewedAt?.toUtc().toIso8601String(),
        'reps': reps,
        'interval_days': intervalDays,
        'ease': ease,
        'due_date':
            '${dueDate.year.toString().padLeft(4, '0')}-${dueDate.month.toString().padLeft(2, '0')}-${dueDate.day.toString().padLeft(2, '0')}',
        'dirty': dirty,
        'deleted': deleted,
      };

  /// Chuyển thành hàng dữ liệu gửi lên bảng `user_saved_words` của Supabase (CONTRACTS 3.3).
  /// Không gửi trường `id` (server tự sinh, xung đột khóa `user_id, lemma_key`).
  /// `source_article_id` được chuẩn hóa thành UUID hợp lệ hoặc null nếu không phải UUID (ADR-021 điểm 9).
  Map<String, dynamic> toRemoteRow({required String userId}) {
    return {
      'user_id': userId,
      'lemma_key': lemmaKey,
      'lexicon_entry_id': sanitizeUuidOrNull(lexiconEntryId),
      'entry_type': entryType,
      'display_text': displayText,
      'vi': vi,
      'example_sentence': exampleSentence,
      'cloze': cloze,
      'source_article_id': sanitizeUuidOrNull(sourceArticleId),
      'saved_at': savedAt.toUtc().toIso8601String(),
      'is_new': isNew,
      'first_reviewed_at': firstReviewedAt?.toUtc().toIso8601String(),
      'reps': reps,
      'interval_days': intervalDays,
      'ease': ease,
      'due_date':
          '${dueDate.year.toString().padLeft(4, '0')}-${dueDate.month.toString().padLeft(2, '0')}-${dueDate.day.toString().padLeft(2, '0')}',
    };
  }

  static DateTime _parseDueDate(dynamic raw) {
    if (raw == null) {
      final now = DateTime.now();
      return DateTime(now.year, now.month, now.day);
    }
    final str = raw.toString().trim();
    if (str.length == 10) {
      final parsed = DateTime.parse(str);
      return DateTime(parsed.year, parsed.month, parsed.day);
    }
    final local = DateTime.parse(str).toLocal();
    return DateTime(local.year, local.month, local.day);
  }

  factory SavedWord.fromMap(Map raw) {
    final map = Map<String, dynamic>.from(raw);
    return SavedWord(
      id: map['id'] as String,
      lemmaKey: map['lemma_key'] as String,
      lexiconEntryId: map['lexicon_entry_id'] as String?,
      entryType: (map['entry_type'] as String?) ?? 'single_word',
      displayText: (map['display_text'] ?? '') as String,
      vi: (map['vi'] ?? '') as String,
      exampleSentence: (map['example_sentence'] ?? '') as String,
      cloze: map['cloze'] != null
          ? Map<String, dynamic>.from(map['cloze'] as Map)
          : const {},
      sourceArticleId: (map['source_article_id'] ?? '') as String,
      savedAt: map['saved_at'] != null
          ? DateTime.parse(map['saved_at'] as String)
          : DateTime.now().toUtc(),
      isNew: (map['is_new'] ?? true) as bool,
      firstReviewedAt: map['first_reviewed_at'] != null
          ? DateTime.parse(map['first_reviewed_at'] as String)
          : null,
      reps: (map['reps'] ?? 0) as int,
      intervalDays: (map['interval_days'] ?? 0) as int,
      ease: (map['ease'] is num) ? (map['ease'] as num).toDouble() : 2.5,
      dueDate: _parseDueDate(map['due_date']),
      dirty: (map['dirty'] ?? true) as bool,
      deleted: (map['deleted'] ?? false) as bool,
    );
  }
}

/// Model sự kiện sử dụng được lưu trong hàng đợi `event_queue`.
/// Khóa là số int tự tăng của Hive box.
class QueuedEvent {
  final int? id;
  final String eventType;
  final String? articleId;
  final String? sectionId;
  final Map<String, dynamic> payload;
  final DateTime clientTs;

  const QueuedEvent({
    this.id,
    required this.eventType,
    this.articleId,
    this.sectionId,
    required this.payload,
    required this.clientTs,
  });

  Map<String, dynamic> toMap() => {
        'event_type': eventType,
        'article_id': articleId,
        'section_id': sectionId,
        'payload': payload,
        'client_ts': clientTs.toUtc().toIso8601String(),
      };

  /// Chuyển thành hàng dữ liệu gửi lên bảng `usage_events` của Supabase (CONTRACTS 3.5).
  Map<String, dynamic> toRemoteRow() => {
        'event_type': eventType,
        'article_id': sanitizeUuidOrNull(articleId),
        'section_id': sanitizeUuidOrNull(sectionId),
        'payload': payload,
        'client_ts': clientTs.toUtc().toIso8601String(),
      };

  factory QueuedEvent.fromMap(Map raw, {int? id}) {
    final map = Map<String, dynamic>.from(raw);
    return QueuedEvent(
      id: id,
      eventType: map['event_type'] as String,
      articleId: map['article_id'] as String?,
      sectionId: map['section_id'] as String?,
      payload: map['payload'] != null
          ? Map<String, dynamic>.from(map['payload'] as Map)
          : const {},
      clientTs: map['client_ts'] != null
          ? DateTime.parse(map['client_ts'] as String)
          : DateTime.now().toUtc(),
    );
  }
}

