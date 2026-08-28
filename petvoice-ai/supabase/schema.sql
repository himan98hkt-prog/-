-- PetVoice AI · Supabase 스키마
--
-- 원칙
--   1. 사용자가 만든 데이터는 전부 auth.users 를 참조하고 ON DELETE CASCADE 를 건다.
--      → 계정 삭제 한 번으로 연관 데이터가 남김없이 사라진다 (Google Play 요구사항).
--   2. RLS 를 켜고 "본인 행만" 정책을 붙인다. 서비스 롤만 사용량 테이블을 쓴다.

-- 사용량 기록 (서버 기준 무료 3회/일 제한) ---------------------------------
create table if not exists public.usage_log (
  id           bigserial primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  used_on      date not null default (now() at time zone 'utc')::date,
  created_at   timestamptz not null default now()
);

create index if not exists usage_log_user_day_idx on public.usage_log (user_id, used_on);

alter table public.usage_log enable row level security;

-- 사용량은 서버(서비스 롤)만 기록·조회한다. 클라이언트는 접근 불가.
drop policy if exists usage_log_no_client on public.usage_log;
create policy usage_log_no_client on public.usage_log for select using (false);

-- 구독 상태 -----------------------------------------------------------------
create table if not exists public.subscriptions (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  pro         boolean not null default false,
  expires_at  timestamptz,
  store       text,           -- 'play' | 'appstore'
  updated_at  timestamptz not null default now()
);

alter table public.subscriptions enable row level security;

drop policy if exists subscriptions_select_own on public.subscriptions;
create policy subscriptions_select_own on public.subscriptions
  for select using (auth.uid() = user_id);

-- 반려동물 프로필 (기기 간 동기화용 · 선택) ---------------------------------
create table if not exists public.pets (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  pet_type    text not null check (pet_type in ('DOG', 'CAT')),
  breed       text,
  age_months  int,
  created_at  timestamptz not null default now()
);

alter table public.pets enable row level security;

drop policy if exists pets_own on public.pets;
create policy pets_own on public.pets
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 분석 히스토리 (선택 동기화) ------------------------------------------------
create table if not exists public.analyses (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  pet_id       uuid references public.pets(id) on delete cascade,
  media_kind   text not null check (media_kind in ('audio', 'image')),
  context      text,
  result       jsonb not null,
  health_level text not null default 'none' check (health_level in ('none', 'watch', 'vet')),
  created_at   timestamptz not null default now()
);

create index if not exists analyses_user_created_idx on public.analyses (user_id, created_at desc);

alter table public.analyses enable row level security;

drop policy if exists analyses_own on public.analyses;
create policy analyses_own on public.analyses
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 사용량 소비 함수 -----------------------------------------------------------
-- 프로면 무조건 통과, 무료면 오늘 사용량이 한도 미만일 때만 1 소비하고 true.
create or replace function public.consume_quota(p_user_id uuid, p_free_limit int)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_pro   boolean := false;
  v_today date := (now() at time zone 'utc')::date;
  v_used  int;
begin
  select (pro and (expires_at is null or expires_at > now()))
    into v_pro
    from public.subscriptions
   where user_id = p_user_id;

  if coalesce(v_pro, false) then
    insert into public.usage_log (user_id, used_on) values (p_user_id, v_today);
    return true;
  end if;

  select count(*) into v_used
    from public.usage_log
   where user_id = p_user_id and used_on = v_today;

  if v_used >= p_free_limit then
    return false;
  end if;

  insert into public.usage_log (user_id, used_on) values (p_user_id, v_today);
  return true;
end;
$$;

revoke all on function public.consume_quota(uuid, int) from public, anon, authenticated;

-- 오래된 사용량 기록 정리 (pg_cron 을 쓴다면 매일 호출) ----------------------
create or replace function public.prune_usage_log()
returns void
language sql
security definer
set search_path = public
as $$
  delete from public.usage_log where used_on < (now() at time zone 'utc')::date - 60;
$$;
