#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация тестовой deeplink ссылки
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.deeplink import create_deeplink

# Создаём тестовую ссылку
link = create_deeplink("darkmaxi_vpn_bot", group_code="moi", promo_code="SKIDKA100RUB")

print("НОВАЯ РАБОЧАЯ ССЫЛКА:")
print(link)
print()
print("Параметр start:")
print(link.split("?start=")[1])
print()
print("Длина параметра:", len(link.split("?start=")[1]), "символов (лимит: 64)")

# Проверяем парсинг
from shop_bot.utils.deeplink import parse_deeplink
param = link.split("?start=")[1]
group, promo, referrer = parse_deeplink(param)
print()
print("Парсинг результата:")
print(f"  group: {group}")
print(f"  promo: {promo}")
print(f"  referrer: {referrer}")
