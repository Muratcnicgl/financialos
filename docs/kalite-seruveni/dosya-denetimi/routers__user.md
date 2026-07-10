# Denetim: app/routers/user.py

### [RUS-001] created_at timezone-naive olarak frontend'e donuyor
- **Sorun:** UserOut.created_at, User.created_at'i (app/models.py:123, Column(DateTime, default=datetime.utcnow) - naive UTC) dogrudan Pydantic'e veriyor. GET/POST/PUT /api/user endpoint'lerinin ucunde tzinfo=timezone.utc eklenmiyor. PROJE.md / docs/architecture.md acikca "Frontend'e tarih yansitan endpoint'lerde serialize oncesi tzinfo=timezone.utc ile aware'e cevrilmeli, aksi halde JS Turkiye saatinde 3 saat geri gosterir" diyor.
- **Kanit:** satir 29 (UserOut.created_at: datetime), satir 48-50 (get_user donusu), satir 66-70 (create_user donusu), satir 78-84 (update_user donusu) - hicbirinde donen user objesi uzerinde created_at.replace(tzinfo=timezone.utc) yapilmiyor.
- **Aksiyon:** get_user/create_user/update_user icinde response donmeden once created_at'i replace(tzinfo=timezone.utc) ile aware yap, veya UserOut icin field_serializer ekleyip merkezi cozum uygula (coach.py'deki _memory_to_history_item pattern'i referans alinabilir).
- **Onem:** Orta · **Guven:** Kesin

### [RUS-002] create_user'da race condition - iki eszamanli POST birden kullanici olusturabilir
- **Sorun:** existing = db.query(User).first() kontrolu ile db.add/commit arasinda es zamanli iki istek gelirse (tek-kullanici MVP'de dusuk olasilik ama kod seviyesinde bir unique constraint/DB kisitlamasi yok), her ikisi de "existing yok" gorup iki User satiri olusturabilir. get_current_user id ASC ile ilkini secer, ikinci kayit sessizce yetim kalir.
- **Kanit:** satir 59-69 - check-then-act pattern, DB'de User.name veya baska bir alan uzerinde UNIQUE constraint yok (app/models.py:118-123).
- **Aksiyon:** Tek-kullanici modelini DB seviyesinde de garanti etmek icin ya id'yi sabit (=1) sec-ya-da-olustur (upsert) pattern'i kullan ya da users tablosunda satir sayisini 1 ile sinirlayan bir constraint/check ekle. Wave-2 MVP kapsaminda dusuk oncelikli ama not edilmeli.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (pratikte tek-kullanici local MVP'de tetiklenme ihtimali cok dusuk)

### [RUS-003] UserUpdate.name bos string'i gecersiz kilmiyor, sadece whitespace-only isim kabul edilebilir
- **Sorun:** Field(None, min_length=1) sadece string uzunlugunun >=1 olmasini garanti eder; " " (sadece bosluk) gibi bir deger min_length kontrolunu gecer, sonra update_user icinde payload.name.strip() ile "" haline gelip DB'ye bos isim olarak yazilir (satir 81). name kolonu nullable=False ama bos string "" bir NULL degildir, bu yuzden DB seviyesinde de yakalanmaz.
- **Kanit:** satir 40 (Field(None, min_length=1, max_length=100)), satir 80-81 (strip sonrasi kontrol yok).
- **Aksiyon:** field_validator ile strip sonrasi bos string kontrolu ekle (Pydantic V2 field_validator kullan, PROJE.md V1 decorator'lari yasakliyor). Ayni sorun UserCreate.name icin de gecerli (satir 36, 66).
- **Onem:** Orta · **Guven:** Kesin

### [RUS-004] UserOut icin from_attributes eski stil Config sinifi ile tanimlanmis
- **Sorun:** class Config: from_attributes = True kullanilmis; bu calisir ama Pydantic V2'nin tercih edilen idiom'u model_config = ConfigDict(from_attributes=True) seklindedir. PROJE.md "Pydantic V2 kullaniliyor - model_config kullan" diyor; bu satir teknik olarak V1 tarzi nested Config class kullanimi (V2'de hala destekleniyor ama deprecated warning uretebilir, proje konvansiyonuna ters).
- **Kanit:** satir 31-32.
- **Aksiyon:** class Config: from_attributes = True yerine model_config = ConfigDict(from_attributes=True) kullan (ConfigDict import'u pydantic'ten eklenmeli).
- **Onem:** Dusuk · **Guven:** Kesin
