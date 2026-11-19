import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../data/models/article_card.dart';
import '../../../data/models/local_models.dart';
import 'category_style.dart';

/// Thẻ bài báo dạng khối màu theo chủ đề (ADR-020 mục 5 & FE-07b).
/// Tuân thủ nguyên tắc no-pressure UX: CEFR trung tính, không hiện %, không hiện "Chưa đọc".
class ArticleTile extends StatelessWidget {
  final ArticleCard card;
  final ReadingProgress? progress;
  final VoidCallback? onTap;

  const ArticleTile({
    super.key,
    required this.card,
    this.progress,
    this.onTap,
  });

  static int estimateReadingMinutes(int wordCount) {
    return math.max(1, (wordCount / 150).round());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = categoryStyle(card.category, theme.brightness);
    final minutes = estimateReadingMinutes(card.wordCount);
    final secondaryColor =
        theme.textTheme.bodySmall?.color ?? theme.colorScheme.onSurfaceVariant;
    final p = progress;

    final String statusText;
    if (p == null) {
      statusText = '';
    } else if (p.completed) {
      statusText = ', Đã đọc';
    } else {
      statusText = ', Đang đọc';
    }

    final semanticLabel =
        '${card.title}, ${card.category}, ${card.cefrLevel}, khoảng $minutes phút đọc$statusText';

    return Semantics(
      button: true,
      excludeSemantics: true,
      label: semanticLabel,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(4.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              // Khối màu chủ đề bo góc 16, cao 120dp, icon lớn ở giữa
              Container(
                key: ValueKey('article_cover_${card.id}'),
                height: 120,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: style.bg,
                  borderRadius: BorderRadius.circular(16),
                ),
                alignment: Alignment.center,
                child: Icon(
                  style.icon,
                  size: 44,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.75),
                ),
              ),
              const SizedBox(height: 10),

              // Dòng phụ: category
              Text(
                card.category,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: secondaryColor,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 4),

              // Tiêu đề: đậm, tối đa 2 dòng
              Text(
                card.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 8),

              // Dòng meta: CEFR · ~N phút đọc [· Đã đọc / Đang đọc]
              Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 6,
                runSpacing: 4,
                children: [
                  // Chip CEFR viền mảnh màu trung tính
                  DecoratedBox(
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: secondaryColor.withValues(alpha: 0.4),
                      ),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      child: Text(
                        card.cefrLevel,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: secondaryColor,
                        ),
                      ),
                    ),
                  ),
                  Text(
                    '·',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: secondaryColor,
                    ),
                  ),
                  Text(
                    '~$minutes phút đọc',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: secondaryColor,
                    ),
                  ),
                  if (p != null) ...[
                    Text(
                      '·',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: secondaryColor,
                      ),
                    ),
                    if (p.completed)
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.check_circle_outline,
                            size: 14,
                            color: secondaryColor,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Đã đọc',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: secondaryColor,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      )
                    else
                      Text(
                        'Đang đọc',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: secondaryColor,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
