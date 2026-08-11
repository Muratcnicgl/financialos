"""
OTURUM İPTALİ — bir kullanıcının TÜM token'larını anında geçersiz kılar.  # BUG #291

Ne zaman kullanılır: bir kullanıcının access/refresh token'ı sızdıysa (ekran görüntüsü,
sohbete yapıştırma, paylaşılan cihaz, kayıp telefon).

NASIL ÇALIŞIR: `users.token_version` artırılır. Her token payload'ında `tv` claim'i vardır
(BUG #172) ve `token_version_ok()` her istekte bunu kullanıcının güncel değeriyle
karşılaştırır. Sayaç artınca **o kullanıcıya ait ÜRETİLMİŞ HER TOKEN** (access, refresh ve
şifre sıfırlama — BUG #225) tek hamlede geçersiz olur.

NEDEN "token'ı kara listeye al" DEĞİL: kara liste, elinizde token'ın kendisi varsa çalışır.
Sızıntıda genellikle kaç kopya çıktığı bilinmez ve JWT durumsuzdur. Sayaç yaklaşımı
**bilinmeyen sayıda kopyayı** aynı anda öldürür — asimetri doğru tarafta.

BEDELİ (yazılı olsun): kullanıcı **yeniden giriş yapmak zorunda kalır**. Sızıntıda bu
kabul edilebilir; rutin işlem değildir.

Kullanım:
    python -m scripts.oturum_iptal --user-id 3
    python -m scripts.oturum_iptal --email birisi@example.com
    python -m scripts.oturum_iptal --user-id 3 --uygula     # gerçekten yaz

`--uygula` verilmezse yalnız ne olacağını gösterir (kuru koşum).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kullanıcının tüm oturumlarını iptal et")
    ap.add_argument("--user-id", type=int, default=None)
    ap.add_argument("--email", default=None)
    ap.add_argument("--uygula", action="store_true", help="Gerçekten yaz (yoksa kuru koşum)")
    a = ap.parse_args(argv)

    if not a.user_id and not a.email:
        print("HATA: --user-id ya da --email verin")
        return 2

    db = SessionLocal()
    try:
        q = db.query(User)
        kullanici = (q.filter(User.id == a.user_id).first() if a.user_id
                     else q.filter(User.email == a.email.lower().strip()).first())
        if kullanici is None:
            print("HATA: kullanıcı bulunamadı")
            return 1

        eski = int(kullanici.token_version or 0)
        # E-posta MASKELENİR: bu çıktı ekran görüntüsüyle paylaşılabilir (BUG #180 ruhu).
        eposta = kullanici.email or ""
        maskeli = (eposta[:2] + "***@" + eposta.split("@")[-1]) if "@" in eposta else "(yok)"
        print(f"Kullanıcı : id={kullanici.id}  {maskeli}")
        print(f"token_version : {eski} -> {eski + 1}")
        print()
        print("Etkisi: bu kullanıcının ÜRETİLMİŞ TÜM token'ları (access + refresh +")
        print("        şifre sıfırlama) anında geçersiz olur. Yeniden giriş yapması gerekir.")

        if not a.uygula:
            print()
            print("KURU KOŞUM — hiçbir şey yazılmadı. Uygulamak için: --uygula")
            return 0

        kullanici.token_version = eski + 1
        db.commit()
        print()
        print(f"UYGULANDI. Yeni token_version: {kullanici.token_version}")
        print("Kullanıcıya HABER VER — 'çıkış yaptın' uyarısı almadan tekrar girmeye")
        print("çalışacak ve neden olduğunu bilmeyecek.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
