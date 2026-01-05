import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    log_dir: Path,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure and return a module-level logger.

    Parameters
    ----------
    name:
        Logger identifier (namespace).
    log_dir:
        Directory where log files should be stored.
    level:
        Logging level (default logging.INFO).
    max_bytes:
        Maximum size per log file before rotation.
    backup_count:
        Number of rotated log files to keep.
    """

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def get_logger(name: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Return a configured logger. Falls back to a default logger when log_dir
    is not provided.
    """

    if log_dir is None:
        return logging.getLogger(name)
    return setup_logger(name=name, log_dir=log_dir)

