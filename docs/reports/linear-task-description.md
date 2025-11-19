# Комплексное покрытие тестами бизнес-процессов Dark Maximus

**Дата создания:** 19.01.2025  
**Версия плана:** 1.0.0  
**Проект:** karshiev

---

## Описание задачи

Требуется создать комплексную систему автоматизированного тестирования для проекта Dark Maximus, покрывающую все бизнес-процессы: от регистрации пользователя до получения VPN ключа после оплаты, включая все способы оплаты, реферальную программу, пробный период, автопродление, веб-панель администратора и пользовательский кабинет.

---

## Анализ текущего состояния

### Существующее покрытие

**Unit-тесты (базовые):**
- Регистрация пользователей
- Операции с БД (промокоды, транзакции, уведомления)
- Валидация данных
- Утилиты (deeplink, timezone)

**Интеграционные тесты (частичные):**
- Deeplink flow (группы, промокоды)

**E2E тесты:**
- Отсутствуют

### Пробелы в покрытии

1. **Полный цикл покупки VPN** - от выбора тарифа до получения ключа
2. **Все способы оплаты** (6 способов) - YooKassa, CryptoBot, TON Connect, Telegram Stars, Heleket, баланс
3. **Webhook'и платежей** - обработка уведомлений от платежных систем
4. **Создание ключей через 3X-UI API** - интеграция с панелью управления
5. **Реферальная программа** - регистрация по ссылке, скидки, начисление бонусов
6. **Пробный период** - выдача триалов, логика повторного использования
7. **Автопродление** - автоматическое продление подписок
8. **Веб-панель администратора** - CRUD операции, API endpoints (139 endpoints)
9. **Пользовательский кабинет** - авторизация по токену, отображение ключей, инструкции

---

## План реализации по этапам для параллельной работы

### Этап 0: Подготовка инфраструктуры (БЛОКИРУЮЩИЙ - должен быть первым)

**Зависимости:** нет  
**Оценка времени:** 2-3 часа

**Файлы для изменения:**
- `tests/conftest.py` - расширение фикстур и моков

**Задачи:**
1. Расширить фикстуру `mock_xui_api` - добавить все необходимые методы
2. Расширить фикстуру `mock_yookassa` - добавить все необходимые методы
3. Создать фикстуру `mock_cryptobot` - мок для CryptoBot API
4. Создать фикстуру `mock_ton_connect` - мок для TON Connect
5. Создать фикстуру `mock_heleket` - мок для Heleket API
6. Создать фикстуру `mock_flask_app` - мок для Flask приложения (user-cabinet)
7. Создать фикстуру `sample_host` - тестовый хост для БД
8. Создать фикстуру `sample_plan` - тестовый план для БД
9. Создать фикстуру `sample_promo_code` - тестовый промокод для БД
10. Создать фикстуру `mock_telegram_bot` - расширенный мок для Telegram Bot
11. Создать фикстуру `mock_support_bot` - мок для support-бота

---

### Этап 1: Unit-тесты для платежей (АГЕНТ 1)

**Зависимости:** Этап 0  
**Оценка времени:** 4-6 часов

**Файлы для создания:**
- `tests/unit/test_bot/test_payment_handlers.py`

**Тесты (10 тестов):**
1. `test_create_yookassa_payment` - создание платежа YooKassa
2. `test_create_cryptobot_invoice` - создание инвойса CryptoBot
3. `test_create_ton_invoice` - создание инвойса TON Connect
4. `test_create_stars_invoice` - создание инвойса Telegram Stars
5. `test_create_heleket_invoice` - создание инвойса Heleket
6. `test_pay_with_balance` - оплата с внутреннего баланса
7. `test_pre_checkout_validation` - валидация pre-checkout для Stars
8. `test_process_successful_payment_new_key` - обработка успешной оплаты (новый ключ)
9. `test_process_successful_payment_extend_key` - обработка успешной оплаты (продление)
10. `test_process_successful_payment_topup` - обработка пополнения баланса

