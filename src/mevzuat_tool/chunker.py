import re
from dataclasses import dataclass

# Madde işareti ailesi — Türkçe büyük/küçük harf güvenli (i/İ için (?i) yerine char-class).
_MADDE_KW = r"[Mm][Aa][Dd][Dd][Ee]"
_PREFIX = (
    r"(?:"
    r"[Ee][Kk]"
    r"|[Gg][Ee][Çç][İIiı][Cc][İIiı]"
    r"|[Mm][Üü][Kk][Ee][Rr][Rr][Ee][Rr]"
    r")\s+"
)
_MADDE_FULL = r"MADDE"  # tam-büyük varyant (tiresiz başlıkların gerçek dizgisi)
_NUM = r"\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?"
_FN = r"(?:\[\d+\])*"  # numara sonrası [dipnot] işaretleri (ör. Gümrük "Madde 15[14][15] -")

# Madde işareti iki dal halinde (capture grupları her ikisinde de: 1=prefix, 2=numara):
#  Dal A — karışık 'Madde' (en yaygın): ayraç = TİRE veya numaradan sonra '(' künyesi.
#    Tire şartı "5. fıkra"yı, paren-lookahead "madde 10 hükmü"yü (küçük-harf gövde atfı) eler.
#  Dal B — tam-büyük 'MADDE': ek olarak TİRESİZ büyük-harf başlık da kabul (Borçlar "MADDE 428
#    İşyerinin..."). Gerçek-veri kanıtı: tiresiz başlıklar HEP tam-büyük 'MADDE'; karışık 'Madde
#    32 Tebliğ' biçimi her zaman gövde-içi ATIF → yalnız tam-büyük dalda büyük-harf ayracı açılır,
#    böylece karışık-büyük atıflar yanlış-pozitif madde SAYILMAZ.
# Ortak son-ek: numara sonrası [dipnot] + opsiyonel nokta (TCK "MADDE 61. -").
_TAIL = rf"{_FN}\s*\.?"
# Dal B tiresiz başlık lookahead'i: '(' künyesi VEYA TITLE-CASE kelime (Başharf büyük + küçük
# harf devam, ör. 'İşyerinin'). Tümü-büyük kelime ('KAPSAMINDA') gövde-içi ATIF işaretidir →
# title-case şartı bu atıfları eler (gerçek veri: tiresiz başlıklar title-case, atıflar all-caps).
_AYRAC_A = r"(?:\s*-\s*|\s+(?=[(]))"
_AYRAC_B = r"(?:\s*-\s*|\s+(?=[(]|[A-ZÇĞİÖŞÜ][a-zçğıöşü]))"
_MADDE = re.compile(
    rf"\b({_PREFIX})?{_MADDE_KW}\s+({_NUM}){_TAIL}{_AYRAC_A}"
    rf"|\b({_PREFIX})?{_MADDE_FULL}\s+({_NUM}){_TAIL}{_AYRAC_B}"
)


def _canon_prefix(prefix: str) -> str:
    p = prefix.lower()
    if p.startswith("ek"):
        return "Ek"
    if p.startswith("g"):
        return "Geçici"
    if p.startswith("m"):
        return "Mükerrer"
    return prefix


@dataclass
class Article:
    no: str
    body: str


