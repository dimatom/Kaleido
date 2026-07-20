import logging
import os
import sys
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIGURED = False

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} - "
    "{message}"
)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logging_dir = os.path.dirname(logging.__file__)
        frame = logging.currentframe()
        depth = 0
        while frame:
            filename = frame.f_code.co_filename
            if filename == __file__ or filename.startswith(logging_dir):
                frame = frame.f_back
                depth += 1
                continue
            break

        if frame is None:
            depth = 2

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logger(base_dir=PROJECT_ROOT):
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(base_dir) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stdout, level="INFO", format=CONSOLE_FORMAT, colorize=True, enqueue=True)
    logger.add(
        log_dir / "{time:YYYY-MM-DD}.log",
        level="INFO",
        format=FILE_FORMAT,
        rotation="00:00",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    _CONFIGURED = True


setup_logger()
