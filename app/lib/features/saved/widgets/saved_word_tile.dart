import 'package:flutter/material.dart';

import '../../../data/models/local_models.dart';

/// Dòng hiển thị một từ vựng đã lưu trong kho từ Tab Đã lưu (FE-07d).
///
/// - Hiển thị `displayText` (đậm) và nghĩa `vi`.
/// - Chạm vào dòng để mở rộng/thu gọn câu ví dụ in nghiêng.
/// - Nút bookmark (đã lưu, vùng chạm >= 44dp, Semantics 'Bỏ lưu') gọi [onUnsave].
/// - Có ValueKey để giữ trạng thái mở/đóng chính xác khi danh sách thay đổi.
class SavedWordTile extends StatefulWidget {
  final SavedWord word;
  final VoidCallback onUnsave;

  SavedWordTile({
    required this.word,
    required this.onUnsave,
  }) : super(key: ValueKey(word.lemmaKey));

  @override
  State<SavedWordTile> createState() => _SavedWordTileState();
}

class _SavedWordTileState extends State<SavedWordTile> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final word = widget.word;

    return Card(
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 4),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withAlpha(80),
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          setState(() {
            _isExpanded = !_isExpanded;
          });
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          word.displayText,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        if (word.vi.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            word.vi,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Semantics(
                    button: true,
                    label: 'Bỏ lưu',
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(
                        minWidth: 44,
                        minHeight: 44,
                      ),
                      child: IconButton(
                        icon: Icon(
                          Icons.bookmark,
                          color: theme.colorScheme.primary,
                        ),
                        tooltip: 'Bỏ lưu',
                        onPressed: widget.onUnsave,
                      ),
                    ),
                  ),
                ],
              ),
              if (_isExpanded && word.exampleSentence.isNotEmpty) ...[
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: 2),
                  child: Text(
                    word.exampleSentence,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontStyle: FontStyle.italic,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
