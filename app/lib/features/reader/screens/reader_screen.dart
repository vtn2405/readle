import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../data/models/article_bundle.dart';
import '../../../data/models/local_models.dart';
import '../../../data/providers/sync_providers.dart';
import '../../../data/services/sync_service.dart';
import '../models/highlight_kind.dart';
import '../models/tap_result.dart';
import '../providers/reader_state.dart';
import '../providers/saved_words_provider.dart';
import '../services/audio_service.dart';
import '../services/tap_resolver.dart';
import '../widgets/item_bottom_sheet.dart';
import '../widgets/phrase_bottom_sheet.dart';
import '../widgets/section_card.dart';
import '../widgets/word_tooltip.dart';

class ReaderScreen extends ConsumerStatefulWidget {
  final String articleId;

  const ReaderScreen({
    super.key,
    required this.articleId,
  });

  @override
  ConsumerState<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends ConsumerState<ReaderScreen> {
  late PageController _pageController;
  late final SyncService _syncService;
  OverlayEntry? _tooltipEntry;

  // Memoization cho lexicon và highlights theo bundle/section (R-FE-04 c)
  String? _loadedArticleId;
  Map<String, LexiconEntry> _lexiconById = {};
  final Map<String, Map<int, HighlightKind>> _highlightsBySectionId = {};

  void _ensureMemoized(ArticleBundle bundle) {
    if (_loadedArticleId != bundle.article.id) {
      _loadedArticleId = bundle.article.id;
      _lexiconById = {for (final e in bundle.lexicon) e.id: e};
      _highlightsBySectionId.clear();
    }
  }

  Map<int, HighlightKind> _getHighlightsForSection(
    ArticleBundle bundle,
    Section section,
  ) {
    _ensureMemoized(bundle);
    return _highlightsBySectionId.putIfAbsent(
      section.id,
      () => computeHighlights(
        sectionId: section.id,
        occurrences: bundle.occurrences,
        lexicon: bundle.lexicon,
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _syncService = ref.read(syncServiceProvider);
    final initialState = ref.read(readerProvider(widget.articleId));
    _pageController =
        PageController(initialPage: initialState.currentSectionIndex);

    final existingBundle =
        ref.read(articleBundleProvider(widget.articleId)).asData?.value;
    if (existingBundle != null) {
      Future.microtask(() {
        if (mounted) {
          ref
              .read(readerProvider(widget.articleId).notifier)
              .initSections(existingBundle.sections);
          final currentIndex =
              ref.read(readerProvider(widget.articleId)).currentSectionIndex;
          if (_pageController.hasClients &&
              _pageController.page?.round() != currentIndex) {
            _pageController.jumpToPage(currentIndex);
          }
        }
      });
    }
  }

  @override
  void dispose() {
    unawaited(_syncService.flush());
    _removeTooltip();
    _pageController.dispose();
    super.dispose();
  }

  void _removeTooltip() {
    if (_tooltipEntry != null) {
      _tooltipEntry?.remove();
      _tooltipEntry = null;
    }
  }

  void _handleTokenTap({
    required BuildContext context,
    required ArticleBundle bundle,
    required Section section,
    required Token token,
    required Offset position,
    required bool inKeyIdea,
  }) {
    // Đóng tooltip đang mở nếu có
    _removeTooltip();

    // Dấu câu không có vùng chạm và không phát sinh bất kỳ hành động nào
    if (!token.isWord) return;

    _ensureMemoized(bundle);
    final lexiconById = _lexiconById;

    // Phân giải chạm từ theo đúng luật
    final result = resolveTap(
      tokens: inKeyIdea ? section.keyIdea.tokens : section.tokens,
      i: token.i,
      sectionOccurrences: inKeyIdea
          ? []
          : bundle.occurrences
              .where((o) => o.sectionId == section.id)
              .toList(),
      lexiconById: lexiconById,
      inKeyIdea: inKeyIdea,
    );

    // Xử lý giao diện theo từng loại kết quả
    switch (result.kind) {
      case TapKind.none:
        break;

      case TapKind.tooltip:
        final currentSpeed = ref.read(speedModeProvider);
        final readerTheme = Theme.of(context);
        _tooltipEntry = OverlayEntry(
          builder: (ctx) => Theme(
            data: readerTheme,
            child: Consumer(
              builder: (context, ref, child) {
                final savedWords = ref.watch(savedWordsNotifierProvider);
                final isWordSaved =
                    savedWords.contains(result.token.lemma.toLowerCase());

                return WordTooltip(
                  token: result.token,
                  position: position,
                  isSaved: isWordSaved,
                  onDismiss: _removeTooltip,
                  onSpeak: () {
                    final payload = buildAudioPlayedPayload(
                      source: AudioEventSource.tooltip,
                      speed: currentSpeed,
                    );
                    debugPrint('Audio event prepared: $payload');
                    ref.read(audioServiceProvider).speak(
                          result.token.lemma.toLowerCase(),
                          speed: currentSpeed,
                        );
                  },
                  onSave: () {
                    ref
                        .read(savedWordsNotifierProvider.notifier)
                        .toggleSaveTooltip(
                          token: result.token,
                          tokens: inKeyIdea
                              ? section.keyIdea.tokens
                              : section.tokens,
                          tokenIndex: result.token.i,
                          articleId: bundle.article.id,
                          sectionId: section.id,
                        );
                  },
                  onReportMissing: () {
                    // Điểm kết nối event meaning_reported (FE-14)
                    debugPrint(
                        'Báo thiếu nghĩa cho token: ${result.token.text}');
                  },
                );
              },
            ),
          ),
        );
        Overlay.of(context).insert(_tooltipEntry!);
        break;

      case TapKind.item:
        final entry = lexiconById[result.item!.lexiconEntryId];
        if (entry == null) return;

        // Cập nhật snapshot nếu từ này đã được lưu trước đó (CONTRACTS 3.3)
        ref.read(savedWordsNotifierProvider.notifier).updateSnapshotIfSaved(
              occ: result.item!,
              entry: entry,
            );

        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          useSafeArea: true,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          builder: (ctx) => ItemBottomSheet(
            occurrence: result.item!,
            entry: entry,
            onSpeak: ({required double speed}) {
              final payload = buildAudioPlayedPayload(
                source: AudioEventSource.item,
                speed: speed,
              );
              debugPrint('Audio event prepared: $payload');
              final audioUrl = entry.audioUrl;
              if (audioUrl != null && audioUrl.isNotEmpty) {
                ref.read(audioServiceProvider).playUrl(
                      audioUrl,
                      speed: speed,
                      fallbackText: entry.canonicalForm,
                    );
              } else {
                ref.read(audioServiceProvider).speak(
                      entry.canonicalForm,
                      speed: speed,
                    );
              }
            },
            onSave: () {
              ref
                  .read(savedWordsNotifierProvider.notifier)
                  .toggleSaveOccurrence(
                    occ: result.item!,
                    entry: entry,
                    articleId: bundle.article.id,
                    from: WordSavedFrom.itemSheet,
                  );
            },
          ),
        ).whenComplete(() {
          ref.read(audioServiceProvider).stop();
        });
        break;

      case TapKind.phrase:
        // Cập nhật snapshot cho các cụm đã lưu nếu có (CONTRACTS 3.3)
        for (final phrase in result.phrases) {
          final phraseEntry = lexiconById[phrase.lexiconEntryId];
          if (phraseEntry != null) {
            ref.read(savedWordsNotifierProvider.notifier).updateSnapshotIfSaved(
                  occ: phrase,
                  entry: phraseEntry,
                );
          }
        }

        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          useSafeArea: true,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          builder: (ctx) => PhraseBottomSheet(
            tapResult: result,
            lexiconById: lexiconById,
            onSpeakPhrase: (text, audioUrl, {required double speed}) {
              final payload = buildAudioPlayedPayload(
                source: AudioEventSource.item,
                speed: speed,
              );
              debugPrint('Audio event prepared: $payload');
              if (audioUrl != null && audioUrl.isNotEmpty) {
                ref.read(audioServiceProvider).playUrl(
                      audioUrl,
                      speed: speed,
                      fallbackText: text,
                    );
              } else {
                ref.read(audioServiceProvider).speak(text, speed: speed);
              }
            },
            onSpeakWord: (word, {required double speed}) {
              final payload = buildAudioPlayedPayload(
                source: AudioEventSource.wordRow,
                speed: speed,
              );
              debugPrint('Audio event prepared: $payload');
              ref.read(audioServiceProvider).speak(word, speed: speed);
            },
            onSavePhrase: (phraseOcc) {
              final phraseEntry = lexiconById[phraseOcc.lexiconEntryId];
              if (phraseEntry != null) {
                ref
                    .read(savedWordsNotifierProvider.notifier)
                    .toggleSaveOccurrence(
                      occ: phraseOcc,
                      entry: phraseEntry,
                      articleId: bundle.article.id,
                      from: WordSavedFrom.phraseRow,
                    );
              }
            },
          ),
        ).whenComplete(() {
          ref.read(audioServiceProvider).stop();
        });
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Chỉ khởi tạo sections 1 lần duy nhất khi bundle chuyển sang trạng thái Data
    ref.listen<AsyncValue<ArticleBundle>>(
      articleBundleProvider(widget.articleId),
      (previous, next) {
        next.whenData((bundle) {
          ref
              .read(readerProvider(widget.articleId).notifier)
              .initSections(bundle.sections);
          final currentIndex =
              ref.read(readerProvider(widget.articleId)).currentSectionIndex;
          if (_pageController.hasClients &&
              _pageController.page?.round() != currentIndex) {
            _pageController.jumpToPage(currentIndex);
          }
        });
      },
    );

    final bundleAsync = ref.watch(articleBundleProvider(widget.articleId));
    final readerState = ref.watch(readerProvider(widget.articleId));

    final brightness = Theme.of(context).brightness;
    final readerTheme = brightness == Brightness.dark
        ? AppTheme.readerDark
        : AppTheme.readerLight;

    return Theme(
      data: readerTheme,
      child: Builder(
        builder: (context) {
          return Scaffold(
            backgroundColor: readerTheme.scaffoldBackgroundColor,
            appBar: AppBar(
              title: bundleAsync.when(
                data: (bundle) => Text(
                  bundle.article.title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 18,
                  ),
                ),
                loading: () => const Text('Đang tải...'),
                error: (_, _) => Text('Bài đọc (${widget.articleId})'),
              ),
              actions: [
                if (readerState.totalSections > 0)
                  Padding(
                    padding: const EdgeInsets.only(right: 16.0),
                    child: Center(
                      child: Text(
                        '${readerState.currentSectionIndex + 1} / ${readerState.totalSections}',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.color
                                  ?.withValues(alpha: 0.8),
                              fontWeight: FontWeight.w500,
                            ),
                      ),
                    ),
                  ),
              ],
            ),
            body: bundleAsync.when(
              loading: () => const Center(
                child: CircularProgressIndicator(),
              ),
              error: (err, stack) => Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Text(
                    'Không thể tải bài đọc: $err',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.grey),
                  ),
                ),
              ),
              data: (bundle) {
                return SafeArea(
                  child: PageView.builder(
                    controller: _pageController,
                    itemCount: bundle.sections.length,
                    onPageChanged: (index) {
                      _removeTooltip();
                      final sectionId =
                          (index >= 0 && index < bundle.sections.length)
                              ? bundle.sections[index].id
                              : null;
                      ref
                          .read(readerProvider(widget.articleId).notifier)
                          .onPageChanged(index, sectionId: sectionId);
                    },
                    itemBuilder: (context, index) {
                      final section = bundle.sections[index];
                      final highlights = _getHighlightsForSection(
                        bundle,
                        section,
                      );

                      return Padding(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                        child: SectionCard(
                          section: section,
                          highlights: highlights,
                          onTokenTap:
                              (
                                token, {
                                required position,
                                bool inKeyIdea = false,
                              }) {
                                _handleTokenTap(
                                  context: context,
                                  bundle: bundle,
                                  section: section,
                                  token: token,
                                  position: position,
                                  inKeyIdea: inKeyIdea,
                                );
                              },
                        ),
                      );
                    },
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
