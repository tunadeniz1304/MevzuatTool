"""Kenar-numaralı (İsviçre-geleneği) madde KORUMA testleri — FAZ 0.2 / E-tuzağı.

TMK 4721, TBK 6098, TTK 6102, FSEK 5846, Anayasa 2709 maddelerinde `madde_baslik`
ve gövde `1. Genel olarak` / `A. ...` / `I. ...` gibi MARJİNAL (kenar) numarayla başlar.
Bu numaralar fıkra/bent DEĞİL — hukukun kitap-stili kenar başlıklarıdır.

Bu testler MEVCUT (doğru) davranışı kilitler: marjinal numara bent SAYILMAZ. FAZ 3'te
numaralı-fıkra desteği (B3) eklenince bu 998 maddeyi toplu bozmamak için — testler
FAZ 3 öncesi yeşil, sonrası DA yeşil kalmalı (regresyon kilidi).

Gövdeler gerçek korpus maddelerinden alınmıştır (id'ler yorumda).
"""
from kanun.fikra import parse_fikralar


def test_marginal_letter_title_not_bent():
    # TMK 4721 M1 (103249-1): madde_baslik 'A. Hukukun uygulanması'. Gövde başlığı
    # tekrarlamaz; tek paragraf hüküm. 'A.' bir kenar başlığı, bent DEĞİL.
    body = ("Kanun, sözüyle ve özüyle değindiği bütün konularda uygulanır. Kanunda "
            "uygulanabilir bir hüküm yoksa, hâkim, örf ve âdet hukukuna göre karar verir.")
    f = parse_fikralar(body)[0]
    assert f.no is None
    assert f.bentler == []


def test_marginal_roman_title_not_bent():
    # TMK 4721 M3 (103249-3): 'II. İyiniyet'. Roman kenar numarası bent değil.
    body = ("Kanunun iyiniyete hukukî bir sonuç bağladığı durumlarda, asıl olan iyiniyetin "
            "varlığıdır. Ancak, durumun gereklerine göre kendisinden beklenen özeni "
            "göstermeyen kimse iyiniyet iddiasında bulunamaz.")
    f = parse_fikralar(body)[0]
    assert f.bentler == []


def test_marginal_number_title_not_bent():
    # TBK 6098 M63 (103273-63): ' 1. Genel olarak'. Satır-başı numara kenar başlığı, bent değil.
    body = ("Kanunun verdiği yetkiye dayanan ve bu yetkinin sınırları içinde kalan bir fiil, "
            "zarara yol açsa bile, hukuka aykırı sayılmaz.")
    f = parse_fikralar(body)[0]
    assert f.bentler == []


def test_marginal_number_with_real_harf_bentler_preserved():
    # TTK 6102 M4 (103039-4): madde_baslik '1. Genel olarak' MARJİNAL; ama gövde gerçek
    # '(1)' paren-fıkrası + içinde GERÇEK 'a) b) c)' harf-bentler. Marjinal '1.' bent
    # SAYILMAMALI, gerçek harf-bentler KORUNMALI. ⚠️ En kritik vaka (FAZ 3 hedefi).
    body = ("(1) Her iki tarafın da ticari işletmesiyle ilgili hususlardan doğan hukuk "
            "davaları ve çekişmesiz yargı işleri ile tarafların tacir olup olmadıklarına "
            "bakılmaksızın; a) Bu Kanunda, b) Türk Medenî Kanununun rehin hükümlerinde, "
            "c) Borçlar Kanununun malvarlığı devrinde, d) Fikrî mülkiyet hukukunda, "
            "e) Borsa ve pazarlarda, f) Bankalara ilişkin işlerde ticari dava sayılır.")
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]
    # gerçek harf-bentler korunur; marjinal '1.' bent listesinde YOK (harf-stili kazanır)
    assert [b.isaret for b in fs[0].bentler] == ["a)", "b)", "c)", "d)", "e)", "f)"]
    # B3 KİLİDİ: harf-bentler ÜST seviyede kalır (alt_bentler'e İNMEZ). Marjinal '1.' başlığı
    # iki-seviyeli modu TETİKLEMEZ — gövdede sıralı '1. 2.' numara-KOŞUSU yok (tek '(1)' paren).
    assert all(b.alt_bentler == [] for b in fs[0].bentler)


def test_consecutive_marginal_numbers_not_numbered_bentler():
    # Anayasa 2709 M1 (103165-1) deseni: gövde sonuna sonraki maddenin kenar başlığı
    # sızabilir ('... Cumhuriyettir. II. Cumhuriyetin nitelikleri'). Roman/numara kenar
    # başlıkları numara-bent SAYILMAZ (mevcut sıralı-koşu + Roman-değil mantığı eler).
    body = "Türkiye Devleti bir Cumhuriyettir. II. Cumhuriyetin nitelikleri"
    f = parse_fikralar(body)[0]
    assert f.bentler == []
