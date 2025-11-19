#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля валидации входных данных

Тестирует валидацию и санитизацию входных данных
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.security.validators import InputValidator, ValidationError


@pytest.mark.unit
@allure.epic("Безопасность")
@allure.feature("Валидация входных данных")
@allure.label("package", "src.shop_bot.security")
class TestInputValidator:
    """Тесты для валидации входных данных"""

    @allure.title("Успешная валидация обязательного поля")
    @allure.description("Проверяет успешную валидацию обязательного поля через validate_required. **Что проверяется:** возврат значения при валидном входном значении. **Тестовые данные:** value='test_value', field_name='test_field'. **Ожидаемый результат:** функция возвращает 'test_value' без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "required", "unit")
    def test_validate_required_success(self):
        result = InputValidator.validate_required("test_value", "test_field")
        assert result == "test_value"

    @allure.title("Валидация обязательного поля со значением None")
    @allure.description("Проверяет валидацию обязательного поля со значением None через validate_required. **Что проверяется:** вызов ValidationError при None значении. **Тестовые данные:** value=None, field_name='test_field'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'обязательно для заполнения'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "required", "error_handling", "unit")
    def test_validate_required_none(self):
        with pytest.raises(ValidationError, match="обязательно для заполнения"):
            InputValidator.validate_required(None, "test_field")

    @allure.title("Валидация обязательного поля с пустой строкой")
    @allure.description("Проверяет валидацию обязательного поля с пустой строкой через validate_required. **Что проверяется:** вызов ValidationError при пустой строке. **Тестовые данные:** value='', field_name='test_field'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'обязательно для заполнения'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "required", "error_handling", "unit")
    def test_validate_required_empty_string(self):
        with pytest.raises(ValidationError, match="обязательно для заполнения"):
            InputValidator.validate_required("", "test_field")

    @allure.title("Валидация обязательного поля со строкой из пробелов")
    @allure.description("Проверяет валидацию обязательного поля со строкой из пробелов через validate_required. **Что проверяется:** вызов ValidationError при строке из пробелов. **Тестовые данные:** value='   ', field_name='test_field'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'обязательно для заполнения'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "required", "error_handling", "unit")
    def test_validate_required_whitespace_string(self):
        with pytest.raises(ValidationError, match="обязательно для заполнения"):
            InputValidator.validate_required("   ", "test_field")

    @allure.title("Успешная валидация строки")
    @allure.description("Проверяет успешную валидацию строки через validate_string. **Что проверяется:** возврат валидной строки. **Тестовые данные:** value='test', field_name='test_field'. **Ожидаемый результат:** функция возвращает 'test' без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "string", "unit")
    def test_validate_string_success(self):
        result = InputValidator.validate_string("test", "test_field")
        assert result == "test"

    @allure.title("Валидация не-строки")
    @allure.description("Проверяет валидацию не-строки через validate_string. **Что проверяется:** вызов ValidationError при не-строковом значении. **Тестовые данные:** value=123, field_name='test_field'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'должно быть строкой'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "string", "error_handling", "unit")
    def test_validate_string_not_string(self):
        with pytest.raises(ValidationError, match="должно быть строкой"):
            InputValidator.validate_string(123, "test_field")

    @allure.title("Валидация слишком короткой строки")
    @allure.description("Проверяет валидацию слишком короткой строки через validate_string. **Что проверяется:** вызов ValidationError при строке короче min_length. **Тестовые данные:** value='', field_name='test_field', min_length=5. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'минимум'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "string", "error_handling", "unit")
    def test_validate_string_too_short(self):
        with pytest.raises(ValidationError, match="минимум"):
            InputValidator.validate_string("", "test_field", min_length=5)

    @allure.title("Валидация слишком длинной строки")
    @allure.description("Проверяет валидацию слишком длинной строки через validate_string. **Что проверяется:** вызов ValidationError при строке длиннее max_length. **Тестовые данные:** value='a'*300, field_name='test_field', max_length=255. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'превышать'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "string", "error_handling", "unit")
    def test_validate_string_too_long(self):
        long_string = "a" * 300
        with pytest.raises(ValidationError, match="превышать"):
            InputValidator.validate_string(long_string, "test_field", max_length=255)

    @allure.title("Валидация строки убирает пробелы")
    @allure.description("Проверяет, что валидация строки убирает пробелы через validate_string. **Что проверяется:** удаление пробелов в начале и конце строки. **Тестовые данные:** value='  test  ', field_name='test_field'. **Ожидаемый результат:** функция возвращает 'test' (без пробелов).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "string", "sanitization", "unit")
    def test_validate_string_strips_whitespace(self):
        result = InputValidator.validate_string("  test  ", "test_field")
        assert result == "test"

    @allure.title("Успешная валидация целого числа")
    @allure.description("Проверяет успешную валидацию целого числа через validate_integer. **Что проверяется:** возврат валидного целого числа. **Тестовые данные:** value=123, field_name='test_field'. **Ожидаемый результат:** функция возвращает 123 без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "unit")
    def test_validate_integer_success(self):
        result = InputValidator.validate_integer(123, "test_field")
        assert result == 123

    @allure.title("Валидация целого числа из строки")
    @allure.description("Проверяет валидацию целого числа из строки через validate_integer. **Что проверяется:** конвертация строки в целое число. **Тестовые данные:** value='123', field_name='test_field'. **Ожидаемый результат:** функция возвращает 123 (целое число).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "unit")
    def test_validate_integer_from_string(self):
        result = InputValidator.validate_integer("123", "test_field")
        assert result == 123

    @allure.title("Валидация невалидного целого числа")
    @allure.description("Проверяет валидацию невалидного целого числа через validate_integer. **Что проверяется:** вызов ValidationError при невалидном значении. **Тестовые данные:** value='abc', field_name='test_field'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'целым числом'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "error_handling", "unit")
    def test_validate_integer_invalid(self):
        with pytest.raises(ValidationError, match="целым числом"):
            InputValidator.validate_integer("abc", "test_field")

    @allure.title("Валидация числа меньше минимума")
    @allure.description("Проверяет валидацию числа меньше минимума через validate_integer. **Что проверяется:** вызов ValidationError при числе меньше min_value. **Тестовые данные:** value=5, field_name='test_field', min_value=10. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'не должно быть меньше'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "error_handling", "unit")
    def test_validate_integer_too_small(self):
        with pytest.raises(ValidationError, match="не должно быть меньше"):
            InputValidator.validate_integer(5, "test_field", min_value=10)

    @allure.title("Валидация числа больше максимума")
    @allure.description("Проверяет валидацию числа больше максимума через validate_integer. **Что проверяется:** вызов ValidationError при числе больше max_value. **Тестовые данные:** value=150, field_name='test_field', max_value=100. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'не должно быть больше'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "error_handling", "unit")
    def test_validate_integer_too_large(self):
        with pytest.raises(ValidationError, match="не должно быть больше"):
            InputValidator.validate_integer(150, "test_field", max_value=100)

    @allure.title("Валидация пустой строки как 0")
    @allure.description("Проверяет валидацию пустой строки как 0 через validate_integer. **Что проверяется:** конвертация пустой строки в 0. **Тестовые данные:** value='', field_name='test_field'. **Ожидаемый результат:** функция возвращает 0.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "integer", "unit")
    def test_validate_integer_empty_string(self):
        result = InputValidator.validate_integer("", "test_field")
        assert result == 0

    @allure.title("Успешная валидация email")
    @allure.description("Проверяет успешную валидацию email через validate_email. **Что проверяется:** возврат валидного email. **Тестовые данные:** value='test@example.com', field_name='email'. **Ожидаемый результат:** функция возвращает 'test@example.com' без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "email", "unit")
    def test_validate_email_success(self):
        result = InputValidator.validate_email("test@example.com", "email")
        assert result == "test@example.com"

    @allure.title("Валидация невалидного email")
    @allure.description("Проверяет валидацию невалидного email через validate_email. **Что проверяется:** вызов ValidationError при невалидном email. **Тестовые данные:** value='invalid_email', field_name='email'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'корректный email'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "email", "error_handling", "unit")
    def test_validate_email_invalid(self):
        with pytest.raises(ValidationError, match="корректный email"):
            InputValidator.validate_email("invalid_email", "email")

    @allure.title("Успешная валидация имени пользователя")
    @allure.description("Проверяет успешную валидацию имени пользователя через validate_username. **Что проверяется:** возврат валидного username. **Тестовые данные:** value='test_user123', field_name='username'. **Ожидаемый результат:** функция возвращает 'test_user123' без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "username", "unit")
    def test_validate_username_success(self):
        result = InputValidator.validate_username("test_user123", "username")
        assert result == "test_user123"

    @allure.title("Валидация имени пользователя с недопустимыми символами")
    @allure.description("Проверяет валидацию имени пользователя с недопустимыми символами через validate_username. **Что проверяется:** вызов ValidationError при недопустимых символах. **Тестовые данные:** value='test@user', field_name='username'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'только буквы, цифры'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "username", "error_handling", "unit")
    def test_validate_username_invalid_chars(self):
        with pytest.raises(ValidationError, match="только буквы, цифры"):
            InputValidator.validate_username("test@user", "username")

    @allure.title("Успешная валидация Telegram ID")
    @allure.description("Проверяет успешную валидацию Telegram ID через validate_telegram_id. **Что проверяется:** возврат валидного telegram_id. **Тестовые данные:** value=123456789, field_name='telegram_id'. **Ожидаемый результат:** функция возвращает 123456789 без ошибок.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "telegram_id", "unit")
    def test_validate_telegram_id_success(self):
        result = InputValidator.validate_telegram_id(123456789, "telegram_id")
        assert result == 123456789

    @allure.title("Валидация отрицательного Telegram ID")
    @allure.description("Проверяет валидацию отрицательного Telegram ID через validate_telegram_id. **Что проверяется:** вызов ValidationError при отрицательном значении. **Тестовые данные:** value=-1, field_name='telegram_id'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'положительным числом'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "telegram_id", "error_handling", "unit")
    def test_validate_telegram_id_negative(self):
        with pytest.raises(ValidationError, match="положительным числом"):
            InputValidator.validate_telegram_id(-1, "telegram_id")

    @allure.title("Валидация нулевого Telegram ID")
    @allure.description("Проверяет валидацию нулевого Telegram ID через validate_telegram_id. **Что проверяется:** вызов ValidationError при нулевом значении. **Тестовые данные:** value=0, field_name='telegram_id'. **Ожидаемый результат:** функция вызывает ValidationError с сообщением 'положительным числом'.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "telegram_id", "error_handling", "unit")
    def test_validate_telegram_id_zero(self):
        with pytest.raises(ValidationError, match="положительным числом"):
            InputValidator.validate_telegram_id(0, "telegram_id")


@pytest.mark.unit
@allure.epic("Безопасность")
@allure.feature("Валидация входных данных")
@allure.label("package", "src.shop_bot.security")
class TestSanitizeString:
    """Тесты для санитизации строк"""

    @allure.title("Санитизация чистой строки")
    @allure.description("Проверяет санитизацию чистой строки через sanitize_string. **Что проверяется:** возврат строки без изменений для чистой строки. **Тестовые данные:** value='clean_string'. **Ожидаемый результат:** функция возвращает 'clean_string' без изменений.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "sanitize", "unit")
    def test_sanitize_string_clean(self):
        """Тест санитизации чистой строки"""
        result = InputValidator.sanitize_string("clean_string")
        assert result == "clean_string"

    @allure.title("Удаление HTML тегов при санитизации")
    @allure.description("Проверяет удаление HTML тегов при санитизации через sanitize_string. **Что проверяется:** удаление HTML тегов из строки. **Тестовые данные:** value='<b>test</b>'. **Ожидаемый результат:** функция возвращает 'test' (без HTML тегов).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "sanitize", "html", "unit")
    def test_sanitize_string_html_tags(self):
        result = InputValidator.sanitize_string("<b>test</b>")
        assert result == "test"

    @allure.title("Удаление опасных символов при санитизации")
    @allure.description("Проверяет удаление опасных символов при санитизации через sanitize_string. **Что проверяется:** удаление HTML тегов и опасных символов (<script>, кавычки). **Тестовые данные:** value='test<script>alert(\"xss\")</script>'. **Ожидаемый результат:** функция возвращает 'testalert(xss)' (без HTML тегов и кавычек).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "sanitize", "security", "unit")
    def test_sanitize_string_dangerous_chars(self):
        result = InputValidator.sanitize_string('test<script>alert("xss")</script>')
        # Функция удаляет HTML теги и символы <>"', но не удаляет скобки
        # Ожидаем: HTML теги <script> и </script> удалены, кавычки удалены, скобки остаются
        assert result == "testalert(xss)"

    @allure.title("Удаление пробелов при санитизации")
    @allure.description("Проверяет удаление пробелов при санитизации через sanitize_string. **Что проверяется:** удаление пробелов в начале и конце строки. **Тестовые данные:** value='  test  '. **Ожидаемый результат:** функция возвращает 'test' (без пробелов).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "sanitize", "unit")
    def test_sanitize_string_strips_whitespace(self):
        result = InputValidator.sanitize_string("  test  ")
        assert result == "test"

    @allure.title("Санитизация не-строки")
    @allure.description("Проверяет санитизацию не-строки через sanitize_string. **Что проверяется:** конвертация не-строкового значения в строку. **Тестовые данные:** value=123. **Ожидаемый результат:** функция возвращает '123' (конвертировано в строку).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "sanitize", "unit")
    def test_sanitize_string_not_string(self):
        result = InputValidator.sanitize_string(123)
        assert result == "123"


@pytest.mark.unit
@allure.epic("Безопасность")
@allure.feature("Валидация входных данных")
@allure.label("package", "src.shop_bot.security")
class TestValidateHtmlTags:
    """Тесты для валидации HTML тегов"""

    @allure.title("Валидация валидных HTML тегов")
    @allure.description("Проверяет валидацию валидных HTML тегов через validate_html_tags. **Что проверяется:** возврат is_valid=True для валидных тегов. **Тестовые данные:** text='<b>bold</b> <i>italic</i>'. **Ожидаемый результат:** функция возвращает (True, []) - валидные теги, ошибок нет.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "unit")
    def test_validate_html_tags_valid(self):
        """Тест валидации валидных HTML тегов"""
        text = "<b>bold</b> <i>italic</i>"
        is_valid, errors = InputValidator.validate_html_tags(text)
        assert is_valid is True
        assert len(errors) == 0

    @allure.title("Валидация незакрытого HTML тега")
    @allure.description("Проверяет валидацию незакрытого HTML тега через validate_html_tags. **Что проверяется:** возврат is_valid=False для незакрытого тега. **Тестовые данные:** text='<b>bold text'. **Ожидаемый результат:** функция возвращает (False, errors) - незакрытый тег, есть ошибки.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "error_handling", "unit")
    def test_validate_html_tags_unclosed_tag(self):
        text = "<b>bold text"
        is_valid, errors = InputValidator.validate_html_tags(text)
        assert is_valid is False
        assert len(errors) > 0

    @allure.title("Валидация HTML тегов в неправильном порядке")
    @allure.description("Проверяет валидацию HTML тегов в неправильном порядке через validate_html_tags. **Что проверяется:** возврат is_valid=False для тегов в неправильном порядке. **Тестовые данные:** text='<b><i>text</b></i>'. **Ожидаемый результат:** функция возвращает (False, errors) - неправильный порядок тегов, есть ошибки.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "error_handling", "unit")
    def test_validate_html_tags_wrong_order(self):
        text = "<b><i>text</b></i>"
        is_valid, errors = InputValidator.validate_html_tags(text)
        assert is_valid is False
        assert len(errors) > 0

    @allure.title("Валидация HTML тегов внутри code блока")
    @allure.description("Проверяет валидацию HTML тегов внутри code блока через validate_html_tags. **Что проверяется:** игнорирование тегов внутри <code> блока. **Тестовые данные:** text='<code><b>bold</b></code>'. **Ожидаемый результат:** функция возвращает (True, []) - теги внутри code игнорируются, валидация успешна.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "code_block", "unit")
    def test_validate_html_tags_code_block(self):
        text = "<code><b>bold</b></code>"
        is_valid, errors = InputValidator.validate_html_tags(text)
        # Теги внутри code игнорируются
        assert is_valid is True

    @allure.title("Валидация HTML тегов внутри pre блока")
    @allure.description("Проверяет валидацию HTML тегов внутри pre блока через validate_html_tags. **Что проверяется:** игнорирование тегов внутри <pre> блока. **Тестовые данные:** text='<pre><b>bold</b></pre>'. **Ожидаемый результат:** функция возвращает (True, []) - теги внутри pre игнорируются, валидация успешна.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "pre_block", "unit")
    def test_validate_html_tags_pre_block(self):
        text = "<pre><b>bold</b></pre>"
        is_valid, errors = InputValidator.validate_html_tags(text)
        # Теги внутри pre игнорируются
        assert is_valid is True

    @allure.title("Валидация HTML тегов в пустой строке")
    @allure.description("Проверяет валидацию HTML тегов в пустой строке через validate_html_tags. **Что проверяется:** возврат is_valid=True для пустой строки. **Тестовые данные:** text=''. **Ожидаемый результат:** функция возвращает (True, []) - пустая строка валидна, ошибок нет.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "unit")
    def test_validate_html_tags_empty_string(self):
        is_valid, errors = InputValidator.validate_html_tags("")
        assert is_valid is True
        assert len(errors) == 0

    @allure.title("Валидация HTML тегов в не-строке")
    @allure.description("Проверяет валидацию HTML тегов в не-строке через validate_html_tags. **Что проверяется:** обработка не-строкового значения. **Тестовые данные:** text=123. **Ожидаемый результат:** функция возвращает (True, []) - не-строковое значение обработано, ошибок нет.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "unit")
    def test_validate_html_tags_not_string(self):
        is_valid, errors = InputValidator.validate_html_tags(123)
        assert is_valid is True
        assert len(errors) == 0

    @allure.title("Игнорирование <br> тегов валидатором")
    @allure.description("Проверяет, что <br> теги игнорируются валидатором через validate_html_tags. **Что проверяется:** игнорирование <br> тегов (не валидируются). **Тестовые данные:** text='<b>Текст</b><br>Строка 2'. **Ожидаемый результат:** функция возвращает (True, []) - <br> теги игнорируются, валидация успешна.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "br_tag", "unit")
    def test_validate_html_tags_br_tag_ignored(self):
        # Валидатор игнорирует невалидные теги, включая <br>
        # Это нормально, так как замена <br> происходит в get_message_text
        text = "<b>Текст</b><br>Строка 2"
        is_valid, errors = InputValidator.validate_html_tags(text)
        # Валидатор игнорирует <br>, поэтому текст считается валидным
        # Но это не проблема, так как <br> заменяется на \n в get_message_text
        assert is_valid is True
        assert len(errors) == 0

    @allure.title("Игнорирование невалидных тегов валидатором")
    @allure.description("Проверяет, что невалидные теги (не из списка поддерживаемых) игнорируются валидатором через validate_html_tags. **Что проверяется:** игнорирование тегов, которых нет в списке valid_tags. **Тестовые данные:** text='<b>Текст</b><unknown_tag>Неизвестный тег</unknown_tag>'. **Ожидаемый результат:** функция возвращает (True, []) - неизвестные теги игнорируются, валидация успешна.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("validators", "html_tags", "invalid_tags", "unit")
    def test_validate_html_tags_invalid_tags_ignored(self):
        # Валидатор игнорирует теги, которых нет в списке valid_tags
        text = "<b>Текст</b><unknown_tag>Неизвестный тег</unknown_tag>"
        is_valid, errors = InputValidator.validate_html_tags(text)
        # Неизвестные теги игнорируются, поэтому текст валиден
        assert is_valid is True
        assert len(errors) == 0

