export const meta = {
  name: 'gold-set-uret',
  description: 'Yari-otomatik gold set: her madde icin dogal-dilde soru uret, sizinti kapisindan gecir',
  phases: [
    { title: 'Uret', detail: 'her madde icin dogal-dilde soru + dogru-madde isaretleme' },
    { title: 'Kapi', detail: 'sizinti + cevaplanabilirlik denetimi' },
  ],
}

// args = [{task_id, hedef_id, hedef_text, kanun_no, kanun_ad, madde_no, yurutluk, komsu_maddeler:[{id,text}]}, ...]
let gorevler = args
if (typeof gorevler === 'string') {
  gorevler = JSON.parse(gorevler)
}
if (!Array.isArray(gorevler)) {
  throw new Error('args bir gorev dizisi olmali; alinan tip: ' + typeof gorevler)
}

const URET_SCHEMA = {
  type: 'object',
  properties: {
    soru: {
      type: 'string',
      description: 'Dogal Turkce hukuk sorusu. Bir vatandas/avukat nasil sorardiysa oyle. ' +
        'YASAK: madde numarasi (m.125, madde 125), kanun numarasi (657, 5237 sayili), ' +
        'maddenin nadir/teknik ozel terimlerini birebir kopyalama. Konuyu sor, referansi degil.',
    },
    dogru_maddeler: {
      type: 'array',
      items: { type: 'string' },
      description: 'Bu sorunun cevabini GERCEKTEN iceren madde idleri. Hedef madde HER ZAMAN dahil. ' +
        'Komsu maddelerden SADECE cevabi gercekten iceren(ler) eklenir. Ilgisiz komsu EKLENMEZ. ' +
        'Emin degilsen ekleme (uydurma yok).',
    },
    soru_tipi: {
      type: 'string',
      enum: ['tek_madde', 'kavramsal_cok_madde'],
      description: 'dogru_maddeler tek ise tek_madde, birden fazla ise kavramsal_cok_madde',
    },
    zorluk: {
      type: 'string',
      enum: ['kolay', 'orta', 'zor'],
      description: 'kolay=metinle dogrudan eslesir; zor=anlam koprusuu gerekir (esanlamli/dolayli)',
    },
    mulga_notu: {
      type: 'string',
      description: 'Madde mulga ise: soru bugun gecerli cevap bekliyor mu? Beklenen: sistem bu maddeyi ' +
        'ELEMELI (mulga). Yururlukte ise bos birak.',
    },
  },
  required: ['soru', 'dogru_maddeler', 'soru_tipi', 'zorluk'],
}

const KAPI_SCHEMA = {
  type: 'object',
  properties: {
    sizinti: {
      type: 'boolean',
      description: 'Soru madde-no / kanun-no / nadir birebir-terim iceriyor mu (BM25 haksiz avantaji)?',
    },
    maddeye_bagli: {
      type: 'boolean',
      description: 'Soru bu maddeye GERCEKTEN bagli mi? true = cevap ancak isaretli madde okunarak verilir ' +
        '(genel kultur/tahminle verilemez -> IYI soru). false = genel kultur/tahminle cevaplanabilir ' +
        '(maddeyi ayirt etmez -> ZAYIF soru, elenmeli).',
    },
    acik_uclu: {
      type: 'boolean',
      description: 'Soru acik-uclu mu (ne/nasil/kim/hangi/kac ile)? true = acik-uclu (IYI). ' +
        'false = evet/hayir sorusu (...var mi / ...kapsiyor mu -> tahminle cevaplanir, ZAYIF).',
    },
    dogru_madde_dogrulama: {
      type: 'boolean',
      description: 'Isaretli dogru maddeler sorunun cevabini gercekten iceriyor mu?',
    },
    gerekce: { type: 'string', description: 'Kisa: neden gecerli/gecersiz' },
    duzeltilmis_soru: {
      type: 'string',
      description: 'Sizinti VEYA evet/hayir sorunu varsa duzeltilmis (sizintisiz, acik-uclu) yeniden yazim; yoksa bos',
    },
  },
  required: ['sizinti', 'maddeye_bagli', 'acik_uclu', 'dogru_madde_dogrulama', 'gerekce'],
}

// gecerli KODDA turetilir (LLM boolean tutarsizligini onlemek icin — pilotta task 1 kendi karariyla celisti)
function geceerliMi(k) {
  return (!k.sizinti) && k.maddeye_bagli && k.acik_uclu && k.dogru_madde_dogrulama
}

