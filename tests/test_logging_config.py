"""M23 — logging_config: rotating file handler + config."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.logging_config import setup_logging, JsonFormatter


def test_setup_rotating_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ROTATION_MAX_MB", "7")
    monkeypatch.setenv("LOG_ROTATION_BACKUP", "3")
    monkeypatch.setenv("ENVIRONMENT", "development")
    active = setup_logging()
    assert active is not None and active.exists()
    fhs = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert fhs, "RotatingFileHandler eklenmeli"
    assert fhs[0].maxBytes == 7 * 1024 * 1024 and fhs[0].backupCount == 3
    logging.getLogger("test").info("m23 log satiri")
    assert (active / "financialos.log").exists()


def test_json_formatter_production(monkeypatch):
    import json
    rec = logging.LogRecord("l", logging.INFO, __file__, 1, "merhaba", (), None)
    out = JsonFormatter().format(rec)
    parsed = json.loads(out)
    assert parsed["level"] == "INFO" and parsed["msg"] == "merhaba" and "ts" in parsed


def test_fail_safe_console_only(tmp_path, monkeypatch):
    # Geçersiz dizin (dosya olarak var) → mkdir OSError → yalnız console, patlamaz
    bad = tmp_path / "afile"
    bad.write_text("x")
    monkeypatch.setenv("LOG_DIR", str(bad / "sub"))  # bad bir dosya → mkdir hata
    active = setup_logging()
    # active None olabilir ama exception atmamalı
    assert active is None or active.exists()
