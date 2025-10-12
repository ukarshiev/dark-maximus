import os
import logging
import asyncio
import json
import hashlib
import base64
import sqlite3
import requests
import time
from hmac import compare_digest
from datetime import datetime
from datetime import timedelta
from functools import wraps
from math import ceil
from flask import Flask, request, render_template, redirect, url_for, flash, session, current_app, jsonify
from flask_wtf.csrf import CSRFProtect
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем путь к базе данных
PROJECT_ROOT = Path("/app/project")
DB_FILE = PROJECT_ROOT / "users.db"

from shop_bot.modules import xui_api
from shop_bot.bot import handlers 
from shop_bot.security import rate_limit, get_client_ip
from shop_bot.security.validators import InputValidator, ValidationError
from shop_bot.utils import handle_exceptions
from shop_bot.data_manager.database import (
    get_all_settings, update_setting, get_all_hosts, get_plans_for_host,
    create_host, delete_host, create_plan, delete_plan, get_user_count,
    get_total_keys_count, get_total_earned_sum, get_total_notifications_count, get_daily_stats_for_charts,
    get_recent_transactions, get_paginated_transactions, get_all_users, get_user_keys,
    ban_user, unban_user, delete_user_keys, get_setting, get_global_domain, find_and_complete_ton_transaction, find_ton_transaction_by_amount,
    get_paginated_keys, get_plan_by_id, update_plan, get_host, update_host, revoke_user_consent,
    search_users as db_search_users, add_to_user_balance, log_transaction, get_user, get_notification_by_id,
    verify_admin_credentials, hash_password, get_all_promo_codes, create_promo_code, update_promo_code,
    delete_promo_code, get_promo_code, get_promo_code_usage_history, get_all_plans, can_user_use_promo_code,
    get_user_promo_codes, validate_promo_code, remove_user_promo_code_usage, can_delete_promo_code
)
from shop_bot.data_manager.scheduler import send_subscription_notification
from shop_bot.ton_monitor import start_ton_monitoring

_bot_controller = None

