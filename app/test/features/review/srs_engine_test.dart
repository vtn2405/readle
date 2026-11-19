import 'package:flutter_test/flutter_test.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/features/review/srs_engine.dart';

SavedWord _createTestWord({
  required String lemmaKey,
  bool isNew = true,
  int reps = 0,
  int intervalDays = 0,
  double ease = 2.5,
  DateTime? dueDate,
  DateTime? savedAt,
  DateTime? firstReviewedAt,
  bool deleted = false,
}) {
  final now = DateTime(2026, 11, 19);
  return SavedWord(
    id: 'test_$lemmaKey',
    lemmaKey: lemmaKey,
    displayText: lemmaKey,
    vi: 'Nghĩa của $lemmaKey',
    exampleSentence: 'This is an example sentence for $lemmaKey.',
    cloze: const {'text_before': 'This is ', 'answer': 'test', 'text_after': '.'},
    sourceArticleId: 'art_1',
    savedAt: savedAt ?? now,
    isNew: isNew,
    firstReviewedAt: firstReviewedAt,
    reps: reps,
    intervalDays: intervalDays,
    ease: ease,
    dueDate: dueDate ?? now,
    deleted: deleted,
  );
}

void main() {
  final today = DateTime(2026, 11, 19);

  group('SrsEngine.rate', () {
    test('thẻ mới: Good 3 lần liên tiếp cho khoảng cách 1 -> 3 -> 8 ngày', () {
      final initial = _createTestWord(lemmaKey: 'tend to', isNew: true);
      expect(initial.isNew, isTrue);
      expect(initial.reps, 0);
      expect(initial.intervalDays, 0);
      expect(initial.ease, 2.5);

      // Lần 1: Good
      final step1 = SrsEngine.rate(initial, SrsRating.good, today: today);
      expect(step1.isNew, isFalse);
      expect(step1.reps, 1);
      expect(step1.intervalDays, 1);
      expect(step1.ease, 2.5);
      expect(step1.dueDate, DateTime(2026, 11, 20));
      expect(step1.firstReviewedAt, isNotNull);
      expect(step1.dirty, isTrue);

      // Lần 2: Good
      final step2 = SrsEngine.rate(step1, SrsRating.good, today: step1.dueDate);
      expect(step2.reps, 2);
      expect(step2.intervalDays, 3);
      expect(step2.ease, 2.5);
      expect(step2.dueDate, DateTime(2026, 11, 23));

      // Lần 3: Good -> round(3 * 2.5) = 8
      final step3 = SrsEngine.rate(step2, SrsRating.good, today: step2.dueDate);
      expect(step3.reps, 3);
      expect(step3.intervalDays, 8);
      expect(step3.ease, 2.5);
      expect(step3.dueDate, DateTime(2026, 12, 1));
      // firstReviewedAt không bị ghi đè lại
      expect(step3.firstReviewedAt, step1.firstReviewedAt);
    });

    test('thẻ mới: Easy cho khoảng cách 3 ngày và tăng ease lên 2.65', () {
      final initial = _createTestWord(lemmaKey: 'vital role', isNew: true);

      // Lần 1: Easy
      final step1 = SrsEngine.rate(initial, SrsRating.easy, today: today);
      expect(step1.isNew, isFalse);
      expect(step1.reps, 1);
      expect(step1.intervalDays, 3);
      expect(step1.ease, closeTo(2.65, 0.0001));
      expect(step1.dueDate, DateTime(2026, 11, 22));

      // Lần 2: Easy
      final step2 = SrsEngine.rate(step1, SrsRating.easy, today: step1.dueDate);
      expect(step2.reps, 2);
      expect(step2.intervalDays, 5);
      expect(step2.ease, closeTo(2.80, 0.0001));
      expect(step2.dueDate, DateTime(2026, 11, 27));

      // Lần 3: Easy -> round(5 * 2.80 * 1.3) = round(18.2) = 18
      final step3 = SrsEngine.rate(step2, SrsRating.easy, today: step2.dueDate);
      expect(step3.reps, 3);
      expect(step3.intervalDays, 18);
      expect(step3.ease, closeTo(2.95, 0.0001));
    });

    test('Again sau 3 lần Good: reps về 0, interval 1, ease giảm 0.2', () {
      final cardAfter3Goods = _createTestWord(
        lemmaKey: 'moderate',
        isNew: false,
        reps: 3,
        intervalDays: 8,
        ease: 2.5,
      );

      final result = SrsEngine.rate(cardAfter3Goods, SrsRating.again, today: today);
      expect(result.reps, 0);
      expect(result.intervalDays, 1);
      expect(result.ease, closeTo(2.3, 0.0001));
      expect(result.dueDate, DateTime(2026, 11, 20));
      expect(result.isNew, isFalse);
    });

    test('Ease không xuống dưới 1.3 sau nhiều lần Again liên tiếp', () {
      var card = _createTestWord(lemmaKey: 'difficult', isNew: false, ease: 2.5);

      for (var i = 0; i < 10; i++) {
        card = SrsEngine.rate(card, SrsRating.again, today: today);
      }

      expect(card.ease, 1.3);
      expect(card.reps, 0);
      expect(card.intervalDays, 1);
    });

    test('Khoảng cách intervalDays bị kẹp tối đa 180 ngày', () {
      final card = _createTestWord(
        lemmaKey: 'mastered',
        isNew: false,
        reps: 10,
        intervalDays: 150,
        ease: 2.5,
      );

      // 150 * 2.5 = 375 > 180
      final result = SrsEngine.rate(card, SrsRating.good, today: today);
      expect(result.intervalDays, 180);
      expect(result.dueDate, today.add(const Duration(days: 180)));
    });
  });

  group('ReviewQueue.buildTodayQueue', () {
    test('giới hạn 20 thẻ ôn + 5 thẻ mới khi có nhiều thẻ đến hạn', () {
      final words = <SavedWord>[];

      // 30 thẻ ôn đến hạn
      for (var i = 1; i <= 30; i++) {
        words.add(_createTestWord(
          lemmaKey: 'review_$i',
          isNew: false,
          reps: 1,
          dueDate: today.subtract(Duration(days: i)), // quá hạn từ 1 đến 30 ngày
          savedAt: DateTime(2026, 10, 1).add(Duration(days: i)),
        ));
      }

      // 12 thẻ mới
      for (var i = 1; i <= 12; i++) {
        words.add(_createTestWord(
          lemmaKey: 'new_$i',
          isNew: true,
          savedAt: DateTime(2026, 11, 1).add(Duration(days: i)),
        ));
      }

      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
      );

      expect(queue.length, 25);
      final reviewCards = queue.where((w) => !w.isNew).toList();
      final newCards = queue.where((w) => w.isNew).toList();
      expect(reviewCards.length, 20);
      expect(newCards.length, 5);

      // Thẻ ôn được ưu tiên theo dueDate cũ nhất (quá hạn nhiều nhất) trước
      expect(reviewCards.first.lemmaKey, 'review_30');
      // Thẻ mới sắp theo savedAt tăng dần
      expect(newCards.first.lemmaKey, 'new_1');
    });

    test('trừ đi số thẻ đã ôn trong ngày (reviewedTodayCount, newReviewedTodayCount)', () {
      final words = <SavedWord>[];
      for (var i = 1; i <= 20; i++) {
        words.add(_createTestWord(
          lemmaKey: 'review_$i',
          isNew: false,
          dueDate: today,
        ));
      }
      for (var i = 1; i <= 10; i++) {
        words.add(_createTestWord(
          lemmaKey: 'new_$i',
          isNew: true,
        ));
      }

      // Đã ôn 15 thẻ ôn, đã học 4 thẻ mới
      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
        reviewedTodayCount: 15,
        newReviewedTodayCount: 4,
      );

      final reviewCards = queue.where((w) => !w.isNew).toList();
      final newCards = queue.where((w) => w.isNew).toList();
      expect(reviewCards.length, 5); // 20 - 15 = 5
      expect(newCards.length, 1); // 5 - 4 = 1
      expect(queue.length, 6);
    });

    test('vượt hạn mức đã ôn hôm nay -> quota về 0 không bị âm', () {
      final words = <SavedWord>[
        _createTestWord(lemmaKey: 'r1', isNew: false, dueDate: today),
        _createTestWord(lemmaKey: 'n1', isNew: true),
      ];

      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
        reviewedTodayCount: 25, // > 20
        newReviewedTodayCount: 10, // > 5
      );

      expect(queue, isEmpty);
    });

    test('nghỉ 10 ngày với 100 thẻ đến hạn -> vẫn chỉ trả về tối đa 20 thẻ ôn', () {
      final words = <SavedWord>[];
      for (var i = 1; i <= 100; i++) {
        words.add(_createTestWord(
          lemmaKey: 'overdue_$i',
          isNew: false,
          dueDate: today.subtract(const Duration(days: 10)),
        ));
      }

      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
      );

      expect(queue.length, 20);
      expect(queue.every((w) => !w.isNew), isTrue);
    });

    test('bỏ qua thẻ chưa đến hạn (dueDate > today) và thẻ đã deleted', () {
      final words = <SavedWord>[
        _createTestWord(
          lemmaKey: 'future',
          isNew: false,
          dueDate: today.add(const Duration(days: 1)),
        ),
        _createTestWord(
          lemmaKey: 'deleted_review',
          isNew: false,
          dueDate: today,
          deleted: true,
        ),
        _createTestWord(
          lemmaKey: 'deleted_new',
          isNew: true,
          deleted: true,
        ),
        _createTestWord(
          lemmaKey: 'valid_due_today',
          isNew: false,
          dueDate: today,
        ),
      ];

      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
      );

      expect(queue.length, 1);
      expect(queue.first.lemmaKey, 'valid_due_today');
    });

    test('cùng dueDate thì sắp xếp thẻ ôn theo savedAt tăng dần', () {
      final words = <SavedWord>[
        _createTestWord(
          lemmaKey: 'later_saved',
          isNew: false,
          dueDate: today,
          savedAt: DateTime(2026, 11, 15),
        ),
        _createTestWord(
          lemmaKey: 'earlier_saved',
          isNew: false,
          dueDate: today,
          savedAt: DateTime(2026, 11, 10),
        ),
      ];

      final queue = ReviewQueue.buildTodayQueue(
        words: words,
        today: today,
      );

      expect(queue.map((w) => w.lemmaKey).toList(), ['earlier_saved', 'later_saved']);
    });
  });
}