**Исходные файлы для изучения:**
- `src/shop_bot/bot/handlers.py` (строки 4630-6400, 7032-7600)

---

### Этап 2: Unit-тесты для 3X-UI API (АГЕНТ 2)

**Зависимости:** Этап 0  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/unit/test_modules/test_xui_api.py`

**Тесты (7 тестов):**
1. `test_create_client` - создание клиента в 3X-UI
2. `test_update_client` - обновление клиента в 3X-UI
3. `test_delete_client` - удаление клиента из 3X-UI
4. `test_get_client_subscription_link` - получение subscription link
5. `test_create_or_update_key_new` - создание нового ключа
6. `test_create_or_update_key_extend` - продление существующего ключа
7. `test_host_quarantine_logic` - логика карантина проблемных хостов

**Исходные файлы для изучения:**
- `src/shop_bot/modules/xui_api.py`

---

### Этап 3: Unit-тесты для реферальной программы (АГЕНТ 3)

**Зависимости:** Этап 0  
**Оценка времени:** 2-3 часа

**Файлы для создания:**
- `tests/unit/test_database/test_referral_operations.py`

**Тесты (5 тестов):**
1. `test_referral_registration` - регистрация по реферальной ссылке
2. `test_referral_discount_calculation` - расчет скидки для реферала
3. `test_referral_bonus_calculation` - расчет бонуса для реферера
4. `test_referral_bonus_accrual` - начисление бонуса на баланс
5. `test_referral_link_generation` - генерация реферальной ссылки

---

### Этап 4: Unit-тесты для пробного периода (АГЕНТ 4)

**Зависимости:** Этап 0  
**Оценка времени:** 2-3 часа

**Файлы для создания:**
- `tests/unit/test_database/test_trial_operations.py`

**Тесты (5 тестов):**
1. `test_trial_eligibility_check` - проверка возможности получить триал
2. `test_trial_creation` - создание триального ключа
3. `test_trial_reuse_logic` - логика повторного использования
4. `test_trial_revocation` - отзыв триального ключа
5. `test_trial_reset` - сброс триала администратором

---

### Этап 5: Unit-тесты для операций с ключами (АГЕНТ 5)

**Зависимости:** Этап 0  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/unit/test_database/test_key_operations.py`
- `tests/unit/test_database/test_host_operations.py`

**Тесты для ключей (8 тестов):**
1. `test_create_key` - создание ключа
2. `test_get_key_by_id` - получение ключа по ID
3. `test_get_key_by_email` - получение ключа по email
4. `test_get_user_keys` - получение всех ключей пользователя
5. `test_update_key_info` - обновление информации о ключе
6. `test_delete_key` - удаление ключа
7. `test_sync_key_with_xui` - синхронизация ключа с 3X-UI
8. `test_key_numbering` - нумерация ключей

**Тесты для хостов (5 тестов):**
1. `test_get_host` - получение хоста
2. `test_get_host_by_code` - получение хоста по коду
3. `test_get_all_hosts` - получение всех хостов
4. `test_get_plans_for_host` - получение планов для хоста
5. `test_get_plan_by_id` - получение плана по ID

---

### Этап 6: Unit-тесты для пользовательского кабинета (АГЕНТ 6)

