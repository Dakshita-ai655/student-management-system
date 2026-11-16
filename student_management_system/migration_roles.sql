-- =====================================================================
-- MIGRATION: Student / Admin roles
-- Run ONCE in Supabase -> SQL Editor, AFTER schema.sql.
-- Safe to run again (idempotent). Does NOT delete or change any
-- existing student, attendance, document, feedback or storage data.
-- =====================================================================

-- 1. PROFILES: one row per login. This is where the role lives.
create table if not exists public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  role         text not null default 'student' check (role in ('student','admin')),
  display_name text,
  created_at   timestamptz not null default now()
);

-- 2. Give every EXISTING student a 'student' profile (keeps current logins working)
insert into public.profiles (id, role, display_name)
select id, 'student', name from public.students
on conflict (id) do nothing;

-- 3. is_admin(): checked by the database on every request.
--    SECURITY DEFINER lets the function read profiles without recursion.
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- 4. PROFILES security: a user can read ONLY their own profile (admins read all).
--    Nobody can insert / update / delete profiles from the app, so nobody can
--    make themselves admin. Admin accounts are created only with the
--    service-role key (create_admin.py) or manually in this SQL Editor.
alter table public.profiles enable row level security;
drop policy if exists "profiles read own"   on public.profiles;
drop policy if exists "profiles admin read" on public.profiles;
create policy "profiles read own"   on public.profiles for select to authenticated using (id = auth.uid());
create policy "profiles admin read" on public.profiles for select to authenticated using (public.is_admin());
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;

-- 5. STUDENTS: admins can read all records (read-only)
drop policy if exists "students admin read" on public.students;
create policy "students admin read" on public.students for select to authenticated using (public.is_admin());

-- 6. ATTENDANCE: only admins can add / change / delete.
--    Students keep their existing read-own policy and have NO write policy.
grant insert, update, delete on public.attendance to authenticated;
drop policy if exists "attendance admin read"   on public.attendance;
drop policy if exists "attendance admin insert" on public.attendance;
drop policy if exists "attendance admin update" on public.attendance;
drop policy if exists "attendance admin delete" on public.attendance;
create policy "attendance admin read"   on public.attendance for select to authenticated using (public.is_admin());
create policy "attendance admin insert" on public.attendance for insert to authenticated with check (public.is_admin());
create policy "attendance admin update" on public.attendance for update to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "attendance admin delete" on public.attendance for delete to authenticated using (public.is_admin());

-- 7. ANNOUNCEMENTS: everyone logged in can read (existing policy); only admins write.
grant insert, update, delete on public.announcements to authenticated;
drop policy if exists "announcements admin insert" on public.announcements;
drop policy if exists "announcements admin update" on public.announcements;
drop policy if exists "announcements admin delete" on public.announcements;
create policy "announcements admin insert" on public.announcements for insert to authenticated with check (public.is_admin());
create policy "announcements admin update" on public.announcements for update to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "announcements admin delete" on public.announcements for delete to authenticated using (public.is_admin());

-- 8. FEEDBACK: admins read all and may change ONLY the status column.
grant update (status) on public.feedback to authenticated;
drop policy if exists "feedback admin read"   on public.feedback;
drop policy if exists "feedback admin update" on public.feedback;
create policy "feedback admin read"   on public.feedback for select to authenticated using (public.is_admin());
create policy "feedback admin update" on public.feedback for update to authenticated using (public.is_admin()) with check (public.is_admin());
-- (students still cannot update or delete feedback: no policy for them)

-- Documents and the private storage bucket are NOT touched:
-- admins get no access to students' files, students keep access to their own.
