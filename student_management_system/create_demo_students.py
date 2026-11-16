"""
create_demo_students.py - creates demo student logins + sample data.
Run ONCE on your own computer (after schema.sql AND migration_roles.sql) (never on Streamlit Cloud):

    python create_demo_students.py

It asks for your Supabase URL and the SERVICE ROLE key (secret! never put it in the app).
"""
import getpass
import os
from supabase import create_client

EMAIL_DOMAIN = "students.sms-demo.edu"   # must match auth.py

DEMO = [
    {"enrollment_no": "00101012024", "name": "Aanya Sharma", "branch": "Computer Science & Engineering", "semester": 4,
     "att": {"Data Structures": (40, 36), "Operating Systems": (38, 25), "DBMS": (36, 30),
             "Computer Networks": (30, 22), "Mathematics III": (42, 41)}},
    {"enrollment_no": "00201012024", "name": "Riya Verma", "branch": "Information Technology", "semester": 4,
     "att": {"Data Structures": (40, 28), "Operating Systems": (38, 33), "DBMS": (36, 36),
             "Computer Networks": (30, 15), "Mathematics III": (42, 30)}},
    {"enrollment_no": "00301012024", "name": "Meera Gupta", "branch": "Electronics & Communication", "semester": 4,
     "att": {"Signals & Systems": (40, 38), "Digital Electronics": (38, 36), "Microprocessors": (36, 27),
             "Analog Circuits": (30, 29), "Mathematics III": (42, 39)}},
]


def main():
    url = os.environ.get("SUPABASE_URL") or input("Supabase project URL: ").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY") or getpass.getpass("Supabase SERVICE ROLE key (hidden): ").strip()
    password = getpass.getpass("Choose ONE demo password for all demo students (min 8 chars): ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    university = input("University name [Indira Gandhi Delhi Technical University for Women]: ").strip() \
        or "Indira Gandhi Delhi Technical University for Women"

    sb = create_client(url, key)
    for s in DEMO:
        email = f"{s['enrollment_no'].lower()}@{EMAIL_DOMAIN}"
        user_id = None
        try:
            res = sb.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
            user_id = res.user.id
        except Exception as exc:
            # already exists? find it and reset the password
            try:
                for u in sb.auth.admin.list_users(per_page=1000):
                    if (u.email or "").lower() == email:
                        user_id = u.id
                        sb.auth.admin.update_user_by_id(u.id, {"password": password})
                        break
            except Exception:
                pass
            if not user_id:
                print(f"  ! Could not create {s['enrollment_no']}: {exc}")
                continue

        sb.table("students").upsert({
            "id": user_id, "enrollment_no": s["enrollment_no"], "name": s["name"],
            "email": f"{s['name'].split()[0].lower()}@example.com", "phone": None,
            "date_of_birth": "2005-01-01", "address": "Delhi, India",
            "university": university, "college": "School of Engineering", "branch": s["branch"],
            "semester": s["semester"], "academic_year": "2025-26", "admission_year": 2024,
        }).execute()
        sb.table("profiles").upsert({"id": user_id, "role": "student", "display_name": s["name"]}).execute()
        sb.table("attendance").upsert(
            [{"student_id": user_id, "subject": sub, "total_classes": t, "attended": a}
             for sub, (t, a) in s["att"].items()],
            on_conflict="student_id,subject").execute()
        print(f"  ✓ {s['name']}  -> login: {s['enrollment_no']}")
    print("\nDone. Log in with the enrollment number above and the password you just chose.")


if __name__ == "__main__":
    main()
