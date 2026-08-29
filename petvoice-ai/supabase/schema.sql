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
-- 이 테이블이 "누가 프로인가"의 유일한 출처다. 앱이 보내온 값이 아니라
-- verify-purchase / play-rtdn 함수가 스토어에 직접 물어본 결과만 들어온다.
create table if not exists public.subscriptions (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  pro            boolean not null default false,
  state          text not null default 'none'
                 check (state in ('active','grace','on_hold','paused','canceled','expired','pending','none')),
  expires_at     timestamptz,
  auto_renewing  boolean not null default false,
  store          text check (store in ('play','appstore')),
  product_id     text,
  -- Play 의 purchaseToken 또는 App Store 영수증. 계정 간 구독 공유를 막는 열쇠.
  purchase_token text,
  is_test        boolean not null default false,
  updated_at     timestamptz not null default now()
);

-- 이미 만들어진 테이블에도 열이 붙도록 (기존 배포 환경 대응)
alter table public.subscriptions add column if not exists state text not null default 'none';
alter table public.subscriptions add column if not exists auto_renewing boolean not null default false;
alter table public.subscriptions add column if not exists product_id text;
alter table public.subscriptions add column if not exists purchase_token text;
alter table public.subscriptions add column if not exists is_test boolean not null default false;

-- 하나의 영수증은 한 계정에만 묶인다
create unique index if not exists subscriptions_purchase_token_idx
  on public.subscriptions (purchase_token)
  where purchase_token is not null;

alter table public.subscriptions enable row level security;

-- 읽기만 본인에게 허용한다. 쓰기는 서비스 롤(Edge Function)만 —
-- 클라이언트가 pro=true 를 직접 써 넣을 수 있으면 결제 검증이 무의미해진다.
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

-- 분석 히스토리 (프로 백업) --------------------------------------------------
-- id 는 기기에서 만든 값을 그대로 쓴다. 같은 기록을 여러 번 올려도 덮어쓰기만 된다.
-- payload 에는 사진·녹음 경로를 뺀 기록 전체가 들어간다 (미디어는 서버에 저장하지 않는다).
create table if not exists public.analyses (
  id           text primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  pet_id       text,
  health_level text not null default 'none' check (health_level in ('none', 'watch', 'vet')),
  payload      jsonb not null,
  created_at   timestamptz not null default now()
);

create index if not exists analyses_user_created_idx on public.analyses (user_id, created_at desc);

alter table public.analyses enable row level security;

drop policy if exists analyses_own on public.analyses;
create policy analyses_own on public.analyses
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 분석 정확도 피드백 ---------------------------------------------------------
-- "맞아요/아니에요" 를 모아 두면 어떤 상황에서 무엇을 틀리는지 보인다.
-- 프롬프트를 고칠 근거이자, 시간이 갈수록 쌓이는 자산이다.
create table if not exists public.analysis_feedback (
  id          bigserial primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  entry_id    text not null,
  verdict     text not null check (verdict in ('up', 'down')),
  emotion     text,
  context_key text,
  media_kind  text,
  model       text,
  locale      text,
  created_at  timestamptz not null default now()
);

create unique index if not exists analysis_feedback_entry_idx on public.analysis_feedback (user_id, entry_id);

alter table public.analysis_feedback enable row level security;

drop policy if exists analysis_feedback_own on public.analysis_feedback;
create policy analysis_feedback_own on public.analysis_feedback
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 분석 품질 지표 -------------------------------------------------------------
-- 실패율·지연·파싱 실패를 남긴다. 이게 없으면 "어제부터 이상하다"를 아무도 모른다.
-- 개인 식별 정보나 미디어는 넣지 않는다.
create table if not exists public.analysis_metrics (
  id           bigserial primary key,
  occurred_at  timestamptz not null default now(),
  model        text,
  media_kind   text,
  outcome      text not null check (outcome in ('ok', 'upstream_error', 'empty', 'quota', 'invalid')),
  latency_ms   int,
  status_code  int
);

create index if not exists analysis_metrics_time_idx on public.analysis_metrics (occurred_at desc);

alter table public.analysis_metrics enable row level security;

-- 지표는 서버만 쓰고 읽는다
drop policy if exists analysis_metrics_no_client on public.analysis_metrics;
create policy analysis_metrics_no_client on public.analysis_metrics for select using (false);

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
