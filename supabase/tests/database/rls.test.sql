-- BE-04 · Test RLS + quyền + get_article_bundle. Chạy: npx supabase test db
-- Mọi thứ nằm trong transaction và rollback ở cuối.
begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(27);

-- ---------- Dữ liệu mẫu (chạy bằng postgres) ----------
insert into auth.users (id, aud, role, is_anonymous) values
  ('00000000-0000-0000-0000-00000000000a', 'authenticated', 'authenticated', true),
  ('00000000-0000-0000-0000-00000000000b', 'authenticated', 'authenticated', true);

insert into sources (id, name, type) values
  ('10000000-0000-0000-0000-000000000001', 'Test Source', 'infographic');
insert into articles (id, title, source_id, category, cefr_level, word_count, processing_order) values
  ('20000000-0000-0000-0000-000000000001', 'Test', '10000000-0000-0000-0000-000000000001', 'Health', 'A2', 3, 1);
-- Chèn section 1 trước section 0 để kiểm sắp xếp theo order_index.
insert into sections (id, article_id, order_index, title, tokens, key_idea, key_idea_tokens) values
  ('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', 1, 'Second', '[]', 'k2', '[]'),
  ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 0, 'First',
   '[{"i":0,"text":"tend","ws":" ","lemma":"tend","pos":"VERB","is_word":true,"is_fn":false,"vi":"có xu hướng","ipa":"/tend/"},
     {"i":1,"text":"to","ws":"","lemma":"to","pos":"PART","is_word":true,"is_fn":true,"vi":"","ipa":"/tuː/"}]',
   'k1', '[]');
insert into lexicon_entries (id, canonical_form, lemma_key, type, pos, cefr_level) values
  ('40000000-0000-0000-0000-000000000001', 'tend to', 'zz_test tend to', 'collocation', 'verb', 'B1');
insert into vocabulary_occurrences (lexicon_entry_id, article_id, section_id, token_start, token_end, vi, example_sentence, cloze) values
  ('40000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
   '30000000-0000-0000-0000-000000000001', 0, 1, 'có xu hướng', 'tend to',
   '{"text_before":"","answer":"tend to","text_after":""}');

-- ---------- 1. get_article_bundle (đọc bằng anon) ----------
set local role anon;
select set_config('request.jwt.claims', '{"role":"anon"}', true);

select is((select count(*)::int from article_cards where id = '20000000-0000-0000-0000-000000000001'), 1, 'anon đọc được article_cards');
select is(get_article_bundle('20000000-0000-0000-0000-000000000001') ->> 'contract_version', '1.4',
          'bundle có contract_version 1.4');
select is(jsonb_path_query_array(get_article_bundle('20000000-0000-0000-0000-000000000001'), '$.sections[*].order_index'),
          '[0, 1]'::jsonb, 'sections sắp theo order_index');
select is((get_article_bundle('20000000-0000-0000-0000-000000000001') -> 'article' ->> 'section_count')::int, 2,
          'section_count đếm đúng');
select is(jsonb_array_length(get_article_bundle('20000000-0000-0000-0000-000000000001') -> 'lexicon'), 1,
          'lexicon chỉ gồm mục từ xuất hiện trong bài');
select ok(get_article_bundle('20000000-0000-0000-0000-000000000001') -> 'sections' -> 0 ? 'check',
          'section có khóa check (null được)');
select is(get_article_bundle('20000000-0000-0000-0000-000000000001') -> 'quiz', '[]'::jsonb, 'quiz rỗng là []');
select is(get_article_bundle('99999999-0000-0000-0000-000000000000'), null, 'bài không tồn tại trả null');

-- ---------- 2. anon không ghi được nội dung, không đụng bảng người dùng ----------
select throws_ok($$ insert into lexicon_entries (canonical_form, lemma_key, type, pos, cefr_level)
                    values ('x', 'x', 'single_word', 'noun', 'A1') $$,
                 '42501', null, 'anon không insert được nội dung');
