import argparse
import os
from getpass import getpass

from sqlalchemy import select


def create_admin() -> int:
    from app.db import SessionLocal
    from app.models import User, UserRole
    from app.security.auth import hash_password, validate_email, validate_password_strength

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


def seed() -> int:
    from app.db import SessionLocal
    from app.seed import SeedError, seed_demo

    db = SessionLocal()
    try:
        report = seed_demo(db)
    except SeedError as exc:
        print(exc)
        return 1
    finally:
        db.close()
    print(
        f"Seed terminé : {report.users} utilisateur(s), {report.jobs} offre(s), "
        f"{report.applications} candidature(s), {report.documents} document(s) créés."
    )
    return 0


def generate_fixtures() -> int:
    from pathlib import Path

    from app.seed import write_fixtures

    files = write_fixtures(Path("data/fixtures"))
    print(f"{len(files)} document(s) fictif(s) écrit(s) dans data/fixtures.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin", "seed-demo", "generate-fixtures"])
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin()
    if args.command == "seed-demo":
        return seed()
    if args.command == "generate-fixtures":
        return generate_fixtures()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
