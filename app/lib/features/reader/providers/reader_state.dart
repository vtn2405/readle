import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_bundle.dart';
import '../../../data/models/local_models.dart';
import '../../../data/providers/local_providers.dart';
import '../../../data/providers/repository_providers.dart';
import '../../../data/repositories/local_storage_repository.dart';

@immutable
class ReaderState {
  final int currentSectionIndex;
  final int totalSections;
  final String lastReadSectionId;
  final int maxIndexReached;
  final int progressPercent;
  final bool isCompleted;

  const ReaderState({
    this.currentSectionIndex = 0,
    this.totalSections = 0,
    this.lastReadSectionId = '',
    this.maxIndexReached = 0,
    this.progressPercent = 0,
    this.isCompleted = false,
  });

  ReaderState copyWith({
    int? currentSectionIndex,
    int? totalSections,
    String? lastReadSectionId,
    int? maxIndexReached,
    int? progressPercent,
    bool? isCompleted,
  }) {
    return ReaderState(
      currentSectionIndex: currentSectionIndex ?? this.currentSectionIndex,
      totalSections: totalSections ?? this.totalSections,
      lastReadSectionId: lastReadSectionId ?? this.lastReadSectionId,
      maxIndexReached: maxIndexReached ?? this.maxIndexReached,
      progressPercent: progressPercent ?? this.progressPercent,
      isCompleted: isCompleted ?? this.isCompleted,
    );
  }
}

class ReaderNotifier extends StateNotifier<ReaderState> {
  final String articleId;
  final ReadingProgressRepository progressRepository;

  ReaderNotifier({
    required this.articleId,
    required this.progressRepository,
  }) : super(const ReaderState()) {
    // Nạp đồng bộ tiến trình đã lưu ngay trong constructor để PageController có trang ngay
    _loadInitialSync();
  }

  void _loadInitialSync() {
    final saved = progressRepository.getProgressSync(articleId);
    if (saved != null) {
      state = state.copyWith(
        currentSectionIndex: saved.lastSectionIndex,
        lastReadSectionId: saved.lastReadSectionId,
        maxIndexReached: saved.maxIndexReached,
        progressPercent: saved.progressPercent,
        isCompleted: saved.completed,
      );
    }
  }

  void initSections(List<Section> sections) {
    if (sections.isEmpty) return;

    int targetIndex = state.currentSectionIndex;

    // Ưu tiên khôi phục theo lastReadSectionId
    if (state.lastReadSectionId.isNotEmpty) {
      final found = sections.indexWhere((s) => s.id == state.lastReadSectionId);
      if (found != -1) {
        targetIndex = found;
      } else {
        targetIndex = targetIndex.clamp(0, sections.length - 1);
      }
    } else {
      targetIndex = targetIndex.clamp(0, sections.length - 1);
    }

    final maxIndex = math.max(state.maxIndexReached, targetIndex);
    final progressPercent =
        (((maxIndex + 1) / sections.length) * 100).round().clamp(0, 100);
    final completed = state.isCompleted ||
        (sections.length <= 1) ||
        (maxIndex >= sections.length - 1);
    final sectionId = sections[targetIndex].id;

    state = state.copyWith(
      currentSectionIndex: targetIndex,
      totalSections: sections.length,
      lastReadSectionId: sectionId,
      maxIndexReached: maxIndex,
      progressPercent: progressPercent,
      isCompleted: completed,
    );

    progressRepository.saveProgress(
      ReadingProgress(
        articleId: articleId,
        lastReadSectionId: sectionId,
        lastSectionIndex: targetIndex,
        maxIndexReached: maxIndex,
        progressPercent: progressPercent,
        completed: completed,
        lastReadAt: DateTime.now().toUtc(),
        dirty: true,
      ),
    );
  }

  void onPageChanged(int index, {String? sectionId}) {
    final maxIndex = math.max(state.maxIndexReached, index);
    final total = state.totalSections;
    final progressPercent = total > 0
        ? (((maxIndex + 1) / total) * 100).round().clamp(0, 100)
        : state.progressPercent;
    final completed =
        state.isCompleted || (total > 0 && maxIndex >= total - 1);
    final effectiveSectionId = sectionId ?? state.lastReadSectionId;

    state = state.copyWith(
      currentSectionIndex: index,
      lastReadSectionId: effectiveSectionId,
      maxIndexReached: maxIndex,
      progressPercent: progressPercent,
      isCompleted: completed,
    );

    progressRepository.saveProgress(
      ReadingProgress(
        articleId: articleId,
        lastReadSectionId: effectiveSectionId,
        lastSectionIndex: index,
        maxIndexReached: maxIndex,
        progressPercent: progressPercent,
        completed: completed,
        lastReadAt: DateTime.now().toUtc(),
        dirty: true,
      ),
    );
  }
}

final articleBundleProvider =
    FutureProvider.family<ArticleBundle, String>((ref, id) async {
  final repository = ref.watch(articleRepositoryProvider);
  return repository.get(id);
});

final readerProvider =
    StateNotifierProvider.family<ReaderNotifier, ReaderState, String>(
  (ref, articleId) {
    final repo = ref.watch(readingProgressRepositoryProvider);
    return ReaderNotifier(
      articleId: articleId,
      progressRepository: repo,
    );
  },
);
