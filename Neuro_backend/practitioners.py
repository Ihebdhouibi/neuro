#!/usr/bin/env python3
"""
Practitioners table — synchronous RPPS lookup by P.Code (initiales)
Used by ocr_to_schema to enrich prescriber data with RPPS from DB.
"""

import os
import re
from typing import Optional, Dict
from loguru import logger

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:JOJOhamouch123@localhost:5432/electron_app"
)


def get_practitioner_by_pcode(pcode: str) -> Optional[Dict]:
    """
    Lookup practitioner by P.Code (initiales).
    Returns dict with full_name, rpps, specialty or None.
    """
    if not pcode or len(pcode.strip()) > 10:
        return None

    pcode_clean = pcode.strip().upper()

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            "SELECT pcode, full_name, rpps, specialty FROM practitioners WHERE pcode = %s AND active = TRUE",
            (pcode_clean,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return {
                "pcode":     row[0],
                "full_name": row[1],
                "rpps":      row[2],
                "specialty": row[3],
            }
        return None

    except Exception as e:
        logger.warning(f"⚠️ Practitioner lookup failed for '{pcode_clean}': {e}")
        return None


def get_practitioner_by_name(name: str) -> Optional[Dict]:
    """
    Fuzzy lookup by partial name (e.g. 'STANANAMARIA' matches 'STAN ANAMARIA-VERON').
    """
    if not name or len(name.strip()) < 3:
        return None

    # Normalize: remove spaces for comparison
    name_clean = re.sub(r'\s+', '', name.strip().upper())

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            "SELECT pcode, full_name, rpps, specialty FROM practitioners WHERE active = TRUE"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            db_name_clean = re.sub(r'[\s\-]', '', row[1].upper())
            # Check if OCR name is contained in DB name or vice versa
            if name_clean in db_name_clean or db_name_clean.startswith(name_clean[:6]):
                return {
                    "pcode":     row[0],
                    "full_name": row[1],
                    "rpps":      row[2],
                    "specialty": row[3],
                }
        return None

    except Exception as e:
        logger.warning(f"⚠️ Practitioner name lookup failed: {e}")
        return None


def init_practitioners_table():
    """Create table if not exists and seed initial data."""
    sql_file = os.path.join(os.path.dirname(__file__), "practitioners_migration.sql")
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        if os.path.exists(sql_file):
            with open(sql_file, "r", encoding="utf-8") as f:
                cur.execute(f.read())
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Practitioners table initialized")
    except Exception as e:
        logger.warning(f"⚠️ Could not init practitioners table: {e}")


if __name__ == "__main__":
    init_practitioners_table()
    print("Lookup VS:", get_practitioner_by_pcode("VS"))
    print("Lookup name:", get_practitioner_by_name("STANANAMARIA-VERON"))
