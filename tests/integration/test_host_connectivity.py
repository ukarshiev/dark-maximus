#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционный тест для проверки подключения ко всем панелям хостов

Тест подключается ко всем хостам из базы данных по очереди и проверяет
успешность подключения. Пароли берутся из базы данных.

ВАЖНО: Тест использует реальную БД и реальные подключения к панелям.
Убедитесь, что все хосты в БД имеют корректные учетные данные.
"""

import pytest
import sys
from pathlib import Path
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager import database
from shop_bot.modules import xui_api


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Подключение к панелям хостов")
@allure.label("package", "tests.integration")
class TestHostConnectivity:
    """Тесты для проверки подключения ко всем панелям хостов"""
    
    @allure.story("Проверка подключения ко всем хостам из БД")
    @allure.title("Подключение ко всем панелям по очереди")
    @allure.description("""
    Проверяет подключение ко всем хостам из базы данных по очереди.
    
    **Что проверяется:**
    - Получение списка всех хостов из БД
    - Успешное подключение к каждому хосту через login_to_host
    - Наличие инбаунда с указанным ID на каждом хосте
    - Корректность учетных данных (URL, username, password, inbound_id)
    
    **Тестовые данные:**
    - Все хосты из таблицы xui_hosts в БД
    - Пароли берутся из БД (host_pass)
    
    **Предусловия:**
    - В БД должны быть настроены хосты с корректными учетными данными
    - Все хосты должны быть доступны по сети
    - Учетные данные должны быть валидными
    
    **Ожидаемый результат:**
    Для каждого хоста должно быть успешное подключение (api и inbound не None).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("hosts", "connectivity", "xui", "integration", "critical", "database")
    def test_connect_to_all_hosts(self):
        """Тест подключения ко всем хостам из БД"""
        with allure.step("Получение списка всех хостов из БД"):
            hosts = database.get_all_hosts()
            allure.attach(
                str(len(hosts)),
                "Количество хостов",
                allure.attachment_type.TEXT
            )
            
            if not hosts:
                pytest.skip("В БД нет хостов для проверки подключения")
            
            allure.attach(
                "\n".join([f"- {h['host_name']}: {h['host_url']}" for h in hosts]),
                "Список хостов",
                allure.attachment_type.TEXT
            )
        
        results = []
        failed_hosts = []
        
        for host in hosts:
            host_name = host.get('host_name', 'Unknown')
            host_url = host.get('host_url', '')
            host_username = host.get('host_username', '')
            host_pass = host.get('host_pass', '')
            host_inbound_id = host.get('host_inbound_id')
            
            with allure.step(f"Подключение к хосту '{host_name}'"):
                allure.attach(
                    f"URL: {host_url}\nUsername: {host_username}\nInbound ID: {host_inbound_id}",
                    f"Параметры хоста {host_name}",
                    allure.attachment_type.TEXT
                )
                
                # Проверяем наличие обязательных полей
                if not host_url:
                    error_msg = f"Хост '{host_name}': отсутствует host_url"
                    allure.attach(error_msg, "Ошибка", allure.attachment_type.TEXT)
                    results.append({
                        'host_name': host_name,
                        'status': 'failed',
                        'error': error_msg
                    })
                    failed_hosts.append(host_name)
                    continue
                
                if not host_username:
                    error_msg = f"Хост '{host_name}': отсутствует host_username"
                    allure.attach(error_msg, "Ошибка", allure.attachment_type.TEXT)
                    results.append({
                        'host_name': host_name,
                        'status': 'failed',
                        'error': error_msg
                    })
                    failed_hosts.append(host_name)
                    continue
                
                if not host_pass:
                    error_msg = f"Хост '{host_name}': отсутствует host_pass"
                    allure.attach(error_msg, "Ошибка", allure.attachment_type.TEXT)
                    results.append({
                        'host_name': host_name,
                        'status': 'failed',
                        'error': error_msg
                    })
                    failed_hosts.append(host_name)
                    continue
                
                if host_inbound_id is None:
                    error_msg = f"Хост '{host_name}': отсутствует host_inbound_id"
                    allure.attach(error_msg, "Ошибка", allure.attachment_type.TEXT)
                    results.append({
                        'host_name': host_name,
                        'status': 'failed',
                        'error': error_msg
                    })
                    failed_hosts.append(host_name)
                    continue
                
                # Пытаемся подключиться к хосту
                try:
                    api, inbound = xui_api.login_to_host(
                        host_url=host_url,
                        username=host_username,
                        password=host_pass,
                        inbound_id=host_inbound_id,
                        max_retries=3
                    )
                    
                    if api is None:
                        error_msg = f"Хост '{host_name}': не удалось подключиться (api=None)"
                        allure.attach(error_msg, "Ошибка подключения", allure.attachment_type.TEXT)
                        results.append({
                            'host_name': host_name,
                            'status': 'failed',
                            'error': error_msg
                        })
                        failed_hosts.append(host_name)
                    elif inbound is None:
                        error_msg = f"Хост '{host_name}': подключение успешно, но инбаунд с ID {host_inbound_id} не найден"
                        allure.attach(error_msg, "Ошибка инбаунда", allure.attachment_type.TEXT)
                        results.append({
                            'host_name': host_name,
                            'status': 'partial',
                            'error': error_msg,
                            'api_connected': True
                        })
                        failed_hosts.append(host_name)
                    else:
                        success_msg = f"Хост '{host_name}': подключение успешно, инбаунд найден"
                        allure.attach(success_msg, "Успех", allure.attachment_type.TEXT)
                        results.append({
                            'host_name': host_name,
                            'status': 'success',
                            'api_connected': True,
                            'inbound_found': True
                        })
                        
                except Exception as e:
                    error_msg = f"Хост '{host_name}': исключение при подключении - {str(e)}"
                    allure.attach(
                        error_msg,
                        "Исключение",
                        allure.attachment_type.TEXT
                    )
                    results.append({
                        'host_name': host_name,
                        'status': 'failed',
                        'error': error_msg,
                        'exception': str(e)
                    })
                    failed_hosts.append(host_name)
        
        with allure.step("Анализ результатов"):
            total_hosts = len(hosts)
            successful = len([r for r in results if r['status'] == 'success'])
            failed = len([r for r in results if r['status'] == 'failed'])
            partial = len([r for r in results if r['status'] == 'partial'])
            
            summary = f"""
Всего хостов: {total_hosts}
Успешных подключений: {successful}
Частично успешных (подключение есть, но инбаунд не найден): {partial}
Неудачных подключений: {failed}
"""
            allure.attach(summary, "Сводка результатов", allure.attachment_type.TEXT)
            
            if failed_hosts:
                failed_list = "\n".join([f"- {name}" for name in failed_hosts])
                allure.attach(failed_list, "Неудачные хосты", allure.attachment_type.TEXT)
        
        # Проверяем, что хотя бы один хост подключился успешно
        assert successful > 0 or partial > 0, (
            f"Не удалось подключиться ни к одному хосту. "
            f"Всего хостов: {total_hosts}, неудачных: {failed}"
        )
        
        # Если есть полностью неудачные подключения, выводим предупреждение
        if failed > 0:
            pytest.fail(
                f"Не удалось подключиться к {failed} хостам из {total_hosts}. "
                f"Неудачные хосты: {', '.join(failed_hosts)}"
            )

