import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTheme {
  static const String fontFamily = 'Inter';

  // --- Theme Khung ngoài (Shell): Trung tính, hiện đại (ADR-020) ---

  static ThemeData get lightTheme {
    final colorScheme = ColorScheme.light(
      primary: AppColors.shellPrimaryLight,
      surface: AppColors.shellSurfaceLight,
      onPrimary: Colors.white,
      onSurface: AppColors.shellTextPrimaryLight,
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: fontFamily,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.shellBgLight,
      cardTheme: const CardThemeData(
        color: AppColors.shellSurfaceLight,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.shellBgLight,
        foregroundColor: AppColors.shellTextPrimaryLight,
        elevation: 0,
        centerTitle: false,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.shellBgLight,
        indicatorColor: AppColors.shellSurfaceLight,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.shellTextPrimaryLight,
            );
          }
          return const TextStyle(
            fontSize: 12,
            color: AppColors.shellTextSecondaryLight,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.shellTextPrimaryLight);
          }
          return const IconThemeData(color: AppColors.shellTextSecondaryLight);
        }),
      ),
      textTheme: const TextTheme(
        bodyLarge: TextStyle(color: AppColors.shellTextPrimaryLight),
        bodyMedium: TextStyle(color: AppColors.shellTextPrimaryLight),
        bodySmall: TextStyle(color: AppColors.shellTextSecondaryLight),
        titleLarge: TextStyle(
          color: AppColors.shellTextPrimaryLight,
          fontWeight: FontWeight.bold,
        ),
        titleMedium: TextStyle(color: AppColors.shellTextPrimaryLight),
        titleSmall: TextStyle(color: AppColors.shellTextSecondaryLight),
      ),
    );
  }

  static ThemeData get darkTheme {
    final colorScheme = ColorScheme.dark(
      primary: AppColors.shellPrimaryDark,
      surface: AppColors.shellSurfaceDark,
      onPrimary: Colors.black,
      onSurface: AppColors.shellTextPrimaryDark,
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: fontFamily,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.shellBgDark,
      cardTheme: const CardThemeData(
        color: AppColors.shellSurfaceDark,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.shellBgDark,
        foregroundColor: AppColors.shellTextPrimaryDark,
        elevation: 0,
        centerTitle: false,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.shellBgDark,
        indicatorColor: AppColors.shellSurfaceDark,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.shellTextPrimaryDark,
            );
          }
          return const TextStyle(
            fontSize: 12,
            color: AppColors.shellTextSecondaryDark,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.shellTextPrimaryDark);
          }
          return const IconThemeData(color: AppColors.shellTextSecondaryDark);
        }),
      ),
      textTheme: const TextTheme(
        bodyLarge: TextStyle(color: AppColors.shellTextPrimaryDark),
        bodyMedium: TextStyle(color: AppColors.shellTextPrimaryDark),
        bodySmall: TextStyle(color: AppColors.shellTextSecondaryDark),
        titleLarge: TextStyle(
          color: AppColors.shellTextPrimaryDark,
          fontWeight: FontWeight.bold,
        ),
        titleMedium: TextStyle(color: AppColors.shellTextPrimaryDark),
        titleSmall: TextStyle(color: AppColors.shellTextSecondaryDark),
      ),
    );
  }

  // --- Theme Màn đọc (Reader): Màu giấy bản sắc (ADR-020 & ARCHITECTURE mục 4) ---

  static ThemeData get readerLight {
    final colorScheme = ColorScheme.light(
      primary: AppColors.readerPrimaryLight,
      surface: AppColors.readerSurfaceLight,
      onPrimary: Colors.white,
      onSurface: AppColors.readerTextPrimaryLight,
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: fontFamily,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.readerBgLight,
      cardTheme: const CardThemeData(
        color: AppColors.readerSurfaceLight,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.readerSurfaceLight,
        surfaceTintColor: Colors.transparent,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.readerBgLight,
        foregroundColor: AppColors.readerTextPrimaryLight,
        elevation: 0,
        centerTitle: false,
      ),
      textTheme: const TextTheme(
        bodyLarge: TextStyle(color: AppColors.readerTextPrimaryLight),
        bodyMedium: TextStyle(color: AppColors.readerTextPrimaryLight),
        bodySmall: TextStyle(color: AppColors.readerTextSecondaryLight),
        titleLarge: TextStyle(
          color: AppColors.readerTextPrimaryLight,
          fontWeight: FontWeight.bold,
        ),
        titleMedium: TextStyle(color: AppColors.readerTextPrimaryLight),
        titleSmall: TextStyle(color: AppColors.readerTextSecondaryLight),
      ),
      extensions: const <ThemeExtension<dynamic>>[
        HighlightColors.light,
      ],
    );
  }

  static ThemeData get readerDark {
    final colorScheme = ColorScheme.dark(
      primary: AppColors.readerPrimaryDark,
      surface: AppColors.readerSurfaceDark,
      onPrimary: Colors.black,
      onSurface: AppColors.readerTextPrimaryDark,
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: fontFamily,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.readerBgDark,
      cardTheme: const CardThemeData(
        color: AppColors.readerSurfaceDark,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.readerSurfaceDark,
        surfaceTintColor: Colors.transparent,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.readerBgDark,
        foregroundColor: AppColors.readerTextPrimaryDark,
        elevation: 0,
        centerTitle: false,
      ),
      textTheme: const TextTheme(
        bodyLarge: TextStyle(color: AppColors.readerTextPrimaryDark),
        bodyMedium: TextStyle(color: AppColors.readerTextPrimaryDark),
        bodySmall: TextStyle(color: AppColors.readerTextSecondaryDark),
        titleLarge: TextStyle(
          color: AppColors.readerTextPrimaryDark,
          fontWeight: FontWeight.bold,
        ),
        titleMedium: TextStyle(color: AppColors.readerTextPrimaryDark),
        titleSmall: TextStyle(color: AppColors.readerTextSecondaryDark),
      ),
      extensions: const <ThemeExtension<dynamic>>[
        HighlightColors.dark,
      ],
    );
  }
}
