import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../data/models/article_bundle.dart';

class WordTooltip extends StatelessWidget {
  final Token token;
  final Offset position;
  final bool isSaved;
  final VoidCallback onDismiss;
  final VoidCallback onSpeak;
  final VoidCallback? onSave;
  final VoidCallback? onReportMissing;

  const WordTooltip({
    super.key,
    required this.token,
    required this.position,
    this.isSaved = false,
    required this.onDismiss,
    required this.onSpeak,
    this.onSave,
    this.onReportMissing,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final screenSize = MediaQuery.of(context).size;

    // Tính toán tọa độ hiển thị tooltip: ưu tiên nằm trên từ, nếu quá gần mép trên thì nằm dưới
    const tooltipWidth = 260.0;
    const estimatedHeight = 60.0;

    double top = position.dy - estimatedHeight - 10;
    if (top < 70) {
      top = position.dy + 24;
    }

    double left = (position.dx - tooltipWidth / 2)
        .clamp(16.0, screenSize.width - tooltipWidth - 16.0);

    final bgColor =
        isDark ? AppColors.readerTooltipDark : AppColors.readerTooltipLight;

    final hasIpa = token.ipa != null && token.ipa!.isNotEmpty;
    final lemmaText = token.lemma.toLowerCase();

    return Stack(
      children: [
        // Dùng TapRegion đóng tooltip khi chạm ra ngoài mà KHÔNG nuốt sự kiện chạm của từ khác
        Positioned(
          top: top,
          left: left,
          child: TapRegion(
            onTapOutside: (_) => onDismiss(),
            child: Material(
              color: Colors.transparent,
              child: Container(
                constraints: const BoxConstraints(
                  minWidth: 160,
                  maxWidth: tooltipWidth,
                ),
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.12)
                        : Colors.black.withValues(alpha: 0.08),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color:
                          Colors.black.withValues(alpha: isDark ? 0.4 : 0.12),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Tiêu đề nhỏ: Lemma + IPA (nếu có) + Nút loa
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Flexible(
                          child: Wrap(
                            crossAxisAlignment: WrapCrossAlignment.center,
                            spacing: 4,
                            children: [
                              Text(
                                lemmaText,
                                style: theme.textTheme.labelMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: theme.colorScheme.onSurface,
                                ),
                              ),
                              if (hasIpa)
                                Text(
                                  token.ipa!,
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    fontSize: 11,
                                    fontStyle: FontStyle.italic,
                                    color: theme.textTheme.bodySmall?.color
                                        ?.withValues(alpha: 0.75),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 4),
                        ConstrainedBox(
                          constraints: const BoxConstraints(
                            minWidth: 44,
                            minHeight: 44,
                          ),
                          child: InkWell(
                            key: const Key('tooltip_speaker_button'),
                            onTap: onSpeak,
                            borderRadius: BorderRadius.circular(22),
                            child: Center(
                              child: Icon(
                                Icons.volume_up_outlined,
                                size: 16,
                                color: theme.colorScheme.primary,
                              ),
                            ),
                          ),
                        ),
                        if (onSave != null) ...[
                          const SizedBox(width: 2),
                          Semantics(
                            button: true,
                            label: isSaved ? 'Đã lưu' : 'Lưu',
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(
                                minWidth: 44,
                                minHeight: 44,
                              ),
                              child: InkWell(
                                key: const Key('tooltip_save_button'),
                                onTap: onSave,
                                borderRadius: BorderRadius.circular(22),
                                child: Center(
                                  child: Icon(
                                    isSaved
                                        ? Icons.bookmark
                                        : Icons.bookmark_border_outlined,
                                    size: 18,
                                    color: isSaved
                                        ? theme.colorScheme.primary
                                        : theme.colorScheme.onSurface
                                            .withValues(alpha: 0.7),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),

                    // Nghĩa tiếng Việt
                    if (token.vi != null)
                      Text(
                        token.vi!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w500,
                          fontSize: 13,
                          color: theme.colorScheme.onSurface,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      )
                    else
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Flexible(
                            child: Text(
                              'Chưa có nghĩa',
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontStyle: FontStyle.italic,
                                color: theme.textTheme.bodySmall?.color
                                    ?.withValues(alpha: 0.7),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          GestureDetector(
                            onTap: () {
                              onReportMissing?.call();
                              onDismiss();
                            },
                            child: Text(
                              'Báo thiếu',
                              style: TextStyle(
                                fontSize: 12,
                                color: theme.colorScheme.primary,
                                fontWeight: FontWeight.w600,
                                decoration: TextDecoration.underline,
                              ),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
