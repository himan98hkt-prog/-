-- PianoEvent AI · Supabase 스키마
-- Supabase 대시보드 → SQL Editor 에 그대로 붙여넣어 실행합니다.
-- 재실행해도 안전하도록 IF NOT EXISTS / DROP POLICY IF EXISTS 를 사용합니다.

create extension if not exists "pgcrypto";

-- ────────────────────────────────────────────────────────────
-- 1. 학원
-- ────────────────────────────────────────────────────────────
create table if not exists public.academies (
  id            uuid primary key default gen_random_uuid(),
  -- Supabase Auth 를 붙이면 원장 계정과 연결된다. MVP(쿠키 세션)에서는 null 이다.
  owner_id      uuid references auth.users(id) on delete cascade,
  name          text        not null default '내 피아노학원',
  director_name text        not null default '원장',
  logo_url      text,
  theme_color   text        not null default '#1f2a44',
  created_at    timestamptz not null default now()
);

create index if not exists academies_owner_idx on public.academies(owner_id);

-- ────────────────────────────────────────────────────────────
-- 2. 행사 (연주회 / 시즌 특강)
-- ────────────────────────────────────────────────────────────
do $$ begin
  create type public.event_type   as enum ('recital', 'season');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.event_status as enum ('draft', 'ready', 'published', 'done');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.season_theme as enum ('halloween', 'christmas', 'vacation');
exception when duplicate_object then null; end $$;

create table if not exists public.events (
  id                   uuid primary key default gen_random_uuid(),
  academy_id           uuid not null references public.academies(id) on delete cascade,
  title                text not null,
  type                 public.event_type   not null default 'recital',
  status               public.event_status not null default 'draft',
  theme                public.season_theme,
  event_at             timestamptz not null,
  venue                text not null default '',
  greeting             text,
  mc_opening           text,
  mc_closing           text,
  program_source       text check (program_source in ('ai', 'rule')),
  program_generated_at timestamptz,
  created_at           timestamptz not null default now()
);

create index if not exists events_academy_idx on public.events(academy_id, event_at desc);

-- ────────────────────────────────────────────────────────────
-- 3. 연주 학생 (순서표의 한 줄)
-- ────────────────────────────────────────────────────────────
do $$ begin
  create type public.student_level as enum ('beginner', 'intermediate', 'advanced', 'ensemble');
exception when duplicate_object then null; end $$;

create table if not exists public.event_students (
  id           uuid primary key default gen_random_uuid(),
  event_id     uuid not null references public.events(id) on delete cascade,
  student_name text not null,
  piece_title  text not null default '',
  composer     text not null default '',
  duration_sec integer not null default 120 check (duration_sec > 0 and duration_sec <= 3600),
  level        public.student_level not null default 'beginner',
  order_no     integer,
  mc_script    text,
  note         text,
  created_at   timestamptz not null default now()
);

create index if not exists event_students_event_idx on public.event_students(event_id, order_no nulls last, created_at);

-- ────────────────────────────────────────────────────────────
-- 4. 참석 회신 (학부모)
-- ────────────────────────────────────────────────────────────
create table if not exists public.rsvps (
  id           uuid primary key default gen_random_uuid(),
  event_id     uuid not null references public.events(id) on delete cascade,
  parent_name  text not null,
  student_name text not null,
  headcount    integer not null default 1 check (headcount >= 0 and headcount <= 20),
  message      text,
  attending    boolean not null default true,
  created_at   timestamptz not null default now()
);

create index if not exists rsvps_event_idx on public.rsvps(event_id, created_at desc);

-- ────────────────────────────────────────────────────────────
-- 5. 행 수준 보안 (RLS)
--    서버(API Route)는 service_role 키로 RLS 를 우회한다.
--    아래 정책은 브라우저가 anon 키로 직접 접근할 때 적용된다.
-- ────────────────────────────────────────────────────────────
alter table public.academies      enable row level security;
alter table public.events         enable row level security;
alter table public.event_students enable row level security;
alter table public.rsvps          enable row level security;

-- 학원: 소유자만 전부
drop policy if exists academies_owner_all on public.academies;
create policy academies_owner_all on public.academies
  for all using (owner_id = auth.uid()) with check (owner_id = auth.uid());

-- 행사: 내 학원의 행사만
drop policy if exists events_owner_all on public.events;
create policy events_owner_all on public.events
  for all using (
    exists (select 1 from public.academies a where a.id = events.academy_id and a.owner_id = auth.uid())
  ) with check (
    exists (select 1 from public.academies a where a.id = events.academy_id and a.owner_id = auth.uid())
  );

-- 행사: 배포된 행사는 초대장에서 읽을 수 있어야 한다 (제목·일시·장소만 노출 목적)
drop policy if exists events_public_read on public.events;
create policy events_public_read on public.events
  for select using (status in ('published', 'ready'));

-- 학생: 내 학원의 행사에 속한 학생만
drop policy if exists event_students_owner_all on public.event_students;
create policy event_students_owner_all on public.event_students
  for all using (
    exists (
      select 1 from public.events e
      join public.academies a on a.id = e.academy_id
      where e.id = event_students.event_id and a.owner_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.events e
      join public.academies a on a.id = e.academy_id
      where e.id = event_students.event_id and a.owner_id = auth.uid()
    )
  );

-- 학생: 배포된 행사의 순서표는 초대장에서 읽힌다 (사회자 대본은 뷰에서 제외해 노출하지 않는다)
drop policy if exists event_students_public_read on public.event_students;
create policy event_students_public_read on public.event_students
  for select using (
    exists (select 1 from public.events e where e.id = event_students.event_id and e.status = 'published')
  );

-- 참석 회신: 학부모는 배포된 행사에 대해 "쓰기만" 할 수 있고, 읽기는 원장만 가능하다
drop policy if exists rsvps_public_insert on public.rsvps;
create policy rsvps_public_insert on public.rsvps
  for insert with check (
    exists (select 1 from public.events e where e.id = rsvps.event_id and e.status in ('ready', 'published'))
  );

drop policy if exists rsvps_owner_read on public.rsvps;
create policy rsvps_owner_read on public.rsvps
  for all using (
    exists (
      select 1 from public.events e
      join public.academies a on a.id = e.academy_id
      where e.id = rsvps.event_id and a.owner_id = auth.uid()
    )
  );

-- ────────────────────────────────────────────────────────────
-- 6. 계정 삭제 (Google Play 계정 삭제 요건)
--    로그인한 사용자가 자기 계정과 모든 데이터를 스스로 지운다.
-- ────────────────────────────────────────────────────────────
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.uid() is null then
    raise exception '로그인이 필요합니다.';
  end if;

  -- events → event_students / rsvps 는 on delete cascade 로 함께 삭제된다
  delete from public.academies where owner_id = auth.uid();
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public;
grant execute on function public.delete_my_account() to authenticated;

-- ────────────────────────────────────────────────────────────
-- 7. 실시간 참석 집계 (선택)
-- ────────────────────────────────────────────────────────────
do $$ begin
  alter publication supabase_realtime add table public.rsvps;
exception when duplicate_object then null; end $$;
