-- Contract 1.3 (ADR-014): chỉ đổi contract_version trả ra; dữ liệu và cấu trúc bundle giữ nguyên.

create or replace function public.get_article_bundle(p_article_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'contract_version', '1.3',
    'article', jsonb_build_object(
      'id', a.id,
      'title', a.title,
      'category', a.category,
      'cefr_level', a.cefr_level,
      'source', jsonb_build_object('name', s.name, 'is_graded', s.is_graded),
      'word_count', a.word_count,
      'section_count', (select count(*) from sections x where x.article_id = a.id)),
    'sections', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', sc.id,
               'order_index', sc.order_index,
               'title', sc.title,
               'icon_hint', sc.icon_hint,
               'tokens', sc.tokens,
               'key_idea', jsonb_build_object('text', sc.key_idea, 'tokens', sc.key_idea_tokens),
               'check', sc.check_data)
             order by sc.order_index)
      from sections sc
      where sc.article_id = a.id), '[]'::jsonb),
    'lexicon', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', le.id,
               'canonical_form', le.canonical_form,
               'lemma_key', le.lemma_key,
               'type', le.type,
               'pos', le.pos,
               'cefr_level', le.cefr_level,
               'ipa', le.ipa,
               'definition_en', le.definition_en,
               'extra_example', le.extra_example,
               'audio_url', le.audio_url)
             order by le.canonical_form)
      from lexicon_entries le
      where le.id in (select o.lexicon_entry_id from vocabulary_occurrences o
                      where o.article_id = a.id)), '[]'::jsonb),
    'occurrences', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', o.id,
               'lexicon_entry_id', o.lexicon_entry_id,
               'section_id', o.section_id,
               'token_start', o.token_start,
               'token_end', o.token_end,
               'vi', o.vi,
               'example_sentence', o.example_sentence,
               'cloze', o.cloze)
             order by sc.order_index, o.token_start, o.token_end desc)
      from vocabulary_occurrences o
      join sections sc on sc.id = o.section_id
      where o.article_id = a.id), '[]'::jsonb),
    'quiz', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', q.id,
               'type', q.type,
               'question', q.question,
               'options', q.options,
               'answer_index', q.answer_index,
               'explanation', q.explanation)
             order by q.order_index)
      from quiz_items q
      where q.article_id = a.id), '[]'::jsonb))
  from articles a
  join sources s on s.id = a.source_id
  where a.id = p_article_id;
$$;
