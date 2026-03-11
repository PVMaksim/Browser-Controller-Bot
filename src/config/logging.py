# src/config/logging.py
"""
Structured logging configuration via loguru.
Вывод в stdout (real-time наблюдение) и в ротируемый файл.
"""

import sys

from loguru import logger

from src.config.constants import (
    LOG_COMPRESSION,
    LOG_RETENTION_DAYS,
    LOG_ROTATION_SIZE,
)
from src.config.paths import get_log_dir


def setup_logging(level: str = "INFO") -> None:
    """
    Configure loguru: stdout handler + rotating file handler.
    Вызывается один раз при старте приложения до создания бота.
    """
    # Убираем дефолтный loguru-хендлер
    logger.remove()

    # Stdout — наблюдение в реальном времени
    logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
    )

    # Файл — полная история с ротацией и архивированием
    log_dir = get_log_dir()
    logger.add(
        log_dir / "bot.log",
        rotation=LOG_ROTATION_SIZE,
        retention=LOG_RETENTION_DAYS,
        compression=LOG_COMPRESSION,
        level="DEBUG",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
    )

    logger.info(f"Logging configured. Level: {level}. Log dir: {log_dir}")
