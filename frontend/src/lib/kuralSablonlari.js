// UX-038 (BUG #481): boş "Kırmızı Çizgiler" için tipik başlangıç şablonları.
// Şablon = yapı, sayı DEĞİL: tutar boş bırakılır, kullanıcı kendi rakamını yazar (ürün
// varsayım yapmaz — H21/BUG #340 dersi: doğru sayı, sessiz kaynak olmaz). Her şablon
// `app/user_rules.py`nin dayattığı üç kural tipinden birine bağlanır; serbest metin yok.
export const KURAL_SABLONLARI = [
  {
    anahtar: 'nakit_tabani',
    baslik: 'Nakit tabanı',
    ozet: 'Nakdim şu tutarın altına inmesin.',
    sablon: {
      title: 'Nakit tabanı',
      description: 'Nakit hesaplarımın toplamı bu tutarın altına inecek hiçbir harcama/aktarım önerme; önerirsen reddet.',
      checkpoint_type: 'rule',
      priority: 1,
      rule_type: 'min_cash_floor',
    },
  },
  {
    anahtar: 'tek_harcama_tavani',
    baslik: 'Tek harcama tavanı',
    ozet: 'Tek seferde şu tutardan fazla harcamayayım.',
    sablon: {
      title: 'Tek harcama tavanı',
      description: 'Tek bir işlemde bu tutarın üstüne çıkan harcamayı bana sormadan kaydetme; büyük alışverişi önce konuşalım.',
      checkpoint_type: 'rule',
      priority: 2,
      rule_type: 'max_single_expense',
    },
  },
  {
    anahtar: 'dokunulmaz_hesap',
    baslik: 'Dokunulmaz hesap',
    ozet: 'Şu hesaba (emanet, birikim) dokunulmasın.',
    hesapGerekir: true,   // hesap yoksa gösterilmez: kullanıcı seçecek bir şey bulamaz
    sablon: {
      title: 'Dokunulmaz hesap',
      description: 'Bu hesaptan çıkış önerme; acil durumda bile önce bana sor.',
      checkpoint_type: 'rule',
      priority: 1,
      rule_type: 'account_untouchable',
    },
  },
];

/** Hesabı olmayan kullanıcıya "hesap seç" şablonu gösterilmez. */
export function uygunSablonlar(accounts) {
  const hesapVar = (accounts || []).length > 0;
  return KURAL_SABLONLARI.filter((s) => !s.hesapGerekir || hesapVar);
}
