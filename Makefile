# Komutların TEK KAYNAĞI scripts/gorev.py'dir (BUG #475 / DEVOPS-014); bu dosya yalnız vekil.
# `make test` → `python -m scripts.gorev test`. Windows'ta make yoksa doğrudan Python komutu.
.DEFAULT:
	python -m scripts.gorev $@

help:
	python -m scripts.gorev
