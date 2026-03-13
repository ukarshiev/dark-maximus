#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Восстановление ключей для оплаченных активных подписок (ключи, удалённые решением по ошибке).

Использует только привязанный inbound (host_inbound_id). Не списывает средства повторно.
По умолчанию dry-run; для применения передайте --apply.

ИСПОЛЬЗОВАНИЕ:
    python recover_paid_keys.py --dry-run [--db-path PATH] [--since-days N]
    python recover_paid_keys.py --apply [--db-path PATH] [--since-days N] [--limit N]
"""

import argparse
import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _parse_metadata(metadata_str):
    if not metadata_str:
        return {}
    try:
        return json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
    except (json.JSONDecodeError, TypeError):
        return {}


def _plan_days(plan: dict) -> float:
    if not plan:
        return 0.0
    months = int(plan.get("months") or 0)
    days = int(plan.get("days") or 0)
    hours = int(plan.get("hours") or 0)
    return months * 30 + days + hours / 24.0


def collect_candidates(conn: sqlite3.Connection, since_days: int | None, limit: int | None):
    """Собирает кандидатов на восстановление: оплаченные транзакции, подписка ещё активна, ключ отсутствует."""
    cursor = conn.cursor()
    since_clause = ""
    params = []
    if since_days is not None:
        since_clause = " AND created_date >= datetime('now', ?)"
        params.append(f"-{since_days} days")
    if limit is not None:
        params.append(limit)
    cursor.execute(
        """
        SELECT payment_id, user_id, amount_rub, created_date, metadata
        FROM transactions
        WHERE status = 'paid' AND metadata IS NOT NULL
        """ + since_clause + """
        ORDER BY created_date DESC
        """ + (" LIMIT ?" if limit is not None else ""),
        params,
    )
    rows = cursor.fetchall()
    candidates = []
    now = datetime.now(timezone.utc)
    for row in rows:
        payment_id, user_id, amount_rub, created_date, metadata_str = row
        meta = _parse_metadata(metadata_str)
        action = meta.get("action")
        plan_id = meta.get("plan_id")
        host_name = meta.get("host_name")
        key_id = meta.get("key_id")
        if not action or not plan_id or not host_name:
            continue
        try:
            plan = _get_plan(conn, plan_id)
        except Exception:
            plan = None
        days_plan = _plan_days(plan)
        if days_plan <= 0:
            continue
        try:
            if isinstance(created_date, str):
                paid_at = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
            else:
                paid_at = created_date
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        expected_end = paid_at + timedelta(days=days_plan)
        if expected_end < now:
            continue
        key_in_db = _key_exists(conn, key_id, user_id, host_name, payment_id, action)
        if action == "extend" and key_in_db:
            candidates.append({
                "payment_id": payment_id,
                "user_id": user_id,
                "action": action,
                "host_name": host_name,
                "plan_id": plan_id,
                "key_id": key_id,
                "days_to_add": days_plan,
                "key_in_db": True,
                "meta": meta,
                "plan": plan,
            })
        elif action == "new" and not key_in_db:
            candidates.append({
                "payment_id": payment_id,
                "user_id": user_id,
                "action": action,
                "host_name": host_name,
                "plan_id": plan_id,
                "key_id": key_id,
                "days_to_add": days_plan,
                "key_in_db": False,
                "meta": meta,
                "plan": plan,
            })
    return candidates


def _get_plan(conn, plan_id):
    cur = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row) if hasattr(row, "keys") else row


def _key_exists(conn, key_id, user_id, host_name, payment_id, action):
    if action == "extend" and key_id is not None:
        cur = conn.execute("SELECT key_id FROM vpn_keys WHERE key_id = ?", (key_id,))
        return cur.fetchone() is not None
    cur = conn.execute(
        "SELECT key_id FROM vpn_keys WHERE user_id = ? AND host_name = ?", (user_id, host_name)
    )
    return cur.fetchone() is not None


async def restore_one(candidate: dict, db_path: str, apply: bool) -> dict:
    """Восстанавливает один ключ: панель + при apply обновление БД (без повторного списания)."""
    from shop_bot.data_manager import database
    from shop_bot.modules import xui_api

    host_name = candidate["host_name"]
    user_id = candidate["user_id"]
    action = candidate["action"]
    days_to_add = candidate["days_to_add"]
    meta = candidate["meta"]
    plan = candidate.get("plan") or {}
    host = database.get_host(host_name)
    if not host:
        return {"payment_id": candidate["payment_id"], "ok": False, "error": "host not found"}
    host_code = (host.get("host_code") or host_name).replace(" ", "").lower()
    comment = str(user_id)
    traffic_gb = float(plan.get("traffic_gb") or 0) if plan else 0.0
    traffic_gb = traffic_gb if traffic_gb > 0 else None
    subscription = None
    telegram_chat_id = user_id

    if action == "extend" and candidate.get("key_in_db"):
        key_data = database.get_key_by_id(candidate["key_id"])
        if key_data:
            email = key_data["key_email"]
            subscription = key_data.get("subscription")
        else:
            return {"payment_id": candidate["payment_id"], "ok": False, "error": "key_id not in db"}
    else:
        key_number = database.get_next_key_number(user_id)
        email = f"user{user_id}-key{key_number}@{host_code}.bot"
        user = database.get_user(user_id)
        username = (user or {}).get("username", "")
        subscription = f"{user_id}-{username}".lower().replace("@", "")

    result = await xui_api.create_or_update_key_on_host(
        host_name=host_name,
        email=email,
        days_to_add=days_to_add,
        comment=comment,
        traffic_gb=traffic_gb,
        sub_id=subscription,
        telegram_chat_id=telegram_chat_id,
        host_code=host.get("host_code"),
    )
    if not result:
        return {"payment_id": candidate["payment_id"], "ok": False, "error": "create_or_update_key_on_host failed"}

    if not apply:
        return {"payment_id": candidate["payment_id"], "ok": True, "dry_run": True}

    if action == "new" and not candidate.get("key_in_db"):
        database.create_key_with_stats_atomic(
            user_id=user_id,
            host_name=host_name,
            xui_client_uuid=result["client_uuid"],
            key_email=result["email"],
            expiry_timestamp_ms=result["expiry_timestamp_ms"],
            amount_spent=0,
            months_purchased=0,
            payment_id=None,
            plan_id=candidate["plan_id"],
            connection_string=result.get("connection_string") or "",
            plan_name=plan.get("plan_name") or "",
            price=candidate.get("meta", {}).get("price"),
            subscription=subscription,
            subscription_link=result.get("subscription_link"),
            telegram_chat_id=telegram_chat_id,
            comment="Recovered key (no double charge)",
        )
    elif action == "extend" and candidate.get("key_in_db"):
        database.update_key_info(
            candidate["key_id"],
            result["client_uuid"],
            result["expiry_timestamp_ms"],
            result.get("subscription_link"),
        )
    return {"payment_id": candidate["payment_id"], "ok": True}


def main():
    parser = argparse.ArgumentParser(description="Recover keys for paid active subscriptions (dry-run by default)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Only report, do not apply (default)")
    parser.add_argument("--apply", action="store_true", help="Apply recovery (create/update keys and DB)")
    parser.add_argument("--db-path", default=None, help="Path to SQLite DB (default: from project)")
    parser.add_argument("--since-days", type=int, default=None, help="Consider only transactions in last N days")
    parser.add_argument("--limit", type=int, default=None, help="Max number of candidates to process")
    args = parser.parse_args()
    apply = args.apply

    db_path = args.db_path
    if not db_path:
        db_path = project_root / "users.db"
        if not db_path.exists():
            db_path = project_root / "src" / "users.db"
    db_path = str(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    candidates = collect_candidates(conn, args.since_days, args.limit)
    conn.close()
    logger.info("Candidates for recovery: %s", len(candidates))
    for c in candidates:
        logger.info(
            "  payment_id=%s user_id=%s action=%s host_name=%s key_id=%s key_in_db=%s",
            c["payment_id"], c["user_id"], c["action"], c["host_name"], c.get("key_id"), c.get("key_in_db"),
        )

    if not candidates:
        return 0
    if not apply:
        logger.info("Dry-run finished. Use --apply to perform recovery.")
        return 0

    from shop_bot.data_manager import database
    database.DB_FILE = db_path

    async def run():
        results = []
        for c in candidates:
            r = await restore_one(c, db_path, apply=True)
            results.append(r)
            logger.info("Result: %s", r)
        return results

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
