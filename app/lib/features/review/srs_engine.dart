import 'dart:math' as math;

import '../../data/models/local_models.dart';

/// Đánh giá chất lượng nhớ thẻ theo SM-2 rút gọn (ADR-006, skill `flutter-srs`).
enum SrsRating {
  again,
  good,
  easy,
}

/// Thuật toán SM-2 rút gọn (ADR-006).
/// Không có bước học lại trong cùng phiên (Again -> gặp lại vào ngày mai).
class SrsEngine {
  /// Đánh giá một thẻ và tính toán trạng thái SRS tiếp theo.
  static SavedWord rate(
    SavedWord card,
    SrsRating rating, {
    DateTime? today,
    DateTime? now,
  }) {
    final todayDate = today != null
        ? DateTime(today.year, today.month, today.day)
        : () {
            final n = DateTime.now();
            return DateTime(n.year, n.month, n.day);
          }();
    final currentNow = now ?? DateTime.now().toUtc();

    final int newReps;
    int newInterval;
    double newEase;

    switch (rating) {
      case SrsRating.again:
        newReps = 0;
        newInterval = 1;
        newEase = math.max(1.3, card.ease - 0.2);
        break;

      case SrsRating.good:
        newReps = card.reps + 1;
        if (newReps == 1) {
          newInterval = 1;
        } else if (newReps == 2) {
          newInterval = 3;
        } else {
          newInterval = (card.intervalDays * card.ease).round();
        }
        newEase = card.ease;
        break;

      case SrsRating.easy:
        newReps = card.reps + 1;
        if (newReps == 1) {
          newInterval = 3;
        } else if (newReps == 2) {
          newInterval = 5;
        } else {
          newInterval = (card.intervalDays * card.ease * 1.3).round();
        }
        newEase = card.ease + 0.15;
        break;
    }

    // Giới hạn khoảng cách tối đa 180 ngày (skill flutter-srs)
    newInterval = math.min(newInterval, 180);

    final newDueDate = todayDate.add(Duration(days: newInterval));
    final newFirstReviewedAt = card.firstReviewedAt ?? currentNow;

    return card.copyWith(
      reps: newReps,
      intervalDays: newInterval,
      ease: newEase,
      dueDate: newDueDate,
      isNew: false,
      firstReviewedAt: newFirstReviewedAt,
      dirty: true,
    );
  }
}

/// Hàng đợi ôn tập hôm nay có giới hạn (skill `flutter-srs`, `no-pressure-ux`).
class ReviewQueue {
  /// Xây dựng hàng đợi ôn tập hôm nay:
  /// - Giới hạn ôn tối đa [dailyReviewCap] (mặc định 20), trừ đi số thẻ đã ôn hôm nay [reviewedTodayCount].
  /// - Giới hạn thẻ mới tối đa [dailyNewCards] (mặc định 5), trừ đi số thẻ mới đã học hôm nay [newReviewedTodayCount].
  /// - Thẻ ôn: `!isNew && dueDate <= today`, sắp theo `dueDate` tăng dần rồi `savedAt`.
  /// - Thẻ mới: `isNew`, sắp theo `savedAt` tăng dần.
  /// - Thẻ quá hạn vượt giới hạn tự rải sang các ngày sau (không tính/hiện số quá hạn).
  static List<SavedWord> buildTodayQueue({
    required List<SavedWord> words,
    required DateTime today,
    int dailyReviewCap = 20,
    int dailyNewCards = 5,
    int reviewedTodayCount = 0,
    int newReviewedTodayCount = 0,
  }) {
    final todayDate = DateTime(today.year, today.month, today.day);
    final reviewQuota = math.max(0, dailyReviewCap - reviewedTodayCount);
    final newQuota = math.max(0, dailyNewCards - newReviewedTodayCount);

    final activeWords = words.where((w) => !w.deleted).toList();

    // 1. Thẻ ôn: !isNew && dueDate <= today
    final reviewCandidates = activeWords.where((w) {
      if (w.isNew) return false;
      final d = DateTime(w.dueDate.year, w.dueDate.month, w.dueDate.day);
      return !d.isAfter(todayDate);
    }).toList();

    reviewCandidates.sort((a, b) {
      final aDue = DateTime(a.dueDate.year, a.dueDate.month, a.dueDate.day);
      final bDue = DateTime(b.dueDate.year, b.dueDate.month, b.dueDate.day);
      final cmpDue = aDue.compareTo(bDue);
      if (cmpDue != 0) return cmpDue;
      return a.savedAt.compareTo(b.savedAt);
    });

    final reviews = reviewCandidates.take(reviewQuota).toList();

    // 2. Thẻ mới: isNew
    final newCandidates = activeWords.where((w) => w.isNew).toList();

    newCandidates.sort((a, b) => a.savedAt.compareTo(b.savedAt));

    final news = newCandidates.take(newQuota).toList();

    return [...reviews, ...news];
  }
}
