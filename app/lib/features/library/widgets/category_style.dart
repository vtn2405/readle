import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';

@immutable
class CategoryStyle {
  final Color bg;
  final IconData icon;

  const CategoryStyle({
    required this.bg,
    required this.icon,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CategoryStyle &&
          runtimeType == other.runtimeType &&
          bg == other.bg &&
          icon == other.icon;

  @override
  int get hashCode => Object.hash(bg, icon);
}

/// Trả về màu nền khối và icon tương ứng với chủ đề bài báo (ADR-020 mục 5).
/// So khớp không phân biệt hoa thường; chủ đề lạ trả về màu trung tính.
CategoryStyle categoryStyle(String category, Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final normalized = category.trim().toLowerCase();

  switch (normalized) {
    case 'health & nutrition':
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryHealthDark
            : AppColors.categoryHealthLight,
        icon: Icons.restaurant_outlined,
      );
    case 'science & technology':
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryScienceDark
            : AppColors.categoryScienceLight,
        icon: Icons.memory_outlined,
      );
    case 'food & farming':
      return CategoryStyle(
        bg: isDark ? AppColors.categoryFoodDark : AppColors.categoryFoodLight,
        icon: Icons.agriculture_outlined,
      );
    case 'energy':
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryEnergyDark
            : AppColors.categoryEnergyLight,
        icon: Icons.bolt_outlined,
      );
    case 'travel & money':
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryTravelDark
            : AppColors.categoryTravelLight,
        icon: Icons.flight_outlined,
      );
    case 'places & culture':
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryPlacesDark
            : AppColors.categoryPlacesLight,
        icon: Icons.account_balance_outlined,
      );
    default:
      return CategoryStyle(
        bg: isDark
            ? AppColors.categoryDefaultDark
            : AppColors.categoryDefaultLight,
        icon: Icons.article_outlined,
      );
  }
}
