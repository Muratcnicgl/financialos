"""
Token tahmini — TEK KAYNAK (LLM-017/018 · BUG #504).

Neden tokenizer yok: sağlayıcılar farklı tokenizer kullanır (Gemini, Llama, Claude, GPT);
`tiktoken cl100k_base` yalnız OpenAI için doğrudur ve kurulu bile değildi (ölçüldü: ImportError
dalı hep aktifti → `len // 4`). Anthropic `count_tokens` bir API çağrısıdır (gecikme + maliyet).
Prompt bütçesi kesin sayı değil, MUHAFAZAKÂR üst sınır ister: Türkçe metin İngilizceden daha
çok token yer (ekler, aksanlı harfler); 3,5 karakter/token payı bütçeyi aşmamayı garantiler.
"""
from __future__ import annotations

import math

KARAKTER_BASINA_TOKEN = 3.5


def token_tahmini(metin: str | None) -> int:
    """Muhafazakâr tahmin: ceil(len / 3.5); boş metin 0."""
    if not metin:
        return 0
    return math.ceil(len(metin) / KARAKTER_BASINA_TOKEN)
