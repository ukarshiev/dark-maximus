#!/bin/bash
# Проверка платежа ID 233 на боевом сервере

PAYMENT_ID="30a48370-000f-5001-9000-16231fa0ad0c"
DB_FILE="/opt/dark-maximus/users.db"

echo "=== Проверка транзакции ==="
sqlite3 "$DB_FILE" "SELECT payment_id, status, user_id, amount_rub FROM transactions WHERE payment_id = '$PAYMENT_ID' LIMIT 1;"

echo ""
echo "=== Проверка metadata ==="
METADATA=$(sqlite3 "$DB_FILE" "SELECT metadata FROM transactions WHERE payment_id = '$PAYMENT_ID' LIMIT 1;")
if [ -n "$METADATA" ]; then
    echo "$METADATA" | python3 -m json.tool 2>/dev/null | grep -E '"host_code"|"host_name"|"plan_id"' || echo "Metadata не в JSON формате или пусто"
else
    echo "Metadata не найдено"
fi

echo ""
echo "=== Последние логи webhook ==="
tail -100 /opt/dark-maximus/logs/application.log | grep -E "$PAYMENT_ID|YOOKASSA_WEBHOOK" | tail -20