# Gövde-taşma: HTML'de sonraki maddenin BAŞLIĞI ('Amaç:') marker'dan önce gelince önceki
# maddenin gövde kuyruğuna yapışır. Desen: gövde sonu '[.!?] <1-5 Title-Case kelime>:'.
# Bu yalnız bir sonraki madde VARSA kırpılır (son maddede yutacak başlık yoktur; gerçek
# 'şunlardır:' liste-başı korunur). Gerçek veri: yutulan başlıklar 'Yürütme','Kapsam',
# 'Tanımlar' gibi gerçek madde başlıkları; liste-başı kelimesi (şöyledir/şunlardır) hiç görülmedi.
#
# Liste-başı sözcükleriyle biten cümle (şunlardır:, aşağıdakiler:) gerçek liste açılışıdır → kırpma.
# FAZ 18a guard genişletme: 'şartlar|unsurlar|nedenler|sebepler|esaslar|haller|kişiler' kökleri
# eklendi — bunlar da yaygın liste-başı/belirsiz başlık kalıpları ('genel şartları:',
# 'manevi unsurları:', 'yararlanamayacak kişiler:'). Gerçek veri: 193:46, 2802:36 — 2 belirsiz vaka,
# TP (gerçek bleed) olsalar bile 0-FP güvenliği için KORUNUR (kesilmez). Master plan: "0-FP
# veremezsen ertele" — belirsizi kesmemek doğru taraf.
_LISTE_BASI = re.compile(
    r"(?i)(?:şunlar|aşağıdaki|şöyle|gibidir|belirtilen|sayılanlar|hususlar|kimseler|kişiler|"
    r"olanlar|halinde|şartlar|unsurlar|nedenler|sebepler|esaslar|haller)"
    r"[\wçğıöşüâî ]*:\s*$"
)
# Gövde-taşma (genişletilmiş): sonraki maddenin BAŞLIĞI ('Müracaat, şikayet ve dava açma:') gövde
# kuyruğuna sızmış. Virgül + max 10 kelime kapsanır (uzun/virgüllü başlıklar). Liste-başı guard ayrı.
_BLEED_BASLIK = re.compile(
    r"(?<=[.!?])\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî,]*(?:\s+[\wçğıöşüâî,]+){0,9}:\s*$"
)

# Gövde-taşma (ROMA-başlık varyantı, FAZ 18b): sonraki maddenin ROMA-numaralı başlığı ('III -
# Kuruluş:') gövde kuyruğuna sızmış. Gerçek veri: 1739 (Milli Eğitim Temel Kanunu) roma-numaralı
# madde başlıkları kullanıyor. İmza: cümle-sonu + ROMA rakamı + ' - ' + Title-Case başlık + ':'
# (kolon ŞART). E-tuzağı kanunları (4721,6098,6102,5846,2709 vb.) için ayrı hariç-tutma YOK —
# split_articles kanun_no görmüyor. Onun yerine TEK-ROMA guard: body içinde bu 'X - ' roma-imzası
# BİRDEN FAZLA geçiyorsa (madde-içi roma-numaralı LİSTE, ör. FSEK 'I - İlim eserleri: ... II - ...')
# KIRPMA — çoklu-roma madde-içi yapıdır, sonraki-madde başlığı değildir. Yalnız TEK roma-imzası
# (bleed eşleşmesinin kendisi) varsa kırp. Controller ölçümü: E-tuzağı-dışı 55 vakada çoklu-roma=0
# (hepsi TP, tek-roma), E-tuzağı'da çoklu-roma yaygın → bu guard E-tuzağı'yı doğal korur.
_BLEED_ROMA_BASLIK = re.compile(
    r"(?<=[.!?])\s+[IVX]{1,4}\s*-\s+[A-ZÇĞİÖŞÜ][\wçğıöşüâî,]*(?:\s+[\wçğıöşüâî,]+){0,9}:\s*$"
)
# Madde-içi roma-imzası sayacı (guard): 'X - ' biçimi (kolon şartı yok — liste içi 'I - ... II - ...'
# kolonla da kolonsuz da olabilir; sayaç yalnız kaç roma-numaralı bölüm işareti geçtiğini ölçer).
_ROMA_IMZA_SAYAC = re.compile(r"(?:(?<=[.!?])|(?<=^))\s*[IVX]{1,4}\s*-\s+[A-ZÇĞİÖŞÜ]")

