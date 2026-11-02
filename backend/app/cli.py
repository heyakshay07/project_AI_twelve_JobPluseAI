"""Command line helpers:  python -m app.cli <command>"""
import argparse
import getpass
import json
import sys

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import Base, Job, User, UserProfile
from app.security import hash_password
from app.services.ingest import SOURCE_NAMES, run_ingest, seed_companies
from app.services.verification import verify_job


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create tables directly (dev shortcut; production uses Alembic)")
    sub.add_parser("seed-companies", help="Load data/companies.seed.json into the company directory")

    p = sub.add_parser("create-admin", help="Create (or promote) an admin user")
    p.add_argument("email")
    p.add_argument("--name", default="Admin")

    p = sub.add_parser("ingest", help="Fetch jobs from sources")
    p.add_argument("--sources", default=",".join(SOURCE_NAMES), help="comma separated")

    p = sub.add_parser("verify", help="Run link/fraud verification on jobs not yet verified")
    p.add_argument("--limit", type=int, default=25)

    args = parser.parse_args(argv)

    if args.cmd == "init-db":
        Base.metadata.create_all(engine)
        print("Tables created.")
    elif args.cmd == "seed-companies":
        with SessionLocal() as db:
            print(f"Seeded {seed_companies(db)} new companies.")
    elif args.cmd == "create-admin":
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password too short.")
            return 1
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == args.email.lower()))
            if user is None:
                user = User(email=args.email.lower(), full_name=args.name, password_hash=hash_password(password))
                user.profile = UserProfile()
                db.add(user)
            user.role = "admin"
            db.commit()
        print(f"Admin ready: {args.email}")
    elif args.cmd == "ingest":
        names = [s.strip() for s in args.sources.split(",") if s.strip()]
        print(json.dumps(run_ingest(names), indent=2, default=str))
    elif args.cmd == "verify":
        with SessionLocal() as db:
            jobs = db.scalars(
                select(Job).where(Job.is_active.is_(True), Job.verification_status == "unverified").limit(args.limit)
            ).all()
            for job in jobs:
                verify_job(db, job)
                print(f"#{job.id} {job.verification_status:<22} {job.company.name} - {job.title[:50]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
