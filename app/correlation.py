"""
Korelasyon kimliği — TEK KAYNAK (B3 / BUG #280, kapalı beta).

Sorun: kapalı betada davetli "bir şeyler patladı" der; operatörün elinde o ANI bulacak
hiçbir tutamak yoktur. Log dosyasında binlerce satır, `error_logs`'ta parmak-izine göre
BİRLEŞTİRİLMİŞ kayıtlar (aynı hata tek satır, sayaç artar) ve kullanıcıda yalnız
"Beklenmedik bir hata oluştu." cümlesi vardır. Yani sistem hatayı KAYDEDİYOR ama
kullanıcının gördüğü olayla kaydı EŞLEŞTİREMİYOR — "spesifik debug" isteğinin eksik
halkası tam burasıdır.

Sözleşme (tek cümle): **bir isteğin kimliği; log satırında, hata yanıtında ve kullanıcıya
gösterilen ekranda AYNIDIR.**

Tasarım kararları ve gerekçeleri:

1. **Vekilin kimliği DEVRALINIR, yoksa üretilir.** Cloudflare Tunnel/nginx arkasında istek
   zaten bir kimlikle gelir (`X-Request-Id`, Cloudflare'da `Cf-Ray`). Kendi kimliğimizi
   dayatmak, kenardaki kaydı bizimkinden KOPARIR ve iki ayrı iz üretir. Devralınan kimlik
   `alinan` olarak işaretlenir; hangi tarafın ürettiği log'da görünür.
2. **Devralınan değer TEMİZLENİR.** Gelen başlık dışarıdan gelir: uzunluk sınırlanır ve
   yalnız güvenli karakterler kabul edilir. Aksi hâlde başlık, log satırına enjeksiyon
   yüzeyi olur (ADR-045'in log tarafındaki karşılığı).
3. **Kimlik SIR TAŞIMAZ ve tahmin edilebilir DEĞİLDİR.** `secrets` ile üretilir; sayaç ya
   da zaman damgası kullanılmaz (sıralı kimlik, trafik hacmini sızdırır).
4. **Kısa ve okunur.** Kullanıcı bunu ekrandan okuyup yazacak; 8 karakter, karışan harf
   yok (0/O, 1/l elenmiş). Çarpışma bu ölçekte (kapalı beta) sorun değil, üstelik log
   satırı zaman damgası da taşır.
5. **ContextVar** kullanılır: aynı isteğin farklı katmanlarındaki (router, servis, hata
   yakalayıcı) kod, kimliği parametre olarak TAŞIMADAN okur. Parametre olarak taşımak,
   bir gün bir çağrıda unutulur ve zincir sessizce kopar (L42 sınıfı).
"""
from __future__ import annotations

import contextvars
import re
import secrets

# Karışan karakterler elendi: 0/O, 1/l/I. Kullanıcı telefondan okuyup yazacak.
_ALFABE = "23456789abcdefghjkmnpqrstuvwxyz"
_UZUNLUK = 8

# Dışarıdan gelen kimlik: yalnız güvenli karakterler, sınırlı uzunluk (log enjeksiyonu yok).
_GUVENLI = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

# İstek başına kimlik. Varsayılan "-": kimlik kurulmadan loglanan satır (açılış, cron)
# boş görünmesin; "kimlik yok" ile "kimlik boş" aynı hücreye yazılmaz (L45 ruhu).
istek_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("istek_id", default="-")


def yeni_id() -> str:
    """Tahmin edilemez, kısa, okunur korelasyon kimliği."""
    return "".join(secrets.choice(_ALFABE) for _ in range(_UZUNLUK))


def gelen_id_temizle(ham: str | None) -> str | None:
    """Vekilden gelen kimliği doğrula; kabul edilemezse None (o zaman kendimiz üretiriz)."""
    if not ham:
        return None
    aday = ham.strip()
    if not _GUVENLI.match(aday):
        return None
    return aday


def istek_id() -> str:
    """Bu isteğin kimliği. İstek bağlamı dışında '-' döner."""
    return istek_id_var.get()


def ayarla(deger: str):
    """Bağlama kimliği yazar; `contextvars.Token` döner (geri almak isteyen için)."""
    return istek_id_var.set(deger)


class IstekIdFiltresi:
    """Her log kaydına `istek_id` ekler.

    `logging.Filter` alt sınıfı yerine ördek-tipi: filtre yalnız `filter(record)` çağrılır.
    Ekleme HER kayda yapılır — eksik alan, formatter'da `KeyError` üretir ve o zaman
    hatanın kendisi log'u susturur (gözlemlenebilirlik aracının kendini vurması).
    """

    def filter(self, record) -> bool:  # noqa: A003 — logging API'si bu adı şart koşar
        record.istek_id = istek_id_var.get()
        return True
