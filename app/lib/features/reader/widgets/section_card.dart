import 'package:flutter/material.dart';

import '../../../data/models/article_bundle.dart';
import '../models/highlight_kind.dart';
import 'token_text_view.dart';

class SectionCard extends StatelessWidget {
  final Section section;
  final Map<int, HighlightKind> highlights;
  final OnTokenTap? onTokenTap;

  const SectionCard({
    super.key,
    required this.section,
    required this.highlights,
    this.onTokenTap,
  });

  IconData _getIconData(String hint) {
    switch (hint.toLowerCase().trim()) {
      case 'salad':
        return Icons.restaurant;
      case 'broccoli':
        return Icons.eco_outlined;
      case 'apple':
      case 'fruit':
        return Icons.apple;
      case 'water':
        return Icons.water_drop_outlined;
      case 'heart':
        return Icons.favorite_border;
      default:
        return Icons.menu_book_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header: Icon + Section Title
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: isDark
                          ? Colors.white.withValues(alpha: 0.05)
                          : Colors.black.withValues(alpha: 0.04),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      _getIconData(section.iconHint),
                      size: 22,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      section.title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Key Idea Box
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: isDark
                      ? Colors.white.withValues(alpha: 0.04)
                      : const Color(0xFFEFE8D0), // Nền kem sáng nhạt hòa cùng bản sắc
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.06)
                        : Colors.black.withValues(alpha: 0.05),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.lightbulb_outline,
                          size: 16,
                          color: theme.colorScheme.primary.withValues(alpha: 0.8),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'Key idea',
                          style: theme.textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.5,
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TokenTextView(
                      tokens: section.keyIdea.tokens,
                      highlights: const {},
                      onTokenTap: onTokenTap,
                      inKeyIdea: true,
                      baseStyle: theme.textTheme.bodyMedium?.copyWith(
                        fontSize: 15,
                        height: 1.5,
                        color: theme.colorScheme.onSurface.withValues(alpha: 0.9),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),

              // Thân bài (Body text render từ tokens)
              TokenTextView(
                tokens: section.tokens,
                highlights: highlights,
                onTokenTap: onTokenTap,
                inKeyIdea: false,
                baseStyle: theme.textTheme.bodyLarge?.copyWith(
                  fontSize: 17,
                  height: 1.7,
                  color: theme.colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