# Seviye-başlık bleed: gövde kuyruğuna sızan 'X. BÖLÜM/KISIM/KİTAP/AYIRIM/FASIL ...' yapısal
# başlığı. Madde içinde yeni bir BÖLÜM/KISIM başlamaz — o, bir sonraki yapısal birimin başlığıdır
# (chunker level-başlıkları madde saymaz, gövdeye sızar). Cümle-sonu (.!?:) VEYA ')' sonrası
# sıra-sözcüğü ('İKİNCİ','ALTINCI','ON BİRİNCİ','SON') + BÖLÜM/KISIM görülünce ORADAN gövde sonuna
# kadar kırp. 'ikinci fıkra' gibi sıra+fıkra/kişi BÖLÜM/KISIM olmadığı için dokunulmaz.
# Notlar: (1) 'ON BİRİNCİ' gibi bileşik sıra; (2) 'altıncı' dizgi bozuğu 'ALTlNCI' (küçük-l) için
# 'ı'↔'l' toleransı; (3) lookbehind'a ')' eklendi ('...md.) İKİNCİ BÖLÜM'). Gerçek veri: 3402,7545,7071.
# Sıra göstergesi sözcüğü: 'İKİNCİ','ALTINCI','ON BİRİNCİ'/'ONBİRİNCİ' (boşluklu|bitişik),
# 'altıncı' dizgi bozuğu 'ALTlNCI' için ı↔l toleransı, 'SON'. (Roma-rakamı 'III.' biçimi ek
# karmaşıklık/risk getirip korpusta etki etmediği için kapsanmadı — kalan ~50 kopuk-dizgi
# varyantı bilinen-sınır.)
_SIRA = (r"(?:on|yirmi)?\s*(?:bir[il]nci|ik[il]nci|üçüncü|dördüncü|beşinci|alt[il]ncı|"
         r"yed[il]nci|sek[il]z[il]nci|dokuzuncu|onuncu)|son")
# Lookbehind: cümle-sonu (.!?:), ')' VEYA dipnot işareti (']' — 'yapılır.[2] ÜÇÜNCÜ BÖLÜM').
_SEVIYE_BASLIK_BLEED = re.compile(
    r"(?i)(?<=[.!?:)\]])\s+(?:" + _SIRA + r")\s+(?:bölüm|kısım|kitap|ayrım|ayirim|fasıl)\b.*$"
)


# Kanun-sonu ek bleed (FAZ 15 / BUG 9): kanunun SON maddesi 'yürütme'dir ('...Bakanlar Kurulu/
# Cumhurbaşkanı yürütür') — kısa, tek cümle. Ama split_articles son maddede end=len(text) olduğu
# için, ardından gelen kanun-sonu ekleri (değişiklik-listesi tablosu 'X SAYILI KANUNA EK VE
# DEĞİŞİKLİK GETİREN...', kadro/tarife cetvelleri 'N SAYILI LİSTE/CETVEL', 'EK GÖSTERGE CETVELİ')
# gövdeye giriyor (5996:50=5791 kar, 7440:25...). ANCHOR = 'yürütür' cümlesi; kuyruk (anchor sonrası)
# TÜMÜ-BÜYÜK belge başlığıyla başlıyorsa oradan sona kes. Ölçüm: 432 kesim, 0 FP (hepsi çöp).
# 0-FP KAPILARI: (1) anchor ŞART (anchorsuz salt-sınır 299 tüm-madde-kaybı); (2) kuyruk tümü-büyük
# OLMALI — küçük-harf başlarsa (meşru hüküm/düz-metin çöp: 7326:18 CB Kararı) KESME → ertelenen semantik;
# (3) meşru 'Yürürlük' maddeleri 'yürütür' içermez, anchor dokunmaz.
_KANUN_SONU_ANCHOR = re.compile(
    r"(?i)(?:"
    r"(?:bakanlar\s+kurulu|cumhurbaşkanı)"
    r"|(?:\w+\s+)?(?:\w+\s+ve\s+)?\w+\s+bakan(?:ı|ları)"   # 'Millî Savunma ve Maliye Bakanları'
    r")\s+yürütür\s*\.?"
)

