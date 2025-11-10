#!/bin/bash
# Проверка логов webhook для платежа ID 233
# Запускать на боевом сервере

PAYMENT_ID="30a48370-000f-5001-9000-16231fa0ad0c"
LOG_FILE="/app/project/logs/application.log"

echo "=========================================="
echo "Проверка логов webhook для платежа $PAYMENT_ID"
echo "=========================================="
echo ""

echo "1. Последние записи с этим payment_id:"
echo "--------------------------------------"
grep "$PAYMENT_ID" "$LOG_FILE" | tail -20

echo ""
echo "2. Записи [YOOKASSA_WEBHOOK] с этим payment_id:"
echo "--------------------------------------"
grep "\[YOOKASSA_WEBHOOK\].*$PAYMENT_ID" "$LOG_FILE" | tail -20

echo ""
echo "3. Проверка использования metadata из БД:"
echo "--------------------------------------"
grep "Using metadata from DB transaction" "$LOG_FILE" | grep "$PAYMENT_ID" | tail -5

echo ""
echo "4. Проверка поиска хоста:"
echo "--------------------------------------"
grep "Host found by host_code\|Host found by host_name\|Host found via plan fallback" "$LOG_FILE" | grep "$PAYMENT_ID" | tail -10

echo ""
echo "5. Ошибки при обработке:"
echo "--------------------------------------"
grep "ERROR\|CRITICAL\|Host resolution failed" "$LOG_FILE" | grep "$PAYMENT_ID" | tail -10

echo ""
echo "=========================================="

