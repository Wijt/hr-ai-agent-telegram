# Telegram İK Botu

Telegram üzerinden CV toplayan, doğrulayan, normalize edip knowledgebase'e kaydeden ve
kayıtlı adaylar üzerinde SWOT / kriter bazlı puanlama yapan bir Agno ajanı.

## Gereksinimler

- Python 3.11+
- Bir Telegram bot token'ı ([@BotFather](https://t.me/BotFather))
- LLM sağlayıcı: OpenAI API anahtarı **veya** yerelde çalışan Ollama

## Kurulum

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env
```

Ardından `.env` dosyasını doldurun (aşağıdaki tabloya bakın) ve çalıştırın:

```bash
.venv/Scripts/python.exe src/main.py
```

Sunucu `http://0.0.0.0:7777` üzerinde açılır.

## Ortam değişkenleri

`.env.example` dosyası şablondur; `.env` git'e girmez.

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `TELEGRAM_TOKEN` | evet | — | @BotFather'dan alınan bot token'ı |
| `APP_ENV` | hayır | `production` | `development` iken webhook secret doğrulaması atlanır |
| `MODEL_PROVIDER` | hayır | `openai` | `openai` veya `ollama` |
| `OPENAI_API_KEY` | OpenAI ise evet | — | OpenAI API anahtarı |
| `OPENAI_MODEL_ID` | hayır | `gpt-4o-mini` | Kullanılacak OpenAI modeli |
| `OLLAMA_MODEL_ID` | Ollama ise evet | `qwen2.5` | Yerel model adı (`ollama list` ile görülür) |
| `OLLAMA_BASE_URL` | hayır | `http://localhost:11434` | Ollama sunucu adresi |
| `OLLAMA_NUM_CTX` | hayır | (boş) | Context penceresi. Boşsa Ollama sunucusunun kendi ayarı geçerli olur |

Sağlayıcıyı `MODEL_PROVIDER` belirler. OpenAI kullanıyorsanız `OLLAMA_*` satırlarını,
Ollama kullanıyorsanız `OPENAI_*` satırlarını boş bırakabilirsiniz.

## Ollama kullanıyorsanız

**Context penceresini büyütün.** Ollama'nın varsayılanı 4096 token. Bu botun tek turluk
prompt'u (ajan talimatları + tool şemaları + CV/SWOT JSON çıktıları + konuşma geçmişi)
tek başına ~4200 token. Pencereye sığmayınca Ollama prompt'u baştan kırpar, modele
üretecek yer kalmaz ve **cevap hata vermeden cümle ortasında kesilir**. `12288` canlı
testte doğrulandı:

```
OLLAMA_NUM_CTX=12288
```

VRAM elverirse artırın. Değeri Ollama sunucusunun kendi ayarından yönetmek isterseniz
bu satırı boş bırakın.

**Model tool desteklemeli.** Bu bot her turda tool gönderir. Modelin yeteneklerini
kontrol edin:

```bash
ollama show MODEL_ADI
```

`capabilities` listesinde `tools` yoksa model kullanılamaz. Bazı Qwen3 build'leri
`tools` desteklediği hâlde 400 `Unable to generate parser for this template` döndürür;
sebebi modelin Jinja şablonundaki `raise_exception` satırlarıdır ve Ollama'nın tool
parser üretimini bozar. Bu durumda başka bir build kullanın.

**Düşünme (thinking) modlu modellerden kaçının.** Akıl yürütme metni cevabın içine
karışabilir ve yapılandırılmış çıktıyı bozar. `ollama show` çıktısında `thinking`
görüyorsanız `instruct` varyantını tercih edin.

## Veri

Adaylar `data/knowledgebase/adaylar/<aday_id>/` altında saklanır: normalize edilmiş
`<aday_id>_normalized.json` ve ham PDF için `_raw/`. Oturum veritabanı
`data/agent-os.db` dosyasındadır. `data/` klasörü git'e girmez.