# FAZ 15 GAP (657:239 ve benzerleri): tümü-büyük kanun-sonu ek başlığının hemen içine/ardına
# değişiklik künyesi '(Ek: ...)','(Mülga: ...)','(Değişik: ...)' vb. (KÜÇÜK harf) sızmış olabilir
# ('I SAYILI CETVEL (Ek: 9/4/1990-KHK-418/3 md.; İptal: ...; Yeniden düzenleme: ...) (Değişik:...)
# HİZMET SINIFLARI...'). Bu künyeler enrich aşamasında temizle_kunyeler ile SİLİNİR ama
# _strip_kanun_sonu_ek DAHA ÖNCE (split_articles içinde) çalışır — künye metni ilk 80 karakterin
# büyük-harf oranını düşürüp (0.25-0.45) guard'ı yanlışlıkla "meşru küçük-harf kuyruk" sandırıyor.
# Künye kalıbı degisiklik.py _KUNYE ile AYNI aile (anahtar kelime + ':') — kapanış ')' YOK sayılabilir
# (uzun künye 80-karakter pencereyi taşabilir; kapanışı aranan pencerede olmayabilir) → açgözlü
# '.*' YERİNE ')' bulunana kadar VEYA pencere sonuna kadar ilerler (span sınırlı, ReDoS riski yok).
_KUNYE_ORAN_ATLA = re.compile(
    r"(?i)\((?:değişik|ek(?:\s+cetvel|\s+kroki\b[^:)]*)?|mülga|iptal|ekleme|"
    r"yeniden\s+düzenleme|aynen\s+kabul)\s*:[^)]*\)?"
)


def _buyuk_oran_kunyesiz(kuyruk: str, hedef: int = 80) -> float | None:
    """SABİT ilk 'hedef' karakterlik pencerenin büyük-harf oranı — künye parantezleri ('(Ek:...)'
    vb.) ölçüme katılmadan. Künye chunker'ın kendi kesim kararı için gürültü (gerçek içerik değil,
    ayrıca enrich'te temizle_kunyeler ile zaten silinecek).
    ÖNEMLİ: pencere GENİŞLETİLMEZ (künye çıkınca eksileni tamamlamak için ileri gidilmez) — deneyle
    (102952-23 regresyonu) kanıtlandı ki genişletme, künye SONRASI gerçek (mesru Title-Case tablo
    başlığı gibi) küçük/karışık-harf içeriği pencereye çekip önceden doğru kesilen bir maddeyi
    YANLIŞLIKLA kesilmez hale getirebiliyor. Bunun yerine SABİT pencere içindeki künye(ler) atılır;
    kalan harf azsa (hatta 0), oran o kadarıyla hesaplanır — daha az örnek ama yön hep aynı tarafa
    (künyesiz veri OLMASAYDI zaten öyle ölçülecekti)."""
    ilk = kuyruk[:hedef]
    kunyesiz = _KUNYE_ORAN_ATLA.sub("", ilk)
    harf = [c for c in kunyesiz if c.isalpha()]
    if not harf:
        return None
    return sum(c.isupper() for c in harf) / len(harf)


def _strip_kanun_sonu_ek(body: str) -> str:
    """Son-madde 'yürütür' anchor'ı sonrası TÜMÜ-BÜYÜK kanun-sonu ek kuyruğunu kırp (0-FP).
    Anchor yoksa VEYA kuyruk (künye parantezleri hariç tutularak ölçülünce) tümü-büyük değilse
    body değişmez."""
    a = _KANUN_SONU_ANCHOR.search(body)
    if not a:
        return body
    kuyruk = body[a.end():].lstrip(". \n")
    if len(kuyruk) < 30:            # kuyruk yok/kısa → temiz madde
        return body
    buyuk_oran = _buyuk_oran_kunyesiz(kuyruk)
    if buyuk_oran is None or buyuk_oran <= 0.85:  # küçük-harf kuyruk (meşru/düz-metin çöp) → KESME
        return body
    return body[:a.end()].strip()   # anchor'a kadar tut, tümü-büyük kuyruğu (künye dahil) at