select throws_ok($$ select * from user_saved_words $$, '42501', null, 'anon không đọc được user_saved_words');
select throws_ok($$ insert into usage_events (event_type, client_ts) values ('x', now()) $$,
                 '42501', null, 'anon không ghi được usage_events');

-- ---------- 3. Người dùng A ----------
set local role authenticated;
select set_config('request.jwt.claims',
                  '{"sub":"00000000-0000-0000-0000-00000000000a","role":"authenticated","is_anonymous":true}', true);

select lives_ok($$ insert into user_saved_words (lemma_key, display_text, vi, example_sentence, cloze)
                   values ('tend to', 'tend to', 'có xu hướng', 'tend to', '{}') $$,
                'A lưu từ (user_id mặc định auth.uid())');
select is((select entry_type from user_saved_words where lemma_key = 'tend to'), 'single_word',
          'entry_type mặc định single_word (1.4)');
select lives_ok($$ insert into user_saved_words (lemma_key, entry_type, lexicon_entry_id, display_text, vi, example_sentence, cloze)
                   values ('zz_test tend to', 'collocation', '40000000-0000-0000-0000-000000000001',
                           'tend to', 'có xu hướng', 'tend to', '{}') $$,
                'A lưu cụm với entry_type collocation (1.4)');
select throws_ok($$ insert into user_saved_words (lemma_key, entry_type, display_text, vi, example_sentence, cloze)
                    values ('bad', 'phrase', 'x', 'x', 'x', '{}') $$,
                 '23514', null, 'entry_type ngoài single_word|collocation bị chặn (1.4)');
select is((select count(*)::int from user_saved_words where entry_type = 'collocation'), 1,
          'A đọc lại được entry_type collocation');
select lives_ok($$ insert into reading_history (article_id, progress_percent)
                   values ('20000000-0000-0000-0000-000000000001', 50) $$, 'A ghi tiến trình đọc');
select lives_ok($$ insert into profiles default values $$, 'A tạo profile');
select lives_ok($$ insert into usage_events (event_type, client_ts, payload)
                   values ('audio_played', now(), '{"source":"item","speed":0.6}') $$, 'A ghi event');
select throws_ok($$ select * from usage_events $$, '42501', null, 'A không đọc được usage_events');
select throws_ok($$ insert into lexicon_entries (canonical_form, lemma_key, type, pos, cefr_level)
                    values ('y', 'y', 'single_word', 'noun', 'A1') $$,
                 '42501', null, 'authenticated không insert được nội dung');

-- ---------- 4. Người dùng B không thấy / không sửa dữ liệu của A ----------
select set_config('request.jwt.claims',
                  '{"sub":"00000000-0000-0000-0000-00000000000b","role":"authenticated","is_anonymous":true}', true);

select is((select count(*)::int from user_saved_words), 0, 'B không thấy từ đã lưu của A');
select is((select count(*)::int from reading_history), 0, 'B không thấy tiến trình của A');

with u as (update user_saved_words set vi = 'hacked' returning 1)
select is((select count(*)::int from u), 0, 'B không sửa được dòng của A');

select throws_ok($$ insert into user_saved_words (user_id, lemma_key, display_text, vi, example_sentence, cloze)
                    values ('00000000-0000-0000-0000-00000000000a', 'x', 'x', 'x', 'x', '{}') $$,
                 '42501', null, 'B không chèn được dòng mang user_id của A');

-- ---------- 5. Kiểm lại bằng postgres: dữ liệu của A vẫn nguyên ----------
reset role;
select is((select count(*)::int from user_saved_words
           where user_id = '00000000-0000-0000-0000-00000000000a' and vi = 'có xu hướng'),
          2, 'dòng của A không bị đổi');
select ok(exists(select 1 from storage.buckets where id = 'audio' and public),
          'bucket audio tồn tại và public');

select * from finish();
rollback;
