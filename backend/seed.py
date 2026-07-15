"""
Database seeding — creates default users on first boot.
Only runs if the users table is empty.
"""
import logging
import os
from sqlalchemy.orm import Session
from .models import User, RoleEnum
from .routers.auth import hash_password

logger = logging.getLogger(__name__)

# Default users — passwords from environment or secure defaults
_DEFAULT_USERS = [
    {"username": "admin", "role": RoleEnum.admin},
    {"username": "operator", "role": RoleEnum.operator},
    {"username": "viewer", "role": RoleEnum.viewer},
]


def seed_users(db: Session) -> None:
    """Create default users if none exist. Passwords come from env vars."""
    existing_count = db.query(User).count()
    if existing_count > 0:
        logger.info("[Seed] Users already exist (%d), skipping seed.", existing_count)
        return

    logger.info("[Seed] No users found — creating default accounts...")

    for user_def in _DEFAULT_USERS:
        username = user_def["username"]
        role = user_def["role"]
        # Password from env: SEED_PASSWORD_ADMIN, SEED_PASSWORD_OPERATOR, SEED_PASSWORD_VIEWER
        env_key = f"SEED_PASSWORD_{username.upper()}"
        password = os.getenv(env_key, f"{username.capitalize()}@CloudAI2026")

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        logger.info("[Seed] Created user: %s (role: %s)", username, role.value)

    db.commit()
    logger.info("[Seed] Default users created successfully.")
