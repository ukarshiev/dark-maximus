import os
import logging
import asyncio
import json
import hashlib
import base64
import sqlite3
from hmac import compare_digest
from datetime import datetime
from functools import wraps
from math import ceil
from flask import Flask, request, render_template, redirect, url_for, flash, session, current_app
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем путь к базе данных
PROJECT_ROOT = Path("/app/project")
DB_FILE = PROJECT_ROOT / "users.db"

from shop_bot.modules import xui_api
from shop_bot.bot import handlers 
from shop_bot.data_manager.database import (
    get_all_settings, update_setting, get_all_hosts, get_plans_for_host,
    create_host, delete_host, create_plan, delete_plan, get_user_count,
    get_total_keys_count, get_total_spent_sum, get_total_notifications_count, get_daily_stats_for_charts,
    get_recent_transactions, get_paginated_transactions, get_all_users, get_user_keys,
    ban_user, unban_user, delete_user_keys, get_setting, find_and_complete_ton_transaction, find_ton_transaction_by_amount,
    get_paginated_keys, get_plan_by_id, update_plan, get_host, update_host
)
from shop_bot.ton_monitor import start_ton_monitoring

_bot_controller = None

ALL_SETTINGS_KEYS = [
    "panel_login", "panel_password", "about_text", "terms_url", "privacy_url",
    "support_user", "support_text", "channel_url", "telegram_bot_token",
    "telegram_bot_username", "admin_telegram_id", "yookassa_shop_id",
    "yookassa_secret_key", "sbp_enabled", "receipt_email", "cryptobot_token",
    "stars_enabled", "stars_conversion_rate",
    "heleket_merchant_id", "heleket_api_key", "domain", "referral_percentage",
    "referral_discount", "ton_wallet_address", "tonapi_key", "force_subscription", "trial_enabled", "trial_duration_days", "enable_referrals", "minimum_withdrawal",
    "support_group_id", "support_bot_token", "ton_monitoring_enabled", "hidden_mode", "support_enabled"
]

