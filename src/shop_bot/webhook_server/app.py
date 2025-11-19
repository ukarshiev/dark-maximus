import os
import logging
import asyncio
import json
import hashlib
import base64
import sqlite3
import requests
import time
import re
import subprocess
from hmac import compare_digest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
from math import ceil
from typing import Optional, Tuple
from flask import Flask, request, render_template, redirect, url_for, flash, session, current_app, jsonify, g
# CSRF отключен
from pathlib import Path
from yookassa import Payment, Configuration
from yookassa.domain.exceptions import ApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем путь к базе данных
import os
if os.path.exists("/app/project"):
    # Docker окружение
    PROJECT_ROOT = Path("/app/project")
    # В Docker база данных в корне проекта
    DB_FILE = PROJECT_ROOT / "users.db"
else:
    # Локальная разработка
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    DB_FILE = PROJECT_ROOT / "users.db"

from shop_bot.modules import xui_api
from shop_bot.bot import handlers 
from shop_bot.security import rate_limit, get_client_ip
from shop_bot.security.validators import InputValidator, ValidationError
from shop_bot.utils import handle_exceptions
from shop_bot.config import get_user_cabinet_domain
from shop_bot.data_manager import database
from shop_bot.data_manager.database import (
    get_all_settings, update_setting, get_all_hosts, get_plans_for_host,
    create_host, delete_host, create_plan, delete_plan, get_user_count,
    get_total_keys_count, get_total_earned_sum, get_total_notifications_count, get_daily_stats_for_charts,
    get_recent_transactions, get_paginated_transactions, get_all_users, get_user_keys,
    ban_user, unban_user, delete_user_keys, get_setting, get_global_domain, find_and_complete_ton_transaction,
    get_paginated_keys, get_plan_by_id, update_plan, get_host, get_host_by_code, update_host, revoke_user_consent,
    search_users as db_search_users, add_to_user_balance, log_transaction, get_user, get_notification_by_id,
    verify_admin_credentials, hash_password, get_all_promo_codes, create_promo_code, update_promo_code,
    delete_promo_code, get_promo_code, get_promo_code_usage_history, get_all_promo_code_usage_history, get_all_plans, can_user_use_promo_code,
    get_user_promo_codes, validate_promo_code, remove_user_promo_code_usage, can_delete_promo_code,
    get_all_user_groups, get_user_group, create_user_group, update_user_group, delete_user_group,
    get_user_group_by_name, get_default_user_group, update_user_group_assignment, get_user_group_info,
    get_users_in_group, get_groups_statistics, update_transaction_status,
    get_message_template, get_all_message_templates, create_message_template, update_message_template,
    delete_message_template, get_message_template_statistics
)
from shop_bot.data_manager.scheduler import (
    get_manual_notification_template,
    get_manual_notification_templates,
    send_autorenew_balance_notice,
    send_autorenew_disabled_notice,
    send_plan_unavailable_notice,
    send_subscription_notification,
    _get_plan_info_for_key,
    _marker_logged,
)
from shop_bot.ton_monitor import start_ton_monitoring
from shop_bot.utils.performance_monitor import get_performance_monitor, get_performance_report, measure_performance, measure_performance_sync
from shop_bot.utils.datetime_utils import (
    ensure_isoformat_for_timezone,
    format_datetime_for_timezone,
    get_timezone_meta,
    normalize_to_timezone,
    DEFAULT_PANEL_TIMEZONE,
)
from shop_bot.data.timezones import TIMEZONES, DEFAULT_TIMEZONE, validate_timezone
from shop_bot.webhook_server.auth_utils import init_flask_auth

_bot_controller = None
get_common_template_data = None  # Экспорт для тестирования

ALL_SETTINGS_KEYS = [
    "panel_login", "panel_password", "about_text", "terms_url", "privacy_url", "bot_username",
    "support_user", "support_text", "channel_url", "telegram_bot_token",
    "telegram_bot_username", "admin_telegram_id", "yookassa_shop_id",
    "yookassa_secret_key", "yookassa_test_mode", "yookassa_test_shop_id", 
    "yookassa_test_secret_key", "yookassa_api_url", "yookassa_test_api_url", "yookassa_verify_ssl", "yookassa_test_verify_ssl", "sbp_enabled", "receipt_email", "cryptobot_token",
    "stars_enabled", "stars_conversion_rate", "yookassa_local_stub",
    "heleket_merchant_id", "heleket_api_key", "domain", "global_domain", "docs_domain", "codex_docs_domain", "user_cabinet_domain", "referral_percentage",
    "referral_discount", "ton_wallet_address", "tonapi_key", "force_subscription", "trial_enabled", "trial_duration_days", "enable_referrals", "minimum_withdrawal",
    "support_group_id", "support_bot_token", "ton_monitoring_enabled", "hidden_mode", "support_enabled",
    # Настройки мониторинга производительности
    "monitoring_enabled", "monitoring_max_metrics", "monitoring_slow_threshold", "monitoring_cleanup_hours"
]


def resolve_panel_timezone(raw_timezone: Optional[str] = None) -> Tuple[str, str]:
    """Определяет timezone панели и сохраняет его в контекст запроса."""
    if raw_timezone is None:
        cached = getattr(g, "_panel_timezone_cache", None)
        if cached:
            return cached

    timezone_value = raw_timezone
    if not timezone_value:
        try:
            timezone_value = database.get_admin_timezone()
        except Exception:
            timezone_value = DEFAULT_PANEL_TIMEZONE

    if not timezone_value:
        timezone_value = DEFAULT_PANEL_TIMEZONE

    tz_name, tz_offset = get_timezone_meta(timezone_value)
    g.panel_timezone = tz_name
    g.panel_timezone_offset = tz_offset
    g._panel_timezone_cache = (tz_name, tz_offset)
    return tz_name, tz_offset


def _ensure_host_metadata(metadata: dict | None, payment_id: str | None = None) -> tuple[bool, dict | None]:
    """Гарантирует, что в metadata присутствует корректный host_name; иначе помечает транзакцию как failed."""
    metadata = metadata or {}
    operation = str(metadata.get("operation") or metadata.get("action") or "").lower()
    host_name = metadata.get("host_name")
    host_code = metadata.get("host_code")
    plan_id = metadata.get("plan_id")

    if not host_name and not host_code:
        # Для пополнений и других операций без привязки к хосту разрешаем отсутствие данных
        if operation in {"topup", "withdraw"}:
            return True, None

    host_record = None
    search_attempts = []
    
    # ИСПРАВЛЕНИЕ: Изменен приоритет - сначала ищем по host_code (более надежно)
    if host_code:
        # Очищаем host_code от эмодзи перед поиском
        import re
        cleaned_host_code = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]', '', str(host_code))
        cleaned_host_code = re.sub(r'[^\w\s-]', '', cleaned_host_code).replace(' ', '').lower()
        
        try:
            host_record = get_host_by_code(cleaned_host_code)
            if host_record:
                search_attempts.append(f"host_code={cleaned_host_code} (found)")
                metadata["host_name"] = host_record.get("host_name")
                metadata["host_code"] = host_record.get("host_code")  # Обновляем на правильный код
                logger.info(
                    f"[YOOKASSA_WEBHOOK] Host found by host_code: {cleaned_host_code} -> {host_record.get('host_name')}"
                )
        except Exception as e:
            search_attempts.append(f"host_code={cleaned_host_code} (error: {e})")
            logger.warning(f"[YOOKASSA_WEBHOOK] Error searching by host_code {cleaned_host_code}: {e}")

    # Если не нашли по host_code, ищем по host_name
    if not host_record and host_name:
        try:
            host_record = get_host(host_name)
            if host_record:
                search_attempts.append(f"host_name={host_name} (found)")
                # Убеждаемся, что host_code есть в metadata
                if not metadata.get("host_code") and host_record.get("host_code"):
                    metadata["host_code"] = host_record.get("host_code")
                logger.info(
                    f"[YOOKASSA_WEBHOOK] Host found by host_name: {host_name} -> code={host_record.get('host_code')}"
                )
        except Exception as e:
            search_attempts.append(f"host_name={host_name} (error: {e})")
            logger.warning(f"[YOOKASSA_WEBHOOK] Error searching by host_name {host_name}: {e}")

    # FALLBACK: Если хост не найден, пытаемся найти через план
    if not host_record and plan_id:
        try:
            from shop_bot.data_manager.database import get_plan_by_id
            plan = get_plan_by_id(plan_id)
            if plan and plan.get('host_name'):
                plan_host_name = plan.get('host_name')
                host_record = get_host(plan_host_name)
                if host_record:
                    search_attempts.append(f"plan_id={plan_id}->host_name={plan_host_name} (found)")
                    metadata["host_name"] = host_record.get("host_name")
                    if host_record.get("host_code"):
                        metadata["host_code"] = host_record.get("host_code")
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] Host found via plan fallback: plan_id={plan_id} -> "
                        f"host_name={plan_host_name}, host_code={host_record.get('host_code')}"
                    )
                else:
                    search_attempts.append(f"plan_id={plan_id}->host_name={plan_host_name} (not found)")
        except Exception as e:
            search_attempts.append(f"plan_id={plan_id} (error: {e})")
            logger.warning(f"[YOOKASSA_WEBHOOK] Error in plan fallback for plan_id {plan_id}: {e}")

    if not host_record:
        logger.error(
            "[YOOKASSA_WEBHOOK] Host resolution failed: host_name=%s, host_code=%s, plan_id=%s, payment_id=%s. "
            "Search attempts: %s",
            host_name,
            host_code,
            plan_id,
            payment_id,
            ", ".join(search_attempts) if search_attempts else "none"
        )
        if payment_id:
            try:
                update_transaction_status(payment_id, "failed")
            except Exception as update_error:
                logger.error(
                    "[YOOKASSA_WEBHOOK] Failed to mark transaction %s as failed: %s",
                    payment_id,
                    update_error,
                    exc_info=True,
                )
        return False, None

    return True, host_record


def to_panel_iso(value):
    """Конвертирует значение даты в ISO формате timezone панели."""
    if value in (None, ''):
        return None

    tz_name, _ = resolve_panel_timezone()

    try:
        if isinstance(value, datetime):
            dt_value = value
        elif isinstance(value, (int, float)):
            dt_value = datetime.fromtimestamp(float(value), tz=timezone.utc)
        elif isinstance(value, str):
            dt_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            return value
    except (ValueError, TypeError):
        return value

    return ensure_isoformat_for_timezone(dt_value, tz_name)

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
    
    # Настройка для автоматической перезагрузки шаблонов
    flask_app.jinja_env.auto_reload = True
    flask_app.config['TEMPLATES_AUTO_RELOAD'] = True
    flask_app.config['DEBUG'] = True
    flask_app.jinja_env.cache = None
    
    # CSRF защита отключена
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    # Инициализация авторизации и сессий через единую функцию
    # Это обеспечивает единообразную настройку сессий во всех сервисах
    init_flask_auth(flask_app, session_dir='/app/sessions')

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

    @flask_app.template_filter('timestamp_to_datetime')
    def timestamp_to_datetime(timestamp):
        """Конвертирует timestamp в datetime объект"""
        if timestamp is None:
            return None
        try:
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            dt_utc = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            tz_name, _ = resolve_panel_timezone()
            return normalize_to_timezone(dt_utc, tz_name)
        except (ValueError, TypeError):
            return None

    @flask_app.template_filter('strftime')
    def strftime_filter(dt, format_string):
        """Фильтр для форматирования datetime в строку"""
        if dt is None:
            return 'N/A'
        try:
            return dt.strftime(format_string)
        except (AttributeError, ValueError):
            return 'N/A'

    @flask_app.template_filter('panel_datetime')
    def panel_datetime_filter(value, fmt='%d.%m.%Y %H:%M', include_offset=False):
        """Форматирует значение даты для timezone панели."""
        if value in (None, ''):
            return 'N/A'

        try:
            if isinstance(value, datetime):
                dt_value = value
            elif isinstance(value, (int, float)):
                dt_value = datetime.fromtimestamp(float(value), tz=timezone.utc)
            elif isinstance(value, str):
                dt_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)

        tz_name, _ = resolve_panel_timezone()
        return format_datetime_for_timezone(dt_value, tz_name, fmt, include_offset=include_offset)

    @flask_app.template_filter('panel_iso')
    def panel_iso_filter(value):
        """Формирует ISO строку для timezone панели."""
        if value in (None, ''):
            return None

        try:
            if isinstance(value, datetime):
                dt_value = value
            elif isinstance(value, (int, float)):
                dt_value = datetime.fromtimestamp(float(value), tz=timezone.utc)
            elif isinstance(value, str):
                dt_value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                return None
        except (ValueError, TypeError):
            return None

        tz_name, _ = resolve_panel_timezone()
        return ensure_isoformat_for_timezone(dt_value, tz_name)

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
        return render_template('login.html', settings=settings)

    @flask_app.route('/logout', methods=['POST'])
    @login_required
    def logout_page():
        session.pop('logged_in', None)
        flash('Вы успешно вышли.', 'success')
        return redirect(url_for('login_page'))

    def get_common_template_data():
        bot_status = _bot_controller.get_status()
        settings = get_all_settings()
        tz_name, tz_offset = resolve_panel_timezone(settings.get('admin_timezone'))
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
        
        # Формируем динамические URL-ы для Wiki и базы знаний
        global_domain = settings.get('global_domain', '')
        docs_domain = settings.get('docs_domain', '')
        codex_docs_domain = settings.get('codex_docs_domain', '')
        
        # URL для Вики (docs)
        if docs_domain:
            # Убираем слэш в конце если есть
            docs_domain = docs_domain.rstrip('/')
            # Проверяем, есть ли уже протокол
            if not docs_domain.startswith(('http://', 'https://')):
                docs_domain = f'https://{docs_domain}'
            wiki_url = docs_domain
        else:
            # Если домен не настроен, используем localhost
            wiki_url = 'http://localhost:50001'
        
        # URL для базы знаний (codex-docs)
        if codex_docs_domain:
            # Убираем слэш в конце если есть
            codex_docs_domain = codex_docs_domain.rstrip('/')
            # Проверяем, есть ли уже протокол
            if not codex_docs_domain.startswith(('http://', 'https://')):
                codex_docs_domain = f'https://{codex_docs_domain}'
            knowledge_base_url = codex_docs_domain
        elif global_domain:
            # Если codex_docs_domain не настроен, но есть global_domain, используем его
            global_domain = global_domain.rstrip('/')
            if not global_domain.startswith(('http://', 'https://')):
                global_domain = f'https://{global_domain}'
            knowledge_base_url = f'{global_domain}:50002'
        else:
            # Если домены не настроены, используем localhost
            knowledge_base_url = 'http://localhost:50002'
        
        return {
            "bot_status": bot_status, 
            "all_settings_ok": all_settings_ok, 
            "hidden_mode": hidden_mode_enabled, 
            "project_version": project_version,
            "global_settings": settings,
            "wiki_url": wiki_url,
            "knowledge_base_url": knowledge_base_url,
            "panel_timezone": tz_name,
            "panel_timezone_offset": tz_offset,
        }

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

    @flask_app.route('/performance')
    @login_required
    def performance_page():
        """Страница мониторинга производительности"""
        try:
            async def get_performance_data():
                monitor = get_performance_monitor()
                settings = get_all_settings()
                # Применяем настройки к монитору при каждом заходе на страницу
                try:
                    await monitor.apply_settings(
                        enabled=(settings.get('monitoring_enabled', 'true') == 'true'),
                        max_metrics=int(settings.get('monitoring_max_metrics') or 1000),
                        slow_threshold=float(settings.get('monitoring_slow_threshold') or 1.0)
                    )
                except Exception:
                    pass
                
                # Получаем сводку по производительности
                performance_summary = await monitor.get_performance_summary()
                
                # Получаем медленные операции
                slow_operations = await monitor.get_slow_operations(limit=20)
                
                # Получаем последние ошибки
                recent_errors = await monitor.get_recent_errors(limit=20)
                
                # Получаем статистику по операциям
                operation_stats = {}
                for operation in performance_summary.get('top_operations', []):
                    op_name = operation['operation']
                    operation_stats[op_name] = await monitor.get_operation_stats(op_name)
                
                return performance_summary, slow_operations, recent_errors, operation_stats, settings
            
            # Запускаем асинхронную функцию
            performance_summary, slow_operations, recent_errors, operation_stats, settings = asyncio.run(get_performance_data())
            
            common_data = get_common_template_data()
            
            return render_template(
                'performance.html',
                performance_summary=performance_summary,
                slow_operations=slow_operations,
                recent_errors=recent_errors,
                operation_stats=operation_stats,
                monitoring_enabled=(settings.get('monitoring_enabled', 'true') == 'true'),
                **common_data
            )
        except Exception as e:
            logger.error(f"Error in performance_page: {e}")
            flash('Ошибка при загрузке данных мониторинга', 'danger')
            return redirect(url_for('dashboard_page'))

    @flask_app.route('/api/monitoring/toggle', methods=['POST'])
    @login_required
    def api_toggle_monitoring():
        try:
            enabled = request.form.get('enabled') or request.json.get('enabled')
            value = 'true' if str(enabled).lower() in ['true', '1', 'on'] else 'false'
            update_setting('monitoring_enabled', value)
            # Применяем немедленно
            monitor = get_performance_monitor()
            asyncio.run(monitor.set_enabled(value == 'true'))
            return {'success': True, 'enabled': (value == 'true')}
        except Exception as e:
            logger.error(f"Failed to toggle monitoring: {e}")
            return {'success': False, 'message': str(e)}, 500

    @flask_app.route('/api/monitoring/export', methods=['GET'])
    @login_required
    def api_export_monitoring():
        try:
            monitor = get_performance_monitor()
            data = asyncio.run(monitor.export_metrics_json())
            return json.dumps(data, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return {'success': False, 'message': str(e)}, 500

    @flask_app.route('/api/monitoring/hourly-stats', methods=['GET'])
    @login_required
    def api_hourly_stats():
        """API endpoint для получения статистики мониторинга по часам"""
        try:
            hours = request.args.get('hours', 24, type=int)
            if hours < 1 or hours > 168:  # Ограничиваем от 1 часа до недели
                hours = 24
            
            monitor = get_performance_monitor()
            data = asyncio.run(monitor.get_hourly_stats_for_charts(hours))
            return json.dumps(data, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except Exception as e:
            logger.error(f"Failed to get hourly stats: {e}")
            return {'success': False, 'message': str(e)}, 500

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
    # @csrf.exempt
    @login_required
    def get_transaction_details(transaction_id):
        """API endpoint для получения детальной информации о транзакции с улучшенными данными"""
        try:
            with sqlite3.connect(DB_FILE, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Улучшенный запрос с LEFT JOIN для получения username, plan_name и connection_string
                cursor.execute("""
                    SELECT 
                        t.transaction_id,
                        t.payment_id,
                        t.user_id,
                        COALESCE(t.username, u.username) as username,
                        t.status,
                        t.amount_rub,
                        t.amount_currency,
                        t.currency_name,
                        t.payment_method,
                        t.metadata,
                        t.transaction_hash,
                        t.payment_link,
                        t.api_request,
                        t.api_response,
                        t.created_date,
                        -- Получаем plan_name из metadata или из таблицы plans (fallback)
                        COALESCE(
                            json_extract(t.metadata, '$.plan_name'),
                            p.plan_name
                        ) as plan_name,
                        -- Получаем connection_string из metadata или из таблицы vpn_keys (fallback)
                        COALESCE(
                            json_extract(t.metadata, '$.connection_string'),
                            vk.connection_string
                        ) as connection_string,
                        -- Получаем host_name из metadata
                        json_extract(t.metadata, '$.host_name') as host_name
                    FROM transactions t
                    LEFT JOIN users u ON t.user_id = u.telegram_id
                    LEFT JOIN plans p ON json_extract(t.metadata, '$.plan_id') = p.plan_id
                    LEFT JOIN vpn_keys vk ON (
                        t.user_id = vk.user_id 
                        AND json_extract(t.metadata, '$.host_name') = vk.host_name
                        AND vk.created_date <= t.created_date
                    )
                    WHERE t.transaction_id = ?
                    ORDER BY vk.created_date DESC
                    LIMIT 1
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
                
                # Парсим api_request и api_response если это строки
                if transaction.get('api_request'):
                    try:
                        transaction['api_request'] = json.loads(transaction['api_request'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Оставляем как строку если не JSON
                
                if transaction.get('api_response'):
                    try:
                        transaction['api_response'] = json.loads(transaction['api_response'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Оставляем как строку если не JSON
                
                # Очищаем None значения для JSON сериализации
                for key in ['username', 'plan_name', 'connection_string', 'host_name']:
                    if transaction.get(key) is None:
                        transaction[key] = None
                
                return jsonify({
                    'status': 'success',
                    'transaction': transaction
                })
                
        except Exception as e:
            logging.error(f"Error fetching transaction {transaction_id}: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Ошибка при загрузке данных транзакции'
            }), 500

    @flask_app.route('/api/webhooks', methods=['GET'])
    @login_required
    def get_webhooks():
        """API endpoint для получения webhook'ов с фильтрацией и пагинацией"""
        try:
            payment_id = request.args.get('payment_id')
            transaction_id = request.args.get('transaction_id', type=int)
            limit = request.args.get('limit', default=100, type=int)
            offset = request.args.get('offset', default=0, type=int)
            
            # Ограничиваем максимальный лимит
            if limit > 500:
                limit = 500
            
            with sqlite3.connect(DB_FILE, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Строим запрос в зависимости от параметров
                query = """
                    SELECT 
                        webhook_id,
                        webhook_type,
                        event_type,
                        payment_id,
                        transaction_id,
                        request_payload,
                        response_payload,
                        status,
                        created_date
                    FROM webhooks
                    WHERE 1=1
                """
                params = []
                
                if payment_id:
                    query += " AND payment_id = ?"
                    params.append(payment_id)
                
                if transaction_id:
                    query += " AND transaction_id = ?"
                    params.append(transaction_id)
                
                query += " ORDER BY created_date DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Получаем общее количество записей для пагинации
                count_query = "SELECT COUNT(*) as total FROM webhooks WHERE 1=1"
                count_params = []
                
                if payment_id:
                    count_query += " AND payment_id = ?"
                    count_params.append(payment_id)
                
                if transaction_id:
                    count_query += " AND transaction_id = ?"
                    count_params.append(transaction_id)
                
                cursor.execute(count_query, count_params)
                total_count = cursor.fetchone()['total']
                
                # Преобразуем Row в dict и парсим JSON payload
                webhooks = []
                for row in rows:
                    webhook = dict(row)
                    
                    # Парсим request_payload если это JSON
                    if webhook.get('request_payload'):
                        try:
                            webhook['request_payload'] = json.loads(webhook['request_payload'])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Оставляем как строку если не JSON
                    
                    # Парсим response_payload если это JSON
                    if webhook.get('response_payload'):
                        try:
                            webhook['response_payload'] = json.loads(webhook['response_payload'])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Оставляем как строку если не JSON
                    
                    webhooks.append(webhook)
                
                return jsonify({
                    'status': 'success',
                    'webhooks': webhooks,
                    'total': total_count,
                    'limit': limit,
                    'offset': offset
                })
                
        except Exception as e:
            logging.error(f"Error fetching webhooks: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Ошибка при загрузке webhook\'ов'
            }), 500

    @flask_app.route('/transactions/retry/<payment_id>', methods=['POST'])
    @login_required
    def retry_payment_processing(payment_id):
        """Повторная обработка зависшего платежа YooKassa"""
        try:
            logger.info(f"[ADMIN_RETRY] Manual retry requested for payment_id={payment_id}")
            
            # Получаем транзакцию из БД
            from shop_bot.data_manager.database import get_transaction_by_payment_id
            transaction = get_transaction_by_payment_id(payment_id)
            
            if not transaction:
                logger.warning(f"[ADMIN_RETRY] Transaction not found for payment_id={payment_id}")
                return jsonify({
                    'success': False,
                    'message': f'Транзакция с payment_id={payment_id} не найдена'
                }), 404
            
            # Проверяем статус
            if transaction.get('status') == 'paid':
                logger.info(f"[ADMIN_RETRY] Transaction already paid, payment_id={payment_id}")
                return jsonify({
                    'success': False,
                    'message': 'Транзакция уже обработана (статус: paid)'
                }), 400
            
            # Парсим metadata
            metadata = transaction.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            # Проверяем, что это YooKassa платеж
            payment_method = transaction.get('payment_method') or metadata.get('payment_method')
            if payment_method != 'YooKassa':
                return jsonify({
                    'success': False,
                    'message': f'Повторная обработка доступна только для YooKassa платежей (текущий метод: {payment_method})'
                }), 400
            
            # Добавляем дополнительные данные
            metadata['yookassa_payment_id'] = payment_id
            metadata['payment_type'] = 'admin_manual_retry'
            
            # Получаем бот instance
            bot = _bot_controller.get_bot_instance()
            if not bot:
                logger.error(f"[ADMIN_RETRY] Bot instance not available")
                return jsonify({
                    'success': False,
                    'message': 'Бот недоступен. Проверьте статус бота.'
                }), 500
            
            # Получаем event loop
            loop = current_app.config.get('EVENT_LOOP')
            if not loop or not loop.is_running():
                logger.error(f"[ADMIN_RETRY] Event loop not available")
                return jsonify({
                    'success': False,
                    'message': 'Event loop недоступен. Перезапустите бота.'
                }), 500
            
            # Запускаем обработку
            logger.info(f"[ADMIN_RETRY] Starting payment processing for payment_id={payment_id}")
            payment_processor = handlers.process_successful_yookassa_payment
            future = asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
            
            try:
                # Ждем результат с таймаутом
                future.result(timeout=10)
                logger.info(f"[ADMIN_RETRY] Successfully processed payment_id={payment_id}")
                
                return jsonify({
                    'success': True,
                    'message': 'Платеж успешно обработан. Ключ выдан пользователю.'
                })
                
            except TimeoutError:
                logger.error(f"[ADMIN_RETRY] Processing timeout for payment_id={payment_id}")
                return jsonify({
                    'success': False,
                    'message': 'Превышено время ожидания обработки. Проверьте логи бота.'
                }), 500
                
            except Exception as processing_error:
                logger.error(f"[ADMIN_RETRY] Processing failed for payment_id={payment_id}: {processing_error}", exc_info=True)
                return jsonify({
                    'success': False,
                    'message': f'Ошибка при обработке: {str(processing_error)}'
                }), 500
                
        except Exception as e:
            logger.error(f"[ADMIN_RETRY] Error in retry handler: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Ошибка: {str(e)}'
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
        try:
            # Локальный импорт, чтобы не тянуть все зависимости наверх файла
            from shop_bot.data_manager.database import get_all_user_groups
            user_groups = get_all_user_groups()
        except Exception:
            user_groups = []
        return render_template('promo_codes.html', user_groups=user_groups, **common_data)

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
        about_content = current_settings.get('about_content', '')
        support_content = current_settings.get('support_content', '')
        
        # Для terms и privacy используем наши внутренние страницы
        terms_content = request.url_root.rstrip('/') + '/terms'
        privacy_content = request.url_root.rstrip('/') + '/privacy'
        
        # НОВОЕ: Определяем активный режим YooKassa
        yookassa_active_mode = 'unknown'
        try:
            active_shop_id = getattr(Configuration, 'account_id', None)
            db_shop_id = current_settings.get('yookassa_shop_id', '')
            db_test_shop_id = current_settings.get('yookassa_test_shop_id', '')
            
            if active_shop_id:
                # Сравниваем первые 8 символов для определения режима
                if db_test_shop_id and active_shop_id.startswith(db_test_shop_id[:8]):
                    yookassa_active_mode = 'test'
                elif db_shop_id and active_shop_id.startswith(db_shop_id[:8]):
                    yookassa_active_mode = 'production'
        except Exception as e:
            logger.debug(f"Could not determine YooKassa active mode: {e}")
        
        common_data = get_common_template_data()
        # Получаем группы пользователей для multiselect в тарифах - точно как в промокодах
        try:
            from shop_bot.data_manager.database import get_all_user_groups
            user_groups = get_all_user_groups()
        except Exception:
            user_groups = []
        return render_template(
            'settings.html',
            hosts=hosts,
            settings=current_settings,
            active_tab=active_tab,
            about_content=about_content,
            support_content=support_content,
            terms_content=terms_content,
            privacy_content=privacy_content,
            user_groups=user_groups,
            timezone_options=TIMEZONES,
            yookassa_active_mode=yookassa_active_mode,  # НОВОЕ
            **common_data,
        )

    @flask_app.route('/settings/panel', methods=['POST'])
    @login_required
    def save_panel_settings():
        """Сохранение настроек панели - v2.1"""
        panel_keys = ['panel_login', 'global_domain', 'docs_domain', 'codex_docs_domain', 'user_cabinet_domain', 'admin_timezone', 'monitoring_max_metrics', 'monitoring_slow_threshold', 'monitoring_cleanup_hours']
        
        # Пароль отдельно, если указан
        if 'panel_password' in request.form and request.form.get('panel_password'):
            new_password = request.form.get('panel_password').strip()
            if new_password:
                hashed_password = hash_password(new_password)
                update_setting('panel_password', hashed_password)
        
        # Обновляем остальные настройки панели
        for key in panel_keys:
            value = request.form.get(key, '')
            if key == 'admin_timezone':
                value = (value or '').strip()
                if not validate_timezone(value):
                    value = DEFAULT_TIMEZONE
            update_setting(key, value)
        
        # Обработка чекбоксов панели
        panel_checkboxes = ['auto_delete_orphans', 'monitoring_enabled']
        for checkbox_key in panel_checkboxes:
            values = request.form.getlist(checkbox_key)
            value = 'true' if 'true' in values else 'false'
            update_setting(checkbox_key, value)
        
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
            'trial_duration_days', 'minimum_withdrawal', 'referral_percentage', 'referral_discount', 'minimum_topup',
            'logging_bot_token', 'logging_bot_username', 'logging_bot_admin_chat_id', 'logging_bot_level'
        ]
        
        bot_checkboxes = ['force_subscription', 'trial_enabled', 'enable_referrals', 'support_enabled']
        
        # Обрабатываем чекбоксы (стандартные: checked = 'true')
        for checkbox_key in bot_checkboxes:
            values = request.form.getlist(checkbox_key)
            value = 'true' if 'true' in values else 'false'
            update_setting(checkbox_key, value)
        
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
        
        # Обрабатываем чекбоксы
        # Для чекбоксов с hidden input (sbp_enabled, stars_enabled, yookassa_verify_ssl, yookassa_test_verify_ssl):
        #   используем getlist() и проверяем наличие 'true' в списке значений
        # Для yookassa_test_mode (без hidden input): простая проверка наличия в форме
        payment_checkboxes_with_hidden = ['sbp_enabled', 'stars_enabled', 'yookassa_verify_ssl', 'yookassa_test_verify_ssl', 'yookassa_local_stub']
        for checkbox_key in payment_checkboxes_with_hidden:
            values = request.form.getlist(checkbox_key)
            value = 'true' if 'true' in values else 'false'
            logging.info(f"[PAYMENT_SETTINGS] Saving {checkbox_key}: value='{value}', all_form_values={values}")
            update_setting(checkbox_key, value)
        
        # Обработка yookassa_test_mode - простой checkbox без hidden input
        # Если checkbox checked, он присутствует в форме со значением 'true'
        # Если checkbox unchecked, его нет в форме вообще
        yookassa_test_mode_value = 'true' if request.form.get('yookassa_test_mode') == 'true' else 'false'
        logging.info(f"[PAYMENT_SETTINGS] Saving yookassa_test_mode: value='{yookassa_test_mode_value}', in_form={request.form.get('yookassa_test_mode')}")
        update_setting('yookassa_test_mode', yookassa_test_mode_value)
        # Проверяем что значение действительно сохранилось (используем database.get_setting чтобы избежать конфликта с локальным импортом ниже)
        saved_value = database.get_setting('yookassa_test_mode')
        logging.info(f"[PAYMENT_SETTINGS] After save yookassa_test_mode: saved_value='{saved_value}'")
        
        # Обрабатываем остальные настройки
        for key in payment_keys:
            update_setting(key, request.form.get(key, ''))
        
        # Изменения сохраняются напрямую в основную базу (DELETE режим журналирования)
        
        # КРИТИЧЕСКИ ВАЖНО: Переинициализируем Configuration после сохранения настроек YooKassa
        try:
            from shop_bot.data_manager.database import get_setting
            
            yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
            
            if yookassa_test_mode:
                shop_id = (get_setting("yookassa_test_shop_id") or "").strip() or (get_setting("yookassa_shop_id") or "").strip()
                secret_key = (get_setting("yookassa_test_secret_key") or "").strip() or (get_setting("yookassa_secret_key") or "").strip()
                api_url = (get_setting("yookassa_test_api_url") or "").strip() or (get_setting("yookassa_api_url") or "").strip() or "https://api.test.yookassa.ru/v3"
                verify_ssl = get_setting("yookassa_test_verify_ssl") != "false"
            else:
                shop_id = (get_setting("yookassa_shop_id") or "").strip()
                secret_key = (get_setting("yookassa_secret_key") or "").strip()
                api_url = (get_setting("yookassa_api_url") or "").strip() or "https://api.yookassa.ru/v3"
                verify_ssl = get_setting("yookassa_verify_ssl") != "false"
            
            if shop_id and secret_key:
                Configuration.configure(
                    account_id=shop_id,
                    secret_key=secret_key,
                    api_url=api_url,
                    verify=verify_ssl
                )
                logger.info(f"YooKassa Configuration updated after settings save: test_mode={yookassa_test_mode}, shop_id={shop_id}, api_url={api_url}")
        except Exception as e:
            logger.error(f"Failed to reconfigure YooKassa after settings save: {e}", exc_info=True)
        
        flash('Настройки платежных систем успешно сохранены!', 'success')
        return redirect(url_for('settings_page', tab='payments'))

    @flask_app.route('/test-logging-bot', methods=['POST'])
    @login_required
    def test_logging_bot():
        """Отправка тестового сообщения в бота логов"""
        try:
            data = request.get_json()
            token = data.get('token')
            chat_id = data.get('chat_id')
            
            if not token or not chat_id:
                return jsonify({'success': False, 'message': 'Не указаны токен или ID чата'}), 400
            
            # Импортируем модуль telegram_logger
            from shop_bot.utils.telegram_logger import TelegramLoggerHandler
            
            # Создаем временный обработчик для тестовой отправки
            handler = TelegramLoggerHandler(
                bot_token=token,
                admin_chat_id=chat_id,
                log_level='all',
                enabled=True
            )
            
            # Отправляем тестовое сообщение
            import asyncio
            result = asyncio.run(handler.send_test_message(
                "🧪 <b>Тестовое сообщение от бота логирования</b>\n\n"
                "✅ Если вы видите это сообщение, значит бот для логов настроен правильно!\n\n"
                "📋 <b>Информация о настройке:</b>\n"
                "• Токен бота: Настроен\n"
                "• ID администратора: Настроен\n"
                "• Статус: Активен\n\n"
                "Теперь все ошибки и предупреждения будут приходить в этот чат."
            ))
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error testing logging bot: {e}")
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

    @flask_app.route('/api/support/check-config', methods=['POST'])
    @login_required
    def api_support_check_config():
        """API для проверки конфигурации бота поддержки"""
        try:
            if not _bot_controller.support_bot or not _bot_controller.support_is_running:
                return jsonify({
                    'success': False,
                    'message': '❌ Бот поддержки не запущен. Запустите его сначала.'
                }), 400
            
            # Получаем настройки
            support_group_id = database.get_setting("support_group_id")
            support_bot_token = database.get_setting("support_bot_token")
            
            config_info = "🔧 Конфигурация бота поддержки:\n\n"
            config_info += f"📋 Support Group ID: {support_group_id or 'Не настроено'}\n"
            config_info += f"🔑 Support Bot Token: {'Настроено' if support_bot_token else 'Не настроено'}\n\n"
            
            if not support_group_id:
                config_info += "❌ Ошибка: ID группы поддержки не настроен\n"
                return jsonify({'success': True, 'message': config_info})
            elif not support_bot_token:
                config_info += "❌ Ошибка: Токен бота поддержки не настроен\n"
                return jsonify({'success': True, 'message': config_info})
            
            # Выполняем асинхронную проверку
            async def check_config():
                bot = _bot_controller.support_bot
                try:
                    chat_info = await bot.get_chat(support_group_id)
                    result = f"✅ Группа найдена: {chat_info.title}\n"
                    
                    # Проверяем темы
                    try:
                        test_topic = await bot.create_forum_topic(
                            chat_id=support_group_id, 
                            name="Тестовая тема для проверки"
                        )
                        await bot.delete_forum_topic(
                            chat_id=support_group_id, 
                            message_thread_id=test_topic.message_thread_id
                        )
                        result += "📊 Тип: Темы включены\n"
                        result += "✅ Статус: Группа настроена корректно\n"
                    except Exception as forum_error:
                        result += "📊 Тип: Обычная группа\n"
                        result += "❌ Ошибка: Темы не включены в группе!\n"
                        result += "💡 Решение: Включите функцию 'Темы' в настройках группы\n"
                    
                    return result
                except Exception as e:
                    error_msg = f"❌ Ошибка доступа к группе: {e}\n"
                    if "upgraded to a supergroup" in str(e):
                        error_msg += "💡 ВАЖНО: Группа была мигрирована в супергруппу!\n"
                        error_msg += "• При включении тем Telegram автоматически мигрирует группу\n"
                        error_msg += "• Новый ID обычно начинается с -100\n"
                        error_msg += "• Обновите ID группы в настройках\n"
                    else:
                        error_msg += "💡 Решение: Убедитесь, что бот добавлен в группу и имеет права администратора\n"
                    return error_msg
            
            import asyncio
            loop = _bot_controller._loop
            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(check_config(), loop)
                check_result = future.result(timeout=30)
            else:
                check_result = "❌ Ошибка: Event loop не запущен"
            config_info += check_result
            
            return jsonify({'success': True, 'message': config_info})
            
        except Exception as e:
            logger.error(f"Error in api_support_check_config: {e}")
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

    @flask_app.route('/api/support/check-test', methods=['POST'])
    @login_required
    def api_support_check_test():
        """API для тестирования бота поддержки"""
        try:
            if not bot_controller_instance.support_bot or not bot_controller_instance.support_is_running:
                return jsonify({
                    'success': False,
                    'message': '❌ Бот поддержки не запущен. Запустите его сначала.'
                }), 400
            
            # Получаем настройки
            support_group_id = database.get_setting("support_group_id")
            support_bot_token = database.get_setting("support_bot_token")
            
            test_info = "🧪 Тест бота поддержки:\n\n"
            test_info += f"📋 Support Group ID: {support_group_id or 'Не настроено'}\n"
            test_info += f"🔑 Support Bot Token: {'Настроено' if support_bot_token else 'Не настроено'}\n\n"
            
            if not support_group_id:
                test_info += "❌ Ошибка: ID группы поддержки не настроен\n"
                return jsonify({'success': True, 'message': test_info})
            elif not support_bot_token:
                test_info += "❌ Ошибка: Токен бота поддержки не настроен\n"
                return jsonify({'success': True, 'message': test_info})
            
            # Выполняем асинхронный тест
            async def test_bot():
                bot = bot_controller_instance.support_bot
                try:
                    chat_info = await bot.get_chat(support_group_id)
                    result = f"✅ Группа найдена: {chat_info.title}\n"
                    result += f"📊 Тип группы: {chat_info.type}\n"
                    result += f"🆔 ID группы: {chat_info.id}\n"
                    
                    # Проверяем права бота
                    try:
                        bot_member = await bot.get_chat_member(support_group_id, bot.id)
                        result += f"👤 Статус бота: {bot_member.status}\n"
                        
                        if bot_member.status in ['administrator', 'creator']:
                            result += "✅ Права: Бот является администратором\n"
                        else:
                            result += "❌ Права: Бот не является администратором\n"
                            result += "💡 Решение: Сделайте бота администратором группы\n"
                    except Exception as member_error:
                        result += f"❌ Ошибка проверки прав: {member_error}\n"
                    
                    # Тест отправки сообщения
                    result += "\n🧪 Тест отправки сообщения:\n"
                    try:
                        await bot.send_message(
                            chat_id=support_group_id,
                            text="🧪 Тестовое сообщение от бота поддержки (через веб-панель)",
                            disable_notification=True
                        )
                        result += "✅ Сообщение отправлено успешно\n"
                    except Exception as send_error:
                        result += f"❌ Ошибка отправки: {send_error}\n"
                    
                    return result
                except Exception as e:
                    error_msg = f"❌ Ошибка доступа к группе: {e}\n"
                    error_msg += "💡 Возможные решения:\n"
                    error_msg += "• Убедитесь, что ID группы правильный\n"
                    error_msg += "• Проверьте, что бот добавлен в группу\n"
                    if "upgraded to a supergroup" in str(e):
                        error_msg += "• ВАЖНО: Группа была мигрирована в супергруппу!\n"
                        error_msg += "• Новый ID обычно начинается с -100\n"
                        error_msg += "• Обновите ID группы в настройках\n"
                    return error_msg
            
            import asyncio
            loop = bot_controller_instance._loop
            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(test_bot(), loop)
                test_result = future.result(timeout=30)
            else:
                test_result = "❌ Ошибка: Event loop не запущен"
            test_info += test_result
            
            return jsonify({'success': True, 'message': test_info})
            
        except Exception as e:
            logger.error(f"Error in api_support_check_test: {e}")
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

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
    # @csrf.exempt
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
                    # Используем то же название поля для настроек
                    update_setting(field_name, value)
            
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
        # Обрабатываем случай, когда result может быть bool или dict
        if isinstance(result, dict):
            flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        else:
            # Если result - bool, используем стандартные сообщения
            flash('Бот успешно запущен.' if result else 'Ошибка при запуске бота.', 'success' if result else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-shop-bot', methods=['POST'])
    @login_required
    def stop_shop_bot_route():
        result = _bot_controller.stop_shop_bot()
        # Обрабатываем случай, когда result может быть bool или dict
        if isinstance(result, dict):
            flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        else:
            # Если result - bool, используем стандартные сообщения
            flash('Бот успешно остановлен.' if result else 'Ошибка при остановке бота.', 'success' if result else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/start-support-bot', methods=['POST'])
    @login_required
    def start_support_bot_route():
        result = _bot_controller.start_support_bot()
        # Обрабатываем случай, когда result может быть bool или dict
        if isinstance(result, dict):
            flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        else:
            # Если result - bool, используем стандартные сообщения
            flash('Бот успешно запущен.' if result else 'Ошибка при запуске бота.', 'success' if result else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-support-bot', methods=['POST'])
    @login_required
    def stop_support_bot_route():
        result = _bot_controller.stop_support_bot()
        # Обрабатываем случай, когда result может быть bool или dict
        if isinstance(result, dict):
            flash(result.get('message', 'An error occurred.'), 'success' if result.get('status') == 'success' else 'danger')
        else:
            # Если result - bool, используем стандартные сообщения
            flash('Бот успешно остановлен.' if result else 'Ошибка при остановке бота.', 'success' if result else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/orphan-deletions-log')
    @login_required
    def orphan_deletions_log():
        """Просмотр лог-файла удалённых orphan клиентов."""
        log_file = PROJECT_ROOT / "logs" / "orphan_deletions.log"
        
        if not log_file.exists():
            return render_template('orphan_deletions_log.html', entries=[], message="Лог-файл пока пуст.")
        
        try:
            entries = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            
            # Сортируем по дате (новые сверху)
            entries.reverse()
            
            return render_template('orphan_deletions_log.html', entries=entries)
        except Exception as e:
            return render_template('orphan_deletions_log.html', entries=[], message=f"Ошибка при чтении лог-файла: {str(e)}")

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
    # @csrf.exempt
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
    # @csrf.exempt
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

    @flask_app.route('/api/update-video-instructions-display', methods=['POST'])
    @login_required
    def update_video_instructions_display():
        """API для обновления настройки отображения кнопки 'Видеоинструкции' в боте"""
        try:
            data = request.get_json()
            show_in_bot = data.get('show_in_bot', False)
            
            from shop_bot.data_manager.database import set_video_instructions_display_setting
            set_video_instructions_display_setting(show_in_bot)
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Failed to update video instructions display setting: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

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
            from shop_bot.data_manager.database import get_all_video_instructions, get_video_instructions_display_setting
            videos = get_all_video_instructions()
            video_instructions_show_in_bot = get_video_instructions_display_setting()
            logger.info(f"Video mode: found {len(videos)} videos")
            common_data = get_common_template_data()
            return render_template(
                'instructions.html',
                mode='video',
                videos=videos,
                active_tab='video',
                video_instructions_show_in_bot=video_instructions_show_in_bot,
                **common_data
            )

        if request.method == 'POST':
            try:
                platform = request.form.get('platform', active_tab)
                new_content = request.form.get('instructions_content', '')
                show_in_bot = request.form.get('show_in_bot') == 'on'
                
                # Сохраняем текст инструкции
                file_path = get_file_for(platform)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Сохраняем настройку отображения в боте
                from shop_bot.data_manager.database import set_instruction_display_setting
                set_instruction_display_setting(platform, show_in_bot)
                
                flash('Инструкции и настройки сохранены.', 'success')
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

        # Получаем настройку отображения в боте для текущей платформы
        from shop_bot.data_manager.database import get_instruction_display_setting
        show_in_bot = get_instruction_display_setting(active_tab)

        return render_template(
            'instructions.html',
            mode='text',
            active_tab=active_tab,
            instructions_text=instructions_text,
            show_in_bot=show_in_bot,
            **get_common_template_data()
        )

    # ============================================
    # API для работы с видеоинструкциями
    # ============================================
    
    @flask_app.route('/api/video/<int:video_id>', methods=['GET'])
    # @csrf.exempt
    @login_required
    def get_video_api(video_id):
        """Получение данных видеоинструкции"""
        from shop_bot.data_manager.database import get_video_instruction_by_id
        
        video = get_video_instruction_by_id(video_id)
        if video:
            return jsonify(video), 200
        return jsonify({'error': 'Video not found'}), 404
    
    @flask_app.route('/api/video/create', methods=['POST'])
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
            if key_provision_mode not in ['key', 'subscription', 'both', 'cabinet', 'cabinet_subscription']:
                key_provision_mode = 'key'
            
            # Получаем режим отображения
            display_mode = request.form.get('display_mode', 'all')
            if display_mode not in ['all', 'hidden_all', 'hidden_new', 'hidden_old']:
                display_mode = 'all'
            
            # Получаем режим отображения (группы) - multiselect
            display_mode_groups_raw = request.form.getlist('display_mode_groups[]')
            display_mode_groups = None
            if display_mode_groups_raw:
                try:
                    display_mode_groups = [int(gid) for gid in display_mode_groups_raw if gid and str(gid).isdigit()]
                    if len(display_mode_groups) == 0:
                        display_mode_groups = None
                except (ValueError, TypeError):
                    display_mode_groups = None
            
            create_plan(
                host_name=host_name,
                plan_name=plan_data['plan_name'],
                months=plan_data['months'],
                price=plan_data['price'],
                days=plan_data['days'],
                traffic_gb=plan_data['traffic_gb'],
                hours=plan_data['hours'],
                key_provision_mode=key_provision_mode,
                display_mode=display_mode,
                display_mode_groups=display_mode_groups
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
        if key_provision_mode not in ['key', 'subscription', 'both', 'cabinet', 'cabinet_subscription']:
            key_provision_mode = 'key'
        
        # Получаем режим отображения
        display_mode = request.form.get('display_mode', plan.get('display_mode', 'all'))
        if display_mode not in ['all', 'hidden_all', 'hidden_new', 'hidden_old']:
            display_mode = 'all'
        
        # Получаем режим отображения (группы) - multiselect
        display_mode_groups_raw = request.form.getlist('display_mode_groups[]')
        display_mode_groups = None
        if display_mode_groups_raw:
            try:
                display_mode_groups = [int(gid) for gid in display_mode_groups_raw if gid and str(gid).isdigit()]
                if len(display_mode_groups) == 0:
                    display_mode_groups = None
            except (ValueError, TypeError):
                display_mode_groups = None
        
        update_plan(plan_id, plan_name, months, days, price, traffic_gb, hours, key_provision_mode, display_mode, display_mode_groups)
        flash("Тариф обновлен.", 'success')
        return redirect(url_for('settings_page', tab='servers'))

    @flask_app.route('/yookassa-webhook', methods=['GET', 'POST'])
    @measure_performance_sync("yookassa_webhook")
    def yookassa_webhook_handler():
        # GET запрос для health check
        if request.method == 'GET':
            return jsonify({
                'status': 'ok',
                'endpoint': 'yookassa-webhook',
                'methods': ['GET', 'POST'],
                'message': 'YooKassa webhook endpoint is available'
            }), 200
        
        # POST запрос для обработки webhook от YooKassa
        try:
            event_json = request.json
            if not event_json:
                logger.warning("[YOOKASSA_WEBHOOK] Received empty or invalid JSON payload")
                return jsonify({'error': 'Invalid JSON payload'}), 400
            
            # Валидация обязательных полей структуры YooKassa
            if not isinstance(event_json, dict):
                logger.warning(f"[YOOKASSA_WEBHOOK] Invalid payload type: {type(event_json).__name__}")
                return jsonify({'error': 'Invalid payload structure'}), 400
            
            event_type = event_json.get("event")
            payment_object = event_json.get("object", {})
            
            # Проверяем, что есть обязательные поля
            if not event_type:
                logger.warning("[YOOKASSA_WEBHOOK] Missing 'event' field in payload")
                return jsonify({'error': 'Missing required field: event'}), 400
            
            if not isinstance(payment_object, dict):
                logger.warning(f"[YOOKASSA_WEBHOOK] Invalid 'object' field type: {type(payment_object).__name__}")
                return jsonify({'error': 'Invalid object structure'}), 400
            
            payment_id = payment_object.get("id")
            
            # Извлекаем поле test для проверки режима
            is_test_payment = payment_object.get("test", False)
            
            logger.info(
                f"[YOOKASSA_WEBHOOK] Received webhook: event={event_type}, payment_id={payment_id}, "
                f"test={is_test_payment}, paid={payment_object.get('paid')}, "
                f"status={payment_object.get('status')}"
            )
            
            # Сохраняем webhook в БД асинхронно (в фоне, чтобы не блокировать обработку)
            try:
                from shop_bot.data_manager.database import save_webhook_to_db, get_transaction_by_payment_id
                # Получаем transaction_id если транзакция существует
                existing_transaction = get_transaction_by_payment_id(payment_id)
                transaction_id = existing_transaction.get('transaction_id') if existing_transaction else None
                
                # Сохраняем webhook в фоне через threading для избежания блокировок БД
                import threading
                def save_webhook_background():
                    try:
                        webhook_id = save_webhook_to_db(
                            webhook_type='yookassa',
                            event_type=event_type,
                            payment_id=payment_id,
                            transaction_id=transaction_id,
                            request_payload=event_json,
                            status='received'
                        )
                        if webhook_id:
                            logger.debug(f"[YOOKASSA_WEBHOOK] Webhook saved to DB with id={webhook_id}")
                    except Exception as e:
                        logger.error(f"[YOOKASSA_WEBHOOK] Failed to save webhook to DB: {e}", exc_info=True)
                
                # Запускаем сохранение в отдельном потоке
                thread = threading.Thread(target=save_webhook_background, daemon=True)
                thread.start()
            except Exception as e:
                logger.warning(f"[YOOKASSA_WEBHOOK] Failed to initiate webhook save: {e}", exc_info=True)
            
            # Проверяем соответствие режимов
            db_test_mode = get_setting("yookassa_test_mode") == "true"
            if is_test_payment != db_test_mode:
                logger.warning(
                    f"[YOOKASSA_WEBHOOK] MODE MISMATCH! webhook test={is_test_payment}, "
                    f"db test_mode={db_test_mode}, payment_id={payment_id}. "
                    f"Проверьте настройки YooKassa в админ-панели!"
                )
            
            # Проверяем транзакцию в БД (если еще не получили выше)
            if 'existing_transaction' not in locals():
                from shop_bot.data_manager.database import get_transaction_by_payment_id
                existing_transaction = get_transaction_by_payment_id(payment_id)
            
            if existing_transaction:
                logger.info(
                    f"[YOOKASSA_WEBHOOK] Transaction found in DB: id={existing_transaction.get('transaction_id')}, "
                    f"status={existing_transaction.get('status')}, user_id={existing_transaction.get('user_id')}"
                )
                
                if existing_transaction.get('status') == 'paid':
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] Payment {payment_id} already processed (status=paid), "
                        f"skipping duplicate webhook"
                    )
                    return 'OK', 200
            else:
                logger.warning(
                    f"[YOOKASSA_WEBHOOK] Transaction NOT FOUND in DB for payment_id={payment_id}! "
                    f"This indicates that create_pending_transaction() failed or was not called. "
                    f"Attempting to process anyway using metadata from webhook..."
                )
            
            # Обрабатываем разные типы событий
            if event_type == "payment.succeeded":
                # Проверяем, что платеж действительно оплачен
                if payment_object.get("paid") is True:
                    # ИСПРАВЛЕНИЕ: Используем metadata из транзакции в БД как основу
                    # Это гарантирует наличие host_code, который был передан при создании платежа
                    metadata = {}
                    metadata_source = "webhook"
                    
                    if existing_transaction and existing_transaction.get('metadata'):
                        # Используем metadata из БД как основу
                        db_metadata = existing_transaction.get('metadata', {})
                        if isinstance(db_metadata, dict):
                            metadata = db_metadata.copy()
                            metadata_source = "database"
                            logger.info(
                                f"[YOOKASSA_WEBHOOK] Using metadata from DB transaction for payment_id={payment_id}"
                            )
                    
                    # Дополняем/перезаписываем данными из webhook payload
                    raw_metadata = payment_object.get("metadata")
                    if isinstance(raw_metadata, dict):
                        # Обновляем metadata данными из webhook (могут быть более свежие значения)
                        metadata.update(raw_metadata)
                        if metadata_source == "database":
                            metadata_source = "database+webhook"
                        else:
                            metadata_source = "webhook"
                    elif raw_metadata:
                        logger.warning(
                            f"[YOOKASSA_WEBHOOK] Received metadata in unexpected format "
                            f"(type={type(raw_metadata).__name__}) for payment_id={payment_id}. "
                            f"Using metadata from {'DB' if existing_transaction else 'empty dict'}."
                        )
                        if raw_metadata:
                            logger.warning(f"[YOOKASSA_WEBHOOK] RAW_METADATA_FALLBACK: {raw_metadata}")
                    
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] Processing payment.succeeded: "
                        f"metadata_source={metadata_source}, "
                        f"user_id={metadata.get('user_id')}, "
                        f"action={metadata.get('action')}, "
                        f"plan_id={metadata.get('plan_id')}, "
                        f"host_code={metadata.get('host_code')}, "
                        f"host_name={metadata.get('host_name')}, "
                        f"amount={payment_object.get('amount', {}).get('value')}"
                    )
                    
                    # Извлекаем дополнительные данные YooKassa
                    yookassa_payment_id = payment_object.get("id")
                    authorization_details = payment_object.get("authorization_details", {})
                    rrn = authorization_details.get("rrn")
                    auth_code = authorization_details.get("auth_code")
                    
                    # Получаем способ оплаты
                    payment_method = payment_object.get("payment_method", {})
                    payment_type = payment_method.get("type", "unknown")
                    
                    # Обновляем метаданные с дополнительной информацией от YooKassa
                    metadata.update({
                        "yookassa_payment_id": yookassa_payment_id,
                        "rrn": rrn,
                        "authorization_code": auth_code,
                        "payment_type": payment_type,
                        "payment_id": payment_id  # Добавляем payment_id для обновления транзакции
                    })

                    host_ok, _ = _ensure_host_metadata(metadata, payment_id)
                    if not host_ok:
                        logger.error(f"[YOOKASSA_WEBHOOK] Aborting processing for payment_id={payment_id} due to missing host binding.")
                        return 'OK', 200
                    
                    bot = _bot_controller.get_bot_instance()
                    payment_processor = handlers.process_successful_yookassa_payment

                    if metadata and bot is not None and payment_processor is not None:
                        loop = current_app.config.get('EVENT_LOOP')
                        if loop and loop.is_running():
                            logger.info(f"[YOOKASSA_WEBHOOK] Submitting payment processing to event loop for payment_id={payment_id}")
                            
                            # Сериализуем webhook payload для сохранения в api_response
                            api_response_json = json.dumps(event_json, ensure_ascii=False)
                            
                            # Атомарно обновляем транзакцию с api_response перед обработкой платежа
                            # Это предотвращает race condition при одновременных webhook'ах
                            try:
                                from shop_bot.data_manager.database import update_yookassa_transaction_atomic
                                amount_value = payment_object.get('amount', {}).get('value')
                                amount_rub = float(amount_value) if amount_value else 0.0
                                
                                # Определяем текущий статус транзакции для атомарного обновления
                                current_status = existing_transaction.get('status') if existing_transaction else 'pending'
                                
                                # Атомарно обновляем только если статус еще не 'paid'
                                if current_status != 'paid':
                                    success = update_yookassa_transaction_atomic(
                                        payment_id, current_status, 'paid', amount_rub,
                                        yookassa_payment_id, rrn, auth_code, payment_type,
                                        metadata, api_response=api_response_json
                                    )
                                    if success:
                                        logger.info(f"[YOOKASSA_WEBHOOK] Atomically updated transaction to 'paid' for payment_id={payment_id}")
                                    else:
                                        logger.warning(f"[YOOKASSA_WEBHOOK] Failed to atomically update transaction (may be already processed) for payment_id={payment_id}")
                                        return 'OK', 200  # Пропускаем обработку, если статус уже изменен
                                else:
                                    logger.info(f"[YOOKASSA_WEBHOOK] Transaction already paid, skipping duplicate webhook for payment_id={payment_id}")
                                    return 'OK', 200
                            except Exception as update_error:
                                logger.error(
                                    f"[YOOKASSA_WEBHOOK] Failed to atomically update transaction with api_response: {update_error}",
                                    exc_info=True
                                )
                                # Не прерываем обработку, но логируем ошибку
                            
                            future = asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
                            
                            # Ждем завершения с таймаутом для логирования результата
                            try:
                                future.result(timeout=5)
                                logger.info(f"[YOOKASSA_WEBHOOK] Payment processing completed successfully for payment_id={payment_id}")
                                
                                # Обновляем статус webhook в БД на 'processed'
                                try:
                                    from shop_bot.data_manager.database import save_webhook_to_db
                                    if existing_transaction:
                                        transaction_id = existing_transaction.get('transaction_id')
                                        # Обновляем статус последнего webhook для этого payment_id
                                        import sqlite3
                                        from shop_bot.data_manager.database import DB_FILE
                                        with sqlite3.connect(DB_FILE, timeout=30) as conn:
                                            cursor = conn.cursor()
                                            cursor.execute("""
                                                UPDATE webhooks 
                                                SET status = 'processed' 
                                                WHERE webhook_id = (
                                                    SELECT webhook_id 
                                                    FROM webhooks 
                                                    WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
                                                    ORDER BY created_date DESC 
                                                    LIMIT 1
                                                )
                                            """, (payment_id, event_type))
                                            conn.commit()
                                except Exception as webhook_update_error:
                                    logger.warning(f"[YOOKASSA_WEBHOOK] Failed to update webhook status: {webhook_update_error}")
                                    
                            except Exception as future_error:
                                logger.error(
                                    f"[YOOKASSA_WEBHOOK] Payment processing failed for payment_id={payment_id}: {future_error}",
                                    exc_info=True
                                )
                                
                                # Обновляем статус webhook в БД на 'error'
                                try:
                                    import sqlite3
                                    from shop_bot.data_manager.database import DB_FILE
                                    with sqlite3.connect(DB_FILE, timeout=30) as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("""
                                            UPDATE webhooks 
                                            SET status = 'error' 
                                            WHERE webhook_id = (
                                                SELECT webhook_id 
                                                FROM webhooks 
                                                WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
                                                ORDER BY created_date DESC 
                                                LIMIT 1
                                            )
                                        """, (payment_id, event_type))
                                        conn.commit()
                                except Exception as webhook_update_error:
                                    logger.warning(f"[YOOKASSA_WEBHOOK] Failed to update webhook error status: {webhook_update_error}")
                        else:
                            logger.error(
                                f"[YOOKASSA_WEBHOOK] CRITICAL: Event loop is not available for payment_id={payment_id}! "
                                f"Payment will NOT be processed. Check bot initialization and webhook app setup."
                            )
                            # Fallback: сохраняем данные для ручной обработки
                            logger.error(f"[YOOKASSA_WEBHOOK] FALLBACK DATA: payment_id={payment_id}, metadata={metadata}")
                    else:
                        logger.error(
                            f"[YOOKASSA_WEBHOOK] Missing required components: "
                            f"metadata={metadata is not None}, bot={bot is not None}, processor={payment_processor is not None}"
                        )
                else:
                    logger.warning(f"[YOOKASSA_WEBHOOK] payment.succeeded but paid=false, payment_id={payment_object.get('id')}")
            
            elif event_type == "payment.waiting_for_capture":
                yookassa_payment_id = payment_object.get("id")
                paid_flag = payment_object.get("paid") is True

                if not paid_flag:
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] payment.waiting_for_capture with paid=false, payment_id={yookassa_payment_id}. "
                        f"Awaiting manual capture."
                    )
                    return 'OK', 200

                logger.info(
                    f"[YOOKASSA_WEBHOOK] payment.waiting_for_capture received with paid=true, attempting capture for payment_id={yookassa_payment_id}"
                )

                capture_payload = {}
                capture_status = None
                try:
                    capture_response = Payment.capture(yookassa_payment_id)
                    raw_capture_json = getattr(capture_response, "json", None)
                    if callable(raw_capture_json):
                        raw_data = raw_capture_json()
                        if isinstance(raw_data, str):
                            capture_payload = json.loads(raw_data)
                        elif isinstance(raw_data, dict):
                            capture_payload = raw_data
                    capture_status = capture_payload.get('status') if isinstance(capture_payload, dict) else getattr(capture_response, "status", None)
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] Capture call completed for payment_id={yookassa_payment_id}, "
                        f"status={capture_status or 'unknown'}"
                    )
                except ApiError as api_error:
                    logger.error(
                        f"[YOOKASSA_WEBHOOK] Capture API error for payment_id={yookassa_payment_id}: {api_error}"
                    )
                    return 'OK', 200
                except Exception as capture_error:
                    logger.error(
                        f"[YOOKASSA_WEBHOOK] Unexpected error during capture for payment_id={yookassa_payment_id}: {capture_error}",
                        exc_info=True
                    )
                    return 'OK', 200

                if capture_status not in ("succeeded", "waiting_for_capture"):
                    logger.warning(
                        f"[YOOKASSA_WEBHOOK] Capture returned non-success status '{capture_status}' for payment_id={yookassa_payment_id}. "
                        f"Skipping subscription grant until final webhook arrives."
                    )
                    return 'OK', 200

                if capture_status != "succeeded":
                    # capture_status == waiting_for_capture: финального статуса ещё нет
                    logger.info(
                        f"[YOOKASSA_WEBHOOK] Capture indicates payment_id={yookassa_payment_id} still waiting for capture confirmation. "
                        f"Will wait for payment.succeeded webhook."
                    )
                    return 'OK', 200

                payment_data_for_processing = capture_payload or payment_object
                
                # ИСПРАВЛЕНИЕ: Используем metadata из транзакции в БД как основу
                metadata = {}
                metadata_source = "webhook"
                
                if existing_transaction and existing_transaction.get('metadata'):
                    # Используем metadata из БД как основу
                    db_metadata = existing_transaction.get('metadata', {})
                    if isinstance(db_metadata, dict):
                        metadata = db_metadata.copy()
                        metadata_source = "database"
                        logger.info(
                            f"[YOOKASSA_WEBHOOK] Using metadata from DB transaction for capture payment_id={yookassa_payment_id}"
                        )
                
                # Дополняем данными из capture payload или webhook
                webhook_metadata = payment_data_for_processing.get("metadata") or payment_object.get("metadata")
                if isinstance(webhook_metadata, dict):
                    metadata.update(webhook_metadata)
                    if metadata_source == "database":
                        metadata_source = "database+webhook"
                    else:
                        metadata_source = "webhook"

                authorization_details = payment_data_for_processing.get("authorization_details", {})
                rrn = authorization_details.get("rrn")
                auth_code = authorization_details.get("auth_code")

                payment_method = payment_data_for_processing.get("payment_method", {})
                payment_type = payment_method.get("type", "unknown")

                logger.info(
                    f"[YOOKASSA_WEBHOOK] Processing captured payment: "
                    f"metadata_source={metadata_source}, "
                    f"host_code={metadata.get('host_code')}, "
                    f"host_name={metadata.get('host_name')}"
                )

                metadata.update({
                    "yookassa_payment_id": yookassa_payment_id,
                    "rrn": rrn,
                    "authorization_code": auth_code,
                    "payment_type": payment_type,
                    "payment_id": yookassa_payment_id  # Добавляем payment_id для обновления транзакции
                })

                host_ok, _ = _ensure_host_metadata(metadata, payment_id)
                if not host_ok:
                    logger.error(f"[YOOKASSA_WEBHOOK] Aborting capture processing for payment_id={payment_id} due to missing host binding.")
                    return 'OK', 200

                bot = _bot_controller.get_bot_instance()
                payment_processor = handlers.process_successful_yookassa_payment

                if metadata and bot is not None and payment_processor is not None:
                    loop = current_app.config.get('EVENT_LOOP')
                    if loop and loop.is_running():
                        logger.info(f"[YOOKASSA_WEBHOOK] Submitting captured payment to event loop for payment_id={payment_id}")
                        
                        # Сериализуем webhook payload для сохранения в api_response
                        api_response_json = json.dumps(event_json, ensure_ascii=False)
                        
                        # Обновляем транзакцию с api_response перед обработкой платежа
                        try:
                            from shop_bot.data_manager.database import update_yookassa_transaction
                            amount_value = payment_data_for_processing.get('amount', {}).get('value') or payment_object.get('amount', {}).get('value')
                            amount_rub = float(amount_value) if amount_value else 0.0
                            
                            update_yookassa_transaction(
                                payment_id, 'paid', amount_rub,
                                yookassa_payment_id, rrn, auth_code, payment_type,
                                metadata, api_response=api_response_json
                            )
                            logger.info(f"[YOOKASSA_WEBHOOK] Capture transaction updated with api_response for payment_id={payment_id}")
                        except Exception as update_error:
                            logger.error(
                                f"[YOOKASSA_WEBHOOK] Failed to update capture transaction with api_response: {update_error}",
                                exc_info=True
                            )
                        
                        future = asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)

                        try:
                            future.result(timeout=5)
                            logger.info(f"[YOOKASSA_WEBHOOK] Capture payment processing completed for payment_id={payment_id}")
                            
                            # Обновляем статус webhook в БД на 'processed'
                            try:
                                import sqlite3
                                from shop_bot.data_manager.database import DB_FILE
                                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE webhooks 
                                        SET status = 'processed' 
                                        WHERE webhook_id = (
                                            SELECT webhook_id 
                                            FROM webhooks 
                                            WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
                                            ORDER BY created_date DESC 
                                            LIMIT 1
                                        )
                                    """, (payment_id, event_type))
                                    conn.commit()
                            except Exception as webhook_update_error:
                                logger.warning(f"[YOOKASSA_WEBHOOK] Failed to update webhook status: {webhook_update_error}")
                                
                        except Exception as future_error:
                            logger.error(
                                f"[YOOKASSA_WEBHOOK] Capture payment processing failed for payment_id={payment_id}: {future_error}",
                                exc_info=True
                            )
                            
                            # Обновляем статус webhook в БД на 'error'
                            try:
                                import sqlite3
                                from shop_bot.data_manager.database import DB_FILE
                                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE webhooks 
                                        SET status = 'error' 
                                        WHERE webhook_id = (
                                            SELECT webhook_id 
                                            FROM webhooks 
                                            WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
                                            ORDER BY created_date DESC 
                                            LIMIT 1
                                        )
                                    """, (payment_id, event_type))
                                    conn.commit()
                            except Exception as webhook_update_error:
                                logger.warning(f"[YOOKASSA_WEBHOOK] Failed to update webhook error status: {webhook_update_error}")
                    else:
                        logger.error(
                            f"[YOOKASSA_WEBHOOK] CRITICAL: Event loop not available for capture payment_id={payment_id}!"
                        )
                        logger.error(f"[YOOKASSA_WEBHOOK] FALLBACK DATA: payment_id={payment_id}, metadata={metadata}")
                else:
                    logger.error(
                        f"[YOOKASSA_WEBHOOK] Missing required components after capture: "
                        f"metadata={metadata is not None}, bot={bot is not None}, processor={payment_processor is not None}"
                    )
            
            elif event_type == "payment.canceled":
                # Платеж отменен
                payment_id = payment_object.get("id")
                metadata = payment_object.get("metadata", {})
                user_id = metadata.get("user_id")
                
                logger.info(f"YooKassa webhook: payment.canceled, payment_id={payment_id}, user_id={user_id}")
                
                # Обновляем транзакцию в БД на статус 'canceled'
                try:
                    from shop_bot.data_manager.database import update_yookassa_transaction
                    if payment_id:
                        # Сериализуем webhook payload для сохранения в api_response
                        api_response_json = json.dumps(event_json, ensure_ascii=False)
                        
                        update_yookassa_transaction(
                            payment_id, 'canceled', 0.0,
                            payment_id, None, None, None,
                            metadata, api_response=api_response_json
                        )
                except Exception as e:
                    logger.error(f"Failed to update canceled transaction: {e}", exc_info=True)
            
            else:
                logger.info(f"YooKassa webhook: unhandled event type={event_type}, payment_id={payment_object.get('id')}")
            
            return 'OK', 200
        except Exception as e:
            logger.error(f"Error in yookassa webhook handler: {e}", exc_info=True)
            return 'Error', 500
        
    @flask_app.route('/cryptobot-webhook', methods=['POST'])
    @measure_performance_sync("cryptobot_webhook")
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

                # Поддержка старого формата (9 частей) и нового (11 частей)
                if len(parts) == 9:
                    # Старый формат без days/hours
                    logger.info("CryptoBot Webhook: Processing old payload format (without days/hours)")
                    metadata = {
                        "user_id": parts[0],
                        "months": parts[1],
                        "days": 0,
                        "hours": 0,
                        "price": parts[2],
                        "action": parts[3],
                        "key_id": parts[4],
                        "host_name": parts[5],
                        "plan_id": parts[6],
                        "customer_email": parts[7] if parts[7] != 'None' else None,
                        "payment_method": parts[8]
                    }
                elif len(parts) == 11:
                    # Новый формат с days/hours
                    logger.info("CryptoBot Webhook: Processing new payload format (with days/hours)")
                    metadata = {
                        "user_id": parts[0],
                        "months": parts[1],
                        "days": parts[2],
                        "hours": parts[3],
                        "price": parts[4],
                        "action": parts[5],
                        "key_id": parts[6],
                        "host_name": parts[7],
                        "plan_id": parts[8],
                        "customer_email": parts[9] if parts[9] != 'None' else None,
                        "payment_method": parts[10]
                    }
                else:
                    logger.error(f"cryptobot Webhook: Invalid payload format received (expected 9 or 11 parts, got {len(parts)}): {payload_string}")
                    return 'Error', 400
                
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
    @measure_performance_sync("heleket_webhook")
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
    @measure_performance("ton_webhook")
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
                                
                                # Безопасность: не используем поиск по сумме без payment_id
                                # Это небезопасно, так как может найти транзакцию другого пользователя
                                logger.warning(
                                    f"[TON_WEBHOOK] Transaction without payment_id comment cannot be safely processed. "
                                    f"Amount: {amount_ton} TON, tx_hash: {tx_hash}"
                                )
                                return 'OK', 200
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
    # @csrf.exempt
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
                        payment['created_date'] = to_panel_iso(payment['created_date'])
                    payments.append(payment)
                
                return {'payments': payments}
                
        except Exception as e:
            logger.error(f"Error getting user payments: {e}")
            return {'payments': []}, 500

    @flask_app.route('/api/user-keys/<int:user_id>')
    # @csrf.exempt
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
                        key['created_date'] = to_panel_iso(key['created_date'])
                    keys.append(key)
                
                return {'keys': keys}
                
        except Exception as e:
            logger.error(f"Error getting user keys: {e}")
            return {'keys': []}, 500

    @flask_app.route('/api/key/<int:key_id>')
    # @csrf.exempt
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
                    key['created_date'] = to_panel_iso(key['created_date'])
                
                if key['expiry_date']:
                    key['expiry_date'] = to_panel_iso(key['expiry_date'])
                
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

                # Ссылки личного кабинета
                cabinet_links: list[dict] = []
                try:
                    cabinet_domain = get_user_cabinet_domain()
                    user_id_value = key.get('user_id')
                    if cabinet_domain and user_id_value:
                        try:
                            database.get_or_create_permanent_token(int(user_id_value), key_id)
                        except Exception as token_error:
                            logger.error(f"Error ensuring permanent cabinet token for key {key_id}: {token_error}")
                        tokens = database.get_tokens_for_key(key_id)
                        seen_tokens = set()
                        for token_info in tokens:
                            token_value = (token_info or {}).get('token')
                            if not token_value or token_value in seen_tokens:
                                continue
                            seen_tokens.add(token_value)
                            cabinet_links.append({
                                'token': token_value,
                                'url': f"{cabinet_domain}/auth/{token_value}",
                                'created_at': token_info.get('created_at'),
                                'last_used_at': token_info.get('last_used_at'),
                                'access_count': token_info.get('access_count'),
                            })
                except Exception as cabinet_error:
                    logger.error(f"Error building cabinet links for key {key_id}: {cabinet_error}")
                    cabinet_links = []
                key['cabinet_links'] = cabinet_links

                return {'key': key}
                
        except Exception as e:
            logger.error(f"Error getting key {key_id}: {e}")
            return {'error': 'Ошибка получения данных ключа'}, 500

    @flask_app.route('/api/key-details/<int:key_id>')
    # @csrf.exempt
    @login_required
    def api_get_key_details(key_id):
        """API для получения деталей ключа (упрощенная версия)"""
        try:
            from shop_bot.data_manager.database import get_key_by_id
            
            key = get_key_by_id(key_id)
            
            if not key:
                return {'error': 'Ключ не найден'}, 404
            
            # Возвращаем основные поля ключа
            return {
                'key_id': key.get('key_id'),
                'key_email': key.get('key_email'),
                'user_id': key.get('user_id'),
                'host_name': key.get('host_name'),
                'plan_name': key.get('plan_name'),
                'expiry_timestamp_ms': key.get('expiry_timestamp_ms'),
                'expiry_date': to_panel_iso(key.get('expiry_date')) if key.get('expiry_date') else None,
                'connection_string': key.get('connection_string'),
                'status': key.get('status'),
                'enabled': key.get('enabled'),
            }
                
        except Exception as e:
            logger.error(f"Error getting key details {key_id}: {e}")
            return {'error': 'Ошибка получения данных ключа'}, 500

    @flask_app.route('/api/user-balance/<int:user_id>')
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
                        notification['created_date'] = to_panel_iso(notification['created_date'])
                    notifications.append(notification)
                
                return {'notifications': notifications}
                
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return {'notifications': []}, 500

    @flask_app.route('/api/user-details/<int:user_id>')
    # @csrf.exempt
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
                        u.group_id,
                        u.auto_renewal_enabled,
                        ug.group_name,
                        (SELECT COUNT(*) FROM vpn_keys WHERE user_id = u.telegram_id) as keys_count,
                        (SELECT COUNT(*) FROM notifications WHERE user_id = u.telegram_id) as notifications_count
                    FROM users u
                    LEFT JOIN user_groups ug ON u.group_id = ug.group_id
                    WHERE u.telegram_id = ?
                """
                cursor.execute(query, (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {'error': 'Пользователь не найден'}, 404
                
                user_data = dict(row)
                
                # Преобразуем auto_renewal_enabled в boolean
                if user_data.get('auto_renewal_enabled') is not None:
                    user_data['auto_renewal_enabled'] = bool(user_data['auto_renewal_enabled'])
                else:
                    user_data['auto_renewal_enabled'] = True  # По умолчанию включено
                
                # Преобразуем registration_date в строку для JSON
                if user_data.get('registration_date'):
                    user_data['registration_date'] = to_panel_iso(user_data['registration_date'])
                
                # Получаем сумму заработанных средств (пока отключено из-за отсутствия колонки referred_by)
                user_data['earned'] = 0
                
                return {'user': user_data}
                
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return {'error': 'Ошибка получения данных пользователя'}, 500

    @flask_app.route('/api/update-user/<int:user_id>', methods=['POST'])
    # @csrf.exempt
    @login_required
    def api_update_user(user_id):
        """API для обновления данных пользователя"""
        try:
            # Поддерживаем как JSON, так и form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            if not data:
                return {'error': 'Нет данных для обновления'}, 400
            
            # Разрешенные поля для обновления
            allowed_fields = ['fio', 'email', 'group_id', 'balance', 'username', 'fullname']
            update_fields = {}
            
            for field in allowed_fields:
                if field in data:
                    update_fields[field] = data[field]
            
            # Обрабатываем reset_trial отдельно (специальная логика)
            reset_trial_requested = data.get('reset_trial') is True
            
            # Если нет разрешенных полей для обновления и не запрошен reset_trial, возвращаем ошибку
            if not update_fields and not reset_trial_requested:
                return {'error': 'Нет разрешенных полей для обновления'}, 400
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                # Проверяем существование пользователя
                cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (user_id,))
                if not cursor.fetchone():
                    return {'error': 'Пользователь не найден'}, 404
                
                # Обрабатываем reset_trial отдельно (специальная логика)
                if reset_trial_requested:
                    from shop_bot.data_manager.database import reset_trial_used
                    reset_trial_used(user_id)
                    logger.info(f"Trial reset for user {user_id}")
                
                # Обрабатываем balance отдельно (устанавливаем напрямую, а не добавляем)
                if 'balance' in update_fields:
                    try:
                        balance_value = float(update_fields['balance'])
                        cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (balance_value, user_id))
                        del update_fields['balance']  # Удаляем из update_fields, чтобы не обновлять дважды
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid balance value for user {user_id}: {e}")
                        return {'error': 'Некорректное значение баланса'}, 400
                
                # Обновляем остальные поля
                if update_fields:
                    set_clause = ', '.join([f"{field} = ?" for field in update_fields.keys()])
                    values = list(update_fields.values()) + [user_id]
                    
                    query = f"UPDATE users SET {set_clause} WHERE telegram_id = ?"
                    cursor.execute(query, values)
                
                conn.commit()
                
                logger.info(f"Updated user {user_id} fields: {list(update_fields.keys()) + (['balance'] if 'balance' in data else [])}")
                return {'message': 'Данные пользователя обновлены успешно'}
                
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
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
    # @csrf.exempt
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

    @flask_app.route('/api/notification-templates')
    @login_required
    def api_notification_templates():
        """Возвращает список доступных шаблонов уведомлений для панели."""
        return jsonify({'templates': get_manual_notification_templates()})

    @flask_app.route('/create-notification', methods=['POST'])
    @login_required
    def create_notification_route():
        """Ручной запуск отправки системных уведомлений.
        Ожидает JSON: {"user_id": int, "template_code": str, "marker_hours": int?, "force": bool?}.
        """
        try:
            data = request.get_json(silent=True) or {}
            user_id = int(data.get('user_id') or 0)
            template_code = str(data.get('template_code') or '').strip()
            force = bool(data.get('force', False))
            if user_id <= 0 or not template_code:
                return jsonify({'message': 'Некорректные данные: требуется пользователь и тип уведомления'}), 400

            template = get_manual_notification_template(template_code)
            if not template:
                return jsonify({'message': 'Неизвестный тип уведомления'}), 400

            markers = template.get('markers', [])
            default_marker = template.get('default_marker')
            marker_value = data.get('marker_hours', default_marker)
            try:
                marker_hours = int(marker_value) if marker_value is not None else None
            except (TypeError, ValueError):
                return jsonify({'message': 'Некорректное значение маркера времени'}), 400

            if markers:
                if marker_hours is None:
                    return jsonify({'message': 'Не выбран момент отправки уведомления'}), 400
                if marker_hours not in markers:
                    return jsonify({'message': 'Выбран недопустимый маркер времени для этого уведомления'}), 400

            if force and not template.get('supports_force', False):
                force = False

            # Проверяем наличие активного бота и цикла событий
            bot = _bot_controller.get_bot_instance()
            loop = current_app.config.get('EVENT_LOOP')
            if not bot or not loop or not loop.is_running():
                return jsonify({'message': 'Бот не запущен. Запустите бота на панели и повторите.'}), 503

            # Ищем ключ пользователя с ближайшим истечением в будущем
            keys = get_user_keys(user_id) or []
            from datetime import datetime as _dt, timezone as _tz
            now = _dt.now(_tz.utc).replace(tzinfo=None)

            def _to_dt(value):
                try:
                    if isinstance(value, str):
                        from datetime import datetime
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except Exception:
                    return None
                return value if isinstance(value, _dt) else None

            future_keys = []
            for key in keys:
                exp = _to_dt(key.get('expiry_date'))
                if exp:
                    if exp.tzinfo is not None:
                        exp = exp.astimezone(_tz.utc).replace(tzinfo=None)
                    if exp > now:
                        future_keys.append((exp, key))

            if not future_keys:
                return jsonify({'message': 'У пользователя нет активных ключей с будущей датой истечения'}), 400

            # Берём ближайший по истечению
            future_keys.sort(key=lambda x: x[0])
            expiry_dt, key = future_keys[0]
            key_id = int(key.get('key_id'))

            if expiry_dt.tzinfo is not None:
                expiry_dt = expiry_dt.astimezone(_tz.utc).replace(tzinfo=None)
            if expiry_dt <= now:
                expiry_dt = now + timedelta(hours=marker_hours or 1)

            try:
                plan_info, price_to_renew, _, _, is_plan_available = _get_plan_info_for_key(key)
            except Exception as e:
                logger.error(f"Failed to resolve plan info for user {user_id}, key {key_id}: {e}", exc_info=True)
                return jsonify({'message': 'Не удалось определить тариф для уведомления'}), 500

            # Дополнительные данные для условий
            from shop_bot.data_manager.database import get_user_balance, get_auto_renewal_enabled

            user_balance = float(get_user_balance(user_id) or 0.0)
            auto_enabled = get_auto_renewal_enabled(user_id)
            balance_covers = price_to_renew > 0 and user_balance >= price_to_renew

            conditions = template.get('conditions', {})
            require_plan_available = conditions.get('require_plan_available')
            require_balance = conditions.get('require_balance_covers')
            require_autorenew_enabled = conditions.get('require_autorenew_enabled')
            require_autorenew_disabled = conditions.get('require_autorenew_disabled')

            if require_plan_available is True and not is_plan_available:
                return jsonify({'message': 'Тариф недоступен. Используйте шаблон предупреждения о недоступности тарифа.'}), 409
            if require_plan_available is False and is_plan_available and not force:
                return jsonify({'message': 'Тариф доступен для продления, уведомление о недоступности не отправлено.'}), 409
            if require_balance and not balance_covers:
                return jsonify({'message': 'Баланс пользователя недостаточен для этого уведомления.'}), 409
            if require_autorenew_enabled and not auto_enabled:
                return jsonify({'message': 'Автопродление отключено. Выберите другой тип уведомления.'}), 409
            if require_autorenew_disabled and auto_enabled:
                return jsonify({'message': 'Автопродление включено. Этот тип уведомления не подходит.'}), 409

            if not force and marker_hours is not None:
                if _marker_logged(user_id, key_id, marker_hours, template_code):
                    return jsonify({'message': 'Такое уведомление уже отправлялось. Включите повторную отправку.'}), 409

            status_override = 'resent' if force else 'sent'

            if template_code == 'subscription_expiry':
                coroutine = send_subscription_notification(
                    bot=bot,
                    user_id=user_id,
                    key_id=key_id,
                    time_left_hours=marker_hours,
                    expiry_date=expiry_dt,
                    status=status_override,
                )
            elif template_code == 'subscription_plan_unavailable':
                coroutine = send_plan_unavailable_notice(
                    bot=bot,
                    user_id=user_id,
                    key_id=key_id,
                    time_left_hours=marker_hours,
                    expiry_date=expiry_dt,
                    force=force,
                    status=status_override,
                )
            elif template_code == 'subscription_autorenew_notice':
                coroutine = send_autorenew_balance_notice(
                    bot=bot,
                    user_id=user_id,
                    key_id=key_id,
                    time_left_hours=marker_hours,
                    expiry_date=expiry_dt,
                    balance_val=user_balance,
                    status=status_override,
                )
            elif template_code == 'subscription_autorenew_disabled':
                coroutine = send_autorenew_disabled_notice(
                    bot=bot,
                    user_id=user_id,
                    key_id=key_id,
                    time_left_hours=marker_hours,
                    expiry_date=expiry_dt,
                    balance_val=user_balance,
                    price_to_renew=price_to_renew,
                    status=status_override,
                )
            else:
                return jsonify({'message': 'Этот тип уведомлений пока не поддерживается вручную'}), 400

            asyncio.run_coroutine_threadsafe(coroutine, loop)
            return jsonify({'message': 'Уведомление запущено в отправку'}), 200
        except Exception as e:
            logger.error(f"Failed to create notification: {e}", exc_info=True)
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
            
            # Валидация промокода
            code = data.get('code', '').strip().upper()
            if len(code) < 3:
                return jsonify({'success': False, 'message': 'Промокод должен содержать минимум 3 символа'}), 400
            
            if len(code) > 50:
                return jsonify({'success': False, 'message': 'Промокод не может содержать более 50 символов'}), 400
            
            if not re.match(r'^[A-Z0-9_-]+$', code):
                return jsonify({'success': False, 'message': 'Промокод может содержать только заглавные буквы, цифры, дефисы и подчеркивания'}), 400
            
            # Валидация бота
            if data.get('bot') not in ['shop']:
                return jsonify({'success': False, 'message': 'Неверный тип бота. Допустимые значения: shop'}), 400
            
            # Валидация скидок
            discount_amount = float(data.get('discount_amount', 0))
            discount_percent = float(data.get('discount_percent', 0))
            discount_bonus = float(data.get('discount_bonus', 0))
            
            if discount_amount < 0:
                return jsonify({'success': False, 'message': 'Скидка в рублях не может быть отрицательной'}), 400
            
            if discount_percent < 0 or discount_percent > 100:
                return jsonify({'success': False, 'message': 'Процентная скидка должна быть от 0 до 100'}), 400
            
            if discount_bonus < 0:
                return jsonify({'success': False, 'message': 'Бонусная скидка не может быть отрицательной'}), 400
            
            if discount_amount == 0 and discount_percent == 0 and discount_bonus == 0:
                return jsonify({'success': False, 'message': 'Укажите хотя бы один тип скидки'}), 400
            
            # Валидация лимита использований
            usage_limit = int(data.get('usage_limit_per_bot', 1))
            if usage_limit < 1:
                return jsonify({'success': False, 'message': 'Лимит использований должен быть не менее 1'}), 400
            
            # Валидация vpn_plan_id (может быть массивом или одиночным значением)
            vpn_plan_id = data.get('vpn_plan_id')
            if vpn_plan_id is not None:
                if isinstance(vpn_plan_id, list):
                    if len(vpn_plan_id) == 0:
                        # Пустой список - это нормально, означает что промокод не привязан к планам
                        vpn_plan_id = None
                    else:
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
            
            # Валидация новых полей
            burn_after_value = data.get('burn_after_value')
            burn_after_unit = data.get('burn_after_unit')
            valid_until = data.get('valid_until')
            target_group_ids = data.get('target_group_ids', [])
            # bot_username теперь берется из выбранного бота
            bot_username = data.get('bot_username')
            
            # Если bot_username не передан, берем из настроек username основного бота
            if not bot_username:
                bot_username = database.get_setting('telegram_bot_username') or None
            # Нормализуем username: убираем ведущий '@'
            if bot_username:
                bot_username = str(bot_username).strip().lstrip('@')
            
            # Валидация burn_after
            if burn_after_value is not None:
                try:
                    burn_after_value = int(burn_after_value)
                    if burn_after_value < 1:
                        return jsonify({'success': False, 'message': 'Срок сгорания должен быть больше 0'}), 400
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Неверный формат срока сгорания'}), 400
            
            if burn_after_unit is not None and burn_after_unit not in ['min', 'hour', 'day']:
                return jsonify({'success': False, 'message': 'Единица срока сгорания должна быть: min, hour или day'}), 400
            
            # Валидация valid_until
            if valid_until:
                try:
                    from datetime import datetime
                    datetime.fromisoformat(valid_until)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Неверный формат даты "Действителен до"'}), 400
            
            # Валидация target_group_ids
            if target_group_ids and not isinstance(target_group_ids, list):
                return jsonify({'success': False, 'message': 'Группы должны быть массивом'}), 400
            
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
                    is_active=data.get('is_active', True),
                    burn_after_value=burn_after_value,
                    burn_after_unit=burn_after_unit,
                    valid_until=valid_until,
                    target_group_ids=target_group_ids,
                    bot_username=bot_username
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
    # @csrf.exempt
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
    # @csrf.exempt
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
            if data.get('bot') not in ['shop']:
                return jsonify({'success': False, 'message': 'Неверный тип бота. Допустимые значения: shop'}), 400
            
            # Валидация vpn_plan_id (может быть массивом или одиночным значением)
            vpn_plan_id = data.get('vpn_plan_id')
            if vpn_plan_id is not None:
                if isinstance(vpn_plan_id, list):
                    if len(vpn_plan_id) == 0:
                        # Пустой список - это нормально, означает что промокод не привязан к планам
                        vpn_plan_id = None
                    else:
                        try:
                            vpn_plan_id = [int(x) for x in vpn_plan_id if x is not None]
                        except (ValueError, TypeError):
                            return jsonify({'success': False, 'message': 'Неверный формат VPN планов'}), 400
                else:
                    try:
                        vpn_plan_id = int(vpn_plan_id)
                    except (ValueError, TypeError):
                        return jsonify({'success': False, 'message': 'Неверный формат VPN плана'}), 400
            
            # Валидация новых полей
            burn_after_value = data.get('burn_after_value')
            burn_after_unit = data.get('burn_after_unit')
            valid_until = data.get('valid_until')
            target_group_ids = data.get('target_group_ids', [])
            # bot_username теперь берется из выбранного бота
            bot_username = data.get('bot_username')
            
            # Если bot_username не передан, берем из настроек username основного бота
            if not bot_username:
                bot_username = database.get_setting('telegram_bot_username') or None
            # Нормализуем username: убираем ведущий '@'
            if bot_username:
                bot_username = str(bot_username).strip().lstrip('@')
            
            # Валидация burn_after
            if burn_after_value is not None:
                try:
                    burn_after_value = int(burn_after_value)
                    if burn_after_value < 1:
                        return jsonify({'success': False, 'message': 'Срок сгорания должен быть больше 0'}), 400
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Неверный формат срока сгорания'}), 400
            
            if burn_after_unit is not None and burn_after_unit not in ['min', 'hour', 'day']:
                return jsonify({'success': False, 'message': 'Единица срока сгорания должна быть: min, hour или day'}), 400
            
            # Валидация valid_until
            if valid_until:
                try:
                    from datetime import datetime
                    datetime.fromisoformat(valid_until)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Неверный формат даты "Действителен до"'}), 400
            
            # Валидация target_group_ids
            if target_group_ids and not isinstance(target_group_ids, list):
                return jsonify({'success': False, 'message': 'Группы должны быть массивом'}), 400
            
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
                    is_active=data.get('is_active', True),
                    burn_after_value=burn_after_value,
                    burn_after_unit=burn_after_unit,
                    valid_until=valid_until,
                    target_group_ids=target_group_ids,
                    bot_username=bot_username
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
    # @csrf.exempt
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

    @flask_app.route('/api/promo-codes-usage-history', methods=['GET'])
    # @csrf.exempt
    @login_required
    def api_get_all_promo_code_usage_history():
        """Получить всю историю использования промокодов"""
        try:
            usage_history = get_all_promo_code_usage_history()
            return jsonify({
                'success': True,
                'usage_history': usage_history
            })
        except Exception as e:
            logger.error(f"Error getting all promo code usage history: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/promo-codes/<int:promo_id>/usage', methods=['GET'])
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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

    @flask_app.route('/api/user-groups', methods=['GET'])
    # @csrf.exempt
    @login_required
    def api_get_user_groups():
        """Получить все группы пользователей"""
        try:
            groups = get_all_user_groups()
            for group in groups:
                group['created_date'] = to_panel_iso(group.get('created_date'))
            return jsonify({
                'success': True,
                'groups': groups
            })
        except Exception as e:
            logger.error(f"Error getting user groups: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/validate-promo-code', methods=['POST'])
    # @csrf.exempt
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
    # @csrf.exempt
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
    # @csrf.exempt
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
    # При необходимости можно включить выборочно через @csrf.protect()() для критичных форм

    # API для работы с базой данных
    @flask_app.route('/api/database/stats')
    @login_required
    def get_database_stats():
        """Получение статистики таблиц базы данных"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Список всех таблиц
                tables = [
                    'users', 'transactions', 'vpn_keys', 'promo_codes', 
                    'promo_code_usage', 'notifications', 'video_instructions',
                    'bot_settings', 'xui_hosts', 'hosts', 'plans', 'support_threads'
                ]
                
                stats = {}
                
                for table in tables:
                    try:
                        # Получаем количество записей
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                        count = cursor.fetchone()['count']
                        
                        # Получаем размер таблицы (примерно)
                        cursor.execute(f"SELECT COUNT(*) * 1024 as size FROM {table}")  # Примерная оценка
                        size_bytes = cursor.fetchone()['size']
                        
                        # Форматируем размер
                        if size_bytes < 1024:
                            size_str = f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            size_str = f"{size_bytes / 1024:.1f} KB"
                        else:
                            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                        
                        stats[table] = {
                            'count': count,
                            'size': size_str
                        }
                    except sqlite3.Error as e:
                        # Если таблица не существует, устанавливаем нулевые значения
                        stats[table] = {
                            'count': 0,
                            'size': '0 B'
                        }
                
                return jsonify({
                    'success': True,
                    'tables': stats
                })
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики БД: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    @flask_app.route('/api/database/delete-table/<table_name>', methods=['DELETE'])
    @login_required
    def delete_table_data(table_name):
        """Удаление всех данных из указанной таблицы"""
        try:
            # Список разрешенных таблиц
            allowed_tables = [
                'users', 'transactions', 'vpn_keys', 'promo_codes', 
                'promo_code_usage', 'notifications', 'video_instructions',
                'bot_settings', 'xui_hosts', 'hosts', 'plans', 'support_threads'
            ]
            
            if table_name not in allowed_tables:
                return jsonify({
                    'success': False,
                    'message': 'Таблица не найдена или удаление запрещено'
                }), 404
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                # Получаем количество записей до удаления
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_before = cursor.fetchone()[0]
                
                # Удаляем все записи из таблицы
                cursor.execute(f"DELETE FROM {table_name}")
                deleted_count = cursor.rowcount
                
                conn.commit()
            
            # Выполняем VACUUM вне транзакции для очистки WAL
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                
                logger.info(f"Удалено {deleted_count} записей из таблицы {table_name}")
                
                return jsonify({
                    'success': True,
                    'deleted_count': deleted_count,
                    'message': f'Удалено {deleted_count} записей из таблицы {table_name}'
                })
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка SQL при удалении из таблицы {table_name}: {e}")
            return jsonify({
                'success': False,
                'message': f'Ошибка базы данных: {str(e)}'
            }), 500
        except Exception as e:
            logger.error(f"Ошибка удаления из таблицы {table_name}: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    @flask_app.route('/api/database/download')
    @login_required
    def download_database():
        """Скачивание резервной копии базы данных"""
        try:
            from flask import send_file
            import tempfile
            import shutil
            from datetime import datetime
            
            # Создаем временную копию базы данных
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"database_backup_{timestamp}.db"
            temp_path = tempfile.mktemp(suffix=f"_{temp_filename}")
            
            # Копируем базу данных во временный файл
            shutil.copy2(DB_FILE, temp_path)
            
            logger.info(f"Создана резервная копия базы данных: {temp_filename}")
            
            # Отправляем файл для скачивания
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=temp_filename,
                mimetype='application/octet-stream'
            )
            
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии БД: {e}")
            return jsonify({
                'success': False,
                'message': f'Ошибка создания резервной копии: {str(e)}'
            }), 500

    # ==================== API ENDPOINTS ДЛЯ БЕКАПОВ ====================
    
    @flask_app.route('/api/backup/create', methods=['POST'])
    @login_required
    def api_create_backup():
        """Создание бекапа вручную"""
        try:
            from shop_bot.data_manager.backup import backup_manager
            backup_info = backup_manager.create_backup()
            
            if backup_info['success']:
                return jsonify({
                    'status': 'success',
                    'message': 'Бекап успешно создан',
                    'backup_name': backup_info['backup_name'],
                    'backup_size': backup_info.get('size', 0)
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Ошибка создания бекапа: {backup_info.get("error")}'
                }), 500
        except Exception as e:
            logger.error(f"Ошибка создания бекапа: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }), 500

    @flask_app.route('/api/backup/list')
    @login_required
    def api_list_backups():
        """Список всех бекапов"""
        try:
            from shop_bot.data_manager.backup import backup_manager
            stats = backup_manager.get_backup_statistics()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Ошибка получения списка бекапов: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/backup/status')
    @login_required
    def api_backup_status():
        """Статус системы бекапов"""
        try:
            from shop_bot.data_manager.backup import backup_manager
            from datetime import datetime, timedelta

            stats = backup_manager.get_backup_statistics()

            # last_backup в часовом поясе панели
            last_backup_iso = stats.get('last_backup_time')
            last_backup_panel_iso = to_panel_iso(last_backup_iso)

            # next_backup расчёт от last_backup или now + interval
            next_backup_iso = None
            next_backup_panel_iso = None
            try:
                if backup_manager.is_running:
                    interval_h = int(backup_manager.backup_interval_hours or 24)
                    now_dt = datetime.now(timezone.utc)
                    base_dt = None
                    if last_backup_iso:
                        try:
                            lb = datetime.fromisoformat(last_backup_iso.replace('Z', '+00:00'))
                            if lb.tzinfo is None:
                                lb = lb.replace(tzinfo=timezone.utc)
                            base_dt = lb
                        except Exception:
                            base_dt = None
                    if base_dt is None:
                        base_dt = now_dt
                    candidate = base_dt + timedelta(hours=interval_h)
                    if candidate <= now_dt:
                        candidate = now_dt + timedelta(hours=interval_h)
                    candidate = candidate.astimezone(timezone.utc)
                    next_backup_iso = candidate.isoformat()
                    next_backup_panel_iso = to_panel_iso(candidate)
            except Exception:
                pass

            # Получаем статус enabled из БД как источник истины
            from shop_bot.data_manager.database import get_backup_setting
            backup_enabled_db = get_backup_setting('backup_enabled')
            enabled_from_db = str(backup_enabled_db).lower() in ('true', '1', 'yes', 'on') if backup_enabled_db else True
            
            return jsonify({
                'enabled': enabled_from_db,
                'is_running': backup_manager.is_running,  # Технический статус потока
                'interval_hours': backup_manager.backup_interval_hours,
                'last_backup': stats.get('last_backup_time'),
                'last_backup_panel': last_backup_panel_iso or last_backup_iso,
                'last_backup_msk': last_backup_panel_iso or last_backup_iso,  # Backward compatibility
                'next_backup': next_backup_iso,
                'next_backup_panel': next_backup_panel_iso or next_backup_iso,
                'next_backup_msk': next_backup_panel_iso or next_backup_iso,  # Backward compatibility
                'total_backups': stats.get('total_backups', 0),
                'total_size': stats.get('total_size', 0),
                'failed_backups': stats.get('failed_backups', 0),
                'retention_days': backup_manager.retention_days,
                'compression_enabled': backup_manager.compression_enabled,
                'verify_backups': backup_manager.verify_backups
            })
        except Exception as e:
            logger.error(f"Ошибка получения статуса бекапов: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/backup/settings', methods=['GET'])
    @login_required
    def api_get_backup_settings():
        """Получение настроек бекапов"""
        try:
            from shop_bot.data_manager.database import get_all_backup_settings
            settings = get_all_backup_settings()
            return jsonify(settings)
        except Exception as e:
            logger.error(f"Ошибка получения настроек бекапов: {e}")
            return jsonify({'error': str(e)}), 500

    @flask_app.route('/api/backup/settings', methods=['POST'])
    @login_required
    def api_save_backup_settings():
        """Сохранение настроек бекапов"""
        try:
            from shop_bot.data_manager.database import update_backup_setting
            from shop_bot.data_manager.backup import backup_manager
            
            # Получаем данные из запроса
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Валидация настроек
            validation_errors = validate_backup_settings(data)
            if validation_errors:
                return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
            
            # Нормализация булевых значений к 'true'/'false' перед сохранением
            def to_str(v):
                if isinstance(v, bool):
                    return 'true' if v else 'false'
                s = str(v).strip().lower()
                if s in ('true', '1', 'yes', 'on'):
                    return 'true'
                if s in ('false', '0', 'no', 'off'):
                    return 'false'
                return s

            # Сохраняем настройки
            for key, value in data.items():
                if key in ['backup_enabled', 'backup_interval_hours', 'backup_retention_days', 
                          'backup_compression', 'backup_verify']:
                    normalized = to_str(value) if key in ['backup_enabled', 'backup_compression', 'backup_verify'] else str(value)
                    update_backup_setting(key, normalized)
            
            # Обновляем настройки менеджера бекапов
            # Приведение типов
            try:
                retention_days = int(data.get('backup_retention_days', 30))
            except (TypeError, ValueError):
                retention_days = 30
            
            compression_enabled = str(data.get('backup_compression', True)).lower() in ('true','1','yes','on')
            verify_backups = str(data.get('backup_verify', True)).lower() in ('true','1','yes','on')
            
            # Управляем системой бекапов
            enabled_flag = str(data.get('backup_enabled', True)).lower() in ('true','1','yes','on')
            
            if enabled_flag:
                if not backup_manager.is_running:
                    # Бекапы отключены, но должны быть включены - запускаем
                    try:
                        backup_manager.start_automatic_backups(int(data.get('backup_interval_hours', 24)))
                    except (TypeError, ValueError):
                        backup_manager.start_automatic_backups(24)
                else:
                    # Бекапы уже работают - просто обновляем настройки без перезапуска
                    try:
                        interval_hours = int(data.get('backup_interval_hours', 24))
                    except (TypeError, ValueError):
                        interval_hours = 24
                    
                    backup_manager.update_settings(
                        interval_hours=interval_hours,
                        retention_days=retention_days,
                        compression_enabled=compression_enabled,
                        verify_backups=verify_backups
                    )
            else:
                # Бекапы должны быть отключены
                backup_manager.stop_automatic_backups()
                # Обновляем настройки для случая, если пользователь включит бекапы позже
                try:
                    interval_hours = int(data.get('backup_interval_hours', 24))
                except (TypeError, ValueError):
                    interval_hours = 24
                
                backup_manager.update_settings(
                    interval_hours=interval_hours,
                    retention_days=retention_days,
                    compression_enabled=compression_enabled,
                    verify_backups=verify_backups
                )
            
            return jsonify({'status': 'success', 'message': 'Настройки бекапов сохранены'})
            
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек бекапов: {e}")
            return jsonify({'error': str(e)}), 500

    def validate_backup_settings(data):
        """Валидация настроек бекапов"""
        errors = []
        
        # Валидация интервала
        if 'backup_interval_hours' in data:
            try:
                interval = int(data['backup_interval_hours'])
                if interval not in [1, 2, 3, 6, 12, 24, 48, 72]:
                    errors.append('backup_interval_hours must be one of: 1, 2, 3, 6, 12, 24, 48, 72')
            except (ValueError, TypeError):
                errors.append('backup_interval_hours must be a valid integer')
        
        # Валидация дней хранения
        if 'backup_retention_days' in data:
            try:
                retention = int(data['backup_retention_days'])
                if retention not in [1, 3, 7, 14, 30, 60, 90, 180, 365]:
                    errors.append('backup_retention_days must be one of: 1, 3, 7, 14, 30, 60, 90, 180, 365')
            except (ValueError, TypeError):
                errors.append('backup_retention_days must be a valid integer')
        
        # Валидация boolean полей
        for field in ['backup_enabled', 'backup_compression', 'backup_verify']:
            if field in data and not isinstance(data[field], bool):
                errors.append(f'{field} must be a boolean value')
        
        return errors

    # ==================== МАРШРУТЫ ДЛЯ РАБОТЫ С ГРУППАМИ ПОЛЬЗОВАТЕЛЕЙ ====================
    
    @flask_app.route('/user-groups')
    @login_required
    def user_groups_page():
        """Страница управления группами пользователей"""
        groups = get_all_user_groups()
        statistics = get_groups_statistics()
        
        common_data = get_common_template_data()
        
        return render_template(
            'user_groups.html',
            groups=groups,
            statistics=statistics,
            **common_data
        )
    
    
    @flask_app.route('/api/user-groups', methods=['POST'])
    @login_required
    def api_create_user_group():
        """API для создания новой группы пользователей"""
        try:
            data = request.get_json()
            group_name = data.get('group_name', '').strip()
            group_description = data.get('group_description', '').strip()
            
            if not group_name:
                return jsonify({'success': False, 'error': 'Название группы не может быть пустым'}), 400
            
            group_id = create_user_group(group_name, group_description)
            
            if group_id:
                return jsonify({'success': True, 'group_id': group_id, 'message': 'Группа успешно создана'})
            else:
                return jsonify({'success': False, 'error': 'Группа с таким названием уже существует'}), 400
                
        except Exception as e:
            logger.error(f"Ошибка создания группы пользователей: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/user-groups/<int:group_id>', methods=['PUT'])
    @login_required
    def api_update_user_group(group_id):
        """API для обновления группы пользователей"""
        try:
            data = request.get_json()
            group_name = data.get('group_name', '').strip()
            group_description = data.get('group_description', '').strip()
            # Если group_code отсутствует или пустой, передаем None
            group_code = data.get('group_code')
            if group_code is not None:
                group_code = group_code.strip()
                if not group_code:  # Если после strip пустая строка
                    group_code = None
            
            if not group_name:
                return jsonify({'success': False, 'error': 'Название группы не может быть пустым'}), 400
            
            logger.info(f"DEBUG API: group_id={group_id}, group_name={group_name}, group_code={group_code}")
            success = update_user_group(group_id, group_name, group_description, group_code)
            
            if success:
                return jsonify({'success': True, 'message': 'Группа успешно обновлена'})
            else:
                return jsonify({'success': False, 'error': 'Группа не найдена или название уже используется'}), 400
                
        except Exception as e:
            logger.error(f"Ошибка обновления группы пользователей: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/user-groups/<int:group_id>', methods=['DELETE'])
    @login_required
    def api_delete_user_group(group_id):
        """API для удаления группы пользователей"""
        try:
            from shop_bot.data_manager.database import get_user_group
            
            success, reassigned_count = delete_user_group(group_id)
            
            if success:
                # Получаем информацию о группе по умолчанию для сообщения
                default_group_name = "Пользователи"  # По умолчанию
                try:
                    default_group = get_user_group(1)  # ID 1 - группа по умолчанию
                    if default_group and default_group.get('is_default'):
                        default_group_name = default_group['group_name']
                except Exception:
                    pass
                
                message = f'Группа успешно удалена. {reassigned_count} пользователей переназначены в группу "{default_group_name}".'
                return jsonify({'success': True, 'message': message, 'reassigned_count': reassigned_count})
            else:
                return jsonify({'success': False, 'error': 'Не удалось удалить группу (возможно, это группа по умолчанию или группа не найдена)'}), 400
                
        except Exception as e:
            logger.error(f"Ошибка удаления группы пользователей: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/user-groups/statistics', methods=['GET'])
    @login_required
    def api_get_groups_statistics():
        """API для получения статистики по группам"""
        try:
            statistics = get_groups_statistics()
            return jsonify({'success': True, 'statistics': statistics})
        except Exception as e:
            logger.error(f"Ошибка получения статистики групп: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/user-groups/<int:group_id>/users', methods=['GET'])
    @login_required
    def api_get_users_in_group(group_id):
        """API для получения пользователей в группе"""
        try:
            users = get_users_in_group(group_id)
            return jsonify({'success': True, 'users': users})
        except Exception as e:
            logger.error(f"Ошибка получения пользователей группы: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates', methods=['GET'])
    @login_required
    def api_get_message_templates():
        """Получить все шаблоны сообщений"""
        try:
            category = request.args.get('category')
            templates = get_all_message_templates(category)
            return jsonify({
                'success': True,
                'templates': templates
            })
        except Exception as e:
            logger.error(f"Error getting message templates: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates/<int:template_id>', methods=['GET'])
    @login_required
    def api_get_message_template(template_id):
        """Получить шаблон по ID"""
        try:
            templates = get_all_message_templates()
            template = next((t for t in templates if t.get('template_id') == template_id), None)
            if template:
                return jsonify({'success': True, 'template': template})
            else:
                return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        except Exception as e:
            logger.error(f"Error getting message template {template_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates', methods=['POST'])
    @login_required
    def api_create_message_template():
        """Создать новый шаблон сообщения"""
        try:
            data = request.get_json()
            template_key = data.get('template_key', '').strip()
            category = data.get('category', '').strip()
            template_text = data.get('template_text', '').strip()
            provision_mode = data.get('provision_mode')
            description = data.get('description', '').strip()
            variables = data.get('variables')
            
            if not template_key or not category or not template_text:
                return jsonify({'success': False, 'error': 'Необходимы template_key, category и template_text'}), 400
            
            # Валидация HTML-тегов перед сохранением
            is_valid, errors = InputValidator.validate_html_tags(template_text)
            if not is_valid:
                error_message = "Ошибка валидации HTML-тегов: " + "; ".join(errors)
                logger.warning(f"HTML validation failed for template {template_key}: {errors}")
                return jsonify({'success': False, 'error': error_message}), 400
            
            template_id = create_message_template(
                template_key=template_key,
                category=category,
                template_text=template_text,
                provision_mode=provision_mode,
                description=description,
                variables=variables
            )
            
            if template_id:
                return jsonify({'success': True, 'template_id': template_id})
            else:
                return jsonify({'success': False, 'error': 'Не удалось создать шаблон (возможно, ключ уже существует)'}), 400
                
        except Exception as e:
            logger.error(f"Error creating message template: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates/<int:template_id>', methods=['PUT'])
    @login_required
    def api_update_message_template(template_id):
        """Обновить шаблон сообщения"""
        try:
            data = request.get_json()
            template_text = data.get('template_text')
            description = data.get('description')
            is_active = data.get('is_active')
            
            if template_text is not None:
                template_text = template_text.strip()
                # Валидация HTML-тегов перед сохранением (только если template_text передан)
                is_valid, errors = InputValidator.validate_html_tags(template_text)
                if not is_valid:
                    error_message = "Ошибка валидации HTML-тегов: " + "; ".join(errors)
                    logger.warning(f"HTML validation failed for template {template_id}: {errors}")
                    return jsonify({'success': False, 'error': error_message}), 400
            
            if description is not None:
                description = description.strip()
            
            success = update_message_template(
                template_id=template_id,
                template_text=template_text,
                description=description,
                is_active=is_active
            )
            
            if success:
                return jsonify({'success': True, 'message': 'Шаблон обновлен'})
            else:
                return jsonify({'success': False, 'error': 'Не удалось обновить шаблон'}), 400
                
        except Exception as e:
            logger.error(f"Error updating message template {template_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates/<int:template_id>', methods=['DELETE'])
    @login_required
    def api_delete_message_template(template_id):
        """Удалить шаблон сообщения"""
        try:
            success = delete_message_template(template_id)
            
            if success:
                return jsonify({'success': True, 'message': 'Шаблон удален'})
            else:
                return jsonify({'success': False, 'error': 'Не удалось удалить шаблон'}), 400
                
        except Exception as e:
            logger.error(f"Error deleting message template {template_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/message-templates/statistics', methods=['GET'])
    @login_required
    def api_get_message_template_statistics():
        """Получить статистику шаблонов сообщений"""
        try:
            statistics = get_message_template_statistics()
            return jsonify({'success': True, 'statistics': statistics})
        except Exception as e:
            logger.error(f"Error getting message template statistics: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/users/<int:user_id>/group', methods=['PUT'])
    @login_required
    def api_update_user_group_assignment(user_id):
        """API для изменения группы пользователя"""
        try:
            data = request.get_json()
            group_id = data.get('group_id')
            
            if group_id is None:
                return jsonify({'success': False, 'error': 'ID группы не указан'}), 400
            
            success = update_user_group_assignment(user_id, group_id)
            
            if success:
                return jsonify({'success': True, 'message': 'Группа пользователя успешно изменена'})
            else:
                return jsonify({'success': False, 'error': 'Пользователь или группа не найдены'}), 400
                
        except Exception as e:
            logger.error(f"Ошибка изменения группы пользователя: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== API ENDPOINTS ДЛЯ DEEPLINK ====================
    
    @flask_app.route('/api/bots', methods=['GET'])
    @login_required
    def api_get_bots():
        """Получить список доступных ботов"""
        try:
            settings = get_all_settings()
            
            bots = []
            
            # Основной бот (shop)
            if settings.get('telegram_bot_username'):
                bots.append({
                    'bot': 'shop',
                    'name': 'Shop Bot',
                    'username': settings.get('telegram_bot_username')
                })
            
            # Support бот (если есть)
            if settings.get('support_bot_token'):
                # Извлекаем username из токена или используем настройку
                support_username = settings.get('support_bot_username') or 'support_bot'
                bots.append({
                    'bot': 'support',
                    'name': 'Support Bot',
                    'username': support_username
                })
            
            return jsonify({
                'success': True,
                'bots': bots
            })
            
        except Exception as e:
            logger.error(f"Error getting bots: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/promo-codes/by-bot', methods=['GET'])
    @login_required
    def api_get_promo_codes_by_bot():
        """Получить промокоды, отфильтрованные по боту"""
        try:
            bot = request.args.get('bot')
            
            if not bot:
                return jsonify({
                    'success': False,
                    'message': 'Параметр bot обязателен'
                }), 400
            
            # Получаем все промокоды
            all_promo_codes = get_all_promo_codes()
            
            # Фильтруем по боту
            filtered_promo_codes = [
                promo for promo in all_promo_codes 
                if promo.get('bot') == bot
            ]
            
            return jsonify({
                'success': True,
                'promo_codes': filtered_promo_codes
            })
            
        except Exception as e:
            logger.error(f"Error getting promo codes by bot: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @flask_app.route('/api/generate-deeplink', methods=['POST'])
    @login_required
    def api_generate_deeplink():
        """Генерировать deeplink ссылку с base64 кодированием"""
        try:
            data = request.get_json()
            bot_username = data.get('bot_username')
            group_code = data.get('group_code')
            promo_code = data.get('promo_code')
            referrer_id = data.get('referrer_id')
            
            if not bot_username:
                return jsonify({
                    'success': False,
                    'message': 'bot_username обязателен'
                }), 400
            
            # Импортируем утилиту deeplink
            from shop_bot.utils.deeplink import create_deeplink
            
            # Генерируем ссылку
            link = create_deeplink(
                bot_username=bot_username,
                group_code=group_code,
                promo_code=promo_code,
                referrer_id=referrer_id
            )
            
            return jsonify({
                'success': True,
                'link': link,
                'bot_username': bot_username,
                'group_code': group_code,
                'promo_code': promo_code,
                'referrer_id': referrer_id
            })
            
        except Exception as e:
            logger.error(f"Error generating deeplink: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== API ENDPOINTS ДЛЯ DOCKER MANAGEMENT ====================
    
    def _find_docker_command():
        """Находит путь к docker executable"""
        import shutil
        import platform
        
        # Пробуем найти docker в PATH
        docker_cmd = shutil.which('docker')
        if docker_cmd:
            return docker_cmd
        
        # Если не найден, пробуем стандартные пути для Windows
        if platform.system() == 'Windows':
            possible_paths = [
                r'C:\Program Files\Docker\Docker\resources\bin\docker.exe',
                r'C:\Program Files\Docker\Docker\resources\docker.exe',
                r'C:\ProgramData\DockerDesktop\version-bin\docker.exe',
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return path
        
        # Если всё ещё не найден, возвращаем просто 'docker' и надеемся на лучшее
        return 'docker'

    def _get_compose_args():
        """Возвращает базовые аргументы для docker compose"""
        compose_file = os.getenv('DOCKER_COMPOSE_FILE')
        if not compose_file:
            default_path = PROJECT_ROOT / 'docker-compose.yml'
            if default_path.exists():
                compose_file = str(default_path)
        
        if compose_file and os.path.exists(compose_file):
            return ['compose', '-f', compose_file]
        
        logger.warning("[DOCKER_API] docker-compose.yml not found (compose_file=%s)", compose_file)
        return ['compose']
    
    @flask_app.route('/api/docker/restart-all', methods=['POST'])
    @login_required
    def docker_restart_all():
        """Перезапускает все сервисы через docker compose restart"""
        try:
            docker_cmd = _find_docker_command()
            compose_args = _get_compose_args()
            logger.info(f"[DOCKER_API] restart-all initiated by {session.get('username')}, docker={docker_cmd}, compose_args={compose_args}")
            result = subprocess.run(
                [docker_cmd, *compose_args, 'restart'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=90
            )
            logger.info(f"[DOCKER_API] restart-all completed: returncode={result.returncode}")
            return jsonify({
                'success': result.returncode == 0,
                'message': 'Restart initiated' if result.returncode == 0 else result.stderr,
                'reload_after': 35
            })
        except Exception as e:
            logger.error(f"[DOCKER_API] restart-all failed: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @flask_app.route('/api/docker/restart-bot', methods=['POST'])
    @login_required
    def docker_restart_bot():
        """Перезапускает только бот"""
        try:
            docker_cmd = _find_docker_command()
            compose_args = _get_compose_args()
            logger.info(f"[DOCKER_API] restart-bot initiated by {session.get('username')}, docker={docker_cmd}, compose_args={compose_args}")
            result = subprocess.run(
                [docker_cmd, *compose_args, 'restart', 'bot'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60
            )
            logger.info(f"[DOCKER_API] restart-bot completed: returncode={result.returncode}")
            return jsonify({
                'success': result.returncode == 0,
                'message': 'Bot restart initiated' if result.returncode == 0 else result.stderr,
                'reload_after': 20
            })
        except Exception as e:
            logger.error(f"[DOCKER_API] restart-bot failed: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @flask_app.route('/api/docker/rebuild', methods=['POST'])
    @login_required
    def docker_rebuild():
        """Пересобирает и перезапускает с очисткой кеша"""
        try:
            docker_cmd = _find_docker_command()
            compose_args = _get_compose_args()
            logger.info(f"[DOCKER_API] rebuild initiated by {session.get('username')}, docker={docker_cmd}, compose_args={compose_args}")

            # Останавливаем только bot, чтобы не воевать с контейнерами docs/codex
            stop_result = subprocess.run(
                [docker_cmd, *compose_args, 'stop', 'bot'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            if stop_result.returncode != 0:
                logger.warning(f"[DOCKER_API] stop bot warning: {stop_result.stderr}")

            remove_result = subprocess.run(
                [docker_cmd, *compose_args, 'rm', '-f', 'bot'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60
            )
            if remove_result.returncode not in (0, 1):  # 1 = контейнера нет
                logger.error(f"[DOCKER_API] remove bot failed: {remove_result.stderr}")
                return jsonify({'success': False, 'message': f'Remove failed: {remove_result.stderr}'}), 500

            # Сборка без кеша
            build_result = subprocess.run(
                [docker_cmd, *compose_args, 'build', '--no-cache', 'bot'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300
            )
            if build_result.returncode != 0:
                logger.error(f"[DOCKER_API] build failed: {build_result.stderr}")
                return jsonify({'success': False, 'message': f'Build failed: {build_result.stderr}'}), 500
            
            # Перезапуск с force-recreate
            up_result = subprocess.run(
                [docker_cmd, *compose_args, 'up', '-d', '--force-recreate', 'bot'],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            logger.info(f"[DOCKER_API] rebuild completed: returncode={up_result.returncode}")
            return jsonify({
                'success': up_result.returncode == 0,
                'message': 'Rebuild completed' if up_result.returncode == 0 else up_result.stderr,
                'reload_after': 200
            })
        except Exception as e:
            logger.error(f"[DOCKER_API] rebuild failed: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # Запускаем мониторинг сразу
    start_ton_monitoring_task()

    # Экспортируем функцию для тестирования
    globals()['get_common_template_data'] = get_common_template_data

    return flask_app