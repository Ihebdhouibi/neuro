#!/usr/bin/env python3
"""
Database initialization script.

Creates all tables and seeds a default admin user (idempotent).
Default credentials can be overridden via environment variables:
  NEUROX_DEFAULT_USERNAME (default: admin)
  NEUROX_DEFAULT_PASSWORD (default: NeuroX@2026)
  NEUROX_DEFAULT_EMAIL    (default: admin@neurox.local)
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure backend root is on sys.path so 'database', 'api.*' resolve when this
# script is invoked by the installer with an absolute path.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv()


async def _seed_default_user():
    """Insert a default admin user if it doesn't already exist."""
    from sqlalchemy import select
    from loguru import logger
    from database import AsyncSessionLocal
    from api import models
    from api.auth import get_password_hash

    username = os.getenv("NEUROX_DEFAULT_USERNAME", "admin")
    password = os.getenv("NEUROX_DEFAULT_PASSWORD", "NeuroX@2026")
    email = os.getenv("NEUROX_DEFAULT_EMAIL", "admin@neurox.local")

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(models.User).where(models.User.username == username)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"Default user '{username}' already exists - skipping seed")
            return

        user = models.User(
            username=username,
            email=email,
            full_name="NeuroX Administrator",
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        logger.info(
            f"Seeded default user '{username}' (email={email}). "
            "Change the password after first login."
        )


async def main():
    """Initialize database tables and seed default user."""
    from database import init_db
    from loguru import logger

    logger.info("Starting database initialization...")
    try:
        await init_db()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise

    try:
        await _seed_default_user()
    except Exception as e:
        # Seeding is non-fatal: table init is the critical step.
        logger.warning(f"Failed to seed default user: {e}")


if __name__ == "__main__":
    asyncio.run(main())