**Зависимости:** Этап 0  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/unit/test_user_cabinet/test_cabinet.py`

**Тесты (17 тестов):**
1. `test_health_endpoint` - healthcheck endpoint (/health)
2. `test_index_without_token` - главная страница без токена (401)
3. `test_index_with_valid_token` - главная страница с валидным токеном
4. `test_index_with_invalid_token` - главная страница с невалидным токеном (403)
5. `test_index_with_deleted_key` - главная страница с токеном для удаленного ключа (404)
6. `test_auth_route_valid_token` - авторизация по токену (/auth/<token>)
7. `test_auth_route_invalid_token` - авторизация с невалидным токеном
8. `test_require_token_decorator` - проверка декоратора @require_token
9. `test_token_validation_success` - успешная валидация токена
10. `test_token_validation_failure` - неудачная валидация токена
11. `test_session_storage` - сохранение данных в сессии
12. `test_rate_limit_decorator` - проверка rate limiting (10 запросов в минуту)
13. `test_rate_limit_exceeded` - превышение лимита запросов (429)
14. `test_ip_info_api_success` - успешное получение информации об IP (/api/ip-info)
15. `test_ip_info_api_failure` - ошибка получения информации об IP
16. `test_build_knowledge_base_url` - построение URL базы знаний
17. `test_fetch_ip_information` - получение информации об IP с внешних сервисов

---

### Этап 7: Интеграционные тесты для платежей - YooKassa, CryptoBot (АГЕНТ 7)

**Зависимости:** Этап 0, Этап 1  
**Оценка времени:** 5-6 часов

**Файлы для создания:**
- `tests/integration/test_payments/test_yookassa_flow.py`
- `tests/integration/test_payments/test_cryptobot_flow.py`

**Тесты для YooKassa (4 теста):**
1. `test_yookassa_full_flow` - полный flow от создания платежа до получения ключа
2. `test_yookassa_webhook_processing` - обработка webhook от YooKassa
3. `test_yookassa_payment_verification` - проверка подписи webhook
4. `test_yookassa_payment_retry` - повторная обработка платежа

**Тесты для CryptoBot (4 теста):**
1. `test_cryptobot_full_flow` - полный flow от создания инвойса до получения ключа
2. `test_cryptobot_webhook_processing` - обработка webhook от CryptoBot
3. `test_cryptobot_invoice_verification` - проверка подписи webhook
4. `test_cryptobot_payment_retry` - повторная обработка платежа

---

### Этап 8: Интеграционные тесты для платежей - TON Connect, Stars, Heleket, Баланс (АГЕНТ 8)

**Зависимости:** Этап 0, Этап 1  
**Оценка времени:** 6-8 часов

**Файлы для создания:**
- `tests/integration/test_payments/test_ton_connect_flow.py`
- `tests/integration/test_payments/test_stars_flow.py`
- `tests/integration/test_payments/test_heleket_flow.py`
- `tests/integration/test_payments/test_balance_flow.py`

**Тесты для TON Connect (4 теста):**
1. `test_ton_connect_full_flow` - полный flow подключения кошелька и оплаты
2. `test_ton_connect_transaction_verification` - проверка транзакции TON
3. `test_ton_connect_wallet_connection` - подключение кошелька
4. `test_ton_connect_error_handling` - обработка ошибок подключения

**Тесты для Telegram Stars (4 теста):**
1. `test_stars_full_flow` - полный flow от создания инвойса до получения ключа
2. `test_stars_pre_checkout_validation` - валидация pre-checkout
3. `test_stars_successful_payment` - обработка успешной оплаты
4. `test_stars_payment_verification` - проверка платежа

**Тесты для Heleket (4 теста):**
1. `test_heleket_full_flow` - полный flow от создания инвойса до получения ключа
2. `test_heleket_webhook_processing` - обработка webhook
3. `test_heleket_invoice_verification` - проверка инвойса
4. `test_heleket_payment_retry` - повторная обработка

**Тесты для баланса (3 теста):**
1. `test_balance_payment_full_flow` - полный flow оплаты с баланса
2. `test_balance_topup_flow` - пополнение баланса
3. `test_balance_insufficient_funds` - обработка недостаточных средств

---

### Этап 9: Интеграционные тесты для покупки VPN (АГЕНТ 9)

**Зависимости:** Этап 0, Этап 1, Этап 2  
**Оценка времени:** 6-8 часов

**Файлы для создания:**
- `tests/integration/test_vpn_purchase/test_full_purchase_flow.py`
- `tests/integration/test_vpn_purchase/test_key_creation_flow.py`
- `tests/integration/test_vpn_purchase/test_key_extension_flow.py`
- `tests/integration/test_vpn_purchase/test_promo_code_application.py`

**Тесты полного цикла покупки (6 тестов):**
1. `test_full_purchase_flow_new_user` - полный цикл для нового пользователя
2. `test_full_purchase_flow_with_promo` - полный цикл с промокодом
3. `test_full_purchase_flow_with_referral` - полный цикл с реферальной скидкой
4. `test_key_creation_after_payment` - создание ключа после оплаты
5. `test_key_extension_after_payment` - продление ключа после оплаты
6. `test_payment_failure_handling` - обработка неудачной оплаты

**Тесты создания ключей (4 теста):**
1. `test_key_creation_flow_new_key` - создание нового ключа через 3X-UI
2. `test_key_creation_flow_subscription_link` - получение subscription link
3. `test_key_creation_flow_connection_string` - формирование connection string
4. `test_key_creation_flow_error_handling` - обработка ошибок создания

**Тесты продления ключей (3 теста):**
1. `test_key_extension_flow_success` - успешное продление ключа
2. `test_key_extension_flow_calculation` - расчет нового времени истечения
3. `test_key_extension_flow_error_handling` - обработка ошибок продления

**Тесты применения промокодов (4 теста):**
1. `test_promo_code_application_discount_amount` - применение скидки по сумме
2. `test_promo_code_application_discount_percent` - применение скидки по проценту
3. `test_promo_code_application_discount_bonus` - применение бонуса
4. `test_promo_code_application_validation` - валидация промокода

---

### Этап 10: Интеграционные тесты для реферальной программы (АГЕНТ 10)

**Зависимости:** Этап 0, Этап 3  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/integration/test_referral/test_referral_flow.py`

