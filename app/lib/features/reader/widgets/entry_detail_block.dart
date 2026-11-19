import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../data/models/article_bundle.dart';
import '../services/audio_service.dart';

/// Khối hiển thị chi tiết một mục từ theo đúng 6 khối của SPEC 3.6 và ADR-010, ADR-015:
/// 1. Mục từ + badge (Word/Collocation) · pos · cefr_level
/// 2. IPA + 1 nút loa + chip chế độ (1x / 0.75x)
/// 3. Nghĩa Việt theo ngữ cảnh
/// 4. Định nghĩa tiếng Anh (≤ 15 từ)
/// 5. Câu gốc (in đậm mục từ) + "Ví dụ: " extra_example (in đậm mục từ)
/// 6. Nút Lưu
///
/// Khi [isCompact] = true (cho cụm thứ 2 trở đi trong sheet cụm):
/// Chỉ hiển thị khối 1, 2, 3 và nút Lưu để sheet gọn gàng.
class EntryDetailBlock extends StatelessWidget {
  final Occurrence occurrence;
  final LexiconEntry entry;
  final bool isCompact;
  final bool isSaved;
  final double speedMode;
  final void Function(double speed) onPlayAudio;
  final ValueChanged<double>? onSpeedModeChanged;
  final VoidCallback? onSave;

  const EntryDetailBlock({
    super.key,
    required this.occurrence,
    required this.entry,
    this.isCompact = false,
    this.isSaved = false,
    this.speedMode = 1.0,
    required this.onPlayAudio,
    this.onSpeedModeChanged,
    this.onSave,
  });

