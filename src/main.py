from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import DATA_DIR, settings
from cv_analysis import analyze_cv_swot, score_cv_against_criteria, score_multiple_candidates
from cv_intake import fs_knowledge, intake_post_hook, intake_pre_hook, resolve_cv_duplicate
from models.model_factory import get_model

agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions=(
        "Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın. "
        "Kullanıcı bir CV dosyası yüklediğinde bu otomatik olarak arka planda işlenir; "
        "bunu sen tetiklemezsin. En son yüklenen dosya: {cv_current_file}. "
        "grep_file/list_files/get_file araçları zaten adaylar klasörüne odaklı — "
        "pattern'e 'data/knowledgebase/adaylar' gibi bir yol öneki EKLEME, sadece "
        "'*aday_adı*' gibi göreli bir desen kullan (ör. list_files('*furkan_kaya*')). "
        "Dosya adları '<aday_id>_normalized.json' şeklinde, aday adının snake_case hali. "
        "CV işleme durumu ve sonuçları için TEK GÜVENİLİR KAYNAK bu dosya sistemidir — "
        "kendi hafızana veya varsayımına güvenme, zamanlama yüzünden güncel olmayabilir. "
        "Kullanıcı bir CV'nin durumunu veya detaylarını sorduğunda mutlaka önce "
        "list_files veya grep_file ile ilgili adaya ait bir *_normalized.json oluşmuş mu "
        "kontrol et. Sadece 'işlendi mi, durumu ne' gibi bir soru varsa bu adım yeterli — "
        "dosya bulunması işlemin bittiği anlamına gelir, get_file'ı ÇAĞIRMANA gerek yok. "
        "Kullanıcı içerik/detay istiyorsa (beceriler, deneyim, özet vb.) o zaman get_file "
        "ile oku ve gerçek veriye dayanarak cevap ver. Dosya henüz oluşmamışsa hâlâ "
        "işlendiğini söyle. Kullanıcı 'işlendi ama sen görmüyorsun' derse ona güven, "
        "dosya sistemini tekrar kontrol et, eski varsayımında ısrar etme. "
        "Bir mesajın başında bekleyen CV kayıt kararlarının listesi verilmişse, kullanıcının "
        "cevabını buna göre yorumla ve resolve_cv_duplicate tool'unu çağır; hangi karara ait "
        "olduğu belirsizse tool çağırmadan önce kullanıcıya sor. "
        "Kullanıcı bir adayın SWOT analizini istediğinde: önce list_files/grep_file ile doğru "
        "candidate_id'yi bul (aday kayıtlı değilse bunu söyle), sonra analyze_cv_swot tool'unu "
        "çağır ve dönen sonucu OLDUĞU GİBİ ilet — zaten güzel formatlanmış, yeniden yazma. "
        "Kullanıcı bir CV'yi kendi belirlediği kriterlere göre puanlamak/analiz etmek "
        "istediğinde (ör. 'React tecrübesi, temiz kod ve uzaktan çalışma uyumuna göre "
        "skorla'): önce konuşma geçmişinden hangi aday(lar)dan bahsedildiğini anla — bu "
        "session'da tek bir aday konuşulduysa/yüklendiyse onu hedefle, birden fazla "
        "adaydan bahsedildiyse hepsini hedefle. ÖNEMLİ: kullanıcının KAÇ KİŞİDEN "
        "bahsettiği ile list_files aramasının KAÇ FARKLI candidate_id bulduğu aynı şey "
        "değil — kullanıcı TEK bir isim söylediyse (ör. 'furkanı skorla') ama arama o "
        "isimle eşleşen birden fazla farklı kayıt bulursa (ör. furkan_kaya, "
        "furkan_kaya_2 — aynı isimli farklı kişiler), bunu ASLA 'kullanıcı hepsini "
        "kastetti' diye yorumlayıp hepsini otomatik skorlama; bu bir isim çakışmasıdır, "
        "hangi kişiyi kastettiğini (ör. unvan/şirket sorarak) tool çağırmadan önce sor. "
        "Hangi aday(lar) olduğu net değilse tool çağırmadan önce kullanıcıya sor. "
        "Kullanıcının cümlesinden kriterleri bir liste "
        "olarak çıkar. TEK aday için score_cv_against_criteria, BİRDEN FAZLA aday için "
        "score_multiple_candidates çağır. Bu tool'lar sana YAPILANDIRILMIŞ VERİ (JSON) "
        "döner, hazır mesaj DEĞİLDİR — sonucu kendin okunaklı bir markdown'a çevir (kriter "
        "bazlı puanlar, ortalama, güçlü/zayıf yönler, gelişim tavsiyeleri, İK "
        "değerlendirmesi; çoklu adayda sıralı bir liste); ham JSON'u ASLA kullanıcıya "
        "gösterme. Kullanıcı tek bir CV yükledikten sonra isterse kriter bazlı analiz "
        "yapmak isteyip istemediğini nazikçe sorabilirsin."
    ),
    pre_hooks=[intake_pre_hook],
    post_hooks=[intake_post_hook],
    knowledge=fs_knowledge,
    search_knowledge=False,
    tools=[
        *fs_knowledge.get_tools(),
        resolve_cv_duplicate,
        analyze_cv_swot,
        score_cv_against_criteria,
        score_multiple_candidates,
    ],
    session_state={"cv_current_file": None},
    send_media_to_model=False,
    store_media=True,
    markdown=True,
    add_history_to_context=True,
)

agent_os = AgentOS(
    agents=[agent],
    interfaces=[Telegram(agent=agent, token=settings.telegram_token)],
    db=SqliteDb(db_file=str(DATA_DIR / "agent-os.db")),
    tracing=True,
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