function uretPrompt(g) {
  const komsu = (g.komsu_maddeler || [])
    .map(k => `  - [${k.id}] ${k.text}`)
    .join('\n')
  return `Sen bir Turk hukuku RAG degerlendirme uzmanisin. Gorevin: asagidaki KANUN MADDESINDEN, o maddenin ` +
    `cevap oldugu DOGAL bir Turkce soru uretmek. Bu soru, bir retrieval sisteminin dogru maddeyi getirip ` +
    `getiremedigini olcecek.\n\n` +
    `KANUN: ${g.kanun_ad} (no ${g.kanun_no}), Madde ${g.madde_no}, durum: ${g.yurutluk}\n` +
    `HEDEF MADDE [${g.hedef_id}]:\n${g.hedef_text}\n\n` +
    (komsu ? `AYNI KANUNDAN KOMSU MADDELER (SADECE cevabi gercekten iceren(ler)ini dogru_maddeler'e ekle; ilgisizleri EKLEME):\n${komsu}\n\n` : '') +
    `KURALLAR (ihlal = gold kirlenir):\n` +
    `1. Soru DOGAL dilde olsun (vatandas/avukat gibi). Madde-no, kanun-no, "madde X" YAZMA.\n` +
    `2. Maddenin nadir/teknik ozel terimlerini birebir kopyalama - konuyu sor. (Dense+BM25 adil yarissin.)\n` +
    `3. ACIK-UCLU sor (ne / nasil / kim / hangi / kac / ne kadar). EVET-HAYIR sorusu URETME ` +
    `("...var mi?", "...kapsiyor mu?", "...zorunda mi?" YASAK) - bunlar tahminle cevaplanir, retrieval'i ayirt etmez.\n` +
    `4. TEK net soru sor. 3-4 alt-soruyu ust uste yigma (yapay olur). Maddenin EN AYIRT EDICI ` +
    `tek noktasini sor; cevabi ancak bu madde okunarak verilebilsin.\n` +
    `5. dogru_maddeler'e YALNIZ metnini GORDUGUN ve cevabi GERCEKTEN iceren maddeleri koy. Hedef her zaman dahil.\n` +
    `6. Ilgisiz komsuyu (baska konu) dogru sayma. Emin degilsen ekleme.\n` +
    (g.yurutluk === 'mülga'
      ? `7. Bu madde MULGA. Soru, bugun gecerli sanki yururluktemis gibi normal sorulsun; mulga_notu'na sistemin bunu elemesi gerektigini yaz.\n`
      : ``) +
    `\nCiktiyi semaya gore ver.`
}

function kapiPrompt(g, uret) {
  const dogruTexts = [g.hedef_text.slice(0, 800)]
  return `Sen bir gold-set kalite denetcisisin. Uretilmis bir soru-madde ciftini denetle.\n\n` +
    `SORU: "${uret.soru}"\n` +
    `ISARETLI DOGRU MADDELER: ${JSON.stringify(uret.dogru_maddeler)}\n` +
    `HEDEF MADDE METNI [${g.hedef_id}]: ${dogruTexts[0]}\n\n` +
    `Denetle (her alani BAGIMSIZ degerlendir):\n` +
    `1. SIZINTI (sizinti): Soru madde-no / kanun-no (${g.kanun_no}, ${g.madde_no}) / nadir birebir-terim iceriyor mu? ` +
    `Iceriyorsa BM25 haksiz kazanir -> sizinti=true (KOTU).\n` +
    `2. MADDEYE_BAGLI (maddeye_bagli): Cevap ancak bu madde OKUNARAK verilebiliyor mu? ` +
    `Genel kultur/tahminle verilebiliyorsa maddeye_bagli=false (ZAYIF soru). Maddeye baglıysa true (IYI).\n` +
    `3. ACIK_UCLU (acik_uclu): Soru acik-uclu mu (ne/nasil/kim/hangi/kac)? Evet-hayir sorusuysa (...var mi/...kapsiyor mu) ` +
    `acik_uclu=false (ZAYIF, tahminle cevaplanir).\n` +
    `4. DOGRULAMA (dogru_madde_dogrulama): Isaretli madde(ler) sorunun cevabini gercekten iceriyor mu? ` +
    `Sorudaki unvan/terim maddedekiyle celisiyorsa (ornek: soru "giris sinavi" der ama madde "yarisma sinavi" der) -> dogrulama=false.\n` +
    `Her alani SADECE kendi olcutune gore isaretle; nihai gecerlilik karari SANA AIT DEGIL (kodda hesaplanir).\n` +
    `Sizinti VEYA evet-hayir sorunu varsa duzeltilmis_soru'ya sizintisiz + acik-uclu halini yaz.\n\nSemaya gore cikti ver.`
}

phase('Uret')
log(`${gorevler.length} madde icin gold set uretimi basliyor...`)

const sonuc = await pipeline(
  gorevler,
  (g) => agent(uretPrompt(g), {
    label: `uret:${g.hedef_id}`,
    phase: 'Uret',
    schema: URET_SCHEMA,
  }).then(u => ({ g, uret: u })),
  (prev, g) => {
    if (!prev || !prev.uret) return null
    return agent(kapiPrompt(prev.g, prev.uret), {
      label: `kapi:${prev.g.hedef_id}`,
      phase: 'Kapi',
      schema: KAPI_SCHEMA,
    }).then(k => ({
      task_id: prev.g.task_id,
      hedef_id: prev.g.hedef_id,
      kanun_no: prev.g.kanun_no,
      kanun_ad: prev.g.kanun_ad,
      madde_no: prev.g.madde_no,
      yurutluk: prev.g.yurutluk,
      soru: ((k.sizinti || !k.acik_uclu) && k.duzeltilmis_soru) ? k.duzeltilmis_soru : prev.uret.soru,
      dogru_maddeler: prev.uret.dogru_maddeler,
      soru_tipi: prev.uret.soru_tipi,
      zorluk: prev.uret.zorluk,
      mulga_notu: prev.uret.mulga_notu || '',
      kapi: {
        gecerli: geceerliMi(k),
        sizinti: k.sizinti,
        maddeye_bagli: k.maddeye_bagli,
        acik_uclu: k.acik_uclu,
        dogru_madde_dogrulama: k.dogru_madde_dogrulama,
        gerekce: k.gerekce,
      },
    }))
  }
)

const temiz = sonuc.filter(Boolean)
const gecerli = temiz.filter(r => r.kapi.gecerli)
log(`Uretilen: ${temiz.length} | Kapiyi gecen (gecerli): ${gecerli.length} | Elenen: ${temiz.length - gecerli.length}`)

return {
  toplam_gorev: gorevler.length,
  uretilen: temiz.length,
  gecerli: gecerli.length,
  elenen: temiz.length - gecerli.length,
  tum_kayitlar: temiz,
}
