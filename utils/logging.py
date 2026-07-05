from loguru import logger


logger.add(
    "logs/FNO-Radar.log",
    rotation="10 MB",
    retention="7 days",
    backtrace=True,
    diagnose=False,
    enqueue=True,
)

__all__ = ["logger"]