# Kanun-sonu 'işlenemeyen madde eki': '(TARİHLİ VE NNNN) SAYILI ... KANUNA İŞLENEMEYEN ...'
# başlığı. Başka kanunlarla bu kanuna eklenmek istenip işlenememiş maddelerin listesidir — bu
# kanunun maddesi DEĞİL. Buradan sonrası madde olarak parse edilmemeli (yoksa tekrarlı 'Geçici 1'
# hayalet chunk'lar doğar: 6183'te 5 kez). Başlığı tarihiyle birlikte kes (önceki maddenin
# gövdesine '... TARİHLİ VE NNNN' kuyruğu kalmasın). 'işlenemeyen' kelimesinin normal içerikte
# geçmesinden ('sisteme işlenemeyen kayıt') ayırmak için 'SAYILI ... KANUN[uA] İŞLENEMEYEN' şart.
_ISLENEMEYEN_EKI = re.compile(
    r"(?i)(?:\d+/\d+/\d+\s+)?(?:tarihli\s+ve\s+\d+\s+)?sayılı\s+.{0,40}?kanun[ua]?\s+işlenemeyen"
)


# Yapışık madde-bleed (FAZ 16 / BUG 2): kaynak metinde sonraki maddenin başlığı önceki gövdeye
# BOŞLUKSUZ yapışık ('...şartlarıMADDE 132- (1)'). Türkçe küçük 'ı'/'i'/'r'/'n' + 'M' arası \b
# OLUŞMAZ → ana _MADDE deseni yakalayamaz → madde önceki gövdeye gömülür. Post-tespit: gövdede
# '<sözcük-karakteri>MADDE <no>- (' yapışık imzası aranır. Dar imza (tam-büyük MADDE + tire + '(' fıkra)
# atıfları ('MADDE 5'e göre', '132 nci maddesi') ELER. Ölçüm: korpus-genelinde desen 4/4 gerçek, 0 FP.
_YAPISIK_MADDE = re.compile(
    r"(?<=[\wçğıöşüâîÇĞİÖŞÜ])"                          # ÖNÜNDE sözcük-karakteri (asıl bug: \b yok)
    rf"MADDE\s+({_NUM})-\s*(?=\()"                      # MADDE <no>- ( → fıkra imzası (0-FP dar)
)

# GERÇEK cümle-sonu (task-reviewer CRITICAL bulgusu — FAZ 16 fix): [.!?] + boşluk(lar) + BÜYÜK
# harf VEYA RAKAMLA başlayan yeni birim (ör. gömülü başlık '5. fıkra hükmüne göre...' RAKAMLA
# başlayabilir — 657:Ek2 gibi vakalar). Sıra-noktası ('5. fıkra') veya kısaltma noktası ('md.',
# 'T.C.') nokta sonrası KÜÇÜK HARFLE devam eder → bu desenle EŞLEŞMEZ (elenir; eski `rfind` kodu
# bunu yanlışlıkla cümle-sonu sanıyordu). Rakam sınıfı yalnız boşluktan HEMEN SONRAKİ karakteri
# kontrol eder — 'duzenlenen 5. fıkra' gibi CÜMLE İÇİ ordinal referanslar bu konumda değil (önlerinde
# gerçek cümle-sonu yok), dolayısıyla yanlış-pozitif üretmez. _BLEED_BASLIK'teki sezgiyle aynı aile:
# (?<=[.!?])\s+[A-ZÇĞİÖŞÜ]... match.end() = yeni başlığın başı (ara boşluk atılır).
_GERCEK_CUMLE_SONU = re.compile(r"[.!?]\s+(?=[A-ZÇĞİÖŞÜ0-9])")


