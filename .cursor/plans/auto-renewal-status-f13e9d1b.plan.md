<!-- f13e9d1b-dd75-4e27-a5d0-2a580ab07334 00da70d7-deda-4546-a529-76913689ce2b -->
# Исправление переменной autorenewalstatus в шаблонах информации о ключе

## Проблема

Переменная `{auto_renewal_status}` не подставляется в шаблоны информации о ключе, потому что:

1. Переменная формируется в `get_key_info_text` (строка 320), но не добавляется в словарь `template_variables` (строки 415-426)
2. Переменная отсутствует в списках разрешённых переменных для шаблонов `key_info_*` в БД

## Решение

### 1. Добавить auto_renewal_status в template_variables

**Файл:** `src/shop_bot/config.py`

- В функции `get_key_info_text` добавить `'auto_renewal_status': auto_renewal_status` в словарь `template_variables` (после строки 425)

### 2. Обновить списки разрешённых переменных в БД

**Файл:** `src/shop_bot/data_manager/database.py`

- Добавить `"auto_renewal_status"` в списки разрешённых переменных для всех шаблонов `key_info_*`:
- `key_info_key` (строка 2525)
- `key_info_subscription` (строка 2529)
- `key_info_both` (строка 2533)
- `key_info_cabinet` (строка 2537)
- `key_info_cabinet_subscription` (строка 2541)

## Файлы для изменения

- `src/shop_bot/config.py` - добавление переменной в template_variables
- `src/shop_bot/data_manager/database.py` - обновление списков разрешённых переменных для шаблонов

### To-dos

- [ ] Добавить 'auto_renewal_status': auto_renewal_status в словарь template_variables в функции get_key_info_text (config.py)
- [ ] Добавить 'auto_renewal_status' в списки разрешённых переменных для всех шаблонов key_info_* в database.py