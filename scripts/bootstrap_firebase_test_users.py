from __future__ import annotations

import argparse
import json
import os
import secrets
import sys

from firebase_admin import auth, get_app, initialize_app

# Allow running from project root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


ROLE_USERS = (
    # (role, email, display_name, operator_name)
    ("Monitor", "monitor.test@fsbus.example.com", "FS Bus Monitor Test", "Internal"),
    (
        "Supervisor",
        "supervisor.test@fsbus.example.com",
        "FS Bus Supervisor Test",
        "Internal",
    ),
    ("Admin", "admin.test@fsbus.example.com", "FS Bus Admin Test", "Internal"),
    ("Admin", "mbsadmin@fsbus.example.com", "MBS Admin", "Maluti Bus Services"),
    ("Admin", "ibladmin@fsbus.example.com", "IBL Admin", "Interstate Bus Lines"),
)


def get_or_initialize_app(project_id: str):
    try:
        return get_app()
    except ValueError:
        return initialize_app(options={"projectId": project_id})


def generate_password() -> str:
    return secrets.token_urlsafe(18)


def upsert_user(
    project_id: str, role: str, email: str, display_name: str, reset_password: bool
) -> dict[str, str]:
    get_or_initialize_app(project_id)

    password = generate_password() if reset_password else None
    created = False

    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        user = auth.create_user(
            email=email,
            email_verified=True,
            password=password or generate_password(),
            display_name=display_name,
            disabled=False,
        )
        created = True
        if password is None:
            password = "generated-on-create"

    update_kwargs = {
        "display_name": display_name,
        "disabled": False,
        "email_verified": True,
    }
    if reset_password:
        update_kwargs["password"] = password
    user = auth.update_user(user.uid, **update_kwargs)
    auth.set_custom_user_claims(user.uid, {"role": role})

    return {
        "role": role,
        "email": email,
        "uid": user.uid,
        "status": "created" if created else "updated",
        "password": password or "unchanged",
    }


def upsert_db_user(
    firebase_uid: str, email: str, full_name: str, role: str, operator_name: str
) -> str:
    """Insert or update the user row in app_auth.app_user. Returns 'created' or 'updated'."""
    from app.database import SessionLocal
    from app.models.app_auth import AppUser
    from app.models.master_data import Operator

    db = SessionLocal()
    try:
        operator = (
            db.query(Operator).filter(Operator.operator_name == operator_name).first()
        )
        if operator is None:
            raise ValueError(
                f"Operator '{operator_name}' not found in master_data.operator"
            )
        operator_id = operator.operator_id

        user = db.query(AppUser).filter(AppUser.firebase_uid == firebase_uid).first()
        if user is None:
            user = db.query(AppUser).filter(AppUser.email == email).first()

        if user is None:
            db.add(
                AppUser(
                    firebase_uid=firebase_uid,
                    email=email,
                    full_name=full_name,
                    role=role,
                    operator_id=operator_id,
                    is_active=True,
                )
            )
            db.commit()
            return "created"
        else:
            user.firebase_uid = firebase_uid
            user.email = email
            user.full_name = full_name
            user.role = role
            user.operator_id = operator_id
            user.is_active = True
            db.commit()
            return "updated"
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update Firebase test users for each role."
    )
    parser.add_argument("--project-id", default="bus-track-480813")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Generate and apply a new random password for each role user.",
    )
    parser.add_argument(
        "--sync-db",
        action="store_true",
        help="Also upsert each user into the app_auth.app_user database table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = [
        upsert_user(args.project_id, role, email, display_name, args.reset_passwords)
        for role, email, display_name, operator_name in ROLE_USERS
    ]

    if args.sync_db:
        for result, (role, email, display_name, operator_name) in zip(
            results, ROLE_USERS
        ):
            db_status = upsert_db_user(
                firebase_uid=result["uid"],
                email=email,
                full_name=display_name,
                role=role,
                operator_name=operator_name,
            )
            result["db_status"] = db_status
            result["operator"] = operator_name

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
