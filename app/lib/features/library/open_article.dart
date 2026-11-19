import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/providers/local_providers.dart';

/// Mở màn đọc bài và làm mới tiến trình đọc sau khi người dùng quay lại.
/// Dùng chung cho Tab Bài báo, Tab Trang chủ và Màn Lịch sử đọc ([R-FE-07b] (b)).
Future<void> openArticle(
  BuildContext context,
  WidgetRef ref,
  String articleId,
) async {
  await context.push('/read/$articleId');
  if (context.mounted) {
    ref.invalidate(progressByArticleProvider);
  }
}
