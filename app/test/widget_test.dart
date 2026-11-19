import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/app.dart';

void main() {
  testWidgets('App renders Shell with HomeScreen and navigates properly',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: ReadleApp(),
      ),
    );
    await tester.pumpAndSettle();

    // Verify Readle title on HomeScreen & 4 bottom tabs
    expect(find.text('Readle'), findsOneWidget);
    expect(find.text('Chào bạn, hôm nay muốn đọc gì?'), findsOneWidget);
    expect(find.text('Xem tất cả'), findsOneWidget);
    expect(find.text('Trang chủ'), findsOneWidget);
    expect(find.text('Bài báo'), findsOneWidget);
    expect(find.text('Đã lưu'), findsOneWidget);
    expect(find.text('Hồ sơ'), findsOneWidget);

    // Tap on 'Xem tất cả' button to go to news screen
    await tester.tap(find.text('Xem tất cả'));
    await tester.pumpAndSettle();

    // Verify NewsScreen is displayed with Eating Well article
    expect(find.text('Bài báo'), findsAtLeastNWidgets(1));
    expect(find.text('Eating Well'), findsOneWidget);

    // Tap on Eating Well article card
    await tester.tap(find.text('Eating Well'));
    await tester.pumpAndSettle();

    // Verify ReaderScreen is displayed with article content
    expect(find.text('Key idea'), findsOneWidget);
    expect(find.text('Eating well'), findsOneWidget);
  });
}
