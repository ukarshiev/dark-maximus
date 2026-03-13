# -*- coding: utf-8 -*-
"""
Unit-тесты: список кандидатов на восстановление ключей (recovery dry-run).
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest
import allure
from datetime import datetime, timezone, timedelta

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))
adhoc_utils = project_root / "tests" / "ad-hoc" / "utils"
if str(adhoc_utils) not in sys.path:
    sys.path.insert(0, str(adhoc_utils))


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Восстановление ключей")
@allure.label("package", "tests.ad-hoc.utils.recover_paid_keys")
class TestRecoveryEligibility:
    """Recovery dry-run строит список кандидатов по оплаченным транзакциям без ключа в БД."""

    @allure.title("collect_candidates находит оплаченную транзакцию new без ключа в БД")
    @allure.description("Одна оплаченная транзакция с action=new, план с days, ключа в vpn_keys нет — в списке один кандидат.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("recovery", "dry-run", "unit")
    def test_recovery_dry_run_builds_candidates_list(self, temp_db):
        from shop_bot.data_manager import database
        database.DB_FILE = temp_db
        database.initialize_db()
        database.create_host("h1", "http://localhost", "u", "p", 1, "c1")
        database.register_user_if_not_exists(100, "user100", None, None)
        plan_id = database.create_plan("h1", "Plan 1", 0, 100.0, 30, 0.0)
        assert plan_id is not None
        with sqlite3.connect(str(temp_db)) as conn:
            cursor = conn.cursor()
            meta = {
                "action": "new",
                "host_name": "h1",
                "plan_id": plan_id,
                "user_id": 100,
                "price": 100.0,
            }
            cursor.execute(
                """INSERT INTO transactions (payment_id, user_id, status, amount_rub, created_date, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "pay-recovery-1",
                    100,
                    "paid",
                    100.0,
                    (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                    json.dumps(meta),
                ),
            )
            conn.commit()
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        import recover_paid_keys
        candidates = recover_paid_keys.collect_candidates(conn, None, None)
        conn.close()
        assert len(candidates) >= 1, "Должен быть хотя бы один кандидат на восстановление"
        c = next((x for x in candidates if x.get("payment_id") == "pay-recovery-1"), None)
        assert c is not None
        assert c["action"] == "new"
        assert c["host_name"] == "h1"
        assert c["key_in_db"] is False
