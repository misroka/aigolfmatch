"""Idempotent recommendation/ingestion schema migration for existing databases."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db


MIGRATION_SQL = """
LOCK TABLE product_sources IN SHARE ROW EXCLUSIVE MODE;
ALTER TABLE golf_clubs ADD COLUMN IF NOT EXISTS price_updated_at TIMESTAMP;
ALTER TABLE golf_clubs ADD COLUMN IF NOT EXISTS source_name VARCHAR(100);
ALTER TABLE golf_clubs ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE golf_clubs ADD COLUMN IF NOT EXISTS specs_validated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE club_specifications ADD COLUMN IF NOT EXISTS source_name VARCHAR(100);
ALTER TABLE club_specifications ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE club_specifications ADD COLUMN IF NOT EXISTS validated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE club_specifications ADD COLUMN IF NOT EXISTS raw_specs JSONB;
ALTER TABLE product_sources ADD COLUMN IF NOT EXISTS price_checked_at TIMESTAMP;
-- Legacy last_checked values may describe assumed stock, not a verified offer.
-- Keep raw source prices, but invalidate an unverifiable cached current price.
UPDATE golf_clubs SET current_price = NULL WHERE price_updated_at IS NULL;
DELETE FROM product_sources WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY golf_club_id, source_name
            ORDER BY last_checked DESC NULLS LAST, id DESC
        ) AS duplicate_rank FROM product_sources
    ) ranked WHERE duplicate_rank > 1
);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'product_sources'::regclass
          AND contype = 'u'
          AND conkey = ARRAY[
              (SELECT attnum FROM pg_attribute WHERE attrelid = 'product_sources'::regclass
               AND attname = 'golf_club_id'),
              (SELECT attnum FROM pg_attribute WHERE attrelid = 'product_sources'::regclass
               AND attname = 'source_name')
          ]::smallint[]
    ) THEN
        ALTER TABLE product_sources ADD CONSTRAINT product_sources_club_source_unique
            UNIQUE (golf_club_id, source_name);
    END IF;
END $$;
"""


def fitting_schema():
    """Reuse the canonical new fitting tables without replaying existing tables."""
    schema = (Path(__file__).parent.parent / 'database' / 'schema.sql').read_text()
    marker = '-- Fitting outcome tables'
    if marker not in schema:
        raise RuntimeError("Fitting outcome schema section is missing")
    section = schema.split(marker, 1)[1]
    section = re.sub(r'CREATE TABLE (?!IF NOT EXISTS)', 'CREATE TABLE IF NOT EXISTS ', section)
    section = re.sub(r'CREATE (UNIQUE )?INDEX (?!IF NOT EXISTS)',
                     r'CREATE \1INDEX IF NOT EXISTS ', section)
    return section


def migrate():
    # One transaction: no deduplication or partial schema changes survive failure.
    sql = fitting_schema()
    with db.get_cursor() as cursor:
        cursor.execute(MIGRATION_SQL)
        cursor.execute(sql)


if __name__ == '__main__':
    migrate()
    print("Recommendation and ingestion migration complete.")
