#!/bin/bash
# Скрипт для запуска pylint с правильной кодировкой UTF-8 в Linux/Mac
# Использование: ./scripts/lint.sh

# Устанавливаем UTF-8 кодировку
export PYTHONIOENCODING=utf-8
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Запускаем pylint с параметрами
python -m pylint src/shop_bot/ --disable=C0111,C0103 --fail-under=7.0

# Возвращаем код выхода
exit $?