**Тесты (4 теста):**
1. `test_referral_registration_flow` - регистрация по реферальной ссылке
2. `test_referral_first_purchase_discount` - скидка при первой покупке реферала
3. `test_referral_bonus_accrual_flow` - начисление бонуса рефереру
4. `test_referral_notification` - уведомление реферера о покупке реферала

---

### Этап 11: Интеграционные тесты для пробного периода (АГЕНТ 11)

**Зависимости:** Этап 0, Этап 2, Этап 4  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/integration/test_trial/test_trial_flow.py`

**Тесты (4 теста):**
1. `test_trial_creation_flow` - создание триального ключа
2. `test_trial_reuse_flow` - повторное использование триала после сброса
3. `test_trial_revocation_flow` - отзыв триального ключа
4. `test_trial_status_check` - проверка статуса триального ключа

---

### Этап 12: Интеграционные тесты для автопродления (АГЕНТ 12)

**Зависимости:** Этап 0, Этап 1, Этап 2  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/integration/test_auto_renewal/test_auto_renewal_process.py`
- `tests/integration/test_auto_renewal/test_auto_renewal_conditions.py`

**Тесты процесса автопродления (5 тестов):**
1. `test_auto_renewal_process_success` - успешное автопродление с достаточным балансом
2. `test_auto_renewal_process_insufficient_balance` - автопродление при недостаточном балансе
3. `test_auto_renewal_process_disabled` - автопродление отключено
4. `test_auto_renewal_process_plan_unavailable` - тариф недоступен
5. `test_auto_renewal_process_notification` - отправка уведомлений об автопродлении

**Тесты условий автопродления (4 теста):**
1. `test_auto_renewal_conditions_check_enabled` - проверка включенного автопродления
2. `test_auto_renewal_conditions_check_balance` - проверка достаточности баланса
3. `test_auto_renewal_conditions_check_plan_available` - проверка доступности тарифа
4. `test_auto_renewal_conditions_time_before_expiry` - проверка времени до истечения

---

### Этап 13: Интеграционные тесты для пользовательского кабинета (АГЕНТ 13)

**Зависимости:** Этап 0, Этап 6  
**Оценка времени:** 2-3 часа

**Файлы для создания:**
- `tests/integration/test_user_cabinet/test_cabinet_flow.py`