def create_webhook_app(bot_controller_instance):
    global _bot_controller
    _bot_controller = bot_controller_instance

    app_file_path = os.path.abspath(__file__)
    app_dir = os.path.dirname(app_file_path)
    template_dir = os.path.join(app_dir, 'templates')
    template_file = os.path.join(template_dir, 'login.html')

    print("--- DIAGNOSTIC INFORMATION ---", flush=True)
    print(f"Current Working Directory: {os.getcwd()}", flush=True)
    print(f"Path of running app.py: {app_file_path}", flush=True)
    print(f"Directory of running app.py: {app_dir}", flush=True)
    print(f"Expected templates directory: {template_dir}", flush=True)
    print(f"Expected login.html path: {template_file}", flush=True)
    print(f"Does template directory exist? -> {os.path.isdir(template_dir)}", flush=True)
    print(f"Does login.html file exist? -> {os.path.isfile(template_file)}", flush=True)
    print("--- END DIAGNOSTIC INFORMATION ---", flush=True)
    
    flask_app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    flask_app.config['SECRET_KEY'] = 'lolkek4eburek'

    @flask_app.context_processor
    def inject_current_year():
        return {'current_year': datetime.utcnow().year}

    @flask_app.context_processor
    def inject_common_defaults():
        """Глобальные значения по умолчанию для всех шаблонов.
        Если конкретный обработчик не передал данные, шаблон всё равно не упадёт."""
        try:
            data = get_common_template_data()
            # Убедимся, что bot_status представим как dict (для dot-notation)
            bot_status_val = data.get('bot_status')
            if isinstance(bot_status_val, dict):
                pass
            else:
                try:
                    bot_status_val = {
                        'shop_bot_running': getattr(bot_status_val, 'shop_bot_running', False),
                        'support_bot_running': getattr(bot_status_val, 'support_bot_running', False)
                    }
                except Exception:
                    bot_status_val = {'shop_bot_running': False, 'support_bot_running': False}
            return {
                'bot_status': bot_status_val,
                'all_settings_ok': data.get('all_settings_ok', False),
                'hidden_mode': data.get('hidden_mode', False),
                'project_version': data.get('project_version', '')
            }
        except Exception:
            return {
                'bot_status': {'shop_bot_running': False, 'support_bot_running': False},
                'all_settings_ok': False,
                'hidden_mode': False,
                'project_version': ''
            }

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated_function

    @flask_app.route('/.well-known/tonconnect-manifest.json')
    def tonconnect_manifest():
        """Возвращает манифест для TON Connect"""
        return current_app.send_static_file('.well-known/tonconnect-manifest.json')

    @flask_app.route('/login', methods=['GET', 'POST'])
    def login_page():
        settings = get_all_settings()
        if request.method == 'POST':
            if request.form.get('username') == settings.get("panel_login") and \
               request.form.get('password') == settings.get("panel_password"):
                session['logged_in'] = True
                return redirect(url_for('dashboard_page'))
            else:
                flash('Неверный логин или пароль', 'danger')
        return render_template('login.html')

    @flask_app.route('/logout', methods=['POST'])
    @login_required
    def logout_page():
        session.pop('logged_in', None)
        flash('Вы успешно вышли.', 'success')
        return redirect(url_for('login_page'))

    def get_common_template_data():
        bot_status = _bot_controller.get_status()
        settings = get_all_settings()
        required_for_start = ['telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id']
        all_settings_ok = all(settings.get(key) for key in required_for_start)
        hidden_mode_enabled = (str(settings.get('hidden_mode')) in ['1', 'true', 'True'])
        # Версию читаем из pyproject.toml
        project_version = ""
        try:
            import tomllib
            pyproject_path = PROJECT_ROOT / 'pyproject.toml'
            if pyproject_path.exists():
                with open(pyproject_path, 'rb') as f:
                    data = tomllib.load(f)
                    project_version = data.get('project', {}).get('version', '')
        except Exception:
            project_version = ""
        return {"bot_status": bot_status, "all_settings_ok": all_settings_ok, "hidden_mode": hidden_mode_enabled, "project_version": project_version}

    @flask_app.route('/')
    @login_required
    def index():
        return redirect(url_for('dashboard_page'))

    @flask_app.route('/dashboard')
    @login_required
    def dashboard_page():
        stats = {
            "user_count": get_user_count(),
            "total_keys": get_total_keys_count(),
            "total_spent": get_total_spent_sum(),
            "host_count": len(get_all_hosts()),
            "total_notifications": get_total_notifications_count()
        }
        
        page = request.args.get('page', 1, type=int)
        tab = request.args.get('tab', 'analytics')
        per_page = 8
        
        transactions, total_transactions = get_paginated_transactions(page=page, per_page=per_page)
        total_pages = ceil(total_transactions / per_page)
        
        chart_data = get_daily_stats_for_charts(days=30)
        common_data = get_common_template_data()
        
        return render_template(
            'dashboard.html',
            stats=stats,
            chart_data=chart_data,
            **common_data
        )

    @flask_app.route('/transactions')
    @login_required
    def transactions_page():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # Ограничиваем возможные значения per_page
        if per_page not in [5, 10, 15, 25, 50]:
            per_page = 15
        
        transactions, total_transactions = get_paginated_transactions(page=page, per_page=per_page)
        total_pages = ceil(total_transactions / per_page)
        
        common_data = get_common_template_data()
        
        return render_template(
            'transactions.html',
            transactions=transactions,
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
            **common_data
        )

    @flask_app.route('/notifications')
    @login_required
    def notifications_page():
        """Страница уведомлений"""
        from shop_bot.data_manager.database import get_paginated_notifications
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # Ограничиваем возможные значения per_page
        if per_page not in [5, 10, 15, 25, 50]:
            per_page = 15
            
        notifications, total = get_paginated_notifications(page, per_page)
        total_pages = ceil(total / per_page) if per_page > 0 else 1
        
        common_data = get_common_template_data()
        return render_template('notifications.html', 
                             notifications=notifications, 
                             current_page=page, 
                             total_pages=total_pages, 
                             per_page=per_page,
                             **common_data)

    @flask_app.route('/keys')
    @login_required
    def keys_page():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # Ограничиваем возможные значения per_page
        if per_page not in [5, 10, 15, 25, 50]:
            per_page = 15
        
        keys, total_keys = get_paginated_keys(page=page, per_page=per_page)
        total_pages = (total_keys + per_page - 1) // per_page
        
        common_data = get_common_template_data()
        
        return render_template(
            'keys.html',
            keys=keys,
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
            **common_data
        )

    @flask_app.route('/users')
    @login_required
    def users_page():
        users = get_all_users()
        for user in users:
            user['user_keys'] = get_user_keys(user['telegram_id'])
        
        common_data = get_common_template_data()
        return render_template('users.html', users=users, **common_data)

    @flask_app.route('/settings', methods=['GET'])
    @login_required
    def settings_page():
        current_settings = get_all_settings()
        hosts = get_all_hosts()
        for host in hosts:
            host['plans'] = get_plans_for_host(host['host_name'])
        
        # Получаем активную вкладку из параметра URL
        active_tab = request.args.get('tab', 'servers')
        
        common_data = get_common_template_data()
        return render_template('settings.html', settings=current_settings, hosts=hosts, active_tab=active_tab, **common_data)

    @flask_app.route('/settings/panel', methods=['POST'])
    @login_required
    def save_panel_settings():
        """Сохранение настроек панели - v2.1"""
        panel_keys = ['panel_login']
        
        # Пароль отдельно, если указан
        if 'panel_password' in request.form and request.form.get('panel_password'):
            update_setting('panel_password', request.form.get('panel_password'))
        
        # Обновляем остальные настройки панели
        for key in panel_keys:
            update_setting(key, request.form.get(key, ''))
        
        flash('Настройки панели успешно сохранены!', 'success')
        return redirect(url_for('settings_page', tab='panel'))

    @flask_app.route('/settings/bot', methods=['POST'])
    @login_required
    def save_bot_settings():
        """Сохранение настроек бота - v2.1"""
        bot_keys = [
            'telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id',
            'support_user', 'support_bot_token', 'support_group_id',
            'about_text', 'support_text', 'terms_url', 'privacy_url', 'channel_url',
            'trial_duration_days', 'minimum_withdrawal', 'referral_percentage', 'referral_discount', 'minimum_topup'
        ]
        
        bot_checkboxes = ['force_subscription', 'trial_enabled', 'enable_referrals', 'support_enabled']
        
        # Обрабатываем чекбоксы
        for checkbox_key in bot_checkboxes:
            values = request.form.getlist(checkbox_key)
            value = values[-1] if values else 'false'
            update_setting(checkbox_key, 'true' if value == 'true' else 'false')
        
        # Обрабатываем остальные настройки
        for key in bot_keys:
            update_setting(key, request.form.get(key, ''))
        
        flash('Настройки бота успешно сохранены!', 'success')
        return redirect(url_for('settings_page', tab='bot'))

    @flask_app.route('/settings/payments', methods=['POST'])
    @login_required
    def save_payment_settings():
        """Сохранение настроек платежных систем - v2.1"""
        payment_keys = [
            'receipt_email', 'yookassa_shop_id', 'yookassa_secret_key',
            'cryptobot_token', 'heleket_merchant_id', 'heleket_api_key', 'domain',
            'ton_wallet_address', 'tonapi_key', 'stars_conversion_rate'
        ]
        
        payment_checkboxes = ['sbp_enabled', 'stars_enabled']
        
        # Обрабатываем чекбоксы
        for checkbox_key in payment_checkboxes:
            values = request.form.getlist(checkbox_key)
            value = values[-1] if values else 'false'
            update_setting(checkbox_key, 'true' if value == 'true' else 'false')
        
        # Обрабатываем остальные настройки
        for key in payment_keys:
            update_setting(key, request.form.get(key, ''))
        
        flash('Настройки платежных систем успешно сохранены!', 'success')
        return redirect(url_for('settings_page', tab='payments'))

    # Старый endpoint для совместимости (удалим позже)
    @flask_app.route('/settings/legacy', methods=['POST'])
    @login_required
    def legacy_settings():
        if 'panel_password' in request.form and request.form.get('panel_password'):
            update_setting('panel_password', request.form.get('panel_password'))

        for checkbox_key in ['force_subscription', 'sbp_enabled', 'trial_enabled', 'enable_referrals', 'stars_enabled']:
            values = request.form.getlist(checkbox_key)
            value = values[-1] if values else 'false'
            update_setting(checkbox_key, 'true' if value == 'true' else 'false')

        for key in ALL_SETTINGS_KEYS:
            if key in ['panel_password', 'force_subscription', 'sbp_enabled', 'trial_enabled', 'enable_referrals', 'stars_enabled']:
                continue
            update_setting(key, request.form.get(key, ''))

        flash('Настройки успешно сохранены!', 'success')
        return redirect(url_for('settings_page'))


    @flask_app.route('/start-shop-bot', methods=['POST'])
    @login_required
    def start_shop_bot_route():
        result = _bot_controller.start_shop_bot()
        flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-shop-bot', methods=['POST'])
    @login_required
    def stop_shop_bot_route():
        result = _bot_controller.stop_shop_bot()
        flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/start-support-bot', methods=['POST'])
    @login_required
    def start_support_bot_route():
        result = _bot_controller.start_support_bot()
        flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-support-bot', methods=['POST'])
    @login_required
    def stop_support_bot_route():
        result = _bot_controller.stop_support_bot()
        flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/toggle-hidden-mode', methods=['POST'])
    @login_required
    def toggle_hidden_mode():
        try:
            from shop_bot.data_manager.database import get_setting, update_setting
            current = str(get_setting('hidden_mode') or '0')
            new_value = '0' if current in ['1', 'true', 'True'] else '1'
            update_setting('hidden_mode', new_value)
            return {'status': 'success', 'hidden_mode': new_value}, 200
        except Exception as e:
            logger.error(f"Failed to toggle hidden mode: {e}")
            return {'status': 'error'}, 500

    @flask_app.route('/versions', methods=['GET', 'POST'])
    @login_required
    def versions_page():
        """Просмотр и редактирование CHANGELOG.md"""
        def resolve_changelog_path():
            try:
                candidates = [
                    PROJECT_ROOT / 'CHANGELOG.md',
                    Path(__file__).resolve().parents[3] / 'CHANGELOG.md',
                    Path.cwd() / 'CHANGELOG.md'
                ]
            except Exception:
                candidates = [PROJECT_ROOT / 'CHANGELOG.md']
            for p in candidates:
                try:
                    if p.exists() or p.parent.exists():
                        return p
                except Exception:
                    continue
            return candidates[0]

        changelog_path = resolve_changelog_path()

        if request.method == 'POST':
            try:
                new_content = request.form.get('changelog_content', '')
                # Безопасно перезаписываем файл (создаём при отсутствии)
                with open(changelog_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                flash('CHANGELOG.md обновлён.', 'success')
                return redirect(url_for('versions_page'))
            except Exception as e:
                logger.error(f"Failed to write CHANGELOG.md: {e}")
                flash('Не удалось сохранить изменения.', 'danger')

        # GET: читаем changelog (создаём, если отсутствует)
        changelog_text = ''
        try:
            if not changelog_path.exists():
                try:
                    with open(changelog_path, 'w', encoding='utf-8') as f:
                        f.write('# История изменений\n\n')
                except Exception as e:
                    logger.error(f"Failed to create CHANGELOG.md: {e}")
            if changelog_path.exists():
                with open(changelog_path, 'r', encoding='utf-8') as f:
                    changelog_text = f.read()
        except Exception as e:
            logger.error(f"Failed to read CHANGELOG.md: {e}")
            changelog_text = ''
        # Общие данные для шаблонов (боты/режим/версия)
        common_data = get_common_template_data()
        return render_template('versions.html', changelog_text=changelog_text, **common_data)

    @flask_app.route('/instructions', methods=['GET', 'POST'])
    @login_required
    def instructions_page():
        """Просмотр и редактирование инструкций по платформам"""
        from pathlib import Path as _Path

        def resolve_base_dir():
            try:
                candidates = [
                    PROJECT_ROOT / 'instructions',
                    _Path(__file__).resolve().parents[3] / 'instructions',
                    Path.cwd() / 'instructions'
                ]
            except Exception:
                candidates = [PROJECT_ROOT / 'instructions']
            for p in candidates:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    return p
                except Exception:
                    continue
            return candidates[0]

        base_dir = resolve_base_dir()

        def get_file_for(platform: str) -> _Path:
            mapping = {
                'android': 'android.md',
                'ios': 'ios.md',
                'windows': 'windows.md',
                'macos': 'macos.md',
                'linux': 'linux.md',
            }
            filename = mapping.get(platform, 'android.md')
            return base_dir / filename

        def default_content(platform: str) -> str:
            if platform == 'android':
                return (
                    "<b>Подключение на Android</b>\n\n"
                    "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
                    "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
                    "3. <b>Импортируйте конфигурацию:</b>\n"
                    "   • Откройте V2RayTun.\n"
                    "   • Нажмите на значок + в правом нижнем углу.\n"
                    "   • Выберите «Импортировать конфигурацию из буфера обмена».\n"
                    "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
                    "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения.\n"
                    "6. <b>Проверьте подключение:</b> Зайдите на https://whatismyipaddress.com/."
                )
            if platform in ['ios', 'macos']:
                return (
                    f"<b>Подключение на {'MacOS' if platform=='macos' else 'iOS (iPhone/iPad)'}</b>\n\n"
                    "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
                    "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
                    "3. <b>Импортируйте конфигурацию:</b>\n"
                    "   • Откройте V2RayTun.\n"
                    "   • Нажмите на значок +.\n"
                    "   • Выберите «Импортировать конфигурацию из буфера обмена».\n"
                    "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
                    "5. <b>Подключитесь к VPN:</b> Включите главный переключатель.\n"
                    "6. <b>Проверьте подключение:</b> Зайдите на https://whatismyipaddress.com/."
                )
            if platform == 'windows':
                return (
                    "<b>Подключение на Windows</b>\n\n"
                    "1. <b>Установите приложение Nekoray</b> с GitHub (Releases).\n"
                    "2. <b>Распакуйте архив</b> в удобное место и запустите Nekoray.exe.\n"
                    "3. <b>Скопируйте ключ (vless://)</b> из раздела «Моя подписка».\n"
                    "4. <b>Импорт:</b> Сервер → Импортировать из буфера обмена.\n"
                    "5. Включите Tun Mode, выберите сервер и подключитесь.\n"
                    "6. Проверьте IP на https://whatismyipaddress.com/."
                )
            if platform == 'linux':
                return (
                    "<b>Подключение на Linux</b>\n\n"
                    "1. <b>Скачайте и распакуйте Nekoray</b> (Releases на GitHub).\n"
                    "2. <b>Запуск:</b> ./nekoray в терминале или через GUI.\n"
                    "3. <b>Скопируйте ключ (vless://)</b> из раздела «Моя подписка».\n"
                    "4. <b>Импорт:</b> Сервер → Импортировать из буфера обмена.\n"
                    "5. Включите Tun Mode, выберите сервер и подключитесь.\n"
                    "6. Проверьте IP на https://whatismyipaddress.com/."
                )
            return ''

        # Активная вкладка
        active_tab = request.args.get('tab', 'android')

        if request.method == 'POST':
            try:
                platform = request.form.get('platform', active_tab)
                new_content = request.form.get('instructions_content', '')
                file_path = get_file_for(platform)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                flash('Инструкции сохранены.', 'success')
                return redirect(url_for('instructions_page', tab=platform))
            except Exception as e:
                logger.error(f"Failed to write instructions: {e}")
                flash('Не удалось сохранить изменения.', 'danger')

        # GET: читаем файл, создаём при отсутствии с дефолтным содержимым
        try:
            file_path = get_file_for(active_tab)
            if not file_path.exists():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(default_content(active_tab))
                except Exception as e:
                    logger.error(f"Failed to create instruction file {file_path}: {e}")
            instructions_text = ''
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    instructions_text = f.read()
        except Exception as e:
            logger.error(f"Failed to read instruction file: {e}")
            instructions_text = ''

        return render_template(
            'instructions.html',
            active_tab=active_tab,
            instructions_text=instructions_text,
            **get_common_template_data()
        )

    @flask_app.route('/users/ban/<int:user_id>', methods=['POST'])
    @login_required
    def ban_user_route(user_id):
        ban_user(user_id)
        flash(f'Пользователь {user_id} был заблокирован.', 'success')
        return redirect(url_for('users_page'))

    @flask_app.route('/users/unban/<int:user_id>', methods=['POST'])
    @login_required
    def unban_user_route(user_id):
        unban_user(user_id)
        flash(f'Пользователь {user_id} был разблокирован.', 'success')
        return redirect(url_for('users_page'))

    @flask_app.route('/users/revoke/<int:user_id>', methods=['POST'])
    @login_required
    def revoke_keys_route(user_id):
        keys_to_revoke = get_user_keys(user_id)
        success_count = 0
        
        for key in keys_to_revoke:
            result = asyncio.run(xui_api.delete_client_on_host(key['host_name'], key['key_email']))
            if result:
                success_count += 1
        
        delete_user_keys(user_id)
        
        if success_count == len(keys_to_revoke):
            flash(f"Все {len(keys_to_revoke)} ключей для пользователя {user_id} были успешно отозваны.", 'success')
        else:
            flash(f"Удалось отозвать {success_count} из {len(keys_to_revoke)} ключей для пользователя {user_id}. Проверьте логи.", 'warning')

        return redirect(url_for('users_page'))

    @flask_app.route('/add-host', methods=['POST'])
    @login_required
    def add_host_route():
        create_host(
            name=request.form['host_name'],
            url=request.form['host_url'],
            user=request.form['host_username'],
            passwd=request.form['host_pass'],
            inbound=int(request.form['host_inbound_id'])
        )
        flash(f"Хост '{request.form['host_name']}' успешно добавлен.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/check-host', methods=['POST'])
    @login_required
    def check_host_route():
        """Проверка соединения с 3x-ui: логин и получение списка inbounds."""
        try:
            host_name = request.form.get('host_name')
            host = get_host(host_name)
            if not host:
                return {'status': 'error', 'message': 'Хост не найден'}, 404
            from shop_bot.modules.xui_api import login_to_host
            api, inbound = login_to_host(host['host_url'], host['host_username'], host['host_pass'], host['host_inbound_id'])
            if not api:
                return {'status': 'error', 'message': 'Не удалось войти в панель'}, 500
            if not inbound:
                return {'status': 'error', 'message': f"Инбаунд ID {host['host_inbound_id']} не найден"}, 400
            return {'status': 'success', 'message': 'Соединение успешно. Инбаунд найден.'}
        except Exception as e:
            logger.error(f"Host check failed: {e}")
            return {'status': 'error', 'message': 'Ошибка проверки'}, 500

    @flask_app.route('/edit-host', methods=['POST'])
    @login_required
    def edit_host_route():
        try:
            old_name = request.form.get('old_host_name')
            new_name = request.form.get('host_name')
            url = request.form.get('host_url')
            user = request.form.get('host_username')
            passwd = request.form.get('host_pass')
            inbound = int(request.form.get('host_inbound_id'))
            ok = update_host(old_name, new_name, url, user, passwd, inbound)
            if ok:
                flash('Хост обновлён.', 'success')
            else:
                flash('Не удалось обновить хост.', 'danger')
        except Exception as e:
            logger.error(f"Edit host failed: {e}")
            flash('Ошибка при обновлении хоста.', 'danger')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/delete-host/<host_name>', methods=['POST'])
    @login_required
    def delete_host_route(host_name):
        delete_host(host_name)
        flash(f"Хост '{host_name}' и все его тарифы были удалены.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/add-plan', methods=['POST'])
    @login_required
    def add_plan_route():
        days_val = int(request.form.get('days', 0) or 0)
        traffic_val = float(request.form.get('traffic_gb', 0) or 0)
        create_plan(
            host_name=request.form['host_name'],
            plan_name=request.form['plan_name'],
            months=int(request.form.get('months', 0) or 0),
            price=float(request.form['price']),
            days=days_val,
            traffic_gb=traffic_val
        )
        flash(f"Новый тариф для хоста '{request.form['host_name']}' добавлен.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/delete-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def delete_plan_route(plan_id):
        delete_plan(plan_id)
        flash("Тариф успешно удален.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/edit-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def edit_plan_route(plan_id):
        from shop_bot.data_manager.database import get_plan_by_id, update_plan
        plan = get_plan_by_id(plan_id)
        if not plan:
            flash("Тариф не найден.", 'error')
            return redirect(url_for('settings_page', tab='servers'))
        plan_name = request.form.get('plan_name', plan['plan_name'])
        months = int(request.form.get('months', plan['months']) or 0)
        days = int(request.form.get('days', plan.get('days', 0)) or 0)
        price = float(request.form.get('price', plan['price']))
        traffic_gb = float(request.form.get('traffic_gb', plan.get('traffic_gb', 0)) or 0)
        update_plan(plan_id, plan_name, months, days, price, traffic_gb)
        flash("Тариф обновлен.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/yookassa-webhook', methods=['POST'])
    def yookassa_webhook_handler():
        try:
            event_json = request.json
            if event_json.get("event") == "payment.succeeded":
                metadata = event_json.get("object", {}).get("metadata", {})
                
                bot = _bot_controller.get_bot_instance()
                payment_processor = handlers.process_successful_payment

                if metadata and bot is not None and payment_processor is not None:
                    loop = current_app.config.get('EVENT_LOOP')
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
                    else:
                        logger.error("YooKassa webhook: Event loop is not available!")
            return 'OK', 200
        except Exception as e:
            logger.error(f"Error in yookassa webhook handler: {e}", exc_info=True)
            return 'Error', 500
        
    @flask_app.route('/cryptobot-webhook', methods=['POST'])
    def cryptobot_webhook_handler():
        try:
            request_data = request.json
            
            if request_data and request_data.get('update_type') == 'invoice_paid':
                payload_data = request_data.get('payload', {})
                
                payload_string = payload_data.get('payload')
                
                if not payload_string:
                    logger.warning("CryptoBot Webhook: Received paid invoice but payload was empty.")
                    return 'OK', 200

                parts = payload_string.split(':')
                if len(parts) < 9:
                    logger.error(f"cryptobot Webhook: Invalid payload format received: {payload_string}")
                    return 'Error', 400

                metadata = {
                    "user_id": parts[0],
                    "months": parts[1],
                    "price": parts[2],
                    "action": parts[3],
                    "key_id": parts[4],
                    "host_name": parts[5],
                    "plan_id": parts[6],
                    "customer_email": parts[7] if parts[7] != 'None' else None,
                    "payment_method": parts[8]
                }
                
                bot = _bot_controller.get_bot_instance()
                loop = current_app.config.get('EVENT_LOOP')
                payment_processor = handlers.process_successful_payment

                if bot and loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
                else:
                    logger.error("cryptobot Webhook: Could not process payment because bot or event loop is not running.")

            return 'OK', 200
            
        except Exception as e:
            logger.error(f"Error in cryptobot webhook handler: {e}", exc_info=True)
            return 'Error', 500
        
    @flask_app.route('/heleket-webhook', methods=['POST'])
    def heleket_webhook_handler():
        try:
            data = request.json
            logger.info(f"Received Heleket webhook: {data}")

            api_key = get_setting("heleket_api_key")
            if not api_key: return 'Error', 500

            sign = data.pop("sign", None)
            if not sign: return 'Error', 400
                
            sorted_data_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
            
            base64_encoded = base64.b64encode(sorted_data_str.encode()).decode()
            raw_string = f"{base64_encoded}{api_key}"
            expected_sign = hashlib.md5(raw_string.encode()).hexdigest()

            if not compare_digest(expected_sign, sign):
                logger.warning("Heleket webhook: Invalid signature.")
                return 'Forbidden', 403

            if data.get('status') in ["paid", "paid_over"]:
                metadata_str = data.get('description')
                if not metadata_str: return 'Error', 400
                
                metadata = json.loads(metadata_str)
                
                bot = _bot_controller.get_bot_instance()
                loop = current_app.config.get('EVENT_LOOP')
                payment_processor = handlers.process_successful_payment

                if bot and loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
            
            return 'OK', 200
        except Exception as e:
            logger.error(f"Error in heleket webhook handler: {e}", exc_info=True)
            return 'Error', 500
        
    @flask_app.route('/ton-webhook', methods=['POST'])
    def ton_webhook_handler():
        try:
            data = request.json
            logger.info(f"Received TonAPI webhook: {data}")

            # Получаем детали транзакции через TonAPI
            if 'tx_hash' in data:
                tx_hash = data['tx_hash']
                account_id = data.get('account_id')
                
                # Запрашиваем детали транзакции
                import requests
                tonapi_key = get_setting('tonapi_key')
                if tonapi_key:
                    try:
                        # Получаем детали транзакции
                        tx_response = requests.get(
                            f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}",
                            headers={"Authorization": f"Bearer {tonapi_key}"}
                        )
                        if tx_response.status_code == 200:
                            tx_details = tx_response.json()
                            logger.info(f"TON Transaction details: {tx_details}")
                            
                            # Ищем входящие сообщения
                            in_msg = tx_details.get('in_msg')
                            if in_msg:
                                amount_nano = int(in_msg.get('value', 0))
                                amount_ton = float(amount_nano / 1_000_000_000)
                                
                                # Игнорируем нулевые транзакции
                                if amount_ton <= 0:
                                    logger.debug(f"Ignoring zero amount transaction: {amount_ton} TON")
                                    return 'OK', 200
                                
                                logger.info(f"TON Transaction amount: {amount_ton} TON")
                                
                                # Ищем pending транзакции с похожей суммой
                                logger.info(f"Searching for pending transaction with amount: {amount_ton} TON")
                                metadata = find_ton_transaction_by_amount(amount_ton)
                                if metadata:
                                    logger.info(f"TON Payment found by amount: {amount_ton} TON, metadata: {metadata}")
                                    
                                    # Обновляем транзакцию с хешем и статусом
                                    from shop_bot.data_manager.database import find_and_complete_ton_transaction
                                    payment_id = metadata.get('payment_id')
                                    if payment_id:
                                        # Обновляем транзакцию с хешем
                                        updated_metadata = find_and_complete_ton_transaction(payment_id, amount_ton, tx_hash)
                                        if updated_metadata:
                                            metadata = updated_metadata
                                        else:
                                            logger.error(f"Failed to complete transaction for payment_id: {payment_id}")
                                            # Попробуем найти транзакцию по сумме как fallback
                                            logger.info(f"Trying fallback search by amount: {amount_ton} TON")
                                            fallback_metadata = find_ton_transaction_by_amount(amount_ton)
                                            if fallback_metadata:
                                                logger.info(f"Found transaction by fallback search, processing payment")
                                                metadata = fallback_metadata
                                                # Обновляем статус напрямую
                                                from shop_bot.data_manager.database import update_transaction_status
                                                update_transaction_status(fallback_metadata.get('payment_id'), 'paid', tx_hash)
                                            else:
                                                logger.error(f"No transaction found even with fallback search")
                                                return 'OK', 200
                                    else:
                                        logger.error("No payment_id found in metadata")
                                        return 'OK', 200
                                    
                                    bot = _bot_controller.get_bot_instance()
                                    loop = current_app.config.get('EVENT_LOOP')
                                    payment_processor = handlers.process_successful_payment

                                    if bot and loop and loop.is_running():
                                        logger.info(f"Processing payment for user {metadata.get('user_id')}")
                                        asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata, tx_hash), loop)
                                    else:
                                        logger.error("Bot or event loop not available for payment processing")
                                else:
                                    logger.warning(f"No pending transaction found for amount: {amount_ton} TON")
                    except Exception as e:
                        logger.error(f"Failed to get transaction details: {e}")
            
            return 'OK', 200
        except Exception as e:
            logger.error(f"Error in ton webhook handler: {e}", exc_info=True)
            return 'Error', 500

    # Запускаем мониторинг TON транзакций при старте приложения
    def start_ton_monitoring_task():
        tonapi_key = get_setting('tonapi_key')
        wallet_address = get_setting('ton_wallet_address')
        ton_monitoring_enabled = get_setting('ton_monitoring_enabled')
        
        # Проверяем, включен ли мониторинг (по умолчанию отключен)
        if ton_monitoring_enabled is None:
            ton_monitoring_enabled = False
        
        # TON мониторинг отключен - используем webhook
        logger.info("TON monitoring disabled - using webhook for payment processing")

    # Тестовый endpoint для проверки мониторинга
    @flask_app.route('/test-ton-monitor', methods=['GET'])
    def test_ton_monitor():
        try:
            tonapi_key = get_setting('tonapi_key')
            wallet_address = get_setting('ton_wallet_address')
            
            if not tonapi_key or not wallet_address:
                return f"TON API key: {bool(tonapi_key)}, Wallet: {bool(wallet_address)}", 200
            
            # Тестируем получение событий
            import requests
            response = requests.get(
                f"https://tonapi.io/v2/accounts/{wallet_address}/events",
                headers={"Authorization": f"Bearer {tonapi_key}"},
                params={"limit": 5}
            )
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                return f"TON Monitor Test: Found {len(events)} events. Bot controller: {bool(_bot_controller)}", 200
            else:
                return f"TON Monitor Test: API Error {response.status_code} - {response.text}", 200
                
        except Exception as e:
            return f"TON Monitor Test Error: {e}", 200

    @flask_app.route('/check-payment', methods=['GET', 'POST'])
    @login_required
    def check_payment():
        """Страница для ручной проверки платежей"""
        result = None
        if request.method == 'POST':
            tx_hash = request.form.get('tx_hash', '').strip()
            if tx_hash:
                try:
                    import requests
                    tonapi_key = get_setting('tonapi_key')
                    if tonapi_key:
                        response = requests.get(
                            f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}",
                            headers={"Authorization": f"Bearer {tonapi_key}"}
                        )
                        if response.status_code == 200:
                            tx_data = response.json()
                            result = {
                                'success': True,
                                'data': tx_data,
                                'amount_ton': 0
                            }
                            # Извлекаем сумму
                            in_msg = tx_data.get('in_msg')
                            if in_msg:
                                amount_nano = int(in_msg.get('value', 0))
                                result['amount_ton'] = float(amount_nano / 1_000_000_000)
                        else:
                            result = {'success': False, 'error': f'API Error: {response.status_code}'}
                    else:
                        result = {'success': False, 'error': 'TON API key not configured'}
                except Exception as e:
                    result = {'success': False, 'error': str(e)}
        
        return render_template('check_payment.html', result=result, **get_common_template_data())

    @flask_app.route('/refresh-transactions', methods=['POST'])
    @login_required
    def refresh_transactions_route():
        """Обновляет статусы транзакций, проверяя TON API"""
        try:
            tonapi_key = get_setting('tonapi_key')
            wallet_address = get_setting('ton_wallet_address')
            
            if not tonapi_key or not wallet_address:
                return {'status': 'error', 'message': 'TON API ключ или адрес кошелька не настроены'}, 400
            
            # Получаем все TON транзакции без transaction_hash
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT transaction_id, payment_id, amount_currency, currency_name, created_date, status
                    FROM transactions 
                    WHERE currency_name = 'TON' AND (transaction_hash IS NULL OR transaction_hash = '')
                    ORDER BY created_date DESC
                    LIMIT 20
                """)
                pending_transactions = cursor.fetchall()
            
            updated_count = 0
            
            for tx in pending_transactions:
                try:
                    # Проверяем транзакцию через TON API
                    import requests
                    url = f"https://tonapi.io/v2/accounts/{wallet_address}/events"
                    headers = {"Authorization": f"Bearer {tonapi_key}"}
                    
                    # Ищем транзакции за последние 24 часа
                    from datetime import datetime, timedelta
                    end_time = int(datetime.now().timestamp())
                    start_time = int((datetime.now() - timedelta(days=1)).timestamp())
                    
                    params = {
                        'start_date': start_time,
                        'end_date': end_time,
                        'limit': 100
                    }
                    
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        events = response.json().get('events', [])
                        
                        for event in events:
                            if event.get('actions'):
                                for action in event['actions']:
                                    if action.get('type') == 'TonTransfer':
                                        amount_nano = int(action.get('TonTransfer', {}).get('amount', 0))
                                        amount_ton = float(amount_nano / 1_000_000_000)
                                        
                                        # Проверяем, соответствует ли сумма
                                        if abs(amount_ton - tx['amount_currency']) < 0.001:  # Допуск 0.001 TON
                                            # Нашли соответствующую транзакцию
                                            tx_hash = event.get('event_id', '').split(':')[0] if ':' in event.get('event_id', '') else event.get('event_id', '')
                                            
                                            # Обновляем статус транзакции
                                            with sqlite3.connect(DB_FILE) as conn:
                                                cursor = conn.cursor()
                                                cursor.execute("""
                                                    UPDATE transactions 
                                                    SET status = 'paid', transaction_hash = ?
                                                    WHERE transaction_id = ?
                                                """, (tx_hash, tx['transaction_id']))
                                                conn.commit()
                                            
                                            updated_count += 1
                                            logger.info(f"Updated transaction {tx['transaction_id']} to paid status with hash {tx_hash}")
                                            break
                                if updated_count > 0:
                                    break
                                    
                except Exception as e:
                    logger.error(f"Error checking transaction {tx['transaction_id']}: {e}")
                    continue
            
            return {'status': 'success', 'message': f'Проверено транзакций: {len(pending_transactions)}, обновлено: {updated_count}'}
            
        except Exception as e:
            logger.error(f"Error refreshing transactions: {e}")
            return {'status': 'error', 'message': f'Ошибка при обновлении: {str(e)}'}, 500

    @flask_app.route('/refresh-keys', methods=['POST'])
    @login_required
    def refresh_keys_route():
        """Обновляет список ключей"""
        try:
            # Синхронизация дат начала/окончания с XUI панелями
            updated = 0
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vpn_keys ORDER BY created_date DESC LIMIT 50")
                keys = [dict(row) for row in cursor.fetchall()]
            
            from shop_bot.modules.xui_api import get_key_details_from_host
            for key in keys:
                try:
                    details = asyncio.run(get_key_details_from_host(key))
                    if details and (details.get('expiry_timestamp_ms') or details.get('status') or details.get('protocol') or details.get('created_at') or details.get('remaining_seconds') is not None or details.get('quota_remaining_bytes') is not None):
                        with sqlite3.connect(DB_FILE) as conn:
                            cursor = conn.cursor()
                            if details.get('expiry_timestamp_ms'):
                                cursor.execute(
                                    "UPDATE vpn_keys SET expiry_date = ? WHERE key_id = ?",
                                    (datetime.fromtimestamp(details['expiry_timestamp_ms']/1000), key['key_id'])
                                )
                            if details.get('created_at'):
                                try:
                                    cursor.execute(
                                        "UPDATE vpn_keys SET start_date = ? WHERE key_id = ?",
                                        (datetime.fromtimestamp(details['created_at']/1000), key['key_id'])
                                    )
                                except Exception:
                                    pass
                            if details.get('status'):
                                cursor.execute(
                                    "UPDATE vpn_keys SET status = ? WHERE key_id = ?",
                                    (details['status'], key['key_id'])
                                )
                            if details.get('protocol'):
                                cursor.execute(
                                    "UPDATE vpn_keys SET protocol = ? WHERE key_id = ?",
                                    (details['protocol'], key['key_id'])
                                )
                            if details.get('remaining_seconds') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET remaining_seconds = ? WHERE key_id = ?",
                                    (details['remaining_seconds'], key['key_id'])
                                )
                            if details.get('quota_remaining_bytes') is not None:
                                try:
                                    cursor.execute(
                                        "ALTER TABLE vpn_keys ADD COLUMN quota_remaining_bytes INTEGER"
                                    )
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET quota_remaining_bytes = ? WHERE key_id = ?",
                                    (details['quota_remaining_bytes'], key['key_id'])
                                )
                            # Кладём также квоту total и down (в байтах) для отображения
                            if details.get('quota_total_gb') is not None:
                                try:
                                    cursor.execute("ALTER TABLE vpn_keys ADD COLUMN quota_total_gb REAL")
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET quota_total_gb = ? WHERE key_id = ?",
                                    (details['quota_total_gb'], key['key_id'])
                                )
                            if details.get('traffic_down_bytes') is not None:
                                try:
                                    cursor.execute("ALTER TABLE vpn_keys ADD COLUMN traffic_down_bytes INTEGER")
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET traffic_down_bytes = ? WHERE key_id = ?",
                                    (details['traffic_down_bytes'], key['key_id'])
                                )
                            conn.commit()
                            updated += 1
                except Exception:
                    continue
            return {'status': 'success', 'message': f'Ключи обновлены: {updated}'}
            
        except Exception as e:
            logger.error(f"Error refreshing keys: {e}")
            return {'status': 'error', 'message': f'Ошибка при обновлении: {str(e)}'}, 500

    # API endpoints для модального окна пользователя
    @flask_app.route('/api/user-payments/<int:user_id>')
    @login_required
    def api_user_payments(user_id):
        """API для получения платежей пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        t.transaction_id,
                        t.amount_rub,
                        t.status,
                        t.created_date,
                        t.metadata,
                        t.amount_currency,
                        t.currency_name,
                        t.payment_method
                    FROM transactions t
                    WHERE t.user_id = ?
                    ORDER BY t.created_date DESC
                """
                cursor.execute(query, (user_id,))
                
                payments = []
                for row in cursor.fetchall():
                    payment = dict(row)
                    
                    # Извлекаем host_name и plan_name из metadata
                    metadata_str = payment.get('metadata')
                    if metadata_str:
                        try:
                            import json
                            metadata = json.loads(metadata_str)
                            payment['host_name'] = metadata.get('host_name', 'N/A')
                            payment['plan_name'] = metadata.get('plan_name', 'N/A')
                            payment['months'] = metadata.get('months', 'N/A')
                            payment['action'] = metadata.get('action', 'N/A')
                        except json.JSONDecodeError:
                            payment['host_name'] = 'Error'
                            payment['plan_name'] = 'Error'
                            payment['months'] = 'Error'
                            payment['action'] = 'Error'
                    else:
                        payment['host_name'] = 'N/A'
                        payment['plan_name'] = 'N/A'
                        payment['months'] = 'N/A'
                        payment['action'] = 'N/A'
                    
                    # Преобразуем created_date в строку для JSON
                    if payment['created_date']:
                        if isinstance(payment['created_date'], str):
                            payment['created_date'] = payment['created_date']
                        else:
                            payment['created_date'] = payment['created_date'].isoformat()
                    payments.append(payment)
                
                return {'payments': payments}
                
        except Exception as e:
            logger.error(f"Error getting user payments: {e}")
            return {'payments': []}, 500

    @flask_app.route('/api/user-keys/<int:user_id>')
    @login_required
    def api_user_keys(user_id):
        """API для получения ключей пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        vk.key_id,
                        vk.host_name,
                        vk.plan_name,
                        vk.price,
                        vk.connection_string,
                        vk.created_date
                    FROM vpn_keys vk
                    WHERE vk.user_id = ?
                    ORDER BY vk.created_date DESC
                """
                cursor.execute(query, (user_id,))
                
                keys = []
                for row in cursor.fetchall():
                    key = dict(row)
                    # Преобразуем created_date в строку для JSON
                    if key['created_date']:
                        if isinstance(key['created_date'], str):
                            key['created_date'] = key['created_date']
                        else:
                            key['created_date'] = key['created_date'].isoformat()
                    keys.append(key)
                
                return {'keys': keys}
                
        except Exception as e:
            logger.error(f"Error getting user keys: {e}")
            return {'keys': []}, 500

    @flask_app.route('/api/user-balance/<int:user_id>')
    @login_required
    def api_user_balance(user_id):
        """API для получения баланса пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
                result = cursor.fetchone()
                balance = float(result['balance']) if result and result['balance'] is not None else 0.0
                
                return {'balance': balance}
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return {'balance': 0.0}, 500

    @flask_app.route('/api/user-earned/<int:user_id>')
    @login_required
    def api_user_earned(user_id):
        """API для получения суммы заработанных денег пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        COALESCE(SUM(t.amount_rub), 0) as total_earned
                    FROM transactions t
                    WHERE t.user_id = ? AND t.status = 'paid'
                """
                cursor.execute(query, (user_id,))
                
                result = cursor.fetchone()
                total_earned = result['total_earned'] if result else 0
                
                return {'earned': total_earned}
        except Exception as e:
            logger.error(f"Error getting user earned amount: {e}")
            return {'earned': 0}, 500

    @flask_app.route('/api/user-notifications/<int:user_id>')
    @login_required
    def api_user_notifications(user_id):
        """API для получения уведомлений пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        notification_id,
                        type,
                        title,
                        message,
                        status,
                        created_date
                    FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_date DESC
                """
                cursor.execute(query, (user_id,))
                
                notifications = []
                for row in cursor.fetchall():
                    notification = dict(row)
                    # Преобразуем created_date в строку для JSON
                    if notification['created_date']:
                        if isinstance(notification['created_date'], str):
                            notification['created_date'] = notification['created_date']
                        else:
                            notification['created_date'] = notification['created_date'].isoformat()
                    notifications.append(notification)
                
                return {'notifications': notifications}
                
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return {'notifications': []}, 500

    # Запускаем мониторинг сразу
    start_ton_monitoring_task()

    return flask_app