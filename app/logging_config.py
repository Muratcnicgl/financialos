"""
M23 (OBS) — Merkezi logging: console + RotatingFileHandler + kalıcı config.

logs/financialos.log (10MB × 5 backup). Format: production'da JSON (structured, log
toplama dostu), development'ta okunur text. Env: LOG_LEVEL, LOG_DIR, LOG_ROTATION_MAX_MB,
LOG_ROTATION_BACKUP. Dosya yazılamazsa (izin/read-only) fail-safe → yalnız console.
"""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_TEXT_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Production için structured JSON log satırı."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> Path | None:
    """Root logger'ı yapılandırır (console + rotating file). Log dizinini döndürür (yoksa None)."""
    from app.settings import is_production

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    max_mb = int(os.getenv("LOG_ROTATION_MAX_MB", "10"))
    backups = int(os.getenv("LOG_ROTATION_BACKUP", "5"))
    formatter: logging.Formatter = JsonFormatter() if is_production() else logging.Formatter(_TEXT_FMT)

    handlers: list[logging.Handler] = []
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    handlers.append(console)

    active_dir: Path | None = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "financialos.log",
            maxBytes=max_mb * 1024 * 1024,
            backupCount=backups,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        handlers.append(fh)
        active_dir = log_dir
    except OSError as e:  # read-only/izin → console yeterli (fail-safe)
        console.handle(logging.LogRecord(
            "logging_config", logging.WARNING, __file__, 0,
            "Log dosyası açılamadı (%s) — yalnız console", (e,), None))

    logging.basicConfig(level=level, handlers=handlers, force=True)
    return active_dir
