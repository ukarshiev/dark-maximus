import sys
from datetime import datetime, timezone
import re

sys.path.insert(0, '/app/project/src')

from shop_bot.data_manager.database import (  # noqa: E402
    get_user_keys,
    get_key_by_id,
    get_or_create_permanent_token,
    get_permanent_token_by_key_id,
    get_plans_for_host,
)
from shop_bot.config import get_purchase_success_text, get_user_cabinet_domain  # noqa: E402


def main():
    print('=' * 60)
    print('ТЕСТИРОВАНИЕ ФУНКЦИОНАЛА ТОКЕНА')
    print('=' * 60)

    # Находим последний ключ
    last_key = None
    for user_id in range(1, 1000):
        keys = get_user_keys(user_id)
        if keys:
            last_key = keys[-1]
            break

    if not last_key:
        print('Ключи не найдены')
        return

    key_id = last_key['key_id']
    user_id = last_key['user_id']
    print(f'Найден ключ: key_id={key_id}, user_id={user_id}')

    # Получаем или создаем токен
    token = get_permanent_token_by_key_id(key_id)
    if not token:
        token = get_or_create_permanent_token(user_id, key_id)
    print(f'Токен: {token[:40]}...')

    # Получаем данные ключа
    key_data = get_key_by_id(key_id)
    print(f'subscription_link: {key_data.get("subscription_link")}')

    # Определяем provision_mode
    host_name = key_data.get('host_name')
    plan_name = key_data.get('plan_name')
    provision_mode = 'key'

    if host_name and plan_name:
        plans = get_plans_for_host(host_name)
        plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
        if plan:
            provision_mode = plan.get('key_provision_mode', 'key')

    print(f'provision_mode: {provision_mode}')

    # Проверяем домен
    cabinet_domain = get_user_cabinet_domain()
    print(f'Домен: {cabinet_domain}')

    # Тестируем get_purchase_success_text с режимом cabinet
    print('\nТест с режимом cabinet:')
    test_text = get_purchase_success_text(
        action='готов',
        key_number=8,
        expiry_date=datetime.now(timezone.utc),
        connection_string=key_data.get('connection_string'),
        subscription_link=key_data.get('subscription_link'),
        provision_mode='cabinet',
        user_id=user_id,
        key_id=key_id,
    )

    has_token = '/auth/' in test_text
    print(f'Ссылка содержит /auth/: {has_token}')

    if has_token:
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f'URL: {url}')
            if '/auth/' in url:
                token_in_url = url.split('/auth/')[-1].split('"')[0].split('>')[0]
                print(f'Токен в URL: {token_in_url[:40]}...')
                if token_in_url == token:
                    print('Токен совпадает!')
                else:
                    print('Токен НЕ совпадает!')
    else:
        print('Ссылка БЕЗ токена!')
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f'URL без токена: {url}')

    print('\n' + '=' * 60)
    if has_token:
        print('ТЕСТ ПРОЙДЕН: Ссылка содержит токен')
    else:
        print('ТЕСТ ПРОВАЛЕН: Ссылка не содержит токен')
    print('=' * 60)


if __name__ == "__main__":
    main()

