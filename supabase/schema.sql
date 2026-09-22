-- ============================================================================
-- 학원 관리노트 Pro — Supabase 스키마 + RLS
--   · 학원마다 별도 프로젝트가 아니라 단일 프로젝트 멀티테넌트(academy_id) 구조.
--   · 모든 테이블은 "내가 속한 학원의 데이터만" 읽고 쓸 수 있다.
--   · Supabase SQL Editor 에 통째로 붙여넣고 한 번 실행하면 됩니다(멱등).
-- ============================================================================

create extension if not exists pgcrypto;

-- ── 원(테넌트) ──────────────────────────────────────────────────────────────
create table if not exists academies (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  logo_url         text,
  brand_color      text default '#2563eb',
  phone            text,
  license_key_hash text,
  plan             text not null default 'pro' check (plan in ('lite', 'pro')),
  invite_code      text unique not null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- 로그인 계정(auth.users) ↔ 학원 매핑. RLS 의 기준점.
create table if not exists academy_members (
  academy_id uuid not null references academies(id) on delete cascade,
  auth_uid   uuid not null references auth.users(id) on delete cascade,
  user_id    uuid,                                   -- users 테이블의 프로필 id
  role       text not null default 'teacher' check (role in ('owner', 'teacher', 'desk')),
  created_at timestamptz not null default now(),
  primary key (academy_id, auth_uid)
);
create index if not exists academy_members_auth_idx on academy_members(auth_uid);

-- 현재 로그인 사용자가 속한 학원 목록 (정책에서 재사용)
create or replace function my_academies()
returns setof uuid
language sql stable security definer set search_path = public as $$
  select academy_id from academy_members where auth_uid = auth.uid()
$$;

create or replace function my_role(p_academy uuid)
returns text
language sql stable security definer set search_path = public as $$
  select role from academy_members where auth_uid = auth.uid() and academy_id = p_academy
$$;

-- ── 업무 테이블 ─────────────────────────────────────────────────────────────
create table if not exists users (           -- 강사/데스크 프로필 (PIN 로그인용)
  id         text primary key,
  academy_id uuid not null references academies(id) on delete cascade,
  role       text not null default 'teacher' check (role in ('owner', 'teacher', 'desk')),
  name       text not null,
  pin        text,
  updated_at timestamptz not null default now()
);

create table if not exists subjects (
  id         text primary key,
  academy_id uuid not null references academies(id) on delete cascade,
  name       text not null,
  color      text default '#2563eb',
  updated_at timestamptz not null default now()
);

create table if not exists classes (
  id         text primary key,
  academy_id uuid not null references academies(id) on delete cascade,
  subject_id text,
  name       text not null,
  teacher_id text,
  schedule   jsonb default '[]'::jsonb,      -- [{dow, start, end}]
  capacity   int default 0,
  room       text,
  fee        int default 0,
  status     text default '운영',
  updated_at timestamptz not null default now()
);

create table if not exists students (
  id             text primary key,
  academy_id     uuid not null references academies(id) on delete cascade,
  name           text not null,
  school         text,
  grade          text,
  phone          text,
  parent_phone   text,
  siblings_group text,
  status         text default '재원' check (status in ('재원', '휴원', '퇴원')),
  joined_at      date,
  left_at        date,
  memo           text,
  custom         jsonb default '{}'::jsonb,  -- 계열별 확장 필드
  updated_at     timestamptz not null default now()
);

create table if not exists enrollments (
  id           text primary key,
  academy_id   uuid not null references academies(id) on delete cascade,
  student_id   text not null,
  class_id     text not null,
  started_at   date,
  ended_at     date,
  fee_override int,
  updated_at   timestamptz not null default now()
);

create table if not exists attendance (
  id         text primary key,
  academy_id uuid not null references academies(id) on delete cascade,
  student_id text not null,
  class_id   text not null,
  date       date not null,
  status     text not null check (status in ('출석', '지각', '결석', '보강', '조퇴')),
  reason_tag text,
  checked_by text,
  checked_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists payments (
  id           text primary key,
  academy_id   uuid not null references academies(id) on delete cascade,
  student_id   text not null,
  month        text not null,                -- 'YYYY-MM'
  amount       int not null default 0,
  method       text,
  paid_at      date,
  status       text default '미납' check (status in ('완납', '부분', '미납')),
  installments jsonb default '[]'::jsonb,
  updated_at   timestamptz not null default now()
);

create table if not exists expenses (
  id         text primary key,
  academy_id uuid not null references academies(id) on delete cascade,
  category   text,
  amount     int not null default 0,
  memo       text,
  date       date not null,
  updated_at timestamptz not null default now()
);

create table if not exists counsel_logs (
  id          text primary key,
  academy_id  uuid not null references academies(id) on delete cascade,
  student_id  text,
  type        text check (type in ('전화', '대면', '입회상담')),
  stage       text,
  content     text,
  next_action text,
  created_by  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists notices (
  id          text primary key,
  academy_id  uuid not null references academies(id) on delete cascade,
  student_id  text,
  channel     text,
  template_id text,
  sent_at     timestamptz,
  body        text,
  updated_at  timestamptz not null default now()
);

-- ── 인덱스 (조회는 전부 월/반 단위 범위 질의) ────────────────────────────────
create index if not exists students_academy_idx     on students(academy_id, status, name);
create index if not exists classes_academy_idx      on classes(academy_id);
create index if not exists enroll_class_idx         on enrollments(academy_id, class_id, ended_at);
create index if not exists enroll_student_idx       on enrollments(academy_id, student_id, ended_at);
create index if not exists attendance_class_date_ix on attendance(academy_id, class_id, date);
create index if not exists attendance_stud_date_ix  on attendance(academy_id, student_id, date);
create index if not exists attendance_sync_idx      on attendance(academy_id, updated_at);
create index if not exists payments_month_idx       on payments(academy_id, month, status);
create index if not exists expenses_date_idx        on expenses(academy_id, date);
create index if not exists counsel_student_idx      on counsel_logs(academy_id, student_id, created_at);

-- 동기화 커서(updated_at) 질의용 인덱스
do $$
declare t text;
begin
  foreach t in array array['users','subjects','classes','students','enrollments','payments','expenses','counsel_logs','notices']
  loop
    execute format('create index if not exists %I on %I(academy_id, updated_at)', t || '_sync_idx', t);
  end loop;
end $$;

-- updated_at 자동 갱신 (클라이언트가 보낸 값이 있으면 존중, 없으면 now())
create or replace function touch_updated_at() returns trigger
language plpgsql as $$
begin
  if new.updated_at is null or new.updated_at = old.updated_at then
    new.updated_at := now();
  end if;
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['users','subjects','classes','students','enrollments','attendance','payments','expenses','counsel_logs','notices','academies']
  loop
    execute format('drop trigger if exists %I on %I', t || '_touch', t);
    execute format('create trigger %I before update on %I for each row execute function touch_updated_at()', t || '_touch', t);
  end loop;
end $$;

-- ── RLS ─────────────────────────────────────────────────────────────────────
-- 원칙: academy_id 가 내 소속 학원이면 read/write 허용, 아니면 아무것도 보이지 않는다.
alter table academies       enable row level security;
alter table academy_members enable row level security;

drop policy if exists academies_read on academies;
create policy academies_read on academies
  for select using (id in (select my_academies()));

drop policy if exists academies_update on academies;
create policy academies_update on academies
  for update using (id in (select my_academies()) and my_role(id) = 'owner');

drop policy if exists members_read on academy_members;
create policy members_read on academy_members
  for select using (academy_id in (select my_academies()));

do $$
declare t text;
begin
  foreach t in array array['users','subjects','classes','students','enrollments','attendance','payments','expenses','counsel_logs','notices']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t || '_tenant_select', t);
    execute format('drop policy if exists %I on %I', t || '_tenant_insert', t);
    execute format('drop policy if exists %I on %I', t || '_tenant_update', t);
    execute format('drop policy if exists %I on %I', t || '_tenant_delete', t);
    execute format('create policy %I on %I for select using (academy_id in (select my_academies()))', t || '_tenant_select', t);
    execute format('create policy %I on %I for insert with check (academy_id in (select my_academies()))', t || '_tenant_insert', t);
    execute format('create policy %I on %I for update using (academy_id in (select my_academies())) with check (academy_id in (select my_academies()))', t || '_tenant_update', t);
    execute format('create policy %I on %I for delete using (academy_id in (select my_academies()))', t || '_tenant_delete', t);
  end loop;
end $$;

-- ── 학원 생성 / 합류 RPC ─────────────────────────────────────────────────────
create or replace function gen_invite_code() returns text
language sql volatile as $$
  -- 혼동 문자(0,O,1,I) 제외 6자리
  select string_agg(substr('23456789ABCDEFGHJKLMNPQRSTUVWXYZ', (floor(random() * 32) + 1)::int, 1), '')
  from generate_series(1, 6)
$$;

create or replace function create_academy(p_name text, p_license_hash text, p_brand_color text default '#2563eb')
returns academies
language plpgsql security definer set search_path = public as $$
declare
  a academies;
  code text;
begin
  if auth.uid() is null then
    raise exception '로그인이 필요합니다';
  end if;
  loop
    code := gen_invite_code();
    exit when not exists (select 1 from academies where invite_code = code);
  end loop;

  insert into academies (name, license_key_hash, brand_color, invite_code, plan)
  values (p_name, p_license_hash, p_brand_color, code, 'pro')
  returning * into a;

  insert into academy_members (academy_id, auth_uid, role) values (a.id, auth.uid(), 'owner');
  return a;
end $$;

create or replace function join_academy(p_invite_code text, p_name text, p_role text default 'teacher', p_pin text default null)
returns academies
language plpgsql security definer set search_path = public as $$
declare
  a academies;
begin
  if auth.uid() is null then
    raise exception '로그인이 필요합니다';
  end if;
  select * into a from academies where invite_code = upper(p_invite_code);
  if a.id is null then
    raise exception '초대 코드를 찾을 수 없습니다';
  end if;
  if p_role not in ('teacher', 'desk') then
    raise exception '초대 코드로는 강사 또는 데스크 계정만 만들 수 있습니다';
  end if;

  insert into academy_members (academy_id, auth_uid, role)
  values (a.id, auth.uid(), p_role)
  on conflict (academy_id, auth_uid) do update set role = excluded.role;

  insert into users (id, academy_id, role, name, pin)
  values (auth.uid()::text, a.id, p_role, p_name, p_pin)
  on conflict (id) do update set name = excluded.name, pin = excluded.pin, role = excluded.role;

  return a;
end $$;

-- ── Realtime ────────────────────────────────────────────────────────────────
-- 두 기기에서 동시에 출결을 체크해도 3초 내 상호 반영되도록 publication 에 등록.
do $$
declare t text;
begin
  foreach t in array array['users','subjects','classes','students','enrollments','attendance','payments','expenses','counsel_logs','notices']
  loop
    begin
      execute format('alter publication supabase_realtime add table %I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;
