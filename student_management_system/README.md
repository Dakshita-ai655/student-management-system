# Cloud-Based Student Management System

Python + Streamlit + Supabase (database + private file storage) + Google Gemini.

## Files
| File | What it does |
|---|---|
| app.py | The whole screen: login page, sidebar, all 6 modules |
| auth.py | Login / logout (Supabase Authentication) |
| database.py | Reads and writes student, attendance, feedback, announcements |
| attendance.py | Attendance maths |
| storage.py | Upload / download link / delete documents in the cloud |
| chatbot.py | Gemini chatbot (sees only the logged-in student's data) |
| schema.sql | Creates all tables, security rules and the private bucket |
| admin.py | Admin pages (students, attendance, announcements, feedback) |
| migration_roles.sql | Adds Student/Admin roles + security rules (run after schema.sql) |
| create_demo_students.py | Creates demo student logins |
| create_admin.py | Creates an Admin login (the only way to make one) |
| test_rls.py | Tests that security is enforced by the database |

## How the tables connect
`students` is the main table (its id = the Supabase login id).
`attendance`, `documents` and `feedback` each have a `student_id` that points to `students.id`.
`documents` only stores file details; the real file sits in the private Storage bucket `documents`, inside a folder named after the student id.
`announcements` is shared by everyone. Security rules (RLS) make sure a student can only see their own rows and files.

## STEP 1 - Supabase (free)
(For roles: after `schema.sql` also run `migration_roles.sql` the same way - see the Roles section below.)
1. Go to supabase.com -> sign up -> **New project** (save the database password somewhere).
2. Open **SQL Editor -> New query**, paste all of `schema.sql`, click **Run**. It should say "Success".
3. Open **Project Settings -> API**. Copy: **Project URL**, **anon public key**, and **service_role key**.
   - anon key goes into the app. service_role key is SECRET: use it only in Step 4, never share or upload it.
4. Open **Authentication -> Providers -> Email**: make sure Email is enabled (confirmations can stay on; demo users are pre-confirmed).

## STEP 2 - Gemini key (free)
Go to aistudio.google.com -> **Get API key** -> create key -> copy it.

## STEP 3 - Run on your computer
1. Install Python 3.10+ from python.org.
2. Open a terminal in this folder and run:
```
pip install -r requirements.txt
```
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your Project URL, anon key and Gemini key.

## STEP 4 - Create demo students
```
python create_demo_students.py
```
Paste the Project URL, then the **service_role key** (typing is hidden), then choose a demo password.
Logins created: `00101012024` (Aanya, has low attendance in some subjects), `00201012024`, `00301012024`.

## STEP 5 - Start the app
```
streamlit run app.py
```
Log in with an enrollment number and your demo password.

## STEP 6 - Deploy (Streamlit Community Cloud, free)
1. Create a GitHub account, make a **new repository**, upload all files in this folder
   (`.gitignore` keeps `secrets.toml` out - do NOT upload your real secrets file).
2. Go to share.streamlit.io -> sign in with GitHub -> **Create app** -> pick the repository, branch `main`, main file `app.py`.
3. Open **Advanced settings -> Secrets** and paste the contents of your local `secrets.toml`. Click **Deploy**.
4. Share the link. Documents stay in Supabase, so they remain after logout or on another device.

## Check that it works
- Login with a wrong password shows an error; 5 wrong tries lock the login for 60 seconds.
- Upload a PDF, log out, log in from another browser: it is still there.
- Log in as a second student: you cannot see the first student's documents.

## Notes
- Attendance is read-only for students; admins edit it in the app (Manage Attendance).
- Announcements and feedback status are now managed by admins inside the app.
- If the chatbot says it is unavailable: check the Gemini key, or set `GEMINI_MODEL` in secrets to a current model name from aistudio.google.com.

## ROLES: Student and Admin

**Upgrading an app you already set up (keeps all students, attendance, documents, feedback):**
1. Supabase -> SQL Editor -> New query -> paste ALL of `migration_roles.sql` -> Run. It is safe to run twice.
2. Replace your project files with the new ones (app.py, auth.py, database.py, admin.py, create_demo_students.py, create_admin.py, test_rls.py) and push to GitHub. Streamlit redeploys by itself. No new secrets are needed.
3. Create your admin (on your own computer):
```
python create_admin.py
```
   Enter the Project URL, the service_role key (hidden), the admin email, a name, and a password (10+ characters).
4. Open the app -> **Admin Login** tab -> sign in with the admin email and password.

**Fresh install order:** `schema.sql`, then `migration_roles.sql`, then `create_demo_students.py`, then `create_admin.py`.

**Turn off public sign-ups (recommended):** Supabase -> Authentication -> Sign In / Providers (or "Settings") -> switch OFF "Allow new users to sign up". Even if left on, a self-registered user has no profile, so the app rejects the login and the database shows them nothing.

**How roles are protected**
- The role lives in the `profiles` table. The app and every logged-in user are blocked from inserting, updating or deleting profiles, so nobody can make themselves admin. Only the service-role key (create_admin.py) or the SQL Editor can.
- Every admin action is checked by the database with `is_admin()`. Hiding buttons is only cosmetic.
- Admins can: see all students (read-only), add/edit/delete attendance, create/edit/delete announcements, read all feedback and change ONLY its status. Admins cannot read students' private documents.
- The service-role key is only typed into create_demo_students.py / create_admin.py on your computer. Never put it in `secrets.toml`, Streamlit Secrets or GitHub.

**Test the security (recommended before every demo):**
```
python test_rls.py
```
It logs in as a student, an admin and a visitor, tries forbidden actions and prints PASS/FAIL. It uses only the anon key.
