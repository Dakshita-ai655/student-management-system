"""
create_admin.py - the ONLY way to create an Admin account.
Run on your own computer (never on Streamlit Cloud):

    python create_admin.py

Needs your Supabase URL and the SERVICE ROLE key (secret!). Admins cannot be created
from the app, and the database blocks everyone from editing the `profiles` table.
"""
import getpass
import os
import re
from supabase import create_client

STUDENT_EMAIL_DOMAIN = "students.sms-demo.edu"


def main():
    url = os.environ.get("SUPABASE_URL") or input("Supabase project URL: ").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY") or getpass.getpass("Supabase SERVICE ROLE key (hidden): ").strip()
    email = input("Admin email address: ").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or email.endswith("@" + STUDENT_EMAIL_DOMAIN):
        raise SystemExit("Enter a real email address (not a student login).")
    name = input("Admin display name [Administrator]: ").strip() or "Administrator"

    sb = create_client(url, key)
    user_id = None
    try:
        for u in sb.auth.admin.list_users(per_page=1000):
            if (u.email or "").lower() == email:
                user_id = u.id
                break
    except Exception:
        pass

    if user_id:
        if input("That user already exists. Make them an admin? (yes/no): ").strip().lower() != "yes":
            raise SystemExit("Cancelled.")
    else:
        pw = getpass.getpass("Choose an admin password (min 10 characters, hidden): ")
        if len(pw) < 10 or pw != getpass.getpass("Repeat the password: "):
            raise SystemExit("Passwords must match and be at least 10 characters.")
        user_id = sb.auth.admin.create_user({"email": email, "password": pw, "email_confirm": True}).user.id

    sb.table("profiles").upsert({"id": user_id, "role": "admin", "display_name": name}).execute()
    print(f"\n✓ Admin ready: {email}\nLog in from the 'Admin Login' tab of the app.")


if __name__ == "__main__":
    main()
