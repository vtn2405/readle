import 'package:flutter/material.dart';

@immutable
class HighlightColors extends ThemeExtension<HighlightColors> {
  final Color collocationBg;
  final Color collocationUnderline;
  final Color singleWordBg;
  final Color savedWordDot;

  const HighlightColors({
    required this.collocationBg,
    required this.collocationUnderline,
    required this.singleWordBg,
    required this.savedWordDot,
  });

  static const light = HighlightColors(
    collocationBg: Color(0xFFDEC98D), // Vàng cát đậm trên nền giấy
    collocationUnderline: Color(0xFFA67C2E), // Gạch chân chấm vàng nâu đậm (tương phản 8.7:1)
    singleWordBg: Color(0xFFBCCFD2), // Xanh bụi trầm hòa hợp nền giấy
    savedWordDot: Color(0xFF3E7C43), // Chấm xanh lá đậm (tương phản 3.72:1)
  );

  static const dark = HighlightColors(
    collocationBg: Color(0xFF4A441E), // Vàng tối dịu mắt
    collocationUnderline: Color(0xFFFDD835),
    singleWordBg: Color(0xFF1B3A4B), // Xanh dương tối dịu mắt
    savedWordDot: Color(0xFF66BB6A),
  );

  @override
  ThemeExtension<HighlightColors> copyWith({
    Color? collocationBg,
    Color? collocationUnderline,
    Color? singleWordBg,
    Color? savedWordDot,
  }) {
    return HighlightColors(
      collocationBg: collocationBg ?? this.collocationBg,
      collocationUnderline: collocationUnderline ?? this.collocationUnderline,
      singleWordBg: singleWordBg ?? this.singleWordBg,
      savedWordDot: savedWordDot ?? this.savedWordDot,
    );
  }

  @override
  ThemeExtension<HighlightColors> lerp(
    covariant ThemeExtension<HighlightColors>? other,
    double t,
  ) {
    if (other is! HighlightColors) return this;
    return HighlightColors(
      collocationBg: Color.lerp(collocationBg, other.collocationBg, t)!,
      collocationUnderline:
          Color.lerp(collocationUnderline, other.collocationUnderline, t)!,
      singleWordBg: Color.lerp(singleWordBg, other.singleWordBg, t)!,
      savedWordDot: Color.lerp(savedWordDot, other.savedWordDot, t)!,
    );
  }
}

class AppColors {
  // Shell (Khung trung tính theo ADR-020)
  static const shellBgLight = Color(0xFFFFFFFF);
  static const shellSurfaceLight = Color(0xFFF4F4F5);
  static const shellTextPrimaryLight = Color(0xFF18181B);
  static const shellTextSecondaryLight = Color(0xFF71717A);
  static const shellPrimaryLight = Color(0xFF18181B);

  static const shellBgDark = Color(0xFF121212);
  static const shellSurfaceDark = Color(0xFF1E1E1E);
  static const shellTextPrimaryDark = Color(0xFFEDEDED);
  static const shellTextSecondaryDark = Color(0xFFA1A1AA);
  static const shellPrimaryDark = Color(0xFFEDEDED);

  // Reader (Bảng màu giấy bản sắc theo ADR-020 & ARCHITECTURE mục 4)
  static const readerBgLight = Color(0xFFE8DDBD); // Màu giấy mẫu (Paper tone bản sắc)
  static const readerBgDark = Color(0xFF171310); // Đen pha nâu ấm
  static const readerSurfaceLight = Color(0xFFF2EBD3); // Kem sáng hơn nền 1 nấc (Card/Sheet)
  static const readerSurfaceDark = Color(0xFF241D16); // Đen pha nâu
  static const readerTooltipLight = Color(0xFFFAF6EE); // Nền tooltip sáng tách khỏi card
  static const readerTooltipDark = Color(0xFF3A3128); // Nền tooltip tối tách khỏi card (#241D16)
  static const readerTextPrimaryLight = Color(0xFF2E2A23); // Đen pha nâu ấm (10.5:1 trên giấy)
  static const readerTextSecondaryLight = Color(0xFF6B6250); // Xám ấm cho metadata/CEFR
  static const readerTextPrimaryDark = Color(0xFFE0E0E0);
  static const readerTextSecondaryDark = Color(0xFF9E9E9E);
  static const readerPrimaryLight = Color(0xFF2C3E50);
  static const readerPrimaryDark = Color(0xFFECEFF1);

  // Khối màu theo chủ đề bài báo (ADR-020 mục 5 & FE-07b)
  static const categoryHealthLight = Color(0xFFDCEFD8);
  static const categoryHealthDark = Color(0xFF22352A);
  static const categoryScienceLight = Color(0xFFDCE6F7);
  static const categoryScienceDark = Color(0xFF1F2C42);
  static const categoryFoodLight = Color(0xFFF6E7C8);
  static const categoryFoodDark = Color(0xFF3A3020);
  static const categoryEnergyLight = Color(0xFFE6E0F5);
  static const categoryEnergyDark = Color(0xFF2D2843);
  static const categoryTravelLight = Color(0xFFFBE3D2);
  static const categoryTravelDark = Color(0xFF3E2B20);
  static const categoryPlacesLight = Color(0xFFF6DCE5);
  static const categoryPlacesDark = Color(0xFF3D2632);
  static const categoryDefaultLight = Color(0xFFECECEC);
  static const categoryDefaultDark = Color(0xFF2A2A2A);

  // Backward compatibility aliases cho Reader
  static const bgLight = readerBgLight;
  static const bgDark = readerBgDark;
  static const surfaceLight = readerSurfaceLight;
  static const surfaceDark = readerSurfaceDark;
  static const textPrimaryLight = readerTextPrimaryLight;
  static const textSecondaryLight = readerTextSecondaryLight;
  static const textPrimaryDark = readerTextPrimaryDark;
  static const textSecondaryDark = readerTextSecondaryDark;
  static const primaryLight = readerPrimaryLight;
  static const primaryDark = readerPrimaryDark;
}