def _split_yapisik_madde(no: str, body: str) -> list[Article]:
    """Gövdede önceki içeriğe yapışık gömülü madde(ler) varsa ayrı Article'lara böl (FAZ 16, 0-FP).
    Bölme noktası: gömülü 'MADDE'den geriye en yakın GERÇEK cümle-sonu ([.!?] + boşluk + BÜYÜK harf)
    = gömülü maddenin başlık başı. Sıra-noktası ('5. fıkra') veya kısaltma noktası ('md.') nokta
    sonrası küçük harfle devam ettiği için gerçek cümle-sonu SAYILMAZ (task-reviewer CRITICAL fix).
    Gerçek cümle-sonu bulunamazsa (başlık önceki gövdeden ayrılamaz) o gömülü madde bölünmez (0-FP).
    Yapışık madde yoksa [Article(no, body)] döner (davranış değişmez).

    ÇİFT-BAŞLIK FIX (FAZ 16 sonrası bug): gömülü maddenin body'si BAŞLIKSIZ üretilir — yalnız
    'MADDE N-' işaretinden SONRAKİ gövde (fıkralar). Başlık metni (kesim..MADDE arası) body'ye
    PREPEND EDİLMEZ ve atılır: sistem sözleşmesi Article.body'nin başlıksız olmasını gerektirir
    (bkz. corpus.py) — başlık, API madde-ağacındaki node.baslik alanından ayrıca gelip corpus.py
    tarafından text'e prepend edilir. Body'ye de eklenirse çift başlık oluşur (M132/M133/M135/M165
    gerçek regresyon). Konteyner (üst) madde body'si zaten başlıksız kalır (değişmez)."""
    marks = list(_YAPISIK_MADDE.finditer(body))
    if not marks:
        return [Article(no=no, body=body)]
    # 1) Kesim noktalarını topla: (baslik_bas, MADDE-isareti-sonu, gomulu_no). baslik_bas = gömülü
    #    'MADDE'den geriye en yakın GERÇEK cümle-sonu eşleşmesinin sonu (büyük harfin başı).
    #    Gerçek cümle-sonu yoksa o gömülü madde atlanır.
    kesimler: list[tuple[int, int, str]] = []
    tarama_bas = 0  # cümle-sonu araması bir önceki gömülü maddenin gövde-başından itibaren
    for m in marks:
        kesim = -1
        for sonu in _GERCEK_CUMLE_SONU.finditer(body, tarama_bas, m.start()):
            kesim = sonu.end()  # en sağdaki (MADDE'ye en yakın) eşleşmeyi tut
        if kesim < 0:
            continue  # gerçek cümle-sonu yok → başlığı ayıramayız → bu gömülü maddeyi bölme (0-FP)
        kesimler.append((kesim, m.end(), m.group(1)))
        tarama_bas = m.end()
    if not kesimler:
        return [Article(no=no, body=body)]
    # 2) Ardışık dilimle. Üst madde: body başından ilk başlık-başına kadar (başlık metni atılır —
    #    kesim..MADDE arası buraya dahil değil, üst maddenin body'sine de sızmaz). Sonra her gömülü
    #    madde: yalnız gövde (MADDE-sonu.. sonraki başlık-başı VEYA body sonu) — başlıksız.
    out: list[Article] = [Article(no=no, body=body[:kesimler[0][0]].strip())]
    for i, (_baslik_bas, madde_sonu, gomulu_no) in enumerate(kesimler):
        govde_son = kesimler[i + 1][0] if i + 1 < len(kesimler) else len(body)
        govde = body[madde_sonu:govde_son].strip()
        out.append(Article(no=gomulu_no, body=govde))
    return out


