import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../data/models/article_bundle.dart';
import '../models/highlight_kind.dart';

typedef OnTokenTap = void Function(
  Token token, {
  required Offset position,
  bool inKeyIdea,
});

class TokenTextView extends StatefulWidget {
  final List<Token> tokens;
  final Map<int, HighlightKind> highlights;
  final OnTokenTap? onTokenTap;
  final TextStyle? baseStyle;
  final bool inKeyIdea;

  const TokenTextView({
    super.key,
    required this.tokens,
    this.highlights = const {},
    this.onTokenTap,
    this.baseStyle,
    this.inKeyIdea = false,
  });

  @override
  State<TokenTextView> createState() => _TokenTextViewState();
}

class _TokenTextViewState extends State<TokenTextView> {
  final Map<int, TapGestureRecognizer> _recognizers = {};

  @override
  void initState() {
    super.initState();
    _initRecognizers();
  }

  @override
  void didUpdateWidget(covariant TokenTextView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tokens != widget.tokens ||
        oldWidget.onTokenTap != widget.onTokenTap ||
        oldWidget.inKeyIdea != widget.inKeyIdea) {
      _disposeRecognizers();
      _initRecognizers();
    }
  }

  @override
  void dispose() {
    _disposeRecognizers();
    super.dispose();
  }

  void _initRecognizers() {
    for (final token in widget.tokens) {
      if (token.isWord && widget.onTokenTap != null) {
        final recognizer = TapGestureRecognizer()
          ..onTapUp = (details) => widget.onTokenTap!(
                token,
                position: details.globalPosition,
                inKeyIdea: widget.inKeyIdea,
              );
        _recognizers[token.i] = recognizer;
      }
    }
  }

  void _disposeRecognizers() {
    for (final recognizer in _recognizers.values) {
      recognizer.dispose();
    }
    _recognizers.clear();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final highlightColors =
        theme.extension<HighlightColors>() ?? HighlightColors.light;

    final defaultStyle = widget.baseStyle ??
        theme.textTheme.bodyLarge?.copyWith(
          fontSize: 18,
          height: 1.7,
          color: theme.colorScheme.onSurface,
        ) ??
        const TextStyle(fontSize: 18, height: 1.7);

    final List<InlineSpan> spans = [];

    for (int idx = 0; idx < widget.tokens.length; idx++) {
      final token = widget.tokens[idx];
      TapGestureRecognizer? recognizer;
      if (token.isWord && widget.onTokenTap != null) {
        recognizer = _recognizers[token.i];
      }

      final kind = widget.highlights[token.i] ?? HighlightKind.none;
      TextStyle tokenStyle = defaultStyle;

      switch (kind) {
        case HighlightKind.collocation:
          tokenStyle = tokenStyle.copyWith(
            backgroundColor: highlightColors.collocationBg,
            decoration: TextDecoration.underline,
            decorationStyle: TextDecorationStyle.dotted,
            decorationColor: highlightColors.collocationUnderline,
            decorationThickness: 2.0,
          );
          break;
        case HighlightKind.singleWord:
          tokenStyle = tokenStyle.copyWith(
            backgroundColor: highlightColors.singleWordBg,
          );
          break;
        case HighlightKind.none:
          break;
      }

      spans.add(
        TextSpan(
          text: token.text,
          style: tokenStyle,
          recognizer: recognizer,
        ),
      );

      if (token.ws.isNotEmpty) {
        TextStyle wsStyle = defaultStyle;
        final nextKind = (idx + 1 < widget.tokens.length)
            ? (widget.highlights[widget.tokens[idx + 1].i] ??
                HighlightKind.none)
            : HighlightKind.none;

        // Nếu token hiện tại và token tiếp theo cùng thuộc 1 loại highlight,
        // tô nền khoảng trắng để dải highlight liền mạch
        if (kind != HighlightKind.none && kind == nextKind) {
          if (kind == HighlightKind.collocation) {
            wsStyle = wsStyle.copyWith(
              backgroundColor: highlightColors.collocationBg,
              decoration: TextDecoration.underline,
              decorationStyle: TextDecorationStyle.dotted,
              decorationColor: highlightColors.collocationUnderline,
              decorationThickness: 2.0,
            );
          } else if (kind == HighlightKind.singleWord) {
            wsStyle = wsStyle.copyWith(
              backgroundColor: highlightColors.singleWordBg,
            );
          }
        }

        spans.add(
          TextSpan(
            text: token.ws,
            style: wsStyle,
          ),
        );
      }
    }

    return Text.rich(
      TextSpan(children: spans),
    );
  }
}