**Тесты (5 тестов):**
1. `test_full_cabinet_flow` - полный flow: токен → авторизация → отображение ключа
2. `test_cabinet_with_subscription_link` - кабинет с subscription link
3. `test_cabinet_without_subscription_link` - кабинет без subscription link
4. `test_cabinet_key_data_display` - отображение данных ключа в кабинете
5. `test_cabinet_error_handling` - обработка ошибок в кабинете

---

### Этап 14: Unit-тесты для веб-панели - авторизация и Dashboard (АГЕНТ 14)

**Зависимости:** Этап 0  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_auth.py`
- `tests/unit/test_webhook_server/test_dashboard.py`

**Тесты авторизации (7 тестов):**
1. `test_login_page_get` - отображение страницы входа
2. `test_login_success` - успешный вход
3. `test_login_failure` - неверные учетные данные
4. `test_login_rate_limit` - ограничение попыток входа (10 в минуту)
5. `test_logout` - выход из системы
6. `test_login_required_decorator` - проверка декоратора @login_required
7. `test_session_persistence` - сохранение сессии на 30 дней

**Тесты Dashboard (3 теста):**
1. `test_dashboard_page` - главная панель (/)
2. `test_performance_page` - страница производительности (/performance)
3. `test_get_common_template_data` - общие данные для шаблонов

---

### Этап 15: Unit-тесты для веб-панели - пользователи и ключи (АГЕНТ 15)

**Зависимости:** Этап 0  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_users.py`
- `tests/unit/test_webhook_server/test_keys.py`

**Тесты пользователей (8 тестов):**
1. `test_users_page` - страница списка пользователей (/users)
2. `test_get_user_details` - получение деталей (API /api/user-details/<user_id>)
3. `test_update_user` - обновление данных (API /api/update-user/<user_id>)
4. `test_update_user_balance` - обновление баланса
5. `test_ban_unban_user` - бан/разбан пользователя
6. `test_revoke_user_consent` - отзыв согласия (/users/revoke-consent/<user_id>)
7. `test_reset_user_trial` - сброс триала
8. `test_delete_user_keys` - удаление ключей пользователя

**Тесты ключей (5 тестов):**
1. `test_keys_page` - страница списка ключей (/keys)
2. `test_get_key_details` - получение деталей ключа (API)
3. `test_sync_key_with_xui` - синхронизация с 3X-UI
4. `test_enable_disable_key` - включение/отключение ключа
5. `test_delete_key` - удаление ключа

---

### Этап 16: Unit-тесты для веб-панели - транзакции и промокоды (АГЕНТ 16)

**Зависимости:** Этап 0  
**Оценка времени:** 3-4 часа

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_transactions.py`
- `tests/unit/test_webhook_server/test_promo_codes.py`

**Тесты транзакций (4 теста):**
1. `test_transactions_page` - страница транзакций (/transactions)
2. `test_get_transaction_details` - детали транзакции (API /api/transaction/<id>)
3. `test_retry_transaction` - повторная обработка (/transactions/retry/<payment_id>)
4. `test_webhook_list` - список webhook'ов (/api/webhooks)

**Тесты промокодов (5 тестов):**
1. `test_promo_codes_page` - страница промокодов (/promo-codes)
2. `test_create_promo_code` - создание промокода (API)
3. `test_update_promo_code` - обновление промокода (API)
4. `test_delete_promo_code` - удаление промокода (API)
5. `test_promo_code_usage_history` - история использования

---

### Этап 17: Unit-тесты для веб-панели - уведомления и настройки (АГЕНТ 17)

**Зависимости:** Этап 0  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_notifications.py`
- `tests/unit/test_webhook_server/test_settings.py`

**Тесты уведомлений (4 теста):**
1. `test_notifications_page` - страница уведомлений (/notifications)
2. `test_create_notification` - создание уведомления (API)
3. `test_resend_notification` - повторная отправка
4. `test_send_manual_notification` - ручная отправка

**Тесты настроек (8 тестов):**
1. `test_settings_page` - страница настроек (/settings)
2. `test_update_panel_settings` - обновление настроек панели (/settings/panel)
3. `test_update_bot_settings` - обновление настроек бота (/settings/bot)
4. `test_update_payment_settings` - обновление платежных настроек (/settings/payments)
5. `test_update_host_settings` - обновление настроек хостов
6. `test_update_plan_settings` - обновление настроек планов
7. `test_toggle_hidden_mode` - переключение скрытого режима (/toggle-hidden-mode)
8. `test_start_stop_bots` - запуск/остановка ботов (/start-shop-bot, /stop-shop-bot, /start-support-bot, /stop-support-bot)

---

### Этап 18: Unit-тесты для веб-панели - TON Connect, инструкции, Wiki (АГЕНТ 18)

**Зависимости:** Этап 0  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_ton_connect.py`
- `tests/unit/test_webhook_server/test_instructions.py`
- `tests/unit/test_webhook_server/test_wiki.py`

**Тесты TON Connect (4 теста):**
1. `test_tonconnect_manifest` - манифест TON Connect (/.well-known/tonconnect-manifest.json)
2. `test_get_ton_manifest_data` - данные манифеста (API /api/get-ton-manifest-data)
3. `test_save_ton_manifest_settings` - сохранение настроек (/save-ton-manifest-settings)
4. `test_upload_ton_icon` - загрузка иконки (/upload-ton-icon)

**Тесты инструкций (5 тестов):**
1. `test_instructions_page` - страница инструкций (/instructions)
2. `test_create_instruction` - создание инструкции
3. `test_update_instruction` - обновление инструкции
4. `test_delete_instruction` - удаление инструкции
5. `test_update_video_instructions_display` - обновление отображения видео (API /api/update-video-instructions-display)

---

### Этап 19: Unit-тесты для веб-панели - документы, мониторинг, поддержка, фильтры (АГЕНТ 19)

**Зависимости:** Этап 0  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/unit/test_webhook_server/test_documents.py`
- `tests/unit/test_webhook_server/test_monitoring.py`
- `tests/unit/test_webhook_server/test_support.py`
- `tests/unit/test_webhook_server/test_filters.py`

**Тесты документов (6 тестов):**
1. `test_terms_page` - страница условий (/terms)
2. `test_privacy_page` - страница политики (/privacy)
3. `test_edit_terms` - редактирование условий (/edit-terms)
4. `test_edit_privacy` - редактирование политики (/edit-privacy)
5. `test_get_terms_content` - получение содержимого условий (API /api/get-terms-content)
6. `test_get_privacy_content` - получение содержимого политики (API /api/get-privacy-content)

**Тесты мониторинга (3 теста):**
1. `test_toggle_monitoring` - переключение мониторинга (API /api/monitoring/toggle)
2. `test_export_monitoring_data` - экспорт данных (API /api/monitoring/export)
3. `test_hourly_stats` - почасовая статистика (API /api/monitoring/hourly-stats)

**Тесты поддержки (2 теста):**
1. `test_support_check_config` - проверка конфигурации (API /api/support/check-config)
2. `test_support_check_test` - тестирование бота (API /api/support/check-test)

**Тесты фильтров (4 теста):**
1. `test_timestamp_to_datetime_filter` - фильтр конвертации timestamp
2. `test_strftime_filter` - фильтр форматирования даты
3. `test_panel_datetime_filter` - фильтр даты для панели
4. `test_panel_iso_filter` - фильтр ISO даты

---

### Этап 20: Интеграционные тесты для веб-панели и webhook'ов (АГЕНТ 20)

**Зависимости:** Этап 0, Этап 7, Этап 8  
**Оценка времени:** 5-6 часов

**Файлы для создания:**
- `tests/integration/test_web_panel/test_admin_workflow.py`
- `tests/integration/test_payments/test_webhook_handling.py`

**Тесты workflow администратора (3 теста):**
1. `test_admin_full_workflow` - полный workflow администратора (вход → dashboard → пользователи → ключи)
2. `test_settings_update_workflow` - обновление настроек через веб-панель
3. `test_promo_code_management_workflow` - управление промокодами через веб-панель

**Тесты webhook'ов (6 тестов):**
1. `test_webhook_yookassa_verification` - проверка подписи webhook YooKassa
2. `test_webhook_cryptobot_verification` - проверка подписи webhook CryptoBot
3. `test_webhook_heleket_verification` - проверка подписи webhook Heleket
4. `test_webhook_retry_mechanism` - механизм повторной обработки webhook'ов
5. `test_webhook_idempotency` - идемпотентность обработки webhook'ов
6. `test_webhook_error_handling` - обработка ошибок webhook'ов

---

### Этап 21: E2E тесты для пользовательских сценариев (АГЕНТ 21)

**Зависимости:** Этап 0, Этап 9, Этап 10, Этап 11  
**Оценка времени:** 6-8 часов

**Файлы для создания:**
- `tests/e2e/test_user_scenarios/test_new_user_purchase.py`
- `tests/e2e/test_user_scenarios/test_existing_user_purchase.py`
- `tests/e2e/test_user_scenarios/test_user_with_referral.py`
- `tests/e2e/test_user_scenarios/test_user_trial_flow.py`
- `tests/e2e/test_user_scenarios/test_user_key_extension.py`

**Тесты (5 тестов):**
1. `test_new_user_registers_and_buys_vpn` - новый пользователь регистрируется и покупает VPN
2. `test_new_user_uses_trial_then_buys` - новый пользователь использует триал, затем покупает
3. `test_user_refers_friend_and_gets_bonus` - пользователь приглашает друга и получает бонус
4. `test_user_extends_key` - пользователь продлевает ключ
5. `test_user_accesses_cabinet` - пользователь открывает личный кабинет по токену

---

### Этап 22: E2E тесты для административных сценариев (АГЕНТ 22)

**Зависимости:** Этап 0, Этап 14, Этап 15, Этап 16, Этап 17  
**Оценка времени:** 4-5 часов

**Файлы для создания:**
- `tests/e2e/test_admin_scenarios/test_admin_user_management.py`
- `tests/e2e/test_admin_scenarios/test_admin_key_management.py`
- `tests/e2e/test_admin_scenarios/test_admin_promo_management.py`

**Тесты (3 теста):**
1. `test_admin_user_management` - управление пользователями (вход → просмотр → обновление баланса → бан/разбан)
2. `test_admin_key_management` - управление ключами (вход → просмотр → синхронизация → включение/отключение)
3. `test_admin_promo_management` - управление промокодами (вход → создание → редактирование → удаление)

---

## Сводная таблица этапов для распределения

| Этап | Агент | Зависимости | Оценка времени | Тип тестов |
|------|-------|-------------|----------------|------------|
| 0 | Все | - | 2-3 часа | Инфраструктура |
| 1 | Агент 1 | 0 | 4-6 часов | Unit (платежи) |
| 2 | Агент 2 | 0 | 3-4 часа | Unit (3X-UI) |
| 3 | Агент 3 | 0 | 2-3 часа | Unit (рефералы) |
| 4 | Агент 4 | 0 | 2-3 часа | Unit (триалы) |
| 5 | Агент 5 | 0 | 3-4 часа | Unit (ключи/хосты) |
| 6 | Агент 6 | 0 | 4-5 часов | Unit (кабинет) |
| 7 | Агент 7 | 0, 1 | 5-6 часов | Integration (YooKassa, CryptoBot) |
| 8 | Агент 8 | 0, 1 | 6-8 часов | Integration (TON, Stars, Heleket, Баланс) |
| 9 | Агент 9 | 0, 1, 2 | 6-8 часов | Integration (покупка VPN) |
| 10 | Агент 10 | 0, 3 | 3-4 часа | Integration (рефералы) |
| 11 | Агент 11 | 0, 2, 4 | 3-4 часа | Integration (триалы) |
| 12 | Агент 12 | 0, 1, 2 | 4-5 часов | Integration (автопродление) |
| 13 | Агент 13 | 0, 6 | 2-3 часа | Integration (кабинет) |
| 14 | Агент 14 | 0 | 3-4 часа | Unit (веб-панель: auth/Dashboard) |
| 15 | Агент 15 | 0 | 4-5 часов | Unit (веб-панель: пользователи/ключи) |
| 16 | Агент 16 | 0 | 3-4 часа | Unit (веб-панель: транзакции/промокоды) |
| 17 | Агент 17 | 0 | 4-5 часов | Unit (веб-панель: уведомления/настройки) |
| 18 | Агент 18 | 0 | 4-5 часов | Unit (веб-панель: TON/Wiki/инструкции) |
| 19 | Агент 19 | 0 | 4-5 часов | Unit (веб-панель: документы/мониторинг) |
| 20 | Агент 20 | 0, 7, 8 | 5-6 часов | Integration (веб-панель/webhook'и) |
| 21 | Агент 21 | 0, 9, 10, 11 | 6-8 часов | E2E (пользователи) |
| 22 | Агент 22 | 0, 14-17 | 4-5 часов | E2E (администраторы) |

---

## Параллельные группы этапов

### Группа 1: Параллельно после Этапа 0 (могут выполняться одновременно)
- Этапы 1, 2, 3, 4, 5, 6, 14, 15, 16, 17, 18, 19 (12 агентов)

### Группа 2: Параллельно после Группы 1 (зависят от unit-тестов)
- Этапы 7, 8, 9, 10, 11, 12, 13 (7 агентов)

### Группа 3: Параллельно после Группы 2 (зависят от integration-тестов)
- Этапы 20, 21, 22 (3 агента)

---

## Общая оценка времени

**Последовательно:** ~90-115 часов

**Параллельно (максимум):**
- Группа 1: 4-6 часов (самый длинный этап)
- Группа 2: 6-8 часов (самый длинный этап)
- Группа 3: 6-8 часов (самый длинный этап)

**Итого при параллельном выполнении:** ~16-22 часа (с учетом Этапа 0)

---

## Метрики успеха

1. **Покрытие кода:** минимум 80% для критичных модулей
2. **Пирамида тестов:** 70% unit, 20% integration, 10% e2e
3. **Все бизнес-процессы покрыты:** каждый критичный процесс имеет минимум один интеграционный тест
4. **Все способы оплаты протестированы:** каждый способ имеет unit и integration тесты
5. **Все webhook'и протестированы:** каждый webhook имеет integration тест

---

## Примечания

- Все тесты должны использовать временную БД через фикстуру `temp_db`
- Все внешние сервисы должны быть замокированы
- Тесты должны быть независимыми и идемпотентными
- Использовать маркеры pytest для категоризации (`@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`)
- Все тесты должны генерировать Allure отчеты
- Все тесты должны следовать правилам из `docs/guides/testing/testing-rules.mdc`

---

## Дополнительные бизнес-процессы (покрыть тестами)

### Система уведомлений
- Автоматические уведомления об истечении подписки (72/48/24/1 час)
- Уведомления об автопродлении
- Уведомления о недоступности тарифа
- Уведомления об отключенном автопродлении
- Планировщик задач (scheduler.py)

### Онбординг и проверки
- Принудительная подписка на канал
- Проверка согласия с документами (условия, политика)
- Процесс онбординга (регистрация → согласие → подписка → главное меню)

### Дополнительные функции
- Выдача инструкций по настройке VPN для разных ОС (Android, iOS, Linux, macOS, Windows)
- Видеоинструкции
- Система поддержки (support-бот, тикеты в форумах)

### Резервное копирование
- Создание бэкапов БД
- Восстановление из бэкапа
- Автоматические бэкапы

---

## Ссылки на документацию

- План реализации: `docs/reports/linear-task-description.md` (этот документ)
- Правила тестирования: `docs/guides/testing/testing-rules.mdc`
- Allure дефекты: `docs/guides/testing/allure-defects-management.md`
- Структура тестов: `tests/` (существующая структура)