def split_articles(text: str) -> list[Article]:
    # Kanun-sonu işlenemeyen-madde ekini at (başka kanunlara ait; hayalet chunk kaynağı).
    eki = _ISLENEMEYEN_EKI.search(text)
    if eki:
        text = text[:eki.start()]
    matches = list(_MADDE.finditer(text))
    out: list[Article] = []
    for i, m in enumerate(matches):
        start = m.end()
        son_madde = i + 1 >= len(matches)
        end = matches[i + 1].start() if not son_madde else len(text)
        # Dal A (karışık 'Madde') grup 1,2 — Dal B (tam-büyük 'MADDE') grup 3,4.
        prefix = (m.group(1) or m.group(3) or "").strip()
        number = m.group(2) or m.group(4)
        no = f"{_canon_prefix(prefix)} {number}" if prefix else number
        body = text[start:end].strip()
        # Seviye-başlık ('X. BÖLÜM/KISIM ...') gövde kuyruğuna sızmışsa oradan sona kadar kırp.
        # (son madde dâhil — kanun-sonu 'Çeşitli ve Son Hükümler' başlığı son maddede de sızabilir)
        body = _SEVIYE_BASLIK_BLEED.sub("", body).strip()
        body = _strip_kanun_sonu_ek(body)
        if not son_madde:  # sonraki maddenin (kolonlu) başlığı gövde kuyruğuna sızmışsa kırp
            m_bleed = _BLEED_BASLIK.search(body)
            if m_bleed and not _LISTE_BASI.search(body[m_bleed.start():]):  # liste-başı değilse kırp
                body = body[:m_bleed.start()].strip()
            else:
                # ROMA-başlık varyantı (FAZ 18b): yalnız TEK roma-imzası varsa (madde-içi çoklu-roma
                # liste DEĞİL) kırp — E-tuzağı (FSEK/TTK iç-roma-listeleri) bu guard ile korunur.
                m_roma = _BLEED_ROMA_BASLIK.search(body)
                if m_roma and len(_ROMA_IMZA_SAYAC.findall(body)) <= 1:
                    body = body[:m_roma.start()].strip()
        out.extend(_split_yapisik_madde(no, body))
    return out


def split_fikralar(body: str) -> list[str]:
    parts = re.split(r"(?=\(\d+\)\s)", body.strip())
    return [p.strip() for p in parts if p.strip()]


# Nitelikli/kısmi mülga: yalnızca BİR fıkra/bent mülga → tüm madde mülga DEĞİL (C1).
# Ör: '(Mülga son fıkra: ...)', '(Mülga ikinci fıkra: ...)', '(Mülga üçüncü cümle: ...)'.
_KISMI_MULGA = re.compile(
    r"(?i)\(\s*mülga\s+(?:son|birinci|ikinci|üçüncü|dördüncü|beşinci|altıncı|yedinci|"
    r"sekizinci|dokuzuncu|onuncu|\d+\s*(?:\.|inci|ıncı|uncu|üncü|nci))\s+"
    r"(?:fıkra|cümle|bent|paragraf)"
)
# Mülga/İptal markeri: parantez içinde 'Mülga' veya AYM 'İptal' (';' sonrası dâhil). 'İptal'
# ardından doğrudan ':' VEYA '(birinci/ikinci/.. ) fıkra/bent/madde:' gelebilir — '(İptal fıkra:)' /
# '(İptal birinci fıkra:)' AYM kararı iptal sinyalidir (Bug 5: 102929-Ek1, 105335-1). FAZ 1 (A1+A3):
# '(İptal bent:)' (7405 M38, 7354 M5/M6) ve '(İptal madde:)' (221 / 103326-1..5, boş iptal maddesi)
# de simetrik olarak iptal sinyalidir — 'fıkra' yanına 'bent|madde' eklendi.
_MULGA_MARKER = re.compile(
    r"(?i)\(\s*mülga|;\s*mülga|\(\s*iptal\s*:|;\s*iptal\s*:"
    r"|\(\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:"
    r"|;\s*iptal\s+(?:\w+\s+)?(?:fıkra|bent|madde)\s*:")

