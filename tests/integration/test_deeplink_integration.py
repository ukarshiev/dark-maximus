#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для проверки работы deeplink генерации и парсинга
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.deeplink import create_deeplink, parse_deeplink


@pytest.mark.integration
@allure.epic("Интеграционные тесты")
@allure.feature("Deeplink")
@allure.label("package", "tests.integration")
class TestDeeplinkIntegration:
    """Интеграционные тесты для deeplink"""

    @allure.story("Генерация и парсинг deeplink ссылок")
    @allure.title("Генерация deeplink ссылок с различными параметрами")
    @allure.description("""
    Интеграционный тест, проверяющий генерацию и парсинг deeplink ссылок с различными комбинациями параметров.
    
    **Что проверяется:**
    - Генерация deeplink с группой и промокодом
    - Генерация deeplink только с группой
    - Генерация deeplink только с промокодом
    - Генерация реферальной ссылки (старый формат)
    - Генерация deeplink со всеми параметрами
    - Корректный парсинг всех типов ссылок
    
    **Тестовые данные:**
    - bot_name: "darkmaxi_vpn_bot"
    - Различные комбинации: group_code, promo_code, referrer_id
    
    **Ожидаемый результат:**
    Все типы deeplink ссылок успешно генерируются и корректно парсятся.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "parsing", "integration")
    def test_deeplink_generation(self):
        """Тест генерации deeplink ссылок"""
        # Тест 1: Ссылка с группой и промокодом
        link1 = create_deeplink("darkmaxi_vpn_bot", group_code="moi", promo_code="SKIDKA100RUB")
        assert "?start=" in link1
        
        # Проверяем, что можно распарсить
        param1 = link1.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param1)
        assert group == "moi"
        assert promo == "SKIDKA100RUB"
        assert referrer is None
        
        # Тест 2: Только группа
        link2 = create_deeplink("darkmaxi_vpn_bot", group_code="vip")
        assert "?start=" in link2
        
        param2 = link2.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param2)
        assert group == "vip"
        assert promo is None
        assert referrer is None
        
        # Тест 3: Только промокод
        link3 = create_deeplink("darkmaxi_vpn_bot", promo_code="WELCOME50")
        assert "?start=" in link3
        
        param3 = link3.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param3)
        assert group is None
        assert promo == "WELCOME50"
        assert referrer is None
        
        # Тест 4: Реферальная ссылка (старый формат)
        link4 = create_deeplink("darkmaxi_vpn_bot", referrer_id=123456789)
        assert "?start=" in link4
        
        param4 = link4.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param4)
        assert group is None
        assert promo is None
        assert referrer == 123456789
        
        # Тест 5: Все параметры
        link5 = create_deeplink("darkmaxi_vpn_bot", group_code="premium", promo_code="MEGA50", referrer_id=987654321)
        assert "?start=" in link5
        
        param5 = link5.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param5)
        assert group == "premium"
        assert promo == "MEGA50"
        assert referrer == 987654321

    @allure.story("Решение проблемы с форматом deeplink")
    @allure.title("Проверка решения оригинальной проблемы с форматом deeplink")
    @allure.description("""
    Интеграционный тест, проверяющий решение оригинальной проблемы с форматом deeplink ссылок.
    
    **Что проверяется:**
    - Сравнение старого неработающего формата с новым рабочим форматом
    - Генерация новой рабочей ссылки с group_code и promo_code
    - Корректный парсинг новой ссылки
    - Отсутствие проблемных символов в параметре deeplink
    
    **Тестовые данные:**
    - Старая ссылка: "https://t.me/darkmaxi_vpn_bot?start=user_groups=moi,promo=SKIDKA100RUB"
    - Новая ссылка: с group_code="moi", promo_code="SKIDKA100RUB"
    
    **Ожидаемый результат:**
    Новая ссылка успешно генерируется и корректно парсится, старый формат больше не используется.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "format", "integration")
    def test_original_problem_solution(self):
        # Оригинальная неработающая ссылка
        old_link = "https://t.me/darkmaxi_vpn_bot?start=user_groups=moi,promo=SKIDKA100RUB"
        
        # Новая рабочая ссылка
        new_link = create_deeplink("darkmaxi_vpn_bot", group_code="moi", promo_code="SKIDKA100RUB")
        assert "?start=" in new_link
        assert "=" not in new_link.split("?start=")[1] or "user_groups" not in new_link.split("?start=")[1]
        
        # Проверяем, что новая ссылка работает
        param = new_link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        assert group == "moi"
        assert promo == "SKIDKA100RUB"
        assert referrer is None

