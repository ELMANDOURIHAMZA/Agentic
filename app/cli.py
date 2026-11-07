import argparse
import os
from getpass import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User, UserRole
from app.security.auth import hash_password, validate_email, validate_password_strength


def create_admin() -> int:
    email = os.getenv("ADMIN_EMAIL") or input("Admin email: ").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or getpass("Admin password: ")
    if not validate_email(email) or not validate_password_strength(password):
        print("Email or password does not meet the requirements.")
        return 1
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == email)) is not None:
            print("Unable to create administrator.")
            return 1
        db.add(
            User(
                first_name="Admin",
                last_name="User",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()
    print("Administrator created.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin"])
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