# Madde 'açılış künye bölgesi': gövde başındaki ardışık künye parantezleri + aralarındaki boşluk.
# İki künye biçimi:
#  (a) anahtar kelime: '(Değişik:...)','(Ek:...)','(Mülga:...)','(İptal:...)','(Yeniden düzenleme:..)'
#  (b) TARİH/ATIF ile başlayan: '(2/1/1961- 203/2 md. ile gelen ... teselsül ettirilmiştir.; Mülga:..)'
#      — 657 Ek2/Geçici1 gibi maddelerde künye tarihle başlar; anahtar kelime aramak yetmez.
# Gerçek içerik (künye-olmayan metin VEYA '(1)' fıkra numarası) başlayınca biter. Fıkra '(1)'
# rakam+KAPANIŞ-paren'dir ')' → tarih-künye '(2/1/1961-...' slash'lı, karışmaz.
# E3 (FAZ 14): künyeler arası '[n]' dipnot işareti ('(Ek:...)[13] (Mülga:...)') künye-dizisini
# kırıyordu → '(Mülga:)' açılış-bölgesinde sayılmıyor, madde yanlış 'yürürlükte' (103912-Gecici14).
# Künyeden sonra opsiyonel '[n]' dipnot işaretine izin ver (B1/D1 dipnot dersinin yürürlük versiyonu).
_KUNYE_PAREN = re.compile(
    r"(?i)^\s*(?:\(\s*(?:"
    r"(?:değişik|ek|mülga|iptal|yeniden\s+düzenleme|mülga\s+ve\s+yeniden)"   # (a) anahtar kelime
    r"|\d+/\d+/\d+"                                                          # (b) tarih ile başlar
    r"|\d+\s+sayılı"                                                         # (c) 'NNNN sayılı ...'
    r")[^)]*\)(?:\s*\[\d+\])?\s*)+"                                          # ')' + opsiyonel '[n]' + boşluk
)


def _madde_basi_iptal(body: str) -> bool:
    """Mülga/İptal markeri maddenin AÇILIŞ KÜNYE bölgesinde mi (→ tüm madde mülga)?
    Gerçek içerik başladıktan sonra geliyorsa bir fıkraya aittir (→ madde yürürlükte)."""
    m = _KUNYE_PAREN.match(body)
    kunye_son = m.end() if m else 0
    mk = _MULGA_MARKER.search(body)
    return mk is not None and mk.start() < max(kunye_son, 1)


def extract_status(body: str, konum_duyarli: bool = False) -> str:
    """Yürürlük durumu. konum_duyarli=False (varsayılan): metinde Mülga/İptal varsa o birim mülga
    — fıkra/bent/alt-bent gibi TEK hüküm birimleri için (içindeki Mülga o birime aittir).
    konum_duyarli=True: MADDE seviyesi için — Mülga/İptal yalnız açılış künye bölgesindeyse tüm
    madde mülga; gerçek içerik başladıktan sonra geliyorsa bir fıkraya aittir (madde yürürlükte).
    Bu ayrım 5651 M3/M5/M6 gibi 'içerikte AYM iptali olan ama maddenin kendisi yürürlükte'
    vakalarını madde-geneline aşırı-yaymayı önler."""
    # Önce kısmi/nitelikli mülgayı ele (madde/birim yürürlükte kalır); yalnız o varsa yürürlükte say.
    kismi = list(_KISMI_MULGA.finditer(body))
    kalan = _KISMI_MULGA.sub("", body) if kismi else body
    mk = _MULGA_MARKER.search(kalan)
    if mk is None:
        return "yürürlükte"
    if not konum_duyarli:
        return "mülga"      # tek-hüküm birimi: içindeki Mülga/İptal o birimi mülga yapar
    # Madde seviyesi: marker açılış künye bölgesinde → tüm madde mülga; içerikte → fıkra iptali.
    return "mülga" if _madde_basi_iptal(kalan) else "yürürlükte"
