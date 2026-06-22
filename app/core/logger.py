import sys
from loguru import logger
from app.core.config import settings

# Remove default handler
logger.remove()

# Add console handler
logger.add(sys.stderr, level=settings.LOG_LEVEL)

# Add file handler
logger.add("logs/app.log", rotation="10 MB", level=settings.LOG_LEVEL, encoding="utf-8")