  Widget _buildExtraExampleText(
    String example,
    String canonicalForm,
    ThemeData theme,
  ) {
    final baseStyle = theme.textTheme.bodySmall?.copyWith(
      fontSize: 13,
      height: 1.4,
      color: theme.textTheme.bodySmall?.color?.withValues(alpha: 0.9),
    );
    final boldStyle = baseStyle?.copyWith(fontWeight: FontWeight.bold);

    // [R-FE-04b]: Dựng regex hỗ trợ các dạng biến hình của từ trong cụm (vd "plays" ↔ "play")
    final words = canonicalForm.trim().split(RegExp(r'\s+'));
    final pattern = r'\b' +
        words.map((w) => '${RegExp.escape(w)}\\w*').join(r'\s+') +
        r'\b';
    final regex = RegExp(pattern, caseSensitive: false);
    final match = regex.firstMatch(example);

    if (match != null) {
      final before = example.substring(0, match.start);
      final matchedText = example.substring(match.start, match.end);
      final after = example.substring(match.end);

      return Text.rich(
        TextSpan(
          style: baseStyle,
          children: [
            const TextSpan(
              text: 'Ví dụ: ',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            TextSpan(text: before),
            TextSpan(text: matchedText, style: boldStyle),
            TextSpan(text: after),
          ],
        ),
      );
    }

    final lowerExample = example.toLowerCase();
    final lowerCanonical = canonicalForm.toLowerCase();
    final index = lowerExample.indexOf(lowerCanonical);

    if (index == -1) {
      return Text.rich(
        TextSpan(
          style: baseStyle,
          children: [
            const TextSpan(
              text: 'Ví dụ: ',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            TextSpan(text: example),
          ],
        ),
      );
    }

    final before = example.substring(0, index);
    final matchText = example.substring(index, index + canonicalForm.length);
    final after = example.substring(index + canonicalForm.length);

    return Text.rich(
      TextSpan(
        style: baseStyle,
        children: [
          const TextSpan(
            text: 'Ví dụ: ',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: before),
          TextSpan(text: matchText, style: boldStyle),
          TextSpan(text: after),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final highlightColors =
        theme.extension<HighlightColors>() ?? HighlightColors.light;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // 1. Tiêu đề + Badge + pos + cefr_level
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 8,
          runSpacing: 4,
          children: [
            Text(
              entry.canonicalForm,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: entry.type == 'collocation'
                    ? highlightColors.collocationBg
                    : highlightColors.singleWordBg,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                entry.type == 'collocation' ? 'Collocation' : 'Word',
                style: theme.textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: theme.colorScheme.onSurface,
                ),
              ),
            ),
            if (entry.pos.isNotEmpty)
              Text(
                '· ${entry.pos}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color:
                      theme.textTheme.bodySmall?.color?.withValues(alpha: 0.8),
                ),
              ),
            if (entry.cefrLevel.isNotEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                decoration: BoxDecoration(
                  color: theme.dividerColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  entry.cefrLevel,
                  style: theme.textTheme.labelSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.8),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 6),

        // 2. IPA + 1 Loa + Chip chế độ 1x/0.75x (ADR-015)
        Row(
          children: [
            if (entry.ipa != null && entry.ipa!.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(right: 8.0),
                child: Text(
                  entry.ipa!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.textTheme.bodySmall?.color
                        ?.withValues(alpha: 0.8),
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            // Nút loa duy nhất
            IconButton(
              onPressed: () => onPlayAudio(speedMode),
              constraints: const BoxConstraints(
                minWidth: 44,
                minHeight: 44,
              ),
              icon: Icon(
                Icons.volume_up_outlined,
                size: 20,
                color: theme.colorScheme.primary,
              ),
              tooltip: 'Phát âm',
            ),
            const SizedBox(width: 4),
            // Chip chế độ 1x/0.75x
            ConstrainedBox(
              constraints: const BoxConstraints(
                minWidth: 44,
                minHeight: 44,
              ),
              child: Tooltip(
                message: 'Đổi tốc độ',
                child: InkWell(
                  onTap: () {
                    final next = toggleSpeed(speedMode);
                    onSpeedModeChanged?.call(next);
                    onPlayAudio(next);
                  },
                  borderRadius: BorderRadius.circular(6),
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: theme.colorScheme.primary
                              .withValues(alpha: 0.35),
                        ),
                      ),
                      child: Text(
                        speedMode == 1.0 ? '1x' : '0.75x',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: theme.colorScheme.primary,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),

        // 3. Nghĩa theo ngữ cảnh
        Text(
          occurrence.vi,
          style: theme.textTheme.titleMedium?.copyWith(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: theme.colorScheme.onSurface,
          ),
        ),

        // 4. Định nghĩa tiếng Anh (ẩn nếu compact hoặc null/rỗng)
        if (!isCompact &&
            entry.definitionEn != null &&
            entry.definitionEn!.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            entry.definitionEn!,
            style: theme.textTheme.bodySmall?.copyWith(
              fontSize: 13,
              height: 1.4,
              fontStyle: FontStyle.italic,
              color: theme.textTheme.bodySmall?.color?.withValues(alpha: 0.85),
            ),
          ),
        ],

        // 5. Câu gốc + Ví dụ mới (ẩn nếu compact)
        if (!isCompact) ...[
          const SizedBox(height: 10),
          // 5a. Câu gốc
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: theme.colorScheme.surface.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: theme.dividerColor.withValues(alpha: 0.08),
              ),
            ),
            child: Text.rich(
              TextSpan(
                style: theme.textTheme.bodySmall?.copyWith(
                  fontSize: 13,
                  height: 1.4,
                  fontStyle: FontStyle.italic,
                ),
                children: [
                  TextSpan(text: '"${occurrence.cloze.textBefore}'),
                  TextSpan(
                    text: occurrence.cloze.answer,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  TextSpan(text: '${occurrence.cloze.textAfter}"'),
                ],
              ),
            ),
          ),
          // 5b. Ví dụ mới (nếu có)
          if (entry.extraExample != null &&
              entry.extraExample!.isNotEmpty) ...[
            const SizedBox(height: 8),
            _buildExtraExampleText(
              entry.extraExample!,
              entry.canonicalForm,
              theme,
            ),
          ],
        ],

        const SizedBox(height: 12),

        // 6. Nút Lưu
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            OutlinedButton.icon(
              onPressed: onSave,
              icon: Icon(
                isSaved ? Icons.bookmark : Icons.bookmark_border_outlined,
                size: 16,
              ),
              label: Text(isSaved ? 'Đã lưu' : 'Lưu'),
              style: OutlinedButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