ALL_SETTINGS_KEYS = [
    "panel_login", "panel_password", "about_text", "terms_url", "privacy_url",
    "support_user", "support_text", "channel_url", "telegram_bot_token",
    "telegram_bot_username", "admin_telegram_id", "yookassa_shop_id",
    "yookassa_secret_key", "yookassa_test_mode", "yookassa_test_shop_id", 
    "yookassa_test_secret_key", "yookassa_api_url", "yookassa_test_api_url", "yookassa_verify_ssl", "yookassa_test_verify_ssl", "sbp_enabled", "receipt_email", "cryptobot_token",
    "stars_enabled", "stars_conversion_rate",
    "heleket_merchant_id", "heleket_api_key", "domain", "global_domain", "referral_percentage",
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
    
    # Безопасное получение секретного ключа из переменных окружения
    import secrets
    flask_app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
    
    # Настройка постоянного хранения сессий в файловой системе
    flask_app.config['SESSION_TYPE'] = 'filesystem'
    flask_app.config['SESSION_FILE_DIR'] = '/app/sessions'
    flask_app.config['SESSION_PERMANENT'] = True
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Сессия на 30 дней
    
    # Настройка CSRF защиты
    csrf = CSRFProtect(flask_app)
    flask_app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Отключаем по умолчанию
    flask_app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 час
    flask_app.config['WTF_CSRF_SSL_STRICT'] = False  # Для разработки
    
    # Инициализация файловой сессии
    from flask_session import Session
    os.makedirs('/app/sessions', exist_ok=True)
    Session(flask_app)

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
        from shop_bot.data_manager.database import get_ton_manifest
        import json
        manifest_data = get_ton_manifest()
        return json.dumps(manifest_data, ensure_ascii=False, indent=2), 200, {'Content-Type': 'application/json'}

    @flask_app.route('/login', methods=['GET', 'POST'])
    @rate_limit('per_minute', 10, "Too many login attempts. Please try again later.")
    def login_page():
        settings = get_all_settings()
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if verify_admin_credentials(username, password):
                session['logged_in'] = True
                session.permanent = True  # Делаем сессию постоянной
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
        hosts = get_all_hosts()
        stats = {
            "user_count": get_user_count(),
            "total_keys": get_total_keys_count(),
            "total_spent": get_total_earned_sum(),
            "host_count": len(hosts),
            "total_notifications": get_total_notifications_count()
        }
        logging.info(f"Dashboard stats: {stats}")
        
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

    @flask_app.route('/api/transaction/<int:transaction_id>')
    @login_required
    def get_transaction_details(transaction_id):
        """API endpoint для получения детальной информации о транзакции"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        transaction_id,
                        payment_id,
                        user_id,
                        username,
                        status,
                        amount_rub,
                        amount_currency,
                        currency_name,
                        payment_method,
                        metadata,
                        transaction_hash,
                        payment_link,
                        created_date
                    FROM transactions
                    WHERE transaction_id = ?
                """, (transaction_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    return jsonify({
                        'status': 'error',
                        'message': 'Транзакция не найдена'
                    }), 404
                
                # Преобразуем Row в dict
                transaction = dict(row)
                
                # Парсим metadata если это строка
                if transaction.get('metadata'):
                    try:
                        transaction['metadata'] = json.loads(transaction['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        transaction['metadata'] = {}
                
                return jsonify({
                    'status': 'success',
                    'transaction': transaction
                })
                
        except Exception as e:
            logging.error(f"Error fetching transaction {transaction_id}: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Ошибка при загрузке данных транзакции'
            }), 500

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

    @flask_app.route('/promo-codes')
    @login_required
    def promo_codes_page():
        common_data = get_common_template_data()
        return render_template('promo_codes.html', **common_data)

    @flask_app.route('/settings', methods=['GET'])
    @login_required
    def settings_page():
        current_settings = get_all_settings()
        hosts = get_all_hosts()
        for host in hosts:
            host['plans'] = get_plans_for_host(host['host_name'])
        
        # Получаем активную вкладку из параметра URL
        active_tab = request.args.get('tab', 'servers')
        
        # Получаем настройки контента для модальных окон
        about_content = current_settings.get('about_text', '')
        support_content = current_settings.get('support_text', '')
        
        # Для terms и privacy используем наши внутренние страницы
        terms_content = request.url_root.rstrip('/') + '/terms'
        privacy_content = request.url_root.rstrip('/') + '/privacy'
        
        common_data = get_common_template_data()
        return render_template('settings.html', 
                             settings=current_settings, 
                             hosts=hosts, 
                             active_tab=active_tab,
                             about_content=about_content,
                             support_content=support_content,
                             terms_content=terms_content,
                             privacy_content=privacy_content,
                             **common_data)

    @flask_app.route('/settings/panel', methods=['POST'])
    @login_required
    def save_panel_settings():
        """Сохранение настроек панели - v2.1"""
        panel_keys = ['panel_login', 'global_domain']
        
        # Пароль отдельно, если указан
        if 'panel_password' in request.form and request.form.get('panel_password'):
            new_password = request.form.get('panel_password').strip()
            if new_password:
                hashed_password = hash_password(new_password)
                update_setting('panel_password', hashed_password)
        
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
            'yookassa_test_shop_id', 'yookassa_test_secret_key', 'yookassa_api_url', 'yookassa_test_api_url',
            'cryptobot_token', 'heleket_merchant_id', 'heleket_api_key', 'domain', 'global_domain',
            'ton_wallet_address', 'tonapi_key', 'stars_conversion_rate'
        ]
        
        payment_checkboxes = ['sbp_enabled', 'stars_enabled', 'yookassa_test_mode', 'yookassa_verify_ssl', 'yookassa_test_verify_ssl']
        
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

    @flask_app.route('/save-ton-manifest-settings', methods=['POST'])
    @login_required
    def save_ton_manifest_settings():
        """Сохранение настроек Ton Connect манифеста"""
        try:
            ton_manifest_keys = [
                'ton_manifest_name', 'app_url', 'ton_manifest_icon_url',
                'ton_manifest_terms_url', 'ton_manifest_privacy_url'
            ]
            
            # Сохраняем каждую настройку
            for key in ton_manifest_keys:
                value = request.form.get(key, '')
                update_setting(key, value)
            
            return {'success': True, 'message': 'Настройки Ton Connect манифеста успешно сохранены'}, 200
            
        except Exception as e:
            logger.error(f"Error saving Ton manifest settings: {e}")
            return {'success': False, 'message': f'Ошибка при сохранении: {str(e)}'}, 500

    @flask_app.route('/upload-ton-icon', methods=['POST'])
    @login_required
    def upload_ton_icon():
        """Загрузка иконки для Ton Connect манифеста"""
        try:
            from werkzeug.utils import secure_filename
            import os
            from pathlib import Path
            
            # Проверяем, что файл был загружен
            if 'icon' not in request.files:
                return {'success': False, 'message': 'Файл не найден'}, 400
            
            file = request.files['icon']
            if file.filename == '':
                return {'success': False, 'message': 'Файл не выбран'}, 400
            
            # Проверяем расширение файла
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if not ('.' in file.filename and 
                   file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                return {'success': False, 'message': 'Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP'}, 400
            
            # Создаем папку для иконок, если её нет
            icons_dir = Path('/app/project/src/shop_bot/webhook_server/static/icons')
            icons_dir.mkdir(exist_ok=True)
            
            # Генерируем уникальное имя файла
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            unique_filename = f"ton_icon_{int(time.time())}{ext}"
            
            # Сохраняем файл
            file_path = icons_dir / unique_filename
            file.save(file_path)
            
            # Генерируем полный URL для доступа к файлу
            # Получаем домен из настроек или используем текущий хост
            domain = get_global_domain()
            icon_url = f"{domain}/static/icons/{unique_filename}"
            
            # Сохраняем URL в настройках
            update_setting('ton_manifest_icon_url', icon_url)
            
            return {
                'success': True, 
                'message': 'Иконка успешно загружена',
                'icon_url': icon_url
            }, 200
            
        except Exception as e:
            logger.error(f"Error uploading Ton icon: {e}")
            return {'success': False, 'message': f'Ошибка при загрузке: {str(e)}'}, 500

    @flask_app.route('/api/get-ton-manifest-data', methods=['GET'])
    @login_required
    def get_ton_manifest_data():
        """Получение актуальных данных Ton Connect манифеста для формы редактирования"""
        try:
            from shop_bot.data_manager.database import get_ton_manifest
            manifest_data = get_ton_manifest()
            
            logger.info(f"Ton manifest data: {manifest_data}")
            
            return {
                'success': True,
                'data': manifest_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting Ton manifest data: {e}")
            return {'success': False, 'message': f'Ошибка при загрузке данных: {str(e)}'}, 500

    @flask_app.route('/save-content-setting', methods=['POST'])
    @login_required
    def save_content_setting():
        """Сохранение отдельной настройки контента через AJAX"""
        try:
            # Получаем все данные из формы
            form_data = request.form.to_dict()
            
            # Сохраняем каждую настройку
            for field_name, value in form_data.items():
                if field_name in ['about_content', 'support_content', 'terms_content', 'privacy_content']:
                    # Преобразуем названия полей в названия настроек
                    setting_name = field_name.replace('_content', '_text') if field_name in ['about_content', 'support_content'] else field_name.replace('_content', '_url')
                    update_setting(setting_name, value)
            
            return {'status': 'success', 'message': 'Настройка сохранена'}, 200
            
        except Exception as e:
            logger.error(f"Error saving content setting: {e}")
            return {'status': 'error', 'message': 'Ошибка при сохранении'}, 500

    # Старый endpoint для совместимости (удалим позже)
    @flask_app.route('/settings/legacy', methods=['POST'])
    @login_required
    def legacy_settings():
        if 'panel_password' in request.form and request.form.get('panel_password'):
            new_password = request.form.get('panel_password').strip()
            if new_password:
                hashed_password = hash_password(new_password)
                update_setting('panel_password', hashed_password)

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

    @flask_app.route('/dev')
    @login_required
    def dev_page():
        """DevPage - страница разработчика с навигацией по разделам"""
        # Перенаправляем на страницу версий по умолчанию
        return redirect(url_for('versions_page_new'))

    @flask_app.route('/versions', methods=['GET', 'POST'], endpoint='versions_page_new')
    @login_required
    def versions_page_new():
        """Страница истории изменений (версий)"""
        def resolve_changelog_path():
            try:
                candidates = [
                    PROJECT_ROOT / 'CHANGELOG.md',
                    Path.cwd() / 'CHANGELOG.md',
                    Path.cwd().parent / 'CHANGELOG.md'
                ]
                for path in candidates:
                    if path.exists():
                        return path
                # Создаём файл в корне проекта
                changelog_path = PROJECT_ROOT / 'CHANGELOG.md'
                changelog_path.parent.mkdir(parents=True, exist_ok=True)
                return changelog_path
            except Exception as e:
                logger.error(f"Failed to resolve changelog path: {e}")
                return PROJECT_ROOT / 'CHANGELOG.md'

        # POST: сохраняем изменения
        if request.method == 'POST':
            try:
                changelog_path = resolve_changelog_path()
                new_content = request.form.get('changelog_content', '')
                # Безопасно перезаписываем файл (создаём при отсутствии)
                with open(changelog_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                flash('CHANGELOG.md обновлён.', 'success')
                return redirect(url_for('versions_page_new'))
            except Exception as e:
                logger.error(f"Failed to write CHANGELOG.md: {e}")
                flash('Не удалось сохранить изменения.', 'danger')

        # GET: читаем changelog (создаём, если отсутствует)
        try:
            changelog_path = resolve_changelog_path()
            if changelog_path.exists():
                with open(changelog_path, 'r', encoding='utf-8') as f:
                    changelog_text = f.read()
            else:
                changelog_text = ''
        except Exception as e:
            logger.error(f"Failed to read CHANGELOG.md: {e}")
            changelog_text = ''

        # Общие данные для шаблонов (боты/режим/версия)
        common_data = get_common_template_data()
        return render_template('versions.html', changelog_text=changelog_text, **common_data)

    @flask_app.route('/demo')
    @login_required
    def demo_page():
        """Демо страница с элементами интерфейса"""
        common_data = get_common_template_data()
        return render_template('demo.html', **common_data)

    @flask_app.route('/terms')
    def terms_page():
        """Страница условий использования"""
        from datetime import datetime
        current_date = datetime.now().strftime('%d.%m.%Y')
        return render_template('terms.html', current_date=current_date)

    @flask_app.route('/privacy')
    def privacy_page():
        """Страница политики конфиденциальности"""
        from datetime import datetime
        current_date = datetime.now().strftime('%d.%m.%Y')
        return render_template('privacy.html', current_date=current_date)

    @flask_app.route('/edit-terms', methods=['GET', 'POST'])
    @login_required
    def edit_terms_page():
        """Редактирование страницы условий использования"""
        from pathlib import Path
        
        def get_terms_file_path():
            return PROJECT_ROOT / 'src' / 'shop_bot' / 'webhook_server' / 'templates' / 'terms.html'
        
        if request.method == 'POST':
            try:
                new_content = request.form.get('terms_content', '')
                file_path = get_terms_file_path()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                flash('Страница условий использования обновлена.', 'success')
                return redirect(url_for('edit_terms_page'))
            except Exception as e:
                logger.error(f"Failed to save terms page: {e}")
                flash('Не удалось сохранить изменения.', 'danger')
        
        # GET: читаем содержимое файла
        try:
            file_path = get_terms_file_path()
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    terms_content = f.read()
            else:
                terms_content = ''
        except Exception as e:
            logger.error(f"Failed to read terms file: {e}")
            terms_content = ''
        
        return render_template('edit_terms.html', terms_content=terms_content, **get_common_template_data())

    @flask_app.route('/edit-privacy', methods=['GET', 'POST'])
    @login_required
    def edit_privacy_page():
        """Редактирование страницы политики конфиденциальности"""
        from pathlib import Path
        
        def get_privacy_file_path():
            return PROJECT_ROOT / 'src' / 'shop_bot' / 'webhook_server' / 'templates' / 'privacy.html'
        
        if request.method == 'POST':
            try:
                new_content = request.form.get('privacy_content', '')
                file_path = get_privacy_file_path()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                flash('Страница политики конфиденциальности обновлена.', 'success')
                return redirect(url_for('edit_privacy_page'))
            except Exception as e:
                logger.error(f"Failed to save privacy page: {e}")
                flash('Не удалось сохранить изменения.', 'danger')
        
        # GET: читаем содержимое файла
        try:
            file_path = get_privacy_file_path()
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    privacy_content = f.read()
            else:
                privacy_content = ''
        except Exception as e:
            logger.error(f"Failed to read privacy file: {e}")
            privacy_content = ''
        
        return render_template('edit_privacy.html', privacy_content=privacy_content, **get_common_template_data())

    @flask_app.route('/api/get-terms-content')
    @login_required
    def get_terms_content():
        """API для получения контента страницы условий использования"""
        from pathlib import Path
        
        try:
            file_path = PROJECT_ROOT / 'src' / 'shop_bot' / 'webhook_server' / 'templates' / 'terms.html'
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = ''
            return jsonify({'content': content})
        except Exception as e:
            logger.error(f"Failed to read terms file: {e}")
            return jsonify({'content': ''}), 500

    @flask_app.route('/api/get-privacy-content')
    @login_required
    def get_privacy_content():
        """API для получения контента страницы политики конфиденциальности"""
        from pathlib import Path
        
        try:
            file_path = PROJECT_ROOT / 'src' / 'shop_bot' / 'webhook_server' / 'templates' / 'privacy.html'
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = ''
            return jsonify({'content': content})
        except Exception as e:
            logger.error(f"Failed to read privacy file: {e}")
            return jsonify({'content': ''}), 500

    @flask_app.route('/debug')
    @login_required
    def debug_page():
        """Страница отладки"""
        common_data = get_common_template_data()
        return render_template('debug.html', **common_data)

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

        # Активная вкладка и режим (text/video)
        active_tab = request.args.get('tab', 'android')
        mode = request.args.get('mode', 'text')
        
        logger.info(f"Instructions page: tab={active_tab}, mode={mode}")
        
        # Если mode='video', показываем видеоинструкции
        if mode == 'video':
            from shop_bot.data_manager.database import get_all_video_instructions
            videos = get_all_video_instructions()
            logger.info(f"Video mode: found {len(videos)} videos")
            common_data = get_common_template_data()
            return render_template(
                'instructions.html',
                mode='video',
                videos=videos,
                active_tab='video',
                **common_data
            )

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
            mode='text',
            active_tab=active_tab,
            instructions_text=instructions_text,
            **get_common_template_data()
        )

    # ============================================
    # API для работы с видеоинструкциями
    # ============================================
    
    @flask_app.route('/api/video/<int:video_id>', methods=['GET'])
    @login_required
    def get_video_api(video_id):
        """Получение данных видеоинструкции"""
        from shop_bot.data_manager.database import get_video_instruction_by_id
        
        video = get_video_instruction_by_id(video_id)
        if video:
            return jsonify(video), 200
        return jsonify({'error': 'Video not found'}), 404
    
    @flask_app.route('/api/video/create', methods=['POST'])
    @login_required
    def create_video_api():
        """Создание новой видеоинструкции"""
        from shop_bot.data_manager.database import create_video_instruction
        from werkzeug.utils import secure_filename
        import uuid
        import os
        
        try:
            title = request.form.get('title', '').strip()
            if not title:
                return jsonify({'success': False, 'message': 'Название обязательно'}), 400
            
            video_file = request.files.get('video')
            if not video_file:
                return jsonify({'success': False, 'message': 'Видеофайл обязателен'}), 400
            
            # Генерируем уникальное имя файла
            video_ext = os.path.splitext(secure_filename(video_file.filename))[1]
            video_filename = f"video_{uuid.uuid4().hex}{video_ext}"
            
            # Путь для сохранения
            video_dir = PROJECT_ROOT / 'video_instructions' / 'videos'
            video_dir.mkdir(parents=True, exist_ok=True)
            video_path = video_dir / video_filename
            
            # Сохраняем видео
            video_file.save(str(video_path))
            
            # Получаем размер файла
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            
            # Обрабатываем превью, если есть
            poster_filename = None
            poster_file = request.files.get('poster')
            if poster_file and poster_file.filename:
                poster_ext = os.path.splitext(secure_filename(poster_file.filename))[1]
                poster_filename = f"poster_{uuid.uuid4().hex}{poster_ext}"
                poster_dir = PROJECT_ROOT / 'video_instructions' / 'posters'
                poster_dir.mkdir(parents=True, exist_ok=True)
                poster_path = poster_dir / poster_filename
                poster_file.save(str(poster_path))
            
            # Создаем запись в БД
            video_id = create_video_instruction(
                title=title,
                filename=video_filename,
                poster_filename=poster_filename,
                file_size_mb=file_size_mb
            )
            
            if video_id:
                return jsonify({'success': True, 'video_id': video_id}), 200
            else:
                return jsonify({'success': False, 'message': 'Ошибка создания записи в БД'}), 500
                
        except Exception as e:
            logger.error(f"Error creating video: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @flask_app.route('/api/video/<int:video_id>', methods=['POST'])
    @login_required
    def update_video_api(video_id):
        """Обновление видеоинструкции"""
        from shop_bot.data_manager.database import (
            update_video_instruction, 
            get_video_instruction_by_id
        )
        from werkzeug.utils import secure_filename
        import uuid
        import os
        
        try:
            video = get_video_instruction_by_id(video_id)
            if not video:
                return jsonify({'success': False, 'message': 'Видео не найдено'}), 404
            
            title = request.form.get('title', '').strip()
            if not title:
                return jsonify({'success': False, 'message': 'Название обязательно'}), 400
            
            updates = {'title': title}
            
            # Обновляем видео, если загружено новое
            video_file = request.files.get('video')
            if video_file and video_file.filename:
                # Удаляем старый файл
                if video['filename']:
                    old_video_path = PROJECT_ROOT / 'video_instructions' / 'videos' / video['filename']
                    if old_video_path.exists():
                        old_video_path.unlink()
                
                # Сохраняем новый
                video_ext = os.path.splitext(secure_filename(video_file.filename))[1]
                video_filename = f"video_{uuid.uuid4().hex}{video_ext}"
                video_dir = PROJECT_ROOT / 'video_instructions' / 'videos'
                video_path = video_dir / video_filename
                video_file.save(str(video_path))
                
                file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
                updates['filename'] = video_filename
                updates['file_size_mb'] = file_size_mb
            
            # Обновляем превью, если загружено новое
            poster_file = request.files.get('poster')
            if poster_file and poster_file.filename:
                # Удаляем старое превью
                if video['poster_filename']:
                    old_poster_path = PROJECT_ROOT / 'video_instructions' / 'posters' / video['poster_filename']
                    if old_poster_path.exists():
                        old_poster_path.unlink()
                
                # Сохраняем новое
                poster_ext = os.path.splitext(secure_filename(poster_file.filename))[1]
                poster_filename = f"poster_{uuid.uuid4().hex}{poster_ext}"
                poster_dir = PROJECT_ROOT / 'video_instructions' / 'posters'
                poster_path = poster_dir / poster_filename
                poster_file.save(str(poster_path))
                
                updates['poster_filename'] = poster_filename
            
            # Обновляем запись в БД
            success = update_video_instruction(video_id, **updates)
            
            if success:
                return jsonify({'success': True}), 200
            else:
                return jsonify({'success': False, 'message': 'Ошибка обновления'}), 500
                
        except Exception as e:
            logger.error(f"Error updating video: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @flask_app.route('/api/video/<int:video_id>', methods=['DELETE'])
    @login_required
    def delete_video_api(video_id):
        """Удаление видеоинструкции"""
        from shop_bot.data_manager.database import (
            delete_video_instruction,
            get_video_instruction_by_id
        )
        
        try:
            video = get_video_instruction_by_id(video_id)
            if not video:
                return jsonify({'success': False, 'message': 'Видео не найдено'}), 404
            
            # Удаляем файлы
            if video['filename']:
                video_path = PROJECT_ROOT / 'video_instructions' / 'videos' / video['filename']
                if video_path.exists():
                    video_path.unlink()
            
            if video['poster_filename']:
                poster_path = PROJECT_ROOT / 'video_instructions' / 'posters' / video['poster_filename']
                if poster_path.exists():
                    poster_path.unlink()
            
            # Удаляем запись из БД
            success = delete_video_instruction(video_id)
            
            if success:
                return jsonify({'success': True}), 200
            else:
                return jsonify({'success': False, 'message': 'Ошибка удаления из БД'}), 500
                
        except Exception as e:
            logger.error(f"Error deleting video: {e}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @flask_app.route('/video/player/<int:video_id>')
    def video_player(video_id):
        """Страница видеоплеера (fullscreen для Telegram WebView)"""
        from shop_bot.data_manager.database import get_video_instruction_by_id
        
        video = get_video_instruction_by_id(video_id)
        return render_template('video_player.html', video=video)
    
    @flask_app.route('/video/embed/<int:video_id>')
    def video_embed(video_id):
        """Встраиваемая версия видеоплеера (для iframe)"""
        from shop_bot.data_manager.database import get_video_instruction_by_id
        
        video = get_video_instruction_by_id(video_id)
        return render_template('video_embed.html', video=video)
    
    @flask_app.route('/video_instructions/<path:subpath>')
    def serve_video_files(subpath):
        """Отдача статических файлов видео и превью"""
        from flask import send_from_directory
        
        video_instructions_dir = PROJECT_ROOT / 'video_instructions'
        return send_from_directory(video_instructions_dir, subpath)

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
        failed_keys = []
        
        logger.info(f"Revoking all keys for user {user_id}, found {len(keys_to_revoke)} keys")
        
        for key in keys_to_revoke:
            logger.info(f"Processing key {key['key_id']} for user {user_id} on host {key['host_name']} with email {key['key_email']} and UUID {key.get('xui_client_uuid', 'Unknown')}")
            
            # Сначала пробуем удалить по UUID с конкретного хоста
            result = False
            if key.get('xui_client_uuid') and key.get('xui_client_uuid') != 'Unknown':
                try:
                    # Прямое удаление по UUID с конкретного хоста
                    host_data = get_host(key['host_name'])
                    if host_data:
                        api, inbound = xui_api.login_to_host(
                            host_url=host_data['host_url'],
                            username=host_data['host_username'],
                            password=host_data['host_pass'],
                            inbound_id=host_data['host_inbound_id']
                        )
                        if api and inbound:
                            api.client.delete(inbound.id, key['xui_client_uuid'])
                            result = True
                            logger.info(f"Successfully deleted key {key['key_id']} by UUID from host {key['host_name']}")
                except Exception as e:
                    logger.warning(f"Failed to delete key {key['key_id']} by UUID from host {key['host_name']}: {e}")
            
            # Если удаление по UUID не удалось, пробуем через общую функцию
            if not result:
                result = asyncio.run(xui_api.delete_client_on_host(
                    host_name=key['host_name'], 
                    client_email=key['key_email'],
                    client_uuid=key.get('xui_client_uuid') or None
                ))
            
            if result:
                success_count += 1
                logger.info(f"Successfully deleted key {key['key_id']} from host {key['host_name']}")
            else:
                failed_keys.append(f"{key['host_name']}:{key['key_email']}")
                logger.warning(f"Failed to delete key {key['key_id']} from host {key['host_name']}")
        
        # Удаляем ключи из базы данных только если они были успешно удалены с серверов
        if success_count > 0:
            delete_user_keys(user_id)
            logger.info(f"Deleted {success_count} keys from database for user {user_id}")
        
        if success_count == len(keys_to_revoke):
            flash(f"Все {len(keys_to_revoke)} ключей для пользователя {user_id} были успешно отозваны.", 'success')
        else:
            message = f"Удалось отозвать {success_count} из {len(keys_to_revoke)} ключей для пользователя {user_id}."
            if failed_keys:
                message += f" Не удалось удалить: {', '.join(failed_keys)}"
            flash(message, 'warning')

        return redirect(url_for('users_page'))


    @flask_app.route('/users/reset-trial/<int:user_id>', methods=['POST'])
    @login_required
    def reset_trial_route(user_id):
        """Сбрасывает флаг использования триала для повторного использования"""
        try:
            from shop_bot.data_manager.database import reset_trial_used, increment_trial_reuses
            reset_trial_used(user_id)
            increment_trial_reuses(user_id)
            flash(f"Пользователю {user_id} разрешено повторное использование триала.", 'success')
        except Exception as e:
            logger.error(f"Error resetting trial for user {user_id}: {e}")
            flash(f"Ошибка при сбросе триала для пользователя {user_id}.", 'error')
        
        return redirect(url_for('users_page'))

    @flask_app.route('/admin/trial-reset', methods=['POST'])
    @login_required
    def admin_trial_reset_route():
        """Админская функция полного сброса триала пользователя"""
        try:
            # Проверяем, это JSON запрос или обычная форма
            if request.is_json:
                data = request.get_json()
                telegram_id = data.get('telegram_id')
                confirm_reset = True  # Для JSON запросов подтверждение уже проверено на фронтенде
            else:
                telegram_id = request.form.get('telegram_id')
                confirm_reset = request.form.get('confirm_reset')
            
            if not telegram_id:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'Telegram ID не указан'}), 400
                else:
                    flash('Telegram ID не указан', 'error')
                    return redirect(url_for('users_page'))
            
            if not request.is_json and not confirm_reset:
                flash('Необходимо подтвердить понимание последствий', 'error')
                return redirect(url_for('users_page'))
            
            try:
                telegram_id = int(telegram_id)
            except ValueError:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'Неверный формат Telegram ID'}), 400
                else:
                    flash('Неверный формат Telegram ID', 'error')
                    return redirect(url_for('users_page'))
            
            # Проверяем, существует ли пользователь
            from shop_bot.data_manager.database import get_user, admin_reset_trial_completely
            user = get_user(telegram_id)
            
            if not user:
                if request.is_json:
                    return jsonify({'success': False, 'message': f'Пользователь с ID {telegram_id} не найден'}), 404
                else:
                    flash(f'Пользователь с ID {telegram_id} не найден', 'error')
                    return redirect(url_for('users_page'))
            
            # Выполняем сброс триала
            success = admin_reset_trial_completely(telegram_id)
            
            if success:
                message = f'Триал для пользователя {telegram_id} (@{user.get("username", "N/A")}) успешно сброшен. Пользователь сможет заново получить пробный период.'
                logger.info(f"Admin reset trial for user {telegram_id} (@{user.get('username', 'N/A')})")
                
                if request.is_json:
                    return jsonify({'success': True, 'message': message})
                else:
                    flash(message, 'success')
            else:
                message = f'Ошибка при сбросе триала для пользователя {telegram_id}'
                if request.is_json:
                    return jsonify({'success': False, 'message': message}), 500
                else:
                    flash(message, 'error')
                
        except Exception as e:
            logger.error(f"Error in admin trial reset: {e}")
            message = 'Произошла ошибка при выполнении операции'
            if request.is_json:
                return jsonify({'success': False, 'message': message}), 500
            else:
                flash(message, 'error')
        
        return redirect(url_for('users_page'))

    @flask_app.route('/add-host', methods=['POST'])
    @login_required
    def add_host_route():
        try:
            # Валидируем данные хоста
            host_data = InputValidator.validate_host_data({
                'host_name': request.form.get('host_name'),
                'host_url': request.form.get('host_url'),
                'host_username': request.form.get('host_username'),
                'host_pass': request.form.get('host_pass'),
                'host_inbound_id': request.form.get('host_inbound_id')
            })
            
            # Получаем host_code из формы (если не указан, create_host сгенерирует автоматически)
            host_code = request.form.get('host_code', '').strip()
            
            create_host(
                name=host_data['host_name'],
                url=host_data['host_url'],
                user=host_data['host_username'],
                passwd=host_data['host_pass'],
                inbound=host_data['host_inbound_id'],
                host_code=host_code if host_code else None
            )
            flash(f"Хост '{host_data['host_name']}' успешно добавлен.", 'success')
        except ValidationError as e:
            flash(f"Ошибка валидации: {e}", 'error')
        except Exception as e:
            logger.error(f"Error adding host: {e}")
            flash(f"Ошибка при добавлении хоста: {e}", 'error')
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
            # Получаем host_code из формы (если не указан, update_host сгенерирует автоматически)
            host_code = request.form.get('host_code', '').strip()
            ok = update_host(old_name, new_name, url, user, passwd, inbound, host_code if host_code else None)
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
        try:
            # Валидируем данные тарифа
            plan_data = InputValidator.validate_plan_data({
                'plan_name': request.form.get('plan_name'),
                'months': request.form.get('months', 0),
                'days': request.form.get('days', 0),
                'hours': request.form.get('hours', 0),
                'price': request.form.get('price'),
                'traffic_gb': request.form.get('traffic_gb', 0)
            })
            
            # Валидируем имя хоста
            host_name = InputValidator.validate_string(
                request.form.get('host_name'), 'host_name', min_length=1, max_length=100
            )
            
            # Получаем режим предоставления ключа
            key_provision_mode = request.form.get('key_provision_mode', 'key')
            if key_provision_mode not in ['key', 'subscription', 'both']:
                key_provision_mode = 'key'
            
            # Получаем режим отображения
            display_mode = request.form.get('display_mode', 'all')
            if display_mode not in ['all', 'hidden_all', 'hidden_new', 'hidden_old']:
                display_mode = 'all'
            
            create_plan(
                host_name=host_name,
                plan_name=plan_data['plan_name'],
                months=plan_data['months'],
                price=plan_data['price'],
                days=plan_data['days'],
                traffic_gb=plan_data['traffic_gb'],
                hours=plan_data['hours'],
                key_provision_mode=key_provision_mode,
                display_mode=display_mode
            )
            flash(f"Новый тариф для хоста '{host_name}' добавлен.", 'success')
        except ValidationError as e:
            logger.error(f"Validation error when adding plan: {e}")
            flash(f"Ошибка валидации: {e}", 'error')
        except Exception as e:
            logger.error(f"Error adding plan: {e}")
            flash(f"Ошибка при добавлении тарифа: {e}", 'error')
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
        hours = int(request.form.get('hours', plan.get('hours', 0)) or 0)
        price = float(request.form.get('price', plan['price']))
        traffic_gb = float(request.form.get('traffic_gb', plan.get('traffic_gb', 0)) or 0)
        
        # Получаем режим предоставления ключа
        key_provision_mode = request.form.get('key_provision_mode', plan.get('key_provision_mode', 'key'))
        if key_provision_mode not in ['key', 'subscription', 'both']:
            key_provision_mode = 'key'
        
        # Получаем режим отображения
        display_mode = request.form.get('display_mode', plan.get('display_mode', 'all'))
        if display_mode not in ['all', 'hidden_all', 'hidden_new', 'hidden_old']:
            display_mode = 'all'
        
        update_plan(plan_id, plan_name, months, days, price, traffic_gb, hours, key_provision_mode, display_mode)
        flash("Тариф обновлен.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/yookassa-webhook', methods=['POST'])
    def yookassa_webhook_handler():
        try:
            event_json = request.json
            if event_json.get("event") == "payment.succeeded":
                payment_object = event_json.get("object", {})
                metadata = payment_object.get("metadata", {})
                
                # Извлекаем дополнительные данные YooKassa
                yookassa_payment_id = payment_object.get("id")
                authorization_details = payment_object.get("authorization_details", {})
                rrn = authorization_details.get("rrn")
                auth_code = authorization_details.get("auth_code")
                
                # Получаем способ оплаты
                payment_method = payment_object.get("payment_method", {})
                payment_type = payment_method.get("type", "unknown")
                
                # Обновляем метаданные с дополнительной информацией
                metadata.update({
                    "yookassa_payment_id": yookassa_payment_id,
                    "rrn": rrn,
                    "authorization_code": auth_code,
                    "payment_type": payment_type
                })
                
                bot = _bot_controller.get_bot_instance()
                payment_processor = handlers.process_successful_yookassa_payment

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
            errors = []  # Список для сбора ошибок
            
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
                            if details.get('enabled') is not None:
                                try:
                                    cursor.execute("ALTER TABLE vpn_keys ADD COLUMN enabled INTEGER DEFAULT 1")
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET enabled = ? WHERE key_id = ?",
                                    (1 if details['enabled'] else 0, key['key_id'])
                                )
                            if details.get('subscription') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription = ? WHERE key_id = ?",
                                    (details['subscription'], key['key_id'])
                                )
                            if details.get('subscription_link') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription_link = ? WHERE key_id = ?",
                                    (details['subscription_link'], key['key_id'])
                                )
                            if details.get('telegram_chat_id') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET telegram_chat_id = ? WHERE key_id = ?",
                                    (details['telegram_chat_id'], key['key_id'])
                                )
                            if details.get('comment') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET comment = ? WHERE key_id = ?",
                                    (details['comment'], key['key_id'])
                                )
                            conn.commit()
                            updated += 1
                    else:
                        # Ключ не найден в 3x-ui панели
                        created_date = key.get('created_date', 'Неизвестно')
                        expiry_date = key.get('expiry_date', 'Неизвестно')
                        # Используем key_email из базы данных (это и есть email из 3x-ui)
                        email = key.get('key_email', 'N/A')
                        host_name = key.get('host_name', 'Unknown')
                        xui_client_uuid = key.get('xui_client_uuid', 'Unknown')
                        error_info = {
                            'email': email,
                            'host_name': host_name,
                            'xui_client_uuid': xui_client_uuid,
                            'created_date': created_date.strftime('%Y-%m-%d %H:%M') if isinstance(created_date, datetime) else str(created_date),
                            'expiry_date': expiry_date.strftime('%Y-%m-%d %H:%M') if isinstance(expiry_date, datetime) else str(expiry_date)
                        }
                        errors.append(error_info)
                except Exception as e:
                    # Ошибка при получении деталей ключа
                    created_date = key.get('created_date', 'Неизвестно')
                    expiry_date = key.get('expiry_date', 'Неизвестно')
                    # Используем key_email из базы данных (это и есть email из 3x-ui)
                    email = key.get('key_email', 'N/A')
                    host_name = key.get('host_name', 'Unknown')
                    xui_client_uuid = key.get('xui_client_uuid', 'Unknown')
                    error_info = {
                        'email': email,
                        'host_name': host_name,
                        'xui_client_uuid': xui_client_uuid,
                        'created_date': created_date.strftime('%Y-%m-%d %H:%M') if isinstance(created_date, datetime) else str(created_date),
                        'expiry_date': expiry_date.strftime('%Y-%m-%d %H:%M') if isinstance(expiry_date, datetime) else str(expiry_date),
                        'error': str(e)
                    }
                    errors.append(error_info)
                    continue
            
            response_data = {'status': 'success', 'message': f'Ключи обновлены: {updated}'}
            if errors:
                response_data['errors'] = errors
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error refreshing keys: {e}")
            return {'status': 'error', 'message': f'Ошибка при обновлении: {str(e)}'}, 500

    @flask_app.route('/refresh-user-keys', methods=['POST'])
    @login_required
    def refresh_user_keys_route():
        """Обновляет ключи конкретного пользователя"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'Не указан user_id'}), 400
            
            # Получаем ключи пользователя
            user_keys = get_user_keys(user_id)
            if not user_keys:
                return jsonify({'success': False, 'error': f'У пользователя {user_id} нет ключей'}), 404
            
            updated_count = 0
            errors = []
            
            from shop_bot.modules.xui_api import get_key_details_from_host
            
            for key in user_keys:
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
                            if details.get('enabled') is not None:
                                try:
                                    cursor.execute("ALTER TABLE vpn_keys ADD COLUMN enabled INTEGER DEFAULT 1")
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET enabled = ? WHERE key_id = ?",
                                    (1 if details['enabled'] else 0, key['key_id'])
                                )
                            if details.get('subscription') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription = ? WHERE key_id = ?",
                                    (details['subscription'], key['key_id'])
                                )
                            if details.get('subscription_link') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription_link = ? WHERE key_id = ?",
                                    (details['subscription_link'], key['key_id'])
                                )
                            if details.get('telegram_chat_id') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET telegram_chat_id = ? WHERE key_id = ?",
                                    (details['telegram_chat_id'], key['key_id'])
                                )
                            if details.get('comment') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET comment = ? WHERE key_id = ?",
                                    (details['comment'], key['key_id'])
                                )
                            conn.commit()
                            updated_count += 1
                    else:
                        # Ключ не найден в 3x-ui панели
                        email = key.get('key_email', 'N/A')
                        host_name = key.get('host_name', 'Unknown')
                        errors.append(f"Ключ {email} на хосте {host_name} не найден в панели")
                except Exception as e:
                    email = key.get('key_email', 'N/A')
                    host_name = key.get('host_name', 'Unknown')
                    errors.append(f"Ошибка обновления ключа {email} на хосте {host_name}: {str(e)}")
                    continue
            
            response_data = {
                'success': True, 
                'updated_count': updated_count,
                'total_keys': len(user_keys)
            }
            
            if errors:
                response_data['errors'] = errors
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Error refreshing user keys: {e}")
            return jsonify({'success': False, 'error': f'Ошибка при обновлении ключей пользователя: {str(e)}'}), 500

    @flask_app.route('/delete-error-keys', methods=['POST'])
    @login_required
    def delete_error_keys_route():
        """Удаляет ключи с ошибками из 3x-ui панелей"""
        try:
            data = request.get_json()
            error_keys = data.get('keys', [])
            
            if not error_keys:
                return {'status': 'error', 'message': 'Нет ключей для удаления'}, 400
            
            deleted_count = 0
            failed_deletions = []
            
            from shop_bot.modules.xui_api import delete_client_by_uuid
            
            for key_data in error_keys:
                try:
                    email = key_data.get('email')
                    host_name = key_data.get('host_name')
                    xui_client_uuid = key_data.get('xui_client_uuid')
                    
                    if not email or not xui_client_uuid or xui_client_uuid == 'Unknown':
                        failed_deletions.append({
                            'email': email or 'Unknown',
                            'error': 'Отсутствует email или UUID клиента'
                        })
                        continue
                    
                    # Удаляем ключ из 3x-ui панели напрямую по UUID
                    success = asyncio.run(delete_client_by_uuid(xui_client_uuid, email))
                    
                    if success:
                        deleted_count += 1
                        logger.info(f"Successfully deleted key {email} (UUID: {xui_client_uuid}) using direct UUID deletion")
                    else:
                        failed_deletions.append({
                            'email': email,
                            'error': 'Не удалось удалить ключ из 3x-ui панели'
                        })
                        
                except Exception as e:
                    failed_deletions.append({
                        'email': key_data.get('email', 'Unknown'),
                        'error': str(e)
                    })
                    logger.error(f"Error deleting key {key_data.get('email')}: {e}")
                    continue
            
            response_data = {
                'status': 'success',
                'deleted_count': deleted_count,
                'failed_count': len(failed_deletions),
                'message': f'Удалено ключей: {deleted_count}, ошибок: {len(failed_deletions)}'
            }
            
            if failed_deletions:
                response_data['failed_deletions'] = failed_deletions
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error deleting error keys: {e}")
            return {'status': 'error', 'message': f'Ошибка при удалении: {str(e)}'}, 500

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
                        vk.created_date,
                        vk.is_trial
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

    @flask_app.route('/api/key/<int:key_id>')
    @login_required
    def api_get_key(key_id):
        """API для получения данных конкретного ключа"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        vk.key_id,
                        vk.user_id,
                        u.username,
                        u.telegram_id,
                        u.fullname,
                        u.fio,
                        vk.host_name,
                        vk.plan_name,
                        vk.price,
                        vk.protocol,
                        vk.is_trial,
                        vk.created_date,
                        vk.expiry_date,
                        vk.quota_total_gb,
                        vk.traffic_down_bytes,
                        vk.quota_remaining_bytes,
                        vk.status,
                        vk.enabled,
                        vk.connection_string,
                        vk.key_email,
                        vk.xui_client_uuid,
                        vk.subscription,
                        vk.subscription_link,
                        vk.telegram_chat_id,
                        vk.comment
                    FROM vpn_keys vk
                    LEFT JOIN users u ON vk.user_id = u.telegram_id
                    WHERE vk.key_id = ?
                """
                cursor.execute(query, (key_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {'error': 'Ключ не найден'}, 404
                
                key = dict(row)
                
                # Преобразуем даты в строки для JSON
                if key['created_date']:
                    if isinstance(key['created_date'], str):
                        key['created_date'] = key['created_date']
                    else:
                        key['created_date'] = key['created_date'].isoformat()
                
                if key['expiry_date']:
                    if isinstance(key['expiry_date'], str):
                        key['expiry_date'] = key['expiry_date']
                    else:
                        key['expiry_date'] = key['expiry_date'].isoformat()
                
                # Вычисляем оставшееся время
                # ВАЖНО: expiry_date хранится в UTC, поэтому для расчета используем UTC+3 (Moscow timezone)
                if key['expiry_date']:
                    try:
                        from datetime import timezone, timedelta
                        # Парсим expiry_date (всегда в UTC)
                        expiry = datetime.fromisoformat(key['expiry_date']) if isinstance(key['expiry_date'], str) else key['expiry_date']
                        # Убедимся, что expiry без timezone info
                        if expiry.tzinfo is not None:
                            expiry = expiry.replace(tzinfo=None)
                        # Текущее время в UTC
                        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                        # Рассчитываем оставшееся время
                        remaining = (expiry - now_utc).total_seconds()
                        key['remaining_seconds'] = max(0, int(remaining))
                    except Exception as e:
                        logger.error(f"Error calculating remaining_seconds for key {key.get('key_id')}: {e}")
                        key['remaining_seconds'] = None
                else:
                    key['remaining_seconds'] = None
                
                return {'key': key}
                
        except Exception as e:
            logger.error(f"Error getting key {key_id}: {e}")
            return {'error': 'Ошибка получения данных ключа'}, 500

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

    @flask_app.route('/api/user-details/<int:user_id>')
    @login_required
    def api_user_details(user_id):
        """API для получения полных данных пользователя"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        u.user_id,
                        u.telegram_id,
                        u.username,
                        u.fullname,
                        u.fio,
                        u.balance,
                        u.referral_balance,
                        u.referral_balance_all,
                        u.total_spent,
                        u.total_months,
                        u.trial_used,
                        u.trial_days_given,
                        u.trial_reuses_count,
                        u.agreed_to_terms,
                        u.agreed_to_documents,
                        u.subscription_status,
                        u.registration_date,
                        u.is_banned,
                        u.email,
                        (SELECT COUNT(*) FROM vpn_keys WHERE user_id = u.telegram_id) as keys_count,
                        (SELECT COUNT(*) FROM notifications WHERE user_id = u.telegram_id) as notifications_count
                    FROM users u
                    WHERE u.telegram_id = ?
                """
                cursor.execute(query, (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {'error': 'Пользователь не найден'}, 404
                
                user_data = dict(row)
                
                # Преобразуем registration_date в строку для JSON
                if user_data.get('registration_date'):
                    if isinstance(user_data['registration_date'], str):
                        user_data['registration_date'] = user_data['registration_date']
                    else:
                        user_data['registration_date'] = user_data['registration_date'].isoformat()
                
                # Получаем сумму заработанных средств (пока отключено из-за отсутствия колонки referred_by)
                user_data['earned'] = 0
                
                return {'user': user_data}
                
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return {'error': 'Ошибка получения данных пользователя'}, 500

    @flask_app.route('/api/update-user/<int:user_id>', methods=['POST'])
    @login_required
    def api_update_user(user_id):
        """API для обновления данных пользователя"""
        try:
            data = request.get_json()
            if not data:
                return {'error': 'Нет данных для обновления'}, 400
            
            # Разрешенные поля для обновления
            allowed_fields = ['fio', 'email']
            update_fields = {}
            
            for field in allowed_fields:
                if field in data:
                    update_fields[field] = data[field]
            
            if not update_fields:
                return {'error': 'Нет разрешенных полей для обновления'}, 400
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                # Проверяем существование пользователя
                cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (user_id,))
                if not cursor.fetchone():
                    return {'error': 'Пользователь не найден'}, 404
                
                # Строим SQL запрос для обновления
                set_clause = ', '.join([f"{field} = ?" for field in update_fields.keys()])
                values = list(update_fields.values()) + [user_id]
                
                query = f"UPDATE users SET {set_clause} WHERE telegram_id = ?"
                cursor.execute(query, values)
                
                conn.commit()
                
                logger.info(f"Updated user {user_id} fields: {list(update_fields.keys())}")
                return {'message': 'Данные пользователя обновлены успешно'}
                
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return {'error': 'Ошибка обновления данных пользователя'}, 500


    @flask_app.route('/users/revoke-consent/<int:user_id>', methods=['POST'])
    @login_required
    def revoke_consent_route(user_id):
        try:
            revoke_user_consent(user_id)
            flash(f'Согласие пользователя {user_id} было отозвано.', 'success')
        except Exception as e:
            logger.error(f"Failed to revoke consent for user {user_id}: {e}")
            flash('Не удалось отозвать согласие пользователя. Проверьте логи.', 'danger')
        return redirect(url_for('users_page'))

    @flask_app.route('/api/search-users')
    @login_required
    @rate_limit('per_minute', 30, "Too many search requests. Please try again later.")
    @handle_exceptions("API search users")
    def api_search_users():
        """Поиск пользователей по части Telegram ID или username.
        Возвращает JSON: {"users": [...]}.
        """
        query = (request.args.get('q') or '').strip()
        limit = request.args.get('limit', 10)
        if not query:
            return jsonify({'users': []})
        users = db_search_users(query=query, limit=limit)
        return jsonify({'users': users})

    @flask_app.route('/create-notification', methods=['POST'])
    @login_required
    def create_notification_route():
        """Ручной запуск отправки уведомления о скором окончании подписки.
        Ожидает JSON: {"user_id": int, "marker_hours": int in [1,24,48,72]}.
        """
        try:
            data = request.get_json(silent=True) or {}
            user_id = int(data.get('user_id') or 0)
            marker_hours = int(data.get('marker_hours') or 0)
            if user_id <= 0 or marker_hours not in (1, 24, 48, 72):
                return jsonify({'message': 'Некорректные данные: выберите пользователя и тип уведомления'}), 400

            # Проверяем наличие активного бота и цикла событий
            bot = _bot_controller.get_bot_instance()
            loop = current_app.config.get('EVENT_LOOP')
            if not bot or not loop or not loop.is_running():
                return jsonify({'message': 'Бот не запущен. Запустите бота на панели и повторите.'}), 503

            # Ищем ключ пользователя с ближайшим истечением в будущем
            keys = get_user_keys(user_id) or []
            from datetime import datetime as _dt
            now = _dt.now()
            def _to_dt(v):
                try:
                    if isinstance(v, str):
                        from datetime import datetime
                        return datetime.fromisoformat(v.replace('Z', '+00:00'))
                except Exception:
                    return None
                return v if isinstance(v, _dt) else None

            future_keys = []
            for k in keys:
                exp = _to_dt(k.get('expiry_date'))
                if exp and exp > now:
                    future_keys.append((exp, k))

            if not future_keys:
                return jsonify({'message': 'У пользователя нет активных ключей с будущей датой истечения'}), 400

            # Берём ближайший по истечению
            future_keys.sort(key=lambda x: x[0])
            expiry_dt, key = future_keys[0]
            key_id = int(key.get('key_id'))

            # Гарантируем, что дата истечения в будущем (на случай рассинхронизации)
            if expiry_dt <= now:
                expiry_dt = now + timedelta(hours=marker_hours)

            # Отправляем уведомление асинхронно
            asyncio.run_coroutine_threadsafe(
                send_subscription_notification(bot=bot, user_id=user_id, key_id=key_id, time_left_hours=marker_hours, expiry_date=expiry_dt),
                loop
            )

            return jsonify({'message': 'Уведомление отправлено'}), 200
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            return jsonify({'message': 'Внутренняя ошибка сервера'}), 500

    @flask_app.route('/resend-notification/<int:notification_id>', methods=['POST'])
    @login_required
    def resend_notification_route(notification_id: int):
        """Повторная отправка ранее созданного уведомления."""
        try:
            notif = get_notification_by_id(notification_id)
            if not notif:
                return jsonify({'message': 'Уведомление не найдено'}), 404

            user_id = int(notif.get('user_id') or 0)
            if user_id <= 0:
                return jsonify({'message': 'Некорректные данные уведомления'}), 400

            # Определяем маркер часов и ключ
            marker_hours = None
            try:
                marker_hours = int(notif.get('marker_hours') or 0)
            except Exception:
                marker_hours = 0

            meta = notif.get('meta')
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            meta = meta or {}

            key_id = meta.get('key_id') or notif.get('key_id')
            try:
                key_id = int(key_id) if key_id is not None else None
            except Exception:
                key_id = None

            # Если не удалось получить marker_hours из записи, используем 24 как разумный дефолт
            if marker_hours not in (1, 24, 48, 72):
                marker_hours = 24

            # Вычисляем дату истечения
            expiry_dt = None
            exp_str = meta.get('expiry_at') if isinstance(meta, dict) else None
            if exp_str:
                try:
                    from datetime import datetime
                    expiry_dt = datetime.fromisoformat(exp_str.replace('Z', '+00:00'))
                except Exception:
                    expiry_dt = None

            # Фоллбек: берём ближайший ключ пользователя
            if expiry_dt is None or key_id is None:
                keys = get_user_keys(user_id) or []
                from datetime import datetime as _dt
                now = _dt.now()
                def _to_dt(v):
                    try:
                        if isinstance(v, str):
                            from datetime import datetime
                            return datetime.fromisoformat(v.replace('Z', '+00:00'))
                    except Exception:
                        return None
                    return v if isinstance(v, _dt) else None
                future = [( _to_dt(k.get('expiry_date')), k) for k in keys]
                future = [(d,k) for d,k in future if d and d>now]
                if future:
                    future.sort(key=lambda x: x[0])
                    expiry_dt, key = future[0]
                    key_id = key.get('key_id') if key_id is None else key_id
                else:
                    # Если совсем нет данных — шлём «через marker_hours» от текущего момента
                    expiry_dt = now + timedelta(hours=marker_hours)
                    # key_id обязателен для клавиатуры; без ключа нет смысла отправлять
                    return jsonify({'message': 'Невозможно отправить: у пользователя нет активных ключей'}), 400

            # Проверяем состояние бота
            bot = _bot_controller.get_bot_instance()
            loop = current_app.config.get('EVENT_LOOP')
            if not bot or not loop or not loop.is_running():
                return jsonify({'message': 'Бот не запущен. Запустите бота на панели и повторите.'}), 503

            asyncio.run_coroutine_threadsafe(
                send_subscription_notification(bot=bot, user_id=user_id, key_id=int(key_id), time_left_hours=int(marker_hours), expiry_date=expiry_dt),
                loop
            )

            return jsonify({'message': 'Уведомление отправлено повторно'}), 200
        except Exception as e:
            logger.error(f"Failed to resend notification {notification_id}: {e}")
            return jsonify({'message': 'Внутренняя ошибка сервера'}), 500

    @flask_app.route('/api/topup-balance', methods=['POST'])
    @login_required
    @rate_limit('per_minute', 5, "Too many balance topup requests. Please try again later.")
    def api_topup_balance():
        """Ручное пополнение баланса пользователя из панели администратора."""
        try:
            data = request.get_json(silent=True) or {}
            user_id = int(data.get('user_id') or 0)
            amount = float(data.get('amount') or 0)
            if user_id <= 0 or amount <= 0:
                return jsonify({'message': 'Некорректные данные: выберите пользователя и укажите сумму > 0'}), 400

            # Пополняем баланс
            if not add_to_user_balance(user_id=user_id, amount=amount):
                return jsonify({'message': 'Не удалось пополнить баланс пользователя'}), 500

            # Логируем транзакцию как зачисление на баланс
            try:
                user_info = get_user(user_id) or {}
                username = user_info.get('username') if isinstance(user_info, dict) else None
            except Exception:
                username = None

            payment_id = f"manual-topup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id}"
            metadata = json.dumps({'type': 'balance_topup', 'operation': 'topup'})
            try:
                log_transaction(username or 'N/A', None, payment_id, user_id, 'paid', float(amount), None, None, 'Balance', metadata)
            except Exception as e:
                logger.warning(f"Balance was topped up but logging failed: {e}")

            return jsonify({'message': 'Баланс успешно пополнен'})
        except Exception as e:
            logger.error(f"Failed to top up balance: {e}")
            return jsonify({'message': 'Внутренняя ошибка сервера'}), 500

    @flask_app.route('/api/hosts')
    @login_required
    def api_get_hosts():
        """API для получения списка хостов для модального окна обновления ключей."""
        try:
            hosts = get_all_hosts()
            # Преобразуем хосты в формат, ожидаемый фронтендом
            hosts_data = []
            for host in hosts:
                hosts_data.append({
                    'host_name': host['host_name'],
                    'host_url': host['host_url'],
                    'host_username': host['host_username'],
                    'host_inbound_id': host['host_inbound_id']
                })
            
            return jsonify({
                'success': True,
                'hosts': hosts_data
            })
        except Exception as e:
            logger.error(f"Error getting hosts: {e}")
            return jsonify({
                'success': False,
                'error': 'Ошибка загрузки хостов'
            }), 500

    @flask_app.route('/api/refresh-keys-by-host', methods=['POST'])
    @login_required
    def api_refresh_keys_by_host():
        """API для обновления ключей по конкретному хосту."""
        try:
            data = request.get_json(silent=True) or {}
            host_name = data.get('host_name')
            
            if not host_name:
                return jsonify({
                    'success': False,
                    'error': 'Не указан хост'
                }), 400
            
            # Получаем хост из базы данных
            host = get_host(host_name)
            if not host:
                return jsonify({
                    'success': False,
                    'error': 'Хост не найден'
                }), 404
            
            # Получаем все ключи для данного хоста
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vpn_keys WHERE host_name = ? ORDER BY created_date DESC", (host_name,))
                keys = [dict(row) for row in cursor.fetchall()]
            
            if not keys:
                return jsonify({
                    'success': True,
                    'message': f'На хосте {host_name} нет ключей для обновления'
                })
            
            # Обновляем ключи
            updated = 0
            errors = []
            
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
                            if details.get('enabled') is not None:
                                try:
                                    cursor.execute("ALTER TABLE vpn_keys ADD COLUMN enabled INTEGER DEFAULT 1")
                                except Exception:
                                    pass
                                cursor.execute(
                                    "UPDATE vpn_keys SET enabled = ? WHERE key_id = ?",
                                    (1 if details['enabled'] else 0, key['key_id'])
                                )
                            if details.get('subscription') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription = ? WHERE key_id = ?",
                                    (details['subscription'], key['key_id'])
                                )
                            if details.get('subscription_link') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET subscription_link = ? WHERE key_id = ?",
                                    (details['subscription_link'], key['key_id'])
                                )
                            if details.get('telegram_chat_id') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET telegram_chat_id = ? WHERE key_id = ?",
                                    (details['telegram_chat_id'], key['key_id'])
                                )
                            if details.get('comment') is not None:
                                cursor.execute(
                                    "UPDATE vpn_keys SET comment = ? WHERE key_id = ?",
                                    (details['comment'], key['key_id'])
                                )
                            conn.commit()
                            updated += 1
                    else:
                        # Ключ не найден в 3x-ui панели
                        created_date = key.get('created_date', 'Неизвестно')
                        expiry_date = key.get('expiry_date', 'Неизвестно')
                        email = key.get('key_email', 'N/A')
                        xui_client_uuid = key.get('xui_client_uuid', 'Unknown')
                        error_info = {
                            'email': email,
                            'host_name': host_name,
                            'xui_client_uuid': xui_client_uuid,
                            'created_date': created_date.strftime('%Y-%m-%d %H:%M') if isinstance(created_date, datetime) else str(created_date),
                            'expiry_date': expiry_date.strftime('%Y-%m-%d %H:%M') if isinstance(expiry_date, datetime) else str(expiry_date)
                        }
                        errors.append(error_info)
                except Exception as e:
                    # Ошибка при получении деталей ключа
                    created_date = key.get('created_date', 'Неизвестно')
                    expiry_date = key.get('expiry_date', 'Неизвестно')
                    email = key.get('key_email', 'N/A')
                    xui_client_uuid = key.get('xui_client_uuid', 'Unknown')
                    error_info = {
                        'email': email,
                        'host_name': host_name,
                        'xui_client_uuid': xui_client_uuid,
                        'created_date': created_date.strftime('%Y-%m-%d %H:%M') if isinstance(created_date, datetime) else str(created_date),
                        'expiry_date': expiry_date.strftime('%Y-%m-%d %H:%M') if isinstance(expiry_date, datetime) else str(expiry_date),
                        'error': str(e)
                    }
                    errors.append(error_info)
                    continue
            
            response_data = {
                'success': True,
                'message': f'Обновлено ключей: {updated} из {len(keys)}',
                'updated': updated,
                'total': len(keys)
            }
            
            if errors:
                response_data['errors'] = errors
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Error refreshing keys by host: {e}")
            return jsonify({
                'success': False,
                'error': f'Ошибка при обновлении ключей: {str(e)}'
            }), 500

    @flask_app.route('/api/get-ton-manifest-content')
    @login_required
    def api_get_ton_manifest_content():
        """API для получения содержимого манифеста TON Connect"""
        try:
            manifest_path = os.path.join(flask_app.static_folder, '.well-known', 'tonconnect-manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({
                    'success': True,
                    'content': content
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Файл манифеста не найден'
                }), 404
        except Exception as e:
            logger.error(f"Error getting TON manifest content: {e}")
            return jsonify({
                'success': False,
                'error': f'Ошибка загрузки манифеста: {str(e)}'
            }), 500

    @flask_app.route('/edit-ton-manifest', methods=['POST'])
    @login_required
    def edit_ton_manifest():
        """Роут для редактирования манифеста TON Connect"""
        try:
            content = request.form.get('ton_manifest_content', '').strip()
            
            if not content:
                flash('Содержимое манифеста не может быть пустым', 'danger')
                return redirect(url_for('settings_page'))
            
            # Проверяем, что это валидный JSON
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                flash(f'Неверный формат JSON: {str(e)}', 'danger')
                return redirect(url_for('settings_page'))
            
            # Сохраняем манифест
            manifest_path = os.path.join(flask_app.static_folder, '.well-known', 'tonconnect-manifest.json')
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
            
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            flash('Манифест TON Connect успешно обновлен', 'success')
            return redirect(url_for('settings_page'))
            
        except Exception as e:
            logger.error(f"Error editing TON manifest: {e}")
            flash(f'Ошибка при сохранении манифеста: {str(e)}', 'danger')
            return redirect(url_for('settings_page'))

    @flask_app.route('/api/toggle-key-enabled', methods=['POST'])
    @login_required
    def api_toggle_key_enabled():
        """API для включения/отключения ключа"""
        try:
            data = request.get_json()
            key_id = data.get('key_id')
            enabled = data.get('enabled')
            
            if key_id is None or enabled is None:
                return jsonify({'success': False, 'error': 'Не указан key_id или enabled'}), 400
            
            # Получаем информацию о ключе
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
                key_data = cursor.fetchone()
                
                if not key_data:
                    return jsonify({'success': False, 'error': 'Ключ не найден'}), 404
                
                key_dict = dict(key_data)
            
            # Обновляем статус в базе данных
            from shop_bot.data_manager.database import update_key_enabled_status
            update_key_enabled_status(key_id, enabled)
            
            # Обновляем статус в 3x-ui
            try:
                loop = current_app.config.get('EVENT_LOOP')
                if loop and loop.is_running():
                    result = asyncio.run_coroutine_threadsafe(
                        xui_api.update_client_enabled_status_on_host(
                            key_dict['host_name'], 
                            key_dict['key_email'], 
                            enabled
                        ), 
                        loop
                    ).result()
                    
                    if not result:
                        logger.warning(f"Failed to update enabled status in 3x-ui for key {key_id}")
                else:
                    logger.warning("Event loop not available for 3x-ui update")
            except Exception as e:
                logger.error(f"Error updating 3x-ui enabled status for key {key_id}: {e}")
                # Не возвращаем ошибку, так как база данных уже обновлена
            
            return jsonify({
                'success': True, 
                'message': f'Ключ успешно {"включен" if enabled else "отключен"}'
            })
            
        except Exception as e:
            logger.error(f"Error in toggle_key_enabled: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # API роуты для промокодов
    @flask_app.route('/api/promo-codes', methods=['GET'])
    @login_required
    def api_get_promo_codes():
        """Получить все промокоды"""
        try:
            promo_codes = get_all_promo_codes()
            return jsonify({
                'success': True,
                'promo_codes': promo_codes
            })
        except Exception as e:
            logger.error(f"Error getting promo codes: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes', methods=['POST'])
    @login_required
    def api_create_promo_code():
        """Создать новый промокод"""
        try:
            data = request.get_json()
            
            # Валидация обязательных полей
            if not data.get('code'):
                return jsonify({'success': False, 'message': 'Промокод обязателен'}), 400
            
            if not data.get('bot'):
                return jsonify({'success': False, 'message': 'Бот обязателен'}), 400
            
            # Валидация бота
            if data.get('bot') not in ['shop', 'support']:
                return jsonify({'success': False, 'message': 'Неверный тип бота. Допустимые значения: shop, support'}), 400
            
            # Валидация vpn_plan_id (может быть массивом или одиночным значением)
            vpn_plan_id = data.get('vpn_plan_id')
            if vpn_plan_id is not None:
                if isinstance(vpn_plan_id, list):
                    try:
                        # Преобразуем список в JSON строку для хранения в базе
                        vpn_plan_id = json.dumps([int(x) for x in vpn_plan_id if x is not None])
                    except (ValueError, TypeError):
                        return jsonify({'success': False, 'message': 'Неверный формат VPN планов'}), 400
                else:
                    try:
                        # Одиночное значение сохраняем как есть
                        vpn_plan_id = int(vpn_plan_id)
                    except (ValueError, TypeError):
                        return jsonify({'success': False, 'message': 'Неверный формат VPN плана'}), 400
            
            # Создание промокода
            try:
                promo_id = create_promo_code(
                    code=data['code'],
                    bot=data['bot'],
                    vpn_plan_id=vpn_plan_id,
                    tariff_code=data.get('tariff_code'),
                    discount_amount=data.get('discount_amount', 0),
                    discount_percent=data.get('discount_percent', 0),
                    discount_bonus=data.get('discount_bonus', 0),
                    usage_limit_per_bot=data.get('usage_limit_per_bot', 1),
                    is_active=data.get('is_active', True)
                )
                
                return jsonify({'success': True, 'message': 'Промокод создан', 'promo_id': promo_id})
            except ValueError as e:
                return jsonify({'success': False, 'message': str(e)}), 400
            except RuntimeError as e:
                return jsonify({'success': False, 'message': str(e)}), 500
                
        except Exception as e:
            logger.error(f"Error creating promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>', methods=['GET'])
    @login_required
    def api_get_promo_code(promo_id):
        """Получить промокод по ID"""
        try:
            promo_code = get_promo_code(promo_id)
            if promo_code:
                return jsonify({
                    'success': True,
                    'promo_code': promo_code
                })
            else:
                return jsonify({'success': False, 'message': 'Промокод не найден'}), 404
        except Exception as e:
            logger.error(f"Error getting promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>', methods=['PUT'])
    @login_required
    def api_update_promo_code(promo_id):
        """Обновить промокод"""
        try:
            data = request.get_json()
            
            # Валидация обязательных полей
            if not data.get('code'):
                return jsonify({'success': False, 'message': 'Промокод обязателен'}), 400
            
            if not data.get('bot'):
                return jsonify({'success': False, 'message': 'Бот обязателен'}), 400
            
            # Валидация бота
            if data.get('bot') not in ['shop', 'support']:
                return jsonify({'success': False, 'message': 'Неверный тип бота. Допустимые значения: shop, support'}), 400
            
            # Валидация vpn_plan_id (может быть массивом или одиночным значением)
            vpn_plan_id = data.get('vpn_plan_id')
            if vpn_plan_id is not None:
                if isinstance(vpn_plan_id, list):
                    try:
                        vpn_plan_id = [int(x) for x in vpn_plan_id if x is not None]
                    except (ValueError, TypeError):
                        return jsonify({'success': False, 'message': 'Неверный формат VPN планов'}), 400
                else:
                    try:
                        vpn_plan_id = int(vpn_plan_id)
                    except (ValueError, TypeError):
                        return jsonify({'success': False, 'message': 'Неверный формат VPN плана'}), 400
            
            # Обновление промокода
            try:
                success = update_promo_code(
                    promo_id=promo_id,
                    code=data['code'],
                    bot=data['bot'],
                    vpn_plan_id=vpn_plan_id,
                    tariff_code=data.get('tariff_code'),
                    discount_amount=data.get('discount_amount', 0),
                    discount_percent=data.get('discount_percent', 0),
                    discount_bonus=data.get('discount_bonus', 0),
                    usage_limit_per_bot=data.get('usage_limit_per_bot', 1),
                    is_active=data.get('is_active', True)
                )
                
                if success:
                    return jsonify({'success': True, 'message': 'Промокод обновлен'})
                else:
                    return jsonify({'success': False, 'message': 'Промокод не найден'}), 404
            except ValueError as e:
                return jsonify({'success': False, 'message': str(e)}), 400
            except RuntimeError as e:
                return jsonify({'success': False, 'message': str(e)}), 500
                
        except Exception as e:
            logger.error(f"Error updating promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>', methods=['DELETE'])
    @login_required
    def api_delete_promo_code(promo_id):
        """Удалить промокод"""
        try:
            # Проверяем, можно ли удалить промокод
            can_delete, usage_count = can_delete_promo_code(promo_id)
            
            if not can_delete:
                return jsonify({
                    'success': False, 
                    'message': f'Нельзя удалить промокод: он был использован {usage_count} раз(а). Удаление возможно только из панели администратора.',
                    'usage_count': usage_count
                }), 400
            
            success = delete_promo_code(promo_id)
            if success:
                return jsonify({'success': True, 'message': 'Промокод удален'})
            else:
                return jsonify({'success': False, 'message': 'Ошибка удаления промокода'}), 500
        except Exception as e:
            logger.error(f"Error deleting promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>/usage', methods=['GET'])
    @login_required
    def api_get_promo_code_usage(promo_id):
        """Получить историю использования промокода"""
        try:
            usage_history = get_promo_code_usage_history(promo_id)
            return jsonify({
                'success': True,
                'usage_history': usage_history
            })
        except Exception as e:
            logger.error(f"Error getting promo code usage: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>/can-delete', methods=['GET'])
    @login_required
    def api_can_delete_promo_code(promo_id):
        """Проверить, можно ли удалить промокод"""
        try:
            can_delete, usage_count = can_delete_promo_code(promo_id)
            return jsonify({
                'success': True, 
                'can_delete': can_delete, 
                'usage_count': usage_count
            })
        except Exception as e:
            logger.error(f"Error checking promo code deletion: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/vpn-plans', methods=['GET'])
    @login_required
    def api_get_vpn_plans():
        """Получить все VPN планы"""
        try:
            plans = get_all_plans()
            return jsonify({
                'success': True,
                'plans': plans
            })
        except Exception as e:
            logger.error(f"Error getting VPN plans: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/validate-promo-code', methods=['POST'])
    @login_required
    def api_validate_promo_code():
        """Валидация промокода для пользователя"""
        try:
            data = request.get_json()
            
            user_id = data.get('user_id')
            promo_code = data.get('promo_code')
            bot = data.get('bot')
            
            if not all([user_id, promo_code, bot]):
                return jsonify({
                    'success': False, 
                    'message': 'Необходимы user_id, promo_code и bot'
                }), 400
            
            validation_result = can_user_use_promo_code(user_id, promo_code, bot)
            
            return jsonify({
                'success': True,
                'can_use': validation_result['can_use'],
                'message': validation_result['message'],
                'promo_data': validation_result.get('promo_data')
            })
            
        except Exception as e:
            logger.error(f"Error validating promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/user-promo-codes', methods=['GET'])
    @login_required
    def api_get_user_promo_codes():
        """Получить применённые промокоды пользователя"""
        try:
            user_id = request.args.get('user_id', type=int)
            bot = request.args.get('bot', 'shop')
            
            if not user_id:
                return jsonify({
                    'success': False, 
                    'message': 'Необходим user_id'
                }), 400
            
            user_promo_codes = get_user_promo_codes(user_id, bot)
            
            return jsonify({
                'success': True,
                'promo_codes': user_promo_codes
            })
            
        except Exception as e:
            logger.error(f"Error getting user promo codes: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/user-promo-codes/<int:promo_id>', methods=['DELETE'])
    @login_required
    def api_remove_user_promo_code(promo_id):
        """Удалить применённый промокод пользователем"""
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            bot = data.get('bot', 'shop')
            
            if not user_id:
                return jsonify({
                    'success': False, 
                    'message': 'Необходим user_id'
                }), 400
            
            success = remove_user_promo_code_usage(user_id, promo_id, bot)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Промокод удалён из вашего списка'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Промокод не найден или уже удалён'
                })
            
        except Exception as e:
            logger.error(f"Error removing user promo code: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # CSRF защита отключена по умолчанию (WTF_CSRF_CHECK_DEFAULT = False)
    # При необходимости можно включить выборочно через @csrf.protect() для критичных форм

    # Запускаем мониторинг сразу
    start_ton_monitoring_task()

    return flask_app