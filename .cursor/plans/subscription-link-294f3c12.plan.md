<!-- 294f3c12-fdbd-42c6-bf97-0f8e9ea122d8 49b5b78b-fafd-46a7-bb21-c2c5efccc61d -->
# Исправление subscription_link для ключей

## Проблема

На боевом сервере subscription_link не отображается в веб-панели (`/keys`) и в личном кабинете показывается сообщение "Ссылка на подписку недоступна.".

## Причина

Функция `get_key_details_from_host` получает `subscription_link` из 3x-ui, но только если у клиента есть `subId` и настроен `subURI` в панели. Если `subscription_link` не получен, он не обновляется в БД, и для существующих ключей остается NULL.

## Решение

1. **Улучшить получение subscription_link в `get_key_details_from_host`**:

- Добавить fallback через `get_client_subscription_link` если прямой способ не сработал
- Улучшить логирование для диагностики проблем с получением subscription_link

## Файлы для изменения

1. `src/shop_bot/modules/xui_api.py`:

- Улучшить функцию `get_key_details_from_host` (строки 754-954)
- Добавить fallback через `get_client_subscription_link` если прямой способ получения subscription_link не сработал
- Добавить подробное логирование для диагностики случаев, когда subscription_link не удается получить

## Тестирование

1. Проверить обновление ключей через веб-панель (`/refresh-keys`)
2. Проверить отображение subscription_link в веб-панели (`/keys`)
3. Проверить отображение subscription_link в личном кабинете
4. Проверить восстановление subscription_link для ключей, у которых он отсутствует
5. **Создать тест для проверки атрибутов ключа в базе данных**:

- Тест должен проверять наличие и корректность следующих атрибутов:
- Subscription (subscription)
- Subscription Link (subscription_link)
- Личный кабинет (cabinet_links через user_tokens)
- Ключ подключения (connection_string)
- Email (3x-ui) (key_email)
- UUID (3x-ui) (xui_client_uuid)
- Telegram ChatID (telegram_chat_id)

### To-dos

- [ ] Улучшить функцию get_key_details_from_host: добавить fallback через get_client_subscription_link если прямой способ получения subscription_link не сработал
- [ ] Добавить подробное логирование для диагностики проблем с получением subscription_link
- [ ] Создать тест для проверки атрибутов ключа в БД: subscription, subscription_link, connection_string, key_email, xui_client_uuid, telegram_chat_id, cabinet_links
- [ ] Протестировать исправления: проверить обновление ключей, отображение в веб-панели и личном кабинете