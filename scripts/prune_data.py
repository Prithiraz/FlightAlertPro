#!/usr/bin/env python3
"""Data retention prune script (Phase 3).

Deletes rows that have aged past their configured retention window:
  - notification_log  older than RETAIN_NOTIFICATION_LOG_DAYS  (default 90)
  - price_history     older than RETAIN_PRICE_HISTORY_DAYS     (default 180)
  - audit_log         older than RETAIN_AUDIT_LOG_DAYS         (default 365)

Usage::

    python scripts/prune_data.py [--dry-run]

Exits 0 on success, 1 on error.
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Allow running from repo root
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import config  # noqa: E402 (after sys.path fix)
from supabase import create_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prune_data")


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _delete_older_than(supabase, table: str, column: str, cutoff: str, dry_run: bool) -> int:
    """Delete rows in *table* where *column* < *cutoff*.  Returns row count deleted."""
    try:
        if dry_run:
            r = (
                supabase.table(table)
                .select("id", count="exact")
                .lt(column, cutoff)
                .execute()
            )
            count = r.count or 0
            logger.info("[dry-run] %s: would delete %d rows older than %s", table, count, cutoff)
            return count
        else:
            # Supabase Python client requires at least one filter to allow delete
            r = supabase.table(table).delete().lt(column, cutoff).execute()
            count = len(r.data or [])
            logger.info("%s: deleted %d rows older than %s", table, count, cutoff)
            return count
    except Exception as exc:
        logger.warning("Could not prune %s: %s", table, exc)
        return 0


def main(dry_run: bool = False) -> None:
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        logger.error("SUPABASE URL / ANON KEY not configured — aborting")
        sys.exit(1)

    # Prefer the service-role key for admin deletion operations; fall back to
    # the anon key only if the service-role key is not set (e.g. local dev).
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or config.SUPABASE_ANON_KEY
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        logger.warning(
            "SUPABASE_SERVICE_ROLE_KEY is not set — using anon key. "
            "Set the service-role key in production for elevated deletion privileges."
        )

    supabase = create_client(config.SUPABASE_URL, supabase_key)

    results = {}

    results["notification_log"] = _delete_older_than(
        supabase,
        table="notification_log",
        column="sent_at",
        cutoff=_cutoff(config.RETAIN_NOTIFICATION_LOG_DAYS),
        dry_run=dry_run,
    )

    results["price_history"] = _delete_older_than(
        supabase,
        table="price_history",
        column="checked_at",
        cutoff=_cutoff(config.RETAIN_PRICE_HISTORY_DAYS),
        dry_run=dry_run,
    )

    results["audit_log"] = _delete_older_than(
        supabase,
        table="audit_log",
        column="created_at",
        cutoff=_cutoff(config.RETAIN_AUDIT_LOG_DAYS),
        dry_run=dry_run,
    )

    total = sum(results.values())
    logger.info("Prune complete — total rows %s: %d", "that would be deleted" if dry_run else "deleted", total)
    logger.info("Breakdown: %s", results)

    # Record prune run in audit_log (skip during dry-run to avoid noise)
    if not dry_run:
        try:
            from audit_log import audit as _audit
            import asyncio

            asyncio.run(
                _audit(
                    action="privacy.prune_run",
                    metadata={
                        "notification_log": results["notification_log"],
                        "price_history": results["price_history"],
                        "audit_log": results["audit_log"],
                        "total": total,
                    },
                )
            )
        except Exception as exc:
            logger.warning("Could not write prune audit entry: %s", exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune old data per retention policy")
    parser.add_argument("--dry-run", action="store_true", help="Count rows to delete without deleting them")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
