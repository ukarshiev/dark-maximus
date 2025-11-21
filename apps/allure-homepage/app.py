#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главная страница для Allure Docker Service
Веб-сервис для отображения главной страницы и проксирования запросов к allure-service
"""

import os
import sys
import logging
import json
import re
import requests
from flask import Flask, render_template, request, Response, abort, redirect, session, flash, url_for
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Добавляем путь к src для импорта модулей
# В контейнере src маппится в /app/src, в локальной разработке - в корень проекта
app_dir = Path(__file__).parent  # /app/ в контейнере
container_src_path = app_dir / "src"  # /app/src в контейнере
local_src_path = app_dir.parent.parent / "src"  # для локальной разработки

# Проверяем, какой путь существует
if container_src_path.exists():
    src_path = container_src_path
elif local_src_path.exists():
    src_path = local_src_path
else:
    # Fallback: используем /app/src (для контейнера)
    src_path = Path("/app/src")

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Импортируем утилиты авторизации
from shop_bot.webhook_server.auth_utils import init_flask_auth, login_required, verify_and_login

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

# Инициализация авторизации
init_flask_auth(app, session_dir='/app/sessions')

# ИСПРАВЛЕНИЕ: Устанавливаем уникальное имя cookie для allure-homepage
# Это предотвращает конфликт cookie между сервисами при использовании одинакового FLASK_SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = 'allure_session'

# URL allure-service (внутренний порт)
ALLURE_SERVICE_URL = os.getenv('ALLURE_SERVICE_URL', 'http://allure-service:5050')

def get_latest_report_id(project='default'):
    """
    Получает ID последнего отчета через API Allure Docker Service.
    
    Args:
        project: Название проекта (по умолчанию 'default')
    
    Returns:
        str: ID последнего отчета или None в случае ошибки
    """
    try:
        # Используем /projects/{project} для получения информации о проекте, включая reports_id
        api_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}"
        logger.info(f"Запрос последнего отчета через API: {api_url}")
        
        response = requests.get(
            api_url,
            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"API вернул статус {response.status_code} для получения списка отчетов")
            return None
        
        data = response.json()
        
        # Извлекаем reports_id из структуры JSON
        # Структура: {"data": {"project": {"reports_id": ["9", "8", "7", ...]}}}
        reports_id = None
        if 'data' in data and 'project' in data['data']:
            project_data = data['data']['project']
            if 'reports_id' in project_data and isinstance(project_data['reports_id'], list):
                reports_id = project_data['reports_id']
            # Альтернативный способ: если reports_id нет, но есть reports с URL, извлекаем ID из URL
            elif 'reports' in project_data and isinstance(project_data['reports'], list) and len(project_data['reports']) > 0:
                # Извлекаем ID из первого URL (например, "/reports/16/index.html" -> "16")
                first_report_url = project_data['reports'][0]
                match = re.search(r'/reports/(\d+)/', first_report_url)
                if match:
                    latest_id = match.group(1)
                    logger.info(f"Найден последний отчет с ID (из URL): {latest_id}")
                    return latest_id
        
        if not reports_id or len(reports_id) == 0:
            logger.warning("Список отчетов пуст")
            return None
        
        # Первый элемент в массиве - это самый новый отчет
        latest_id = reports_id[0]
        logger.info(f"Найден последний отчет с ID: {latest_id}")
        return latest_id
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API для получения последнего отчета: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Ошибка при парсинге JSON ответа API: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении последнего отчета: {e}")
        return None

def get_report_statistics(report_id, project='default'):
    """
    Получает статистику тестов из JSON файла отчета.
    
    Args:
        report_id: ID отчета
        project: Название проекта (по умолчанию 'default')
    
    Returns:
        dict: {'test_count': int, 'success_percentage': float} или None
    """
    try:
        # Формируем URL для получения widgets/summary.json
        summary_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}/reports/{report_id}/widgets/summary.json"
        logger.info(f"Запрос статистики отчета через API: {summary_url}")
        
        response = requests.get(
            summary_url,
            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"API вернул статус {response.status_code} для получения статистики отчета")
            return None
        
        data = response.json()
        
        # Извлекаем статистику из структуры JSON
        # Структура: {"statistic": {"total": 482, "passed": 459, "failed": 10, ...}}
        if 'statistic' in data:
            statistic = data['statistic']
            total = statistic.get('total', 0)
            passed = statistic.get('passed', 0)
            
            if total > 0:
                success_percentage = (passed / total) * 100
                return {
                    'test_count': total,
                    'success_percentage': round(success_percentage, 1)
                }
        
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API для получения статистики отчета: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Ошибка при парсинге JSON статистики отчета: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении статистики отчета: {e}")
        return None

def get_report_execution_time(report_id, project='default'):
    """
    Получает время выполнения тестов из JSON файла отчета.
    
    Args:
        report_id: ID отчета
        project: Название проекта (по умолчанию 'default')
    
    Returns:
        dict: {'execution_start': str, 'execution_end': str, 'execution_duration': str, 'report_date': str} или None
        Формат времени: HH:MM:SS
        Формат даты: DD.MM.YYYY
        Формат длительности: "Xm Ys"
    """
    try:
        # Пробуем получить данные из widgets/summary.json (может содержать время выполнения)
        summary_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}/reports/{report_id}/widgets/summary.json"
        logger.info(f"Запрос времени выполнения через API: {summary_url}")
        
        response = requests.get(
            summary_url,
            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"API вернул статус {response.status_code} для получения времени выполнения")
            return None
        
        data = response.json()
        
        # Ищем время выполнения в структуре JSON
        # Может быть в разных местах: time, start, stop, duration и т.д.
        execution_start = None
        execution_end = None
        report_date = None
        
        # Пробуем получить из summary.json
        if 'time' in data:
            time_data = data['time']
            if isinstance(time_data, dict):
                execution_start = time_data.get('start')
                execution_end = time_data.get('stop')
            elif isinstance(time_data, (int, float)):
                # Если это timestamp
                execution_start = time_data
                execution_end = time_data
        
        # Если не нашли, пробуем получить из data/test-cases.json
        if not execution_start or not execution_end:
            test_cases_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}/reports/{report_id}/data/test-cases.json"
            try:
                test_cases_response = requests.get(
                    test_cases_url,
                    headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
                    timeout=10
                )
                
                if test_cases_response.status_code == 200:
                    test_cases_data = test_cases_response.json()
                    if isinstance(test_cases_data, list) and len(test_cases_data) > 0:
                        # Находим минимальное и максимальное время из всех тестов
                        start_times = []
                        stop_times = []
                        
                        for test_case in test_cases_data:
                            if 'time' in test_case:
                                time_info = test_case['time']
                                if isinstance(time_info, dict):
                                    if 'start' in time_info:
                                        start_times.append(time_info['start'])
                                    if 'stop' in time_info:
                                        stop_times.append(time_info['stop'])
                                elif isinstance(time_info, (int, float)):
                                    start_times.append(time_info)
                                    stop_times.append(time_info)
                        
                        if start_times:
                            execution_start = min(start_times)
                        if stop_times:
                            execution_end = max(stop_times)
            except Exception as e:
                logger.warning(f"Не удалось получить время из test-cases.json: {e}")
        
        # Если все еще нет данных, используем текущее время как fallback
        if not execution_start:
            execution_start = datetime.now(timezone.utc).timestamp() * 1000
        if not execution_end:
            execution_end = execution_start
        
        # Конвертируем timestamp в datetime (может быть в миллисекундах или секундах)
        if execution_start > 1e12:  # Миллисекунды
            start_dt = datetime.fromtimestamp(execution_start / 1000, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(execution_end / 1000, tz=timezone.utc)
        else:  # Секунды
            start_dt = datetime.fromtimestamp(execution_start, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(execution_end, tz=timezone.utc)
        
        # Конвертируем в UTC+3 (Moscow timezone)
        moscow_tz = timezone(timedelta(hours=3))
        start_dt_moscow = start_dt.astimezone(moscow_tz)
        end_dt_moscow = end_dt.astimezone(moscow_tz)
        
        # Форматируем время
        execution_start_str = start_dt_moscow.strftime('%H:%M:%S')
        execution_end_str = end_dt_moscow.strftime('%H:%M:%S')
        report_date_str = start_dt_moscow.strftime('%d.%m.%Y')
        
        # Вычисляем длительность
        duration = end_dt_moscow - start_dt_moscow
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        execution_duration_str = f"{minutes}m {seconds}s"
        
        return {
            'execution_start': execution_start_str,
            'execution_end': execution_end_str,
            'execution_duration': execution_duration_str,
            'report_date': report_date_str
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API для получения времени выполнения: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Ошибка при парсинге JSON времени выполнения: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении времени выполнения: {e}")
        return None

def get_latest_report_info(project='default'):
    """
    Получает информацию о последнем отчете через API Allure Docker Service.
    
    Args:
        project: Название проекта (по умолчанию 'default')
    
    Returns:
        dict: Расширенная информация об отчете:
        {
            'report_id': str,
            'created_at': str,
            'status': str,  # 'created', 'generating', 'no_reports'
            'test_count': int,  # количество тестов
            'success_percentage': float,  # процент успешных тестов
            'report_date': str,  # дата отчета (DD.MM.YYYY)
            'execution_start': str,  # время начала (HH:MM:SS)
            'execution_end': str,  # время окончания (HH:MM:SS)
            'execution_duration': str  # длительность (Xm Ys)
        } или None
    """
    try:
        api_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}"
        logger.info(f"Запрос информации о последнем отчете через API: {api_url}")
        
        response = requests.get(
            api_url,
            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"API вернул статус {response.status_code} для получения информации об отчете")
            return None
        
        data = response.json()
        
        # Извлекаем информацию о последнем отчете
        if 'data' in data and 'project' in data['data']:
            project_data = data['data']['project']
            
            # Получаем список отчетов
            reports_id = None
            latest_id = None
            
            if 'reports_id' in project_data and isinstance(project_data['reports_id'], list):
                reports_id = project_data['reports_id']
            elif 'reports' in project_data and isinstance(project_data['reports'], list) and len(project_data['reports']) > 0:
                # Извлекаем ID из первого URL
                first_report_url = project_data['reports'][0]
                match = re.search(r'/reports/(\d+)/', first_report_url)
                if match:
                    latest_id = match.group(1)
            
            if reports_id and len(reports_id) > 0:
                # Пропускаем "latest" и берем первый реальный ID отчета
                for rid in reports_id:
                    if rid != 'latest' and rid.isdigit():
                        latest_id = rid
                        break
                # Если не нашли цифровой ID, используем первый элемент
                if not latest_id or latest_id == 'latest':
                    latest_id = reports_id[0] if reports_id else None
            
            if latest_id and latest_id != 'latest':
                # Получаем базовую информацию
                created_at = None
                if 'last_execution' in project_data:
                    created_at = project_data['last_execution']
                elif 'execution_blocks' in project_data and len(project_data['execution_blocks']) > 0:
                    first_block = project_data['execution_blocks'][0]
                    if 'time' in first_block:
                        created_at = first_block['time']
                elif 'last_report_time' in project_data:
                    created_at = project_data['last_report_time']
                
                # Получаем расширенную информацию из JSON файлов отчета
                statistics = get_report_statistics(latest_id, project)
                execution_time = get_report_execution_time(latest_id, project)
                
                result = {
                    'report_id': latest_id,
                    'created_at': created_at,
                    'status': 'created'
                }
                
                # Добавляем статистику тестов
                if statistics:
                    result['test_count'] = statistics.get('test_count')
                    result['success_percentage'] = statistics.get('success_percentage')
                else:
                    result['test_count'] = None
                    result['success_percentage'] = None
                
                # Добавляем информацию о времени выполнения
                if execution_time:
                    result['report_date'] = execution_time.get('report_date')
                    result['execution_start'] = execution_time.get('execution_start')
                    result['execution_end'] = execution_time.get('execution_end')
                    result['execution_duration'] = execution_time.get('execution_duration')
                else:
                    result['report_date'] = None
                    result['execution_start'] = None
                    result['execution_end'] = None
                    result['execution_duration'] = None
                
                return result
        
        # Если отчетов нет, возможно идет генерация
        # Проверяем наличие результатов тестов
        return {'report_id': None, 'created_at': None, 'status': 'no_reports'}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API для получения информации об отчете: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Ошибка при парсинге JSON ответа API: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении информации об отчете: {e}")
        return None

def get_reports_with_dates(project='default'):
    """
    Получает информацию о всех отчетах с датами создания.
    
    Args:
        project: Название проекта (по умолчанию 'default')
    
    Returns:
        list: Список словарей с информацией об отчетах:
        [{'report_id': str, 'created_at': str, 'execution_name': str}, ...]
    """
    try:
        api_url = f"{ALLURE_SERVICE_URL}/allure-docker-service/projects/{project}"
        logger.info(f"Запрос информации о всех отчетах через API: {api_url}")
        
        response = requests.get(
            api_url,
            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"API вернул статус {response.status_code} для получения информации об отчетах")
            return []
        
        data = response.json()
        reports_info = []
        
        # Извлекаем информацию об отчетах
        if 'data' in data and 'project' in data['data']:
            project_data = data['data']['project']
            
            # Получаем список отчетов
            reports_id = None
            if 'reports_id' in project_data and isinstance(project_data['reports_id'], list):
                reports_id = project_data['reports_id']
            elif 'reports' in project_data and isinstance(project_data['reports'], list):
                # Извлекаем ID из URL
                reports_id = []
                for report_url in project_data['reports']:
                    match = re.search(r'/reports/(\d+)/', report_url)
                    if match:
                        reports_id.append(match.group(1))
            
            if reports_id and len(reports_id) > 0:
                # Получаем информацию о времени создания из execution_blocks, если доступно
                execution_blocks = project_data.get('execution_blocks', [])
                execution_times = {}
                if execution_blocks:
                    for block in execution_blocks:
                        if 'report_id' in block and 'time' in block:
                            execution_times[block['report_id']] = block['time']
                
                # Формируем список отчетов с датами
                for report_id in reports_id:
                    created_at = execution_times.get(report_id) or project_data.get('last_execution') or project_data.get('last_report_time')
                    reports_info.append({
                        'report_id': report_id,
                        'created_at': created_at,
                        'execution_name': None  # Имя выполнения может быть недоступно через этот API
                    })
        
        return reports_info
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API для получения информации об отчетах: {e}")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Ошибка при парсинге JSON ответа API: {e}")
        return []
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении информации об отчетах: {e}")
        return []

def extract_redirect_url_from_html(html_content: str) -> str | None:
    """
    Извлекает URL из HTML-страницы "Redirecting..." от allure-service.
    
    Args:
        html_content: HTML-контент страницы
        
    Returns:
        str: Путь без базового URL или None, если URL не найден
        Возвращает 'projects/default' или 'projects/default/', если редирект ведет на /projects/default
    """
    patterns = [
        r'target URL: <a href="([^"]+)"',  # target URL: <a href="...">
        r'href="([^"]+)"',  # href="http://..."
        r'target URL: ([^\s<]+)',  # target URL: http://...
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Убираем базовый URL, оставляем только путь
            url = url.replace('http://localhost:50005/allure-docker-service/', '')
            url = url.replace('http://localhost:50004/allure-docker-service/', '')
            url = url.replace('http://allure-service:5050/allure-docker-service/', '')
            if url.startswith('/'):
                url = url[1:]
            
            # Нормализуем путь для /projects/default
            if url == 'projects/default' or url == 'projects/default/':
                return 'projects/default'
            
            return url
    
    return None

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Страница входа в систему"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if verify_and_login(username, password):
            # Редирект на главную страницу после успешного входа
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout_page():
    """Выход из системы"""
    service_name = 'allure-homepage'
    session_id = session.get('_id', 'unknown')
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    logger.info(
        f"[AUTH] [{service_name}] Logout: "
        f"ip={client_ip}, session_id={session_id}"
    )
    
    session.pop('logged_in', None)
    flash('Вы успешно вышли.', 'success')
    return redirect(url_for('login_page'))

@app.route('/allure-docker-service/api/report-status')
@login_required
def report_status():
    """API эндпоинт для получения статуса последнего отчета с расширенной информацией"""
    report_info = get_latest_report_info('default')
    if report_info:
        return json.dumps(report_info, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
    return json.dumps({
        'status': 'no_reports',
        'report_id': None,
        'created_at': None,
        'test_count': None,
        'success_percentage': None,
        'report_date': None,
        'execution_start': None,
        'execution_end': None,
        'execution_duration': None
    }, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/allure-docker-service/api/reports-with-dates')
@login_required
def reports_with_dates():
    """API эндпоинт для получения списка отчетов с датами"""
    project = request.args.get('project', 'default')
    reports_info = get_reports_with_dates(project)
    return json.dumps({'reports': reports_info}, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/allure-docker-service/')
@login_required
def index():
    """Главная страница с ссылками на отчеты и API"""
    return render_template('index.html')

@app.route('/allure-docker-service/projects')
@login_required
def projects():
    """
    Страница со списком проектов.
    Если запрос с Accept: application/json (и без text/html) - проксируем к API.
    Иначе возвращаем HTML-страницу.
    """
    accept_header = request.headers.get('Accept', '').lower()
    logger.info(f"Projects route: Accept={accept_header}, has_text_html={'text/html' in accept_header}")
    
    # Если запрос явно требует только JSON (без text/html), проксируем к API
    # Иначе (браузеры отправляют text/html) возвращаем HTML
    if 'text/html' not in accept_header and 'application/json' in accept_header:
        logger.info("Проксируем /projects к API (JSON запрос)")
        # Проксируем к API
        target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', 'projects')
        
        try:
            params = request.args.to_dict()
            headers = dict(request.headers)
            headers.pop('Host', None)
            headers.pop('Connection', None)
            headers.pop('Content-Length', None)
            headers['Host'] = 'localhost:50005'
            
            response = requests.get(
                target_url,
                params=params,
                headers=headers,
                timeout=60
            )
            
            response_headers = dict(response.headers)
            response_headers.pop('Content-Encoding', None)
            response_headers.pop('Transfer-Encoding', None)
            response_headers.pop('Content-Length', None)
            
            content = response.content
            content_type = response.headers.get('Content-Type', 'application/json')
            
            # Исправляем пути в JSON
            if content_type.startswith('application/json'):
                try:
                    content_str = content.decode('utf-8')
                    data = json.loads(content_str)
                    
                    def fix_double_paths(obj):
                        if isinstance(obj, dict):
                            for key, value in obj.items():
                                if isinstance(value, str):
                                    value = value.replace('/allure-docker-service/allure-docker-service/', '/allure-docker-service/')
                                    value = value.replace('http://allure-service:5050/', 'http://localhost:50005/')
                                    obj[key] = value
                                else:
                                    fix_double_paths(value)
                        elif isinstance(obj, list):
                            for item in obj:
                                fix_double_paths(item)
                    
                    fix_double_paths(data)
                    content = json.dumps(data, ensure_ascii=False).encode('utf-8')
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Не удалось исправить пути в JSON ответе: {e}")
            
            return Response(
                content,
                status=response.status_code,
                headers=response_headers,
                mimetype=content_type
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при проксировании запроса к /projects: {e}")
            abort(502, description=f"Ошибка подключения к allure-service: {str(e)}")
    else:
        # Возвращаем HTML-страницу для браузеров
        logger.info("Возвращаем HTML-страницу projects.html")
        return render_template('projects.html')

@app.route('/allure-docker-service/<path:path>')
@login_required
def proxy(path):
    """Проксирование всех запросов к allure-service"""
    # Логируем в начале функции для диагностики
    session_logged_in = session.get('logged_in', False)
    print(f"[PROXY] Проксирование запроса: path={path}, method={request.method}, session={session_logged_in}", flush=True)
    logger.info(f"Проксирование запроса: path={path}, method={request.method}, session_logged_in={session_logged_in}")
    
    # Если это запрос к /projects, не обрабатываем его здесь (должен обрабатываться специальным роутом)
    if path == 'projects':
        logger.warning("Запрос /projects попал в proxy роут вместо projects роута!")
        # Пробуем вернуть HTML для браузеров
        accept_header = request.headers.get('Accept', '').lower()
        if 'text/html' in accept_header:
            logger.info("Возвращаем HTML из proxy роута")
            return render_template('projects.html')
    
    # Формируем полный URL для запроса к allure-service
    # Все пути проксируются на те же пути в allure-service
    target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', path)
    
    try:
        
        # Получаем параметры запроса
        params = request.args.to_dict()
        
        # Получаем заголовки запроса (исключаем Host и Connection)
        headers = dict(request.headers)
        headers.pop('Host', None)
        headers.pop('Connection', None)
        headers.pop('Content-Length', None)
        # Устанавливаем правильный Host для allure-service
        headers['Host'] = 'localhost:50005'
        
        # Для swagger.json всегда запрашиваем JSON и удаляем заголовки браузера
        if path == 'swagger.json' or path.endswith('/swagger.json'):
            headers['Accept'] = 'application/json'
            # Удаляем заголовки, которые могут заставить allure-service вернуть HTML
            headers.pop('User-Agent', None)
            headers.pop('Referer', None)
            headers.pop('Origin', None)
            headers.pop('Accept-Language', None)
            headers.pop('Accept-Encoding', None)
            # Устанавливаем простой User-Agent для API запросов
            headers['User-Agent'] = 'Allure-Homepage-Proxy/1.0'
            # Используем внутренний Host для allure-service
            headers['Host'] = 'allure-service:5050'
        
        # Определяем метод запроса
        method = request.method
        
        # Получаем тело запроса
        data = request.get_data() if request.data else None
        
        # Выполняем запрос к allure-service
        # Отключаем автоматические редиректы, чтобы видеть исходные редиректы от allure-service
        response = requests.request(
            method=method,
            url=target_url,
            params=params,
            headers=headers,
            data=data,
            stream=True,
            timeout=60,
            allow_redirects=False
        )
        
        # Обработка редиректов от allure-service
        # Если allure-service возвращает редирект на /login, перенаправляем на наш /login
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            session_logged_in = session.get('logged_in', False)
            logger.info(f"Получен редирект от allure-service: {response.status_code} -> {location}, path={path}, session_logged_in={session_logged_in}")
            
            # Если редирект ведет на /login, перенаправляем на наш /login
            if '/login' in location or location.endswith('/login'):
                logger.info("Редирект на /login обнаружен, перенаправляю на наш /login")
                return redirect(url_for('login_page'), code=302)
            
            # Если редирект ведет на тот же путь с trailing slash (например, /swagger -> /swagger/),
            # делаем внутренний запрос к allure-service на новый путь, без редиректа браузера
            # Это сохраняет сессию и избегает повторной проверки @login_required
            redirect_handled = False
            logger.info(f"Проверка условия редиректа: location.endswith('/')={location.endswith('/')}, not path.endswith('/')={not path.endswith('/')}")
            if location.endswith('/') and not path.endswith('/'):
                # Извлекаем путь из location (убираем базовый URL)
                # allure-service может вернуть Location с разными базовыми URL:
                # - http://allure-service:5050/allure-docker-service/...
                # - http://localhost:50005/allure-docker-service/...
                # - /allure-docker-service/...
                location_path = location
                # Убираем различные варианты базового URL
                location_path = location_path.replace(ALLURE_SERVICE_URL + '/allure-docker-service/', '')
                location_path = location_path.replace('http://localhost:50005/allure-docker-service/', '')
                location_path = location_path.replace('http://127.0.0.1:50005/allure-docker-service/', '')
                location_path = location_path.replace('/allure-docker-service/', '')
                # Если location начинается с /, убираем его
                if location_path.startswith('/'):
                    location_path = location_path[1:]
                
                logger.info(f"Проверка редиректа с trailing slash: path={path}, location_path={location_path}")
                
                if location_path == path + '/':
                    logger.info(f"Редирект на путь с trailing slash: {path} -> {location_path}, делаю внутренний запрос к allure-service")
                    # Формируем новый URL для запроса к allure-service
                    new_target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', location_path)
                    # Делаем внутренний запрос к allure-service на новый путь
                    # Используем те же параметры, заголовки и данные, что и в исходном запросе
                    internal_response = requests.request(
                        method=method,
                        url=new_target_url,
                        params=params,
                        headers=headers,
                        data=data,
                        stream=True,
                        timeout=60,
                        allow_redirects=False
                    )
                    # Используем ответ от внутреннего запроса для дальнейшей обработки
                    response = internal_response
                    logger.info(f"Внутренний запрос к {new_target_url} завершен: status={response.status_code}")
                    
                    # Проверяем, не вернул ли внутренний запрос HTML-страницу "Redirecting..."
                    internal_content_type = response.headers.get('Content-Type', '')
                    if internal_content_type.startswith('text/html'):
                        try:
                            internal_content_str = response.content.decode('utf-8', errors='ignore')
                            if 'Redirecting...' in internal_content_str and 'target URL' in internal_content_str.lower():
                                logger.info("Внутренний запрос вернул HTML-страницу 'Redirecting...', извлекаю URL")
                                redirect_url = extract_redirect_url_from_html(internal_content_str)
                                if redirect_url:
                                    logger.info(f"Извлечен URL из HTML внутреннего запроса: {redirect_url}, делаю еще один внутренний запрос")
                                    # Делаем еще один внутренний запрос к allure-service на новый путь
                                    final_target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', redirect_url)
                                    final_response = requests.request(
                                        method=method,
                                        url=final_target_url,
                                        params=params,
                                        headers=headers,
                                        data=data,
                                        stream=True,
                                        timeout=60,
                                        allow_redirects=False
                                    )
                                    # Используем ответ от финального запроса
                                    response = final_response
                                    logger.info(f"Финальный внутренний запрос к {final_target_url} завершен: status={response.status_code}")
                        except Exception as e:
                            logger.warning(f"Ошибка при проверке HTML контента внутреннего запроса на 'Redirecting...': {e}")
                    
                    redirect_handled = True
            
            # Специальная обработка для редиректа на /projects/default при запросе /latest/index.html
            if not redirect_handled:
                # Проверяем, был ли исходный запрос к /latest/index.html
                is_latest_request = (path == 'projects/default/reports/latest/index.html' or 
                                   path.endswith('/projects/default/reports/latest/index.html'))
                
                # Проверяем, ведет ли редирект на /projects/default
                is_projects_default_redirect = (
                    '/projects/default' in location or 
                    location.endswith('/projects/default') or
                    location.endswith('/projects/default/')
                )
                
                if is_latest_request and is_projects_default_redirect:
                    logger.info("Редирект на /projects/default при запросе /latest/index.html, получаю последний отчет через API")
                    # Получаем ID последнего отчета через API
                    latest_report_id = get_latest_report_id('default')
                    if latest_report_id:
                        # Делаем редирект на конкретный отчет
                        redirect_url = f"/allure-docker-service/projects/default/reports/{latest_report_id}/index.html"
                        logger.info(f"Редирект на последний отчет: {redirect_url}")
                        return redirect(redirect_url, code=302)
                    else:
                        logger.warning("Не удалось получить ID последнего отчета при обработке редиректа")
            
            # Для других редиректов логируем предупреждение
            # Для безопасности не следуем редиректам автоматически
            if not redirect_handled:
                logger.warning(f"Необработанный редирект от allure-service: {location}")
                # Если редирект не обработан, но в теле ответа есть HTML-страница "Redirecting...",
                # обрабатываем её после формирования заголовков ответа
                # (проверка будет выполнена ниже в блоке обработки HTML-контента)
        
        # Формируем заголовки ответа
        response_headers = dict(response.headers)
        # Удаляем заголовки, которые могут вызвать проблемы
        response_headers.pop('Content-Encoding', None)
        response_headers.pop('Transfer-Encoding', None)
        response_headers.pop('Content-Length', None)
        # Удаляем Location заголовок, если он есть (мы обработали редиректы выше)
        response_headers.pop('Location', None)
        
        # Логируем информацию о ответе для диагностики
        logger.info(f"Ответ от allure-service: status={response.status_code}, content_type={response.headers.get('Content-Type', 'unknown')}, path={path}")
        
        # Исправляем двойные пути в ответах (JSON и HTML)
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        
        # Проверяем, если это HTML страница логина от allure-service, перенаправляем на наш /login
        if content_type.startswith('text/html'):
            try:
                content_str = content.decode('utf-8', errors='ignore')
                logger.info(f"Проверка HTML-контента: path={path}, status={response.status_code}, content_length={len(content_str)}")
                # Более надежные признаки страницы логина
                is_login_page = (
                    'Вход в Allure Docker Service' in content_str or
                    ('login' in content_str.lower() and 'password' in content_str.lower() and 
                     ('form' in content_str.lower() or 'input' in content_str.lower())) or
                    ('<title>' in content_str and 'login' in content_str.lower() and 
                     '</title>' in content_str)
                )
                if is_login_page:
                    logger.info("Обнаружена HTML страница логина от allure-service, перенаправляю на наш /login")
                    return redirect(url_for('login_page'), code=302)
                
                # Проверяем, является ли контент HTML-страницей "Redirecting..."
                if 'Redirecting...' in content_str and 'target URL' in content_str.lower():
                    logger.info("Обнаружена HTML-страница 'Redirecting...', извлекаю URL")
                    redirect_url = extract_redirect_url_from_html(content_str)
                    if redirect_url:
                        # Специальная обработка для редиректа на /projects/default при запросе /latest/index.html
                        is_latest_request = (path == 'projects/default/reports/latest/index.html' or 
                                           path.endswith('/projects/default/reports/latest/index.html'))
                        
                        is_projects_default = (redirect_url == 'projects/default' or 
                                             redirect_url.startswith('projects/default/'))
                        
                        if is_latest_request and is_projects_default:
                            logger.info("Редирект на /projects/default при запросе /latest/index.html, получаю последний отчет через API")
                            # Получаем ID последнего отчета через API
                            latest_report_id = get_latest_report_id('default')
                            if latest_report_id:
                                # Делаем редирект на конкретный отчет
                                final_redirect_url = f"/allure-docker-service/projects/default/reports/{latest_report_id}/index.html"
                                logger.info(f"Редирект на последний отчет: {final_redirect_url}")
                                return redirect(final_redirect_url, code=302)
                            else:
                                logger.warning("Не удалось получить ID последнего отчета при обработке HTML 'Redirecting...'")
                        
                        logger.info(f"Извлечен URL из HTML: {redirect_url}, делаю внутренний запрос")
                        # Делаем внутренний запрос к allure-service на новый путь
                        new_target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', redirect_url)
                        internal_response = requests.request(
                            method=method,
                            url=new_target_url,
                            params=params,
                            headers=headers,
                            data=data,
                            stream=True,
                            timeout=60,
                            allow_redirects=False
                        )
                        # Используем ответ от внутреннего запроса
                        response = internal_response
                        content = response.content
                        content_type = response.headers.get('Content-Type', '')
                        # Обновляем заголовки ответа после внутреннего запроса
                        response_headers = dict(response.headers)
                        response_headers.pop('Content-Encoding', None)
                        response_headers.pop('Transfer-Encoding', None)
                        response_headers.pop('Content-Length', None)
                        response_headers.pop('Location', None)
                        logger.info(f"Внутренний запрос к {new_target_url} завершен: status={response.status_code}")
            except Exception as e:
                logger.warning(f"Ошибка при проверке HTML контента на страницу логина: {e}")
        
        # Специальная обработка для /latest/index.html: если получен JSON или HTML с редиректом на /projects/default,
        # делаем редирект на последний доступный отчет через API
        if path == 'projects/default/reports/latest/index.html' or path.endswith('/projects/default/reports/latest/index.html'):
            # Проверяем, если получен редирект на /projects/default (если не был обработан выше)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('Location', '')
                if '/projects/default' in location or location.endswith('/projects/default'):
                    logger.info("Редирект на /projects/default для /latest/index.html, получаю последний отчет через API")
                    latest_report_id = get_latest_report_id('default')
                    if latest_report_id:
                        redirect_url = f"/allure-docker-service/projects/default/reports/{latest_report_id}/index.html"
                        logger.info(f"Редирект на последний отчет: {redirect_url}")
                        return redirect(redirect_url, code=302)
            
            # Если получен JSON вместо HTML
            if content_type.startswith('application/json'):
                logger.warning(f"Запрос к /latest/index.html вернул JSON вместо HTML. Перенаправляю на последний доступный отчет...")
                # Получаем ID последнего отчета через API
                latest_report_id = get_latest_report_id('default')
                if latest_report_id:
                    # Делаем редирект на конкретный отчет
                    redirect_url = f"/allure-docker-service/projects/default/reports/{latest_report_id}/index.html"
                    logger.info(f"Редирект на последний отчет: {redirect_url}")
                    return redirect(redirect_url, code=302)
                else:
                    # Если не удалось получить ID отчета, возвращаем HTML-страницу с ошибкой
                    logger.error("Не удалось получить ID последнего отчета через API")
                    return render_template('error.html'), 503, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Для swagger.json принудительно устанавливаем JSON, если ответ не JSON
        if path == 'swagger.json' or path.endswith('/swagger.json'):
            logger.info(f"Обработка swagger.json: path={path}, content_type={content_type}, status={response.status_code}")
            if not content_type.startswith('application/json'):
                logger.info(f"Content-Type не JSON, проверяю контент...")
                # Если пришел HTML вместо JSON, делаем прямой запрос к allure-service
                try:
                    content_str = content.decode('utf-8')
                    logger.info(f"Контент начинается с: {content_str[:50]}")
                    if content_str.strip().startswith('<!') or content_str.strip().startswith('<!--'):
                        # Это HTML, делаем прямой запрос к allure-service
                        logger.info("Swagger.json вернул HTML, делаю прямой запрос к allure-service")
                        direct_response = requests.get(
                            ALLURE_SERVICE_URL + '/allure-docker-service/swagger.json',
                            headers={'Accept': 'application/json', 'User-Agent': 'Allure-Homepage-Proxy/1.0'},
                            timeout=10
                        )
                        if direct_response.status_code == 200 and direct_response.headers.get('Content-Type', '').startswith('application/json'):
                            content = direct_response.content
                            content_type = 'application/json'
                            response_headers['Content-Type'] = 'application/json'
                            logger.info("Успешно получен JSON от allure-service напрямую")
                        elif direct_response.status_code == 200:
                            # Пробуем распарсить как JSON
                            try:
                                json.loads(direct_response.content.decode('utf-8'))
                                content = direct_response.content
                                content_type = 'application/json'
                                response_headers['Content-Type'] = 'application/json'
                                logger.info("Успешно распарсен JSON из прямого ответа")
                            except:
                                pass
                    elif content_str.strip().startswith('{') or content_str.strip().startswith('['):
                        # Это JSON, исправляем Content-Type
                        content_type = 'application/json'
                        response_headers['Content-Type'] = 'application/json'
                except Exception as e:
                    logger.warning(f"Ошибка при обработке swagger.json: {e}")
                    pass
        
        if content_type.startswith('application/json'):
            try:
                content_str = content.decode('utf-8')
                data = json.loads(content_str)
                
                # Рекурсивно исправляем все строковые значения с двойными путями и внутренними адресами
                def fix_double_paths(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str):
                                # Заменяем двойной путь на одинарный
                                value = value.replace('/allure-docker-service/allure-docker-service/', '/allure-docker-service/')
                                # Заменяем внутренний адрес на публичный
                                value = value.replace('http://allure-service:5050/', 'http://localhost:50005/')
                                obj[key] = value
                            else:
                                fix_double_paths(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            fix_double_paths(item)
                
                fix_double_paths(data)
                content = json.dumps(data, ensure_ascii=False).encode('utf-8')
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Не удалось исправить пути в JSON ответе: {e}")
        elif content_type.startswith('text/html') or content_type.startswith('application/javascript') or 'javascript' in content_type or content_type.startswith('text/css'):
            try:
                content_str = content.decode('utf-8')
                # Исправляем двойные пути в HTML/JS/CSS контенте
                content_str = content_str.replace('/allure-docker-service/allure-docker-service/', '/allure-docker-service/')
                content_str = content_str.replace('http://allure-service:5050/', 'http://localhost:50005/')
                content = content_str.encode('utf-8')
            except UnicodeDecodeError as e:
                logger.warning(f"Не удалось исправить пути в HTML/JS/CSS ответе: {e}")
        
        # Возвращаем ответ
        return Response(
            content,
            status=response.status_code,
            headers=response_headers,
            mimetype=content_type
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при проксировании запроса: {e}")
        abort(502, description=f"Ошибка подключения к allure-service: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        abort(500, description=f"Внутренняя ошибка сервера: {str(e)}")

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'service': 'allure-homepage'}, 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 50005))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

