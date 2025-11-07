"""Вспомогательные функции для настройки кодировки stdout/stderr в тестах.

Избегаем прямой замены `sys.stdout`/`sys.stderr` на новые обёртки, так как
это может приводить к преждевременному закрытию файлов захвата pytest
(`ValueError: I/O operation on closed file`).

Вместо этого используем `reconfigure`, если он доступен, и только в крайних
случаях создаём новую обёртку.
"""

from __future__ import annotations

import io
import sys
from typing import TextIO


def _configure_stream(stream: TextIO) -> TextIO:
    """Гарантирует UTF-8 кодировку для указанного потока.

    Если поток поддерживает метод ``reconfigure`` (начиная с Python 3.7),
    используем его, чтобы не создавать новую обёртку и не закрывать файл
    при сборке мусора. В противном случае, при наличии ``buffer`` создаём
    ``TextIOWrapper`` с нужной кодировкой.
    """

    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream

    # Начиная с Python 3.13, создание новой обёртки вокруг ``stream.buffer``
    # приводит к преждевременному закрытию исходного файла при сборке
    # мусора (``pytest`` теряет файловый дескриптор и падает с
    # ``ValueError: I/O operation on closed file``). Поэтому в случае,
    # когда ``reconfigure`` недоступен, оставляем поток как есть.

    return stream


def ensure_utf8_output() -> None:
    """Переводит stdout/stderr в UTF-8 на Windows."""

    sys.stdout = _configure_stream(sys.stdout)
    sys.stderr = _configure_stream(sys.stderr)

