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

def extract_redirect_url_from_html(html_content: str) -> str | None:
    """
    Извлекает URL из HTML-страницы "Redirecting..." от allure-service.
    
    Args:
        html_content: HTML-контент страницы
        
    Returns:
        str: Путь без базового URL или None, если URL не найден
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
    session.pop('logged_in', None)
    flash('Вы успешно вышли.', 'success')
    return redirect(url_for('login_page'))

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
        
        # Специальная обработка для /latest/index.html: если получен JSON вместо HTML,
        # делаем редирект на последний доступный отчет через API
        if path == 'projects/default/reports/latest/index.html' or path.endswith('/projects/default/reports/latest/index.html'):
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

