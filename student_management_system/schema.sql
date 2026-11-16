-- =====================================================================
-- Cloud-Based Student Management System : COMPLETE DATABASE SCHEMA
-- Run this ONCE in Supabase -> SQL Editor -> New query -> Run
-- =====================================================================

-- 1. STUDENTS (one row per student, id = the Supabase login user id)
create table if not exists public.students (
  id             uuid primary key references auth.users(id) on delete cascade,
  enrollment_no  text unique not null,
  name           text not null,
  email          text,
  phone          text,
  date_of_birth  date,
  address        text,
  university     text not null,
  college        text not null,
  branch         text not null,
  semester       int  not null check (semester between 1 and 12),
  academic_year  text not null,
  admission_year int  not null,
  created_at     timestamptz not null default now()
);

-- 2. ATTENDANCE (one row per student per subject)
create table if not exists public.attendance (
  id             uuid primary key default gen_random_uuid(),
  student_id     uuid not null references public.students(id) on delete cascade,
  subject        text not null,
  total_classes  int  not null default 0 check (total_classes >= 0),
  attended       int  not null default 0 check (attended >= 0),
  constraint attended_not_more_than_total check (attended <= total_classes),
  unique (student_id, subject)
);

-- 3. DOCUMENTS (metadata only; the real file lives in Supabase Storage)
create table if not exists public.documents (
  id           uuid primary key default gen_random_uuid(),
  student_id   uuid not null default auth.uid() references public.students(id) on delete cascade,
  category     text not null check (category in (
                 'Academic Certificates','Internship Certificates','Resume',
                 'Assignments','Identity Documents','Other Documents')),
  file_name    text not null,
  file_type    text not null,
  file_size    bigint not null check (file_size >= 0),
  storage_path text not null unique,
  uploaded_at  timestamptz not null default now()
);
create index if not exists documents_student_idx on public.documents(student_id);

-- 4. FEEDBACK
create table if not exists public.feedback (
  id          uuid primary key default gen_random_uuid(),
  student_id  uuid not null default auth.uid() references public.students(id) on delete cascade,
  category    text not null check (category in ('Faculty','Academics','Infrastructure','Administration','Other')),
  message     text not null check (char_length(message) between 10 and 1000),
  status      text not null default 'Submitted' check (status in ('Submitted','Under Review','Resolved')),
  created_at  timestamptz not null default now()
);

-- 5. ANNOUNCEMENTS (same for everyone)
create table if not exists public.announcements (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  description  text not null,
  category     text not null,
  published_on date not null default current_date
);

-- =====================================================================
-- ROW LEVEL SECURITY: every student can only touch THEIR OWN rows
-- =====================================================================
alter table public.students      enable row level security;
alter table public.attendance    enable row level security;
alter table public.documents     enable row level security;
alter table public.feedback      enable row level security;
alter table public.announcements enable row level security;

drop policy if exists "students read own"   on public.students;
drop policy if exists "students update own" on public.students;
create policy "students read own"   on public.students for select to authenticated using (id = auth.uid());
create policy "students update own" on public.students for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- Students may change ONLY these columns (name, branch, semester... stay locked)
revoke update on public.students from authenticated;
grant  update (email, phone, date_of_birth, address) on public.students to authenticated;

drop policy if exists "attendance read own" on public.attendance;
create policy "attendance read own" on public.attendance for select to authenticated using (student_id = auth.uid());
revoke insert, update, delete on public.attendance from authenticated;   -- only faculty/admin edit attendance

drop policy if exists "documents read own"   on public.documents;
drop policy if exists "documents insert own" on public.documents;
drop policy if exists "documents delete own" on public.documents;
create policy "documents read own"   on public.documents for select to authenticated using (student_id = auth.uid());
create policy "documents insert own" on public.documents for insert to authenticated with check (student_id = auth.uid());
create policy "documents delete own" on public.documents for delete to authenticated using (student_id = auth.uid());
revoke update on public.documents from authenticated;

drop policy if exists "feedback read own"   on public.feedback;
drop policy if exists "feedback insert own" on public.feedback;
create policy "feedback read own"   on public.feedback for select to authenticated using (student_id = auth.uid());
create policy "feedback insert own" on public.feedback for insert to authenticated
  with check (student_id = auth.uid() and status = 'Submitted');
revoke update, delete on public.feedback from authenticated;              -- only admin changes status

drop policy if exists "announcements read all" on public.announcements;
create policy "announcements read all" on public.announcements for select to authenticated using (true);
revoke insert, update, delete on public.announcements from authenticated;

-- Nobody who is not logged in can read anything
revoke all on public.students, public.attendance, public.documents, public.feedback, public.announcements from anon;

-- =====================================================================
-- PRIVATE STORAGE BUCKET for documents
-- Files are saved as  <student-id>/<random>_<filename>
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 10485760)       -- private, 10 MB max
on conflict (id) do update set public = false, file_size_limit = 10485760;

drop policy if exists "docs storage read own"   on storage.objects;
drop policy if exists "docs storage insert own" on storage.objects;
drop policy if exists "docs storage delete own" on storage.objects;
create policy "docs storage read own"   on storage.objects for select to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "docs storage insert own" on storage.objects for insert to authenticated
  with check (bucket_id = 'documents' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "docs storage delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = auth.uid()::text);

-- =====================================================================
-- SAMPLE ANNOUNCEMENTS (demo data only, NOT real university notices)
-- =====================================================================
insert into public.announcements (title, description, category, published_on)
select * from (values
  ('Mid-Semester Examination Schedule (Sample)', 'Sample notice: mid-semester exams will begin next month. Check the date sheet on the notice board.', 'Examination', current_date - 2),
  ('Library Timing Change (Sample)', 'Sample notice: the central library will stay open until 8 PM on weekdays during exam season.', 'General', current_date - 5),
  ('Technical Fest Registrations Open (Sample)', 'Sample notice: students can register for the annual technical fest through their department coordinators.', 'Events', current_date - 7),
  ('Attendance Shortage Reminder (Sample)', 'Sample notice: students below 75% attendance should meet their class coordinator.', 'Academics', current_date - 10),
  ('Scholarship Form Last Date (Sample)', 'Sample notice: scholarship applications must be submitted before the deadline mentioned by the administration.', 'Administration', current_date - 12)
) as v(title, description, category, published_on)
where not exists (select 1 from public.announcements);
