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
üretecek yer kalmaz ve **cevap hata vermeden cümle ortasında kesilir**. `16384` canlı
testte doğrulandı:

```
OLLAMA_NUM_CTX=16384
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

## CV metni PDF'ten nasıl çıkarılıyor

Ham PDF modele **gönderilmiyor**; metni `pymupdf` ile yerelde çıkarıp prompt'a koyuyoruz.
Sebebi ölçüldü: dosya girişi yalnızca OpenAI'da çalışıyor.

| Sağlayıcı | Dosya girişi |
|---|---|
| OpenAI | Çalışır — sunucu PDF'ten metin + sayfa görüntüsü çıkarır (vision modeli gerekir, pahalı) |
| Ollama | **Yok** — agno dosyayı atar, log'a `File input is currently unsupported.` düşer |
| LM Studio | **Yok** — sunucu 400 döner: `'content' objects must have a 'type' field that is either 'text' or 'image_url'` |

Metni biz çıkarınca üç sağlayıcıda da aynı kod yolu çalışıyor ve sayfa görüntüsü
göndermediğimiz için maliyet çok daha düşük.

**Aksan onarımı.** LaTeX ile üretilmiş PDF'lerde `ç` tek precomposed karakter değil:
`C` + ayrı bir `¸` (U+00B8 CEDILLA, boşluklu/spacing karakter, **birleştirici değil**)
olarak gömülü. Bu pymupdf'e özgü bir hata değil — PDF'in kendi metin akışı böyle
kodlanmış; aynı sınıf sorun pdfminer ve poppler'da da var, kütüphane seviyesinde bir
düzeltme yok ([pymupdf/PyMuPDF#2279](https://github.com/pymupdf/PyMuPDF/issues/2279)).
`unicodedata.normalize("NFC")` tek başına yetmiyor çünkü boşluklu işaretler NFC'nin
tanıdığı combining mark'lar değil.

`_aksan_onar` iki adımlı çalışıyor: (1) boşluklu aksan işaretini gerçek bir combining
mark'a (U+0300 Combining Diacritical Marks bloğu) çevirip taban harfin yanına taşı,
(2) `unicodedata.normalize("NFC")` ile birleştir. Harf tablosu **Türkçe'ye özgü değil**
— işaret bazlı (¨ ´ \` ˆ ~ ˘ ˚ ˇ ¯ ¸ ˛), bu yüzden aksan kullanan her Latin alfabesi
için aynı mekanizma çalışır: Fransızca (é, à, è), Almanca (ü, ö, ä), Çekçe/Slovakça
(š, č, ž), Lehçe (ą, ę), Portekizce (ã, õ) — sentetik testlerle doğrulandı. Gerçek
CV'lerde test edildi: 24 kırık işaret sıfıra indi ve sonuç sayfanın birebir aynısı oldu.

**Metin katmanı olmayan PDF** (taranmış görüntü) yüklenirse kullanıcıya bu açıkça
söyleniyor; belgeyi "geçersiz" diye suçlayan bir mesaj verilmiyor.

## notebooks/

Bu kararın dayandığı ölçümler. Üçü de aynı `NormalizedCV` şemasını, aynı talimatı ve
aynı çıkarım modelini kullanır — tek değişken metnin nasıl elde edildiğidir.

| Notebook | Yöntem |
|---|---|
| `1_openai.ipynb` | PDF → OpenAI dosya girişi (ara adım görünmez, sunucuda olur) |
| `2_unlimited_ocr.ipynb` | PDF → 300 dpi PNG → Unlimited-OCR → metin |
| `3_pymupdf.ipynb` | PDF → pymupdf metin → aksan onarımı |

OCR yolu **denendi ve seçilmedi**: Türkçeyi doğru okuyor ama Ollama'da
`no_repeat_ngram_size` karşılığı olmadığı için yoğun sayfalarda aynı satırı onlarca kez
tekrarlayıp `num_predict` tavanına dayanıyor ve sayfayı yarıda kesiyor. Ayrıca 4 GB VRAM
ve sayfa render'ı gerektiriyor. `pymupdf` + onarım aynı sonucu sıfır maliyetle veriyor.
Notebook duruyor — taranmış PDF ihtiyacı doğarsa başlangıç noktası hazır.
