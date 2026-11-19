-- BE-04 · Migration khởi tạo — khớp docs/CONTRACTS.md (contract 1.2) mục 2-3.
-- Bảng nội dung: chỉ đọc với app (select cho anon + authenticated), ghi bằng service role (seed, BE-05).
-- Bảng người dùng: RLS user_id = auth.uid(); người dùng ẩn danh có role `authenticated`.

create extension if not exists pgcrypto with schema extensions;

-- ===================================================================
-- NỘI DUNG
-- ===================================================================
create table public.sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null check (type in ('infographic', 'text_article', 'pdf')),
  is_graded boolean not null default false
);

create table public.articles (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_id uuid not null references public.sources (id),
  category text not null,
  cefr_level text not null check (cefr_level in ('A2', 'B1', 'B2')),
  word_count int not null default 0 check (word_count >= 0),
  processing_order int not null,
  created_at timestamptz not null default now()
);

create table public.sections (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references public.articles (id) on delete cascade,
  order_index int not null check (order_index >= 0),
  title text not null,
  icon_hint text not null default '',
  tokens jsonb not null check (jsonb_typeof(tokens) = 'array'),
  key_idea text not null,
  key_idea_tokens jsonb not null check (jsonb_typeof(key_idea_tokens) = 'array'),
  check_data jsonb,  -- JSON trả ra dùng khóa `check` (tránh từ khóa SQL)
  unique (article_id, order_index)
);

create table public.lexicon_entries (
  id uuid primary key default gen_random_uuid(),
  canonical_form text not null,
  lemma_key text not null unique,
  type text not null check (type in ('single_word', 'collocation')),
  pos text not null,
  cefr_level text not null check (cefr_level in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')),
  ipa text,
  definition_en text,
  extra_example text,
  audio_url text
);

create table public.vocabulary_occurrences (
  id uuid primary key default gen_random_uuid(),
  lexicon_entry_id uuid not null references public.lexicon_entries (id),
  article_id uuid not null references public.articles (id) on delete cascade,
  section_id uuid not null references public.sections (id) on delete cascade,
  token_start int not null check (token_start >= 0),
  token_end int not null,
  vi text not null,
  example_sentence text not null,
  cloze jsonb not null,
  check (token_end >= token_start)
);
create index vocabulary_occurrences_article_idx on public.vocabulary_occurrences (article_id);
create index vocabulary_occurrences_lexicon_idx on public.vocabulary_occurrences (lexicon_entry_id);

create table public.quiz_items (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references public.articles (id) on delete cascade,
  order_index int not null default 0,
  type text not null check (type in ('true_false', 'multiple_choice', 'true_false_ng')),
  question text not null,
  options jsonb not null check (jsonb_typeof(options) = 'array'),
  answer_index int not null check (answer_index >= 0),
  explanation text not null
);
create index quiz_items_article_idx on public.quiz_items (article_id);

do $$
declare t text;
begin
  foreach t in array array['sources', 'articles', 'sections', 'lexicon_entries',
                           'vocabulary_occurrences', 'quiz_items'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "content readable" on public.%I for select to anon, authenticated using (true)', t);
    -- Supabase mặc định cấp ALL cho anon/authenticated; nội dung chỉ cần select.
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select on public.%I to anon, authenticated', t);
  end loop;
end $$;

create view public.article_cards with (security_invoker = true) as
select a.id,
       a.title,
       a.category,
       a.cefr_level,
       s.name as source_name,
       a.word_count,
       (select count(*) from public.sections x where x.article_id = a.id)::int as section_count,
       a.processing_order
from public.articles a
join public.sources s on s.id = a.source_id;

revoke all on public.article_cards from anon, authenticated;
grant select on public.article_cards to anon, authenticated;

-- ArticleBundle (CONTRACTS mục 1). security invoker: RLS của bảng gốc vẫn áp dụng.
create or replace function public.get_article_bundle(p_article_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'contract_version', '1.2',
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

revoke all on function public.get_article_bundle(uuid) from public;
grant execute on function public.get_article_bundle(uuid) to anon, authenticated;

-- ===================================================================
-- NGƯỜI DÙNG (RLS user_id = auth.uid())
-- Khóa ngoại sang nội dung dùng `on delete set null` khi có thể để seed lại nội dung
-- không bị chặn và không xóa dữ liệu người dùng (thẻ đã lưu giữ snapshot — ADR-003).
-- ===================================================================
create table public.profiles (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  daily_new_cards int not null default 5 check (daily_new_cards >= 0),
  daily_review_cap int not null default 20 check (daily_review_cap >= 0),
  reminder_enabled boolean not null default false,
  reminder_time time,
  consent_at timestamptz
);

create table public.reading_history (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  article_id uuid not null references public.articles (id) on delete cascade,
  last_read_section_id uuid references public.sections (id) on delete set null,
  progress_percent int not null default 0 check (progress_percent between 0 and 100),
  completed boolean not null default false,
  last_read_at timestamptz not null default now(),
  primary key (user_id, article_id)
);

create table public.user_saved_words (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  lemma_key text not null,
  lexicon_entry_id uuid references public.lexicon_entries (id) on delete set null,
  display_text text not null,
  vi text not null,
  example_sentence text not null,
  cloze jsonb not null,
  source_article_id uuid references public.articles (id) on delete set null,
  saved_at timestamptz not null default now(),
  is_new boolean not null default true,
  first_reviewed_at timestamptz,
  reps int not null default 0,
  interval_days int not null default 0,
  ease real not null default 2.5,
  due_date date not null default current_date,
  unique (user_id, lemma_key)
);
create index user_saved_words_due_idx on public.user_saved_words (user_id, due_date);

create table public.user_quiz_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  article_id uuid not null references public.articles (id) on delete cascade,
  quiz_item_id uuid references public.quiz_items (id) on delete set null,
  section_id uuid references public.sections (id) on delete set null,
  kind text not null check (kind in ('quiz', 'quick_check')),
  chosen_index int not null,
  correct boolean not null,
  answered_at timestamptz not null default now()
);

-- Không khóa ngoại: event phải ghi được kể cả khi nội dung đã đổi.
create table public.usage_events (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid(),
  event_type text not null,
  article_id uuid,
  section_id uuid,
  payload jsonb not null default '{}'::jsonb,
  client_ts timestamptz not null,
  created_at timestamptz not null default now()
);
create index usage_events_type_idx on public.usage_events (event_type, created_at);

do $$
declare t text;
begin
  foreach t in array array['profiles', 'reading_history', 'user_saved_words', 'user_quiz_results'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "own rows" on public.%I for all to authenticated '
                   'using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end $$;

-- usage_events: chỉ insert; không ai đọc qua API (phân tích bằng SQL Editor / service role).
alter table public.usage_events enable row level security;
create policy "insert own events" on public.usage_events
  for insert to authenticated with check (user_id = (select auth.uid()));
revoke all on public.usage_events from anon, authenticated;
grant insert on public.usage_events to authenticated;

-- ===================================================================
-- STORAGE: bucket `audio` đọc công khai qua URL public; chỉ service role ghi.
-- ===================================================================
insert into storage.buckets (id, name, public, allowed_mime_types)
values ('audio', 'audio', true, array['audio/mpeg'])
on conflict (id) do nothing;
