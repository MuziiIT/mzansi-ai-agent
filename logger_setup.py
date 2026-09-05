"""
logger_setup.py — one place to configure logging for the whole pipeline.
Writes to both the console (same as your print() output today) AND a
persistent log file, so an overnight unattended run leaves a record you
can actually check the next morning instead of relying on a terminal
window that's long since closed.
"""

import logging
import os

from config import LOG_DIR, LOG_LEVEL

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("mzansi_pipeline")