class Token {
  final int i;
  final String text;
  final String ws;
  final String lemma;
  final String pos;
  final bool isWord;
  final bool isFn;
  final String? vi;
  final String? ipa;

  const Token({
    required this.i,
    required this.text,
    required this.ws,
    required this.lemma,
    required this.pos,
    required this.isWord,
    required this.isFn,
    this.vi,
    this.ipa,
  });

  factory Token.fromJson(Map<String, dynamic> json) {
    if (json['i'] == null ||
        json['text'] == null ||
        json['ws'] == null ||
        json['lemma'] == null ||
        json['pos'] == null ||
        json['is_word'] == null ||
        json['is_fn'] == null) {
      throw FormatException('Token missing required fields: $json');
    }
    return Token(
      i: json['i'] as int,
      text: json['text'] as String,
      ws: json['ws'] as String,
      lemma: json['lemma'] as String,
      pos: json['pos'] as String,
      isWord: json['is_word'] as bool,
      isFn: json['is_fn'] as bool,
      vi: json['vi'] as String?,
      ipa: json['ipa'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'i': i,
        'text': text,
        'ws': ws,
        'lemma': lemma,
        'pos': pos,
        'is_word': isWord,
        'is_fn': isFn,
        'vi': vi,
        if (ipa != null) 'ipa': ipa,
      };
}

class KeyIdea {
  final String text;
  final List<Token> tokens;

  const KeyIdea({
    required this.text,
    required this.tokens,
  });

  factory KeyIdea.fromJson(Map<String, dynamic> json) {
    if (json['text'] == null || json['tokens'] == null) {
      throw FormatException('KeyIdea missing required fields: $json');
    }
    return KeyIdea(
      text: json['text'] as String,
      tokens: (json['tokens'] as List<dynamic>)
          .map((e) => Token.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'text': text,
        'tokens': tokens.map((e) => e.toJson()).toList(),
      };
}

class QuickCheck {
  final String question;
  final List<String> options;
  final int answerIndex;
  final String explanation;

  const QuickCheck({
    required this.question,
    required this.options,
    required this.answerIndex,
    required this.explanation,
  });

  factory QuickCheck.fromJson(Map<String, dynamic> json) {
    if (json['question'] == null ||
        json['options'] == null ||
        json['answer_index'] == null ||
        json['explanation'] == null) {
      throw FormatException('QuickCheck missing required fields: $json');
    }
    return QuickCheck(
      question: json['question'] as String,
      options: (json['options'] as List<dynamic>).map((e) => e as String).toList(),
      answerIndex: json['answer_index'] as int,
      explanation: json['explanation'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'question': question,
        'options': options,
        'answer_index': answerIndex,
        'explanation': explanation,
      };
}

class Section {
  final String id;
  final int orderIndex;
  final String title;
  final String iconHint;
  final List<Token> tokens;
  final KeyIdea keyIdea;
  final QuickCheck? check;

  const Section({
    required this.id,
    required this.orderIndex,
    required this.title,
    required this.iconHint,
    required this.tokens,
    required this.keyIdea,
    this.check,
  });

  factory Section.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['order_index'] == null ||
        json['title'] == null ||
        json['icon_hint'] == null ||
        json['tokens'] == null ||
        json['key_idea'] == null) {
      throw FormatException('Section missing required fields: $json');
    }
    return Section(
      id: json['id'] as String,
      orderIndex: json['order_index'] as int,
      title: json['title'] as String,
      iconHint: json['icon_hint'] as String,
      tokens: (json['tokens'] as List<dynamic>)
          .map((e) => Token.fromJson(e as Map<String, dynamic>))
          .toList(),
      keyIdea: KeyIdea.fromJson(json['key_idea'] as Map<String, dynamic>),
      check: json['check'] != null
          ? QuickCheck.fromJson(json['check'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'order_index': orderIndex,
        'title': title,
        'icon_hint': iconHint,
        'tokens': tokens.map((e) => e.toJson()).toList(),
        'key_idea': keyIdea.toJson(),
        if (check != null) 'check': check!.toJson(),
      };
}

class ArticleSource {
  final String name;
  final bool isGraded;

  const ArticleSource({
    required this.name,
    required this.isGraded,
  });

  factory ArticleSource.fromJson(Map<String, dynamic> json) {
    if (json['name'] == null || json['is_graded'] == null) {
      throw FormatException('ArticleSource missing required fields: $json');
    }
    return ArticleSource(
      name: json['name'] as String,
      isGraded: json['is_graded'] as bool,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'is_graded': isGraded,
      };
}

class ArticleMeta {
  final String id;
  final String title;
  final String category;
  final String cefrLevel;
  final ArticleSource source;
  final int wordCount;
  final int sectionCount;

  const ArticleMeta({
    required this.id,
    required this.title,
    required this.category,
    required this.cefrLevel,
    required this.source,
    required this.wordCount,
    required this.sectionCount,
  });

  factory ArticleMeta.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['title'] == null ||
        json['category'] == null ||
        json['cefr_level'] == null ||
        json['source'] == null ||
        json['word_count'] == null ||
        json['section_count'] == null) {
      throw FormatException('ArticleMeta missing required fields: $json');
    }
    return ArticleMeta(
      id: json['id'] as String,
      title: json['title'] as String,
      category: json['category'] as String,
      cefrLevel: json['cefr_level'] as String,
      source: ArticleSource.fromJson(json['source'] as Map<String, dynamic>),
      wordCount: json['word_count'] as int,
      sectionCount: json['section_count'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'category': category,
        'cefr_level': cefrLevel,
        'source': source.toJson(),
        'word_count': wordCount,
        'section_count': sectionCount,
      };
}

class LexiconEntry {
  final String id;
  final String canonicalForm;
  final String lemmaKey;
  final String type; // 'single_word' | 'collocation'
  final String pos;
  final String cefrLevel;
  final String? ipa;
  final String? definitionEn;
  final String? extraExample;
  final String? audioUrl;

  const LexiconEntry({
    required this.id,
    required this.canonicalForm,
    required this.lemmaKey,
    required this.type,
    required this.pos,
    required this.cefrLevel,
    this.ipa,
    this.definitionEn,
    this.extraExample,
    this.audioUrl,
  });

  factory LexiconEntry.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['canonical_form'] == null ||
        json['lemma_key'] == null ||
        json['type'] == null ||
        json['pos'] == null ||
        json['cefr_level'] == null) {
      throw FormatException('LexiconEntry missing required fields: $json');
    }
    return LexiconEntry(
      id: json['id'] as String,
      canonicalForm: json['canonical_form'] as String,
      lemmaKey: json['lemma_key'] as String,
      type: json['type'] as String,
      pos: json['pos'] as String,
      cefrLevel: json['cefr_level'] as String,
      ipa: json['ipa'] as String?,
      definitionEn: json['definition_en'] as String?,
      extraExample: json['extra_example'] as String?,
      audioUrl: json['audio_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'canonical_form': canonicalForm,
        'lemma_key': lemmaKey,
        'type': type,
        'pos': pos,
        'cefr_level': cefrLevel,
        'ipa': ipa,
        'definition_en': definitionEn,
        'extra_example': extraExample,
        'audio_url': audioUrl,
      };
}

class Cloze {
  final String textBefore;
  final String answer;
  final String textAfter;

  const Cloze({
    required this.textBefore,
    required this.answer,
    required this.textAfter,
  });

  factory Cloze.fromJson(Map<String, dynamic> json) {
    if (json['text_before'] == null ||
        json['answer'] == null ||
        json['text_after'] == null) {
      throw FormatException('Cloze missing required fields: $json');
    }
    return Cloze(
      textBefore: json['text_before'] as String,
      answer: json['answer'] as String,
      textAfter: json['text_after'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'text_before': textBefore,
        'answer': answer,
        'text_after': textAfter,
      };
}

class Occurrence {
  final String id;
  final String lexiconEntryId;
  final String sectionId;
  final int tokenStart;
  final int tokenEnd; // inclusive
  final String vi;
  final String exampleSentence;
  final Cloze cloze;

  const Occurrence({
    required this.id,
    required this.lexiconEntryId,
    required this.sectionId,
    required this.tokenStart,
    required this.tokenEnd,
    required this.vi,
    required this.exampleSentence,
    required this.cloze,
  });

  factory Occurrence.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['lexicon_entry_id'] == null ||
        json['section_id'] == null ||
        json['token_start'] == null ||
        json['token_end'] == null ||
        json['vi'] == null ||
        json['example_sentence'] == null ||
        json['cloze'] == null) {
      throw FormatException('Occurrence missing required fields: $json');
    }
    return Occurrence(
      id: json['id'] as String,
      lexiconEntryId: json['lexicon_entry_id'] as String,
      sectionId: json['section_id'] as String,
      tokenStart: json['token_start'] as int,
      tokenEnd: json['token_end'] as int,
      vi: json['vi'] as String,
      exampleSentence: json['example_sentence'] as String,
      cloze: Cloze.fromJson(json['cloze'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'lexicon_entry_id': lexiconEntryId,
        'section_id': sectionId,
        'token_start': tokenStart,
        'token_end': tokenEnd,
        'vi': vi,
        'example_sentence': exampleSentence,
        'cloze': cloze.toJson(),
      };
}

class QuizItem {
  final String id;
  final String type; // 'true_false' | 'multiple_choice' | 'true_false_ng'
  final String question;
  final List<String> options;
  final int answerIndex;
  final String explanation;

  const QuizItem({
    required this.id,
    required this.type,
    required this.question,
    required this.options,
    required this.answerIndex,
    required this.explanation,
  });

  factory QuizItem.fromJson(Map<String, dynamic> json) {
    if (json['id'] == null ||
        json['type'] == null ||
        json['question'] == null ||
        json['options'] == null ||
        json['answer_index'] == null ||
        json['explanation'] == null) {
      throw FormatException('QuizItem missing required fields: $json');
    }
    return QuizItem(
      id: json['id'] as String,
      type: json['type'] as String,
      question: json['question'] as String,
      options: (json['options'] as List<dynamic>).map((e) => e as String).toList(),
      answerIndex: json['answer_index'] as int,
      explanation: json['explanation'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'question': question,
        'options': options,
        'answer_index': answerIndex,
        'explanation': explanation,
      };
}

class ArticleBundle {
  final String contractVersion;
  final ArticleMeta article;
  final List<Section> sections;
  final List<LexiconEntry> lexicon;
  final List<Occurrence> occurrences;
  final List<QuizItem> quiz;

  const ArticleBundle({
    required this.contractVersion,
    required this.article,
    required this.sections,
    required this.lexicon,
    required this.occurrences,
    required this.quiz,
  });

  factory ArticleBundle.fromJson(Map<String, dynamic> json) {
    if (json['contract_version'] == null ||
        json['article'] == null ||
        json['sections'] == null ||
        json['lexicon'] == null ||
        json['occurrences'] == null) {
      throw FormatException('ArticleBundle missing required fields: $json');
    }
    return ArticleBundle(
      contractVersion: json['contract_version'] as String,
      article: ArticleMeta.fromJson(json['article'] as Map<String, dynamic>),
      sections: (json['sections'] as List<dynamic>)
          .map((e) => Section.fromJson(e as Map<String, dynamic>))
          .toList(),
      lexicon: (json['lexicon'] as List<dynamic>)
          .map((e) => LexiconEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      occurrences: (json['occurrences'] as List<dynamic>)
          .map((e) => Occurrence.fromJson(e as Map<String, dynamic>))
          .toList(),
      quiz: json['quiz'] != null
          ? (json['quiz'] as List<dynamic>)
              .map((e) => QuizItem.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'contract_version': contractVersion,
        'article': article.toJson(),
        'sections': sections.map((e) => e.toJson()).toList(),
        'lexicon': lexicon.map((e) => e.toJson()).toList(),
        'occurrences': occurrences.map((e) => e.toJson()).toList(),
        'quiz': quiz.map((e) => e.toJson()).toList(),
      };
}

