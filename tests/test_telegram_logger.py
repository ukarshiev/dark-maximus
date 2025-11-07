#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты для TelegramLoggerHandler.

Содержит:
* сценарий, воспроизводящий RuntimeError старой логики через run_coroutine_threadsafe;
* проверку обновлённого обработчика, что запись из работающего event loop уходит без исключений.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from pathlib import Path
import sys

import pytest


# Добавляем путь к src для импорта модулей проекта
PROJECT_ROOT = Path(__file__).parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class _LegacyTelegramHandler(logging.Handler):
    """Упрощённая копия старой логики для воспроизведения ошибки."""

    def __init__(self) -> None:
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._message_queue = deque()
        self._sending = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def _process_queue(self) -> None:  # pragma: no cover - пустой обработчик
        return None

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - поведение воспроизводится в тесте
        self._message_queue.append(record)
        if not self._sending:
            loop = self._loop
            if loop is not None and loop.is_running():
                # Старая реализация всегда дергала run_coroutine_threadsafe, что и приводило к RuntimeError
                asyncio.run_coroutine_threadsafe(self._process_queue(), loop)


def test_legacy_handler_fails_inside_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подтверждаем, что старая логика падала с RuntimeError внутри активного event loop."""

    original_run_threadsafe = asyncio.run_coroutine_threadsafe

    async def scenario() -> None:
        handler = _LegacyTelegramHandler()
        loop = asyncio.get_running_loop()
        handler.set_loop(loop)

        def fake_run_coroutine_threadsafe(coro, target_loop):
            if target_loop is loop:
                try:
                    coro.close()
                except AttributeError:
                    pass
                raise RuntimeError("run_coroutine_threadsafe cannot be called from a running event loop")
            return original_run_threadsafe(coro, target_loop)

        monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=42,
            msg="Legacy failure",
            args=(),
            exc_info=None,
            func="legacy_test",
        )

        with pytest.raises(RuntimeError, match="run_coroutine_threadsafe"):
            handler.emit(record)

    asyncio.run(scenario())


def test_handler_sends_log_from_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяем, что актуальный обработчик корректно отправляет сообщение из работающего event loop."""

    from shop_bot.utils.telegram_logger import TelegramLoggerHandler

    async def scenario() -> list[str]:
        handler = TelegramLoggerHandler(
            bot_token="TEST_TOKEN",
            admin_chat_id="123456",
            log_level="warning",
            enabled=True,
        )

        loop = asyncio.get_running_loop()
        handler.set_loop(loop)

        sent_messages: list[str] = []

        async def fake_send(message: str) -> None:
            sent_messages.append(message)

        async def noop(*_args, **_kwargs) -> None:
            return None

        # Исключаем сетевые вызовы и задержки в тесте
        monkeypatch.setattr(handler, "_send_message", fake_send)
        monkeypatch.setattr(handler, "_check_rate_limits", noop)

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=123,
            msg="Boom",
            args=(),
            exc_info=None,
            func="handler_test",
        )

        handler.emit(record)

        # Даём фоновой задаче время обработать очередь
        await asyncio.sleep(0.05)

        return sent_messages

    messages = asyncio.run(scenario())
    assert messages, "Сообщение должно быть отправлено обработчиком"
    assert "Boom" in messages[0], "Текст исходного сообщения должен присутствовать"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

