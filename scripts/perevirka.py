#!/usr/bin/env python3
"""Перевірка українського тексту за словниками ukrainianizer.

Запуск:
    python3 scripts/perevirka.py FILE [FILE ...]
    python3 scripts/perevirka.py --all

Виходить з кодом 1, якщо знайдено помилки рівня ERROR. Попередження (WARN)
код виходу не міняють — це місця, куди варто подивитися очима.

Скрипт бере слова буквально й не бачить контексту. Він не заміна редактурі,
а сито, яке ловить те, що людина пропускає на десятому перечитуванні.
"""

import argparse
import glob
import re
import statistics
import sys
import unicodedata
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
SLOVNYKY = KOREN / ".cursor/skills/ukrainianizer/references"


# ── Витягання прози ─────────────────────────────────────────────────────────
#
# Головна складність: файли-словники складаються з поганих слів за задумом.
# Рахувати «ну» у файлі про слова-паразити безглуздо. Тому перед перевіркою
# викидаємо все, що є цитатою поганого прикладу, а не авторською мовою.

def pereliк(riadok):
    """Чи рядок — перелік слів через кому, а не речення.

    Файл про граматику містить переліки самих слів («навіть, майже, приблизно,
    принаймні…»). Для скрипта це виглядає як речення, де кожне друге слово
    взято в коми, і він рапортує вісімнадцять пунктуаційних помилок поспіль.

    Ознака переліку — не частка коротких відрізків, а їхній безперервний ряд:
    у звичайному реченні коми теж є, але між ними стоять цілі частини.
    """
    ryad = maks = 0
    for c in riadok.split(","):
        if 0 < len(c.split()) <= 2 and "." not in c:
            ryad += 1
            maks = max(maks, ryad)
        else:
            ryad = 0
    return maks >= 4


def vytiahnuty_prozu(text):
    """Лишає тільки авторські речення. Повертає (проза, кількість_викинутих)."""
    bez_kodu = re.sub(r"```.*?```", "", text, flags=re.S)

    prozа_riadky = []
    vykynuto = 0
    for riadok in bez_kodu.split("\n"):
        golyj = riadok.strip()
        if not golyj:
            continue
        # таблиці, цитати, заголовки, YAML
        if golyj.startswith(("|", ">", "#", "---", "===")):
            vykynuto += 1
            continue
        # рядки словника «поганий → добрий»
        if "→" in golyj or "←" in golyj:
            vykynuto += 1
            continue
        # пункти-переліки маркерів усередині словників
        if golyj.startswith(("- ❌", "- ✅", "**Слова-маркери:**", "**Заміни:**",
                             "**На що дивитися:**", "**До:**", "**Після:**")):
            vykynuto += 1
            continue
        if pereliк(golyj):
            vykynuto += 1
            continue
        prozа_riadky.append(riadok)

    chastka_prozy = len(prozа_riadky) / max(len(prozа_riadky) + vykynuto, 1)
    proza = "\n".join(prozа_riadky)
    # згадка слова ≠ вживання слова: «власне» в лапках або в `коді` — це приклад
    proza = re.sub(r"«[^»]{0,60}»", " ", proza)
    proza = re.sub(r"`[^`]{0,80}`", " ", proza)
    proza = re.sub(r'"[^"]{0,60}"', " ", proza)
    # від посилання лишається підпис, адреса викидається: інакше кожен http
    # роздуває лічильник слів і злипає перелік джерел в одне «речення»
    proza = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", proza)
    return proza, vykynuto, chastka_prozy


def rechennia(proza):
    """Речення. Рядок — завжди межа: пункт списку не тягнеться в наступний."""
    out = []
    for riadok in proza.split("\n"):
        riadok = re.sub(r"^\s*[-*]\s+", "", riadok)
        for r in re.split(r"(?<=[.!?])\s+", riadok):
            r = r.strip()
            if len(r.split()) >= 3:
                out.append(r)
    return out


# ── Читання словників ───────────────────────────────────────────────────────

# Службові слова, які лишаються після різання комою («зрозуміло, що» → «що»)
# і як окремі терміни ловлять кожне друге речення.
SLUZHBOVI = {"що", "то", "як", "а", "і", "й", "та", "чи", "бо", "же", "ж", "у", "в", "з"}


def terminy_z_tablyc(shlyah):
    """Бере перший стовпчик тих таблиць, чия шапка позначена ❌.

    Позначка обов'язкова. Без неї в словник протікають шапки інших таблиць
    («Робота», «Показник») і перетворюються на слова, яких треба уникати.
    """
    if not shlyah.exists():
        return []
    out = []
    slovnykova = False
    for riadok in shlyah.read_text(encoding="utf-8").split("\n"):
        if not riadok.startswith("|"):
            slovnykova = False
            continue
        komirky = [k.strip() for k in riadok.strip("|").split("|")]
        if len(komirky) < 2:
            continue
        if "❌" in komirky[0]:
            slovnykova = True
            continue
        if not slovnykova or komirky[0].startswith("-"):
            continue
        # Дужка в статті — це уточнення контексту («так (як заповнювач)»,
        # «просто (як підсилювач)»). Контексту скрипт не бачить, а без нього
        # такий термін ловить кожне вживання звичайного слова. Лишаємо очам.
        if "(" in komirky[0]:
            continue
        komirka = komirky[0].strip().lower().strip("*")
        # «абсолютно, повністю, цілком» — три терміни в одній комірці.
        # Але «можна сказати, що» — один термін, і різати його комою не можна,
        # інакше в словник потрапляє голе «що» й ловить кожне друге речення.
        chastyny = [c.strip() for c in komirka.split(",")]
        terminy = chastyny if all(c and " " not in c for c in chastyny) else [komirka]
        for t in terminy:
            if "+" in t or "%" in t or t.startswith("х ") or t in SLUZHBOVI:
                continue
            if 1 < len(t) < 45:
                out.append(t)
    return out


def terminy_z_markeriv(shlyah):
    """Бере переліки після «**Слова-маркери:**» в ai-patterns.md."""
    if not shlyah.exists():
        return []
    out = []
    for m in re.finditer(r"\*\*Слова-маркери:\*\*(.+)", shlyah.read_text(encoding="utf-8")):
        for t in re.split(r"[,;]", m.group(1)):
            t = t.strip().strip("*").lower()
            if 2 < len(t) < 45 and "/" not in t:
                out.append(t)
    return out


def zbraty_slovnyky():
    grupy = {
        "русизм": terminy_z_tablyc(SLOVNYKY / "rusyzmy.md"),
        "англіцизм": terminy_z_tablyc(SLOVNYKY / "anglicyzmy.md"),
        "канцелярит": terminy_z_tablyc(SLOVNYKY / "kancelyaryzmy.md"),
        "плеоназм": terminy_z_tablyc(SLOVNYKY / "pleonazmy.md"),
        "паразит": terminy_z_tablyc(SLOVNYKY / "parazyty.md"),
        "AI-лексика": terminy_z_markeriv(SLOVNYKY / "ai-patterns.md"),
    }
    return {k: sorted(set(v), key=len, reverse=True) for k, v in grupy.items() if v}


# ── Структурні перевірки ────────────────────────────────────────────────────
#
# Ці категорії взято з asaulyuk/humanizer-ukr (MIT) — у словниках ukrainianizer
# їх немає взагалі. Вони ловлять не слова, а конструкції.

# Питомі прикметники на -учий/-ючий. Вони збігаються за формою з активними
# дієприкметниками, але дієприкметниками не є: «балакучий» правильне слово,
# а «існуючий» — калька. Список закритий, тому виняток безпечний.
PRYKMETNYKY_UCH = {
    "балакуч", "летюч", "колюч", "гаряч", "зряч", "тремтяч", "сипуч", "повзуч",
    "кипуч", "пахуч", "живуч", "плакуч", "співуч", "скрипуч", "тягуч", "тонюч",
    "жагуч", "болюч", "рвуч", "минуч", "линюч", "квітуч", "видюч", "ходяч",
}

STRUKTURNI = [
    ("дієприкметник -ючий", r"\b\w+[юу]ч(?:ий|а|е|і|ого|ому|им|их|ими)\b",
     "активні дієприкметники в українській не вживаються: «керуючий» → «керівник», «наступаючий» → «що настає»"),
    ("заперечний паралелізм", r"\bне (?:просто|лише|тільки|стільки) [^,.]{2,40}, (?:а|але|це)\b",
     "калька з «not just X, but Y» — один із найпомітніших маркерів машинного тексту"),
    ("розщеплений присудок", r"\b(?:здійсн|провод|виконує|робить|надає|веде)\w* \w{4,}(?:ння|ція)\b",
     "дієслово розтягнуто в пару «дієслово + іменник»: «здійснює аналіз» → «аналізує»"),
    ("Title Case", r"(?:\b[А-ЯІЇЄҐ][а-яіїєґ']{2,}\s+){2}[А-ЯІЇЄҐ][а-яіїєґ']{2,}",
     "українська не має Title Case: велика літера лише перша та у власних назвах"),
]


# Слова, які ніколи не бувають вставними, тобто ніколи не виділяються комами.
# Перелік закритий, тому перевірка точна: кома з обох боків — граматична помилка.
# Джерело: webpen.com.ua, розділ про вставні та вставлені конструкції.
NE_VSTAVNI = [
    "навіть", "майже", "приблизно", "принаймні", "все-таки", "мовби", "немовби",
    "наче", "неначе", "ніби", "нібито", "адже", "притому", "при цьому",
    "тим часом", "якраз", "як-не-як", "буквально", "якби",
]


# Слова, що збігаються за формою з наказовим способом множини, але ним не є.
NE_NAKAZ = {"навіть"}

ZAJMENNYKY = {
    "ти": r"\b(ти|тебе|тобі|тобою|твій|твоя|твоє|твої|твого|твоєї|твоєму|твоїх)\b",
    "ви": r"\b(ви|вас|вам|вами|ваш|ваша|ваше|ваші|вашого|вашої|вашому|ваших)\b",
}


def holos(shlyah):
    """Читає файл голосу: регістр, межа довжини речення, заборонені слова."""
    text = shlyah.read_text(encoding="utf-8")
    rehistr = re.search(r"\*\*Регістр:\*\*\s*(ти|ви)", text)
    mezha = re.search(r"\*\*Максимум слів у реченні:\*\*\s*(\d+)", text)
    return {
        "регістр": rehistr.group(1) if rehistr else None,
        "межа": int(mezha.group(1)) if mezha else None,
        "заборонені": terminy_z_tablyc(shlyah),
    }


def zvertannia(proza):
    """Форми звертання в тексті. Повертає (кількість ти-форм, кількість ви-форм)."""
    nyzhnia = proza.lower()
    ty = len(re.findall(ZAJMENNYKY["ти"], nyzhnia))
    vy = len(re.findall(ZAJMENNYKY["ви"], nyzhnia))
    nakaz = [m for m in re.findall(r"\b\w{3,}(?:іть|айте|уйте|ийте)\b", nyzhnia)
             if m not in NE_NAKAZ]
    return ty, vy + len(nakaz)


def ukrainskyj(text):
    """Частка кирилиці серед літер. Англійські скіли перевіряти цим нема сенсу."""
    kyryl = len(re.findall(r"[а-яіїєґА-ЯІЇЄҐ]", text))
    lat = len(re.findall(r"[a-zA-Z]", text))
    return kyryl / max(kyryl + lat, 1)


def homohlify(text):
    """Латинські літери, підмінені на позиції кириличних (aеорсхі тощо)."""
    pastky = set("aAeEoOpPcCxXyBHKMTiI")
    znajdeni = []
    for m in re.finditer(r"[а-яіїєґА-ЯІЇЄҐ]+[a-zA-Z]+[а-яіїєґА-ЯІЇЄҐ]*|"
                         r"[а-яіїєґА-ЯІЇЄҐ]*[a-zA-Z]+[а-яіїєґА-ЯІЇЄҐ]+", text):
        slovo = m.group()
        if any(c in pastky for c in slovo if c.isascii()):
            znajdeni.append(slovo)
    return znajdeni


NEVYDYMI = ["\u200b", "\u200c", "\u200d", "\u00ad", "\u202f", "\u2060", "\ufeff"]


# ── Статистика ──────────────────────────────────────────────────────────────

def statystyka(proza):
    rech = rechennia(proza)
    dovzhyny = [len(r.split()) for r in rech]
    slova = re.findall(r"[а-яіїєґА-ЯІЇЄҐ']+", proza.lower())
    # Пороги взято з чеклиста самого ukrainianizer: «Variance в довжині > 20 слів?»
    # і «Є коротке речення (1-3 слова)?». Розкид, а не стандартне відхилення.
    return {
        "речень": len(rech),
        "слів": len(slova),
        "розкид": (max(dovzhyny) - min(dovzhyny)) if dovzhyny else 0,
        "коротких": sum(1 for d in dovzhyny if d <= 3),
        "середнє": round(statistics.mean(dovzhyny), 1) if dovzhyny else 0,
        "TTR": round(len(set(slova)) / len(slova), 3) if slova else 0,
        "найдовше": max(dovzhyny) if dovzhyny else 0,
    }


# ── Перевірка одного файлу ──────────────────────────────────────────────────

def perevirty(shlyah, slovnyky, holos_pravyla=None):
    text = shlyah.read_text(encoding="utf-8")
    proza, vykynuto, chastka_prozy = vytiahnuty_prozu(text)
    nyzhnia = proza.lower()
    problemy = []

    for symvol in NEVYDYMI:
        if symvol in text:
            nazva = unicodedata.name(symvol, f"U+{ord(symvol):04X}")
            problemy.append(("ERROR", "вотермарка", f"{nazva} × {text.count(symvol)}", ""))

    for slovo in homohlify(text):
        problemy.append(("ERROR", "гомогліф", slovo, "латинська літера всередині кириличного слова"))

    parazytiv = 0
    for grupa, terminy in slovnyky.items():
        for t in terminy:
            n = len(re.findall(rf"(?<![а-яіїєґ]){re.escape(t)}(?![а-яіїєґ])", nyzhnia))
            if n:
                problemy.append(("WARN", grupa, f"{t} × {n}", ""))
                if grupa == "паразит":
                    parazytiv += n

    # Пороги з parazyty.md: до 0,5% чисто, 0,5–1,5% норма, понад 1,5% чистити.
    slova_prozy = len(re.findall(r"[а-яіїєґ']+", nyzhnia))
    shchilnist = parazytiv / slova_prozy * 100 if slova_prozy else 0
    if shchilnist > 1.5:
        problemy.append(("WARN", "щільність паразитів", f"{shchilnist:.2f}%",
                         "понад 1,5% — за порогом із parazyty.md текст треба чистити"))

    for slovo in NE_VSTAVNI:
        n = len(re.findall(rf",\s*{re.escape(slovo)}\s*,", nyzhnia))
        if n:
            problemy.append(("WARN", "зайві коми", f"«, {slovo},» × {n}",
                             f"«{slovo}» ніколи не буває вставним словом і комами не виділяється"))

    if holos_pravyla:
        for t in holos_pravyla["заборонені"]:
            n = len(re.findall(rf"(?<![а-яіїєґ]){re.escape(t)}(?![а-яіїєґ])", nyzhnia))
            if n:
                problemy.append(("WARN", "проти голосу", f"{t} × {n}", ""))

        ochikuvanyj = holos_pravyla["регістр"]
        if ochikuvanyj:
            ty, vy = zvertannia(proza)
            chuzhyh = vy if ochikuvanyj == "ти" else ty
            svoyih = ty if ochikuvanyj == "ти" else vy
            if chuzhyh and chuzhyh > svoyih:
                inshyj = "ви" if ochikuvanyj == "ти" else "ти"
                problemy.append(("WARN", "регістр", f"{inshyj}-форм {chuzhyh}, {ochikuvanyj}-форм {svoyih}",
                                 f"голос вимагає звертання на «{ochikuvanyj}»"))

    for nazva, vzir, poyasnennia in STRUKTURNI:
        znajdeni = re.findall(vzir, proza)
        if nazva.startswith("дієприкметник"):
            znajdeni = [z for z in znajdeni
                        if not any(z.lower().startswith(k) for k in PRYKMETNYKY_UCH)]
        if znajdeni:
            zrazok = znajdeni[0] if isinstance(znajdeni[0], str) else " ".join(znajdeni[0])
            problemy.append(("WARN", nazva, f"{len(znajdeni)}× напр. {zrazok!r}", poyasnennia))

    # тире: в українській обов'язкове, але три й більше на абзац — машинний ритм.
    # Рахуємо за оригінальним розбиттям на абзаци: у прозі порожні рядки з'їдено
    # разом із таблицями, і весь файл злипається в один фальшивий абзац.
    for i, abzac in enumerate(re.sub(r"```.*?```", "", text, flags=re.S).split("\n\n"), 1):
        riadky = [r for r in abzac.split("\n")
                  if not re.match(r"\s*([|\-*>#]|\d+\.)", r)]
        n = "\n".join(riadky).count("—")
        if n >= 3:
            problemy.append(("WARN", "тире", f"{n} в абзаці {i}",
                             "1–2 на абзац норма, від 3 — ознака машинного ритму"))

    return statystyka(proza), problemy, vykynuto, chastka_prozy


def main():
    p = argparse.ArgumentParser(description="Перевірка українського тексту")
    p.add_argument("files", nargs="*")
    p.add_argument("--all", action="store_true", help="усі .md, крім словників")
    p.add_argument("--holos", help="файл голосу з voices/")
    args = p.parse_args()

    if args.all:
        # include_hidden — інакше все під .cursor/ тихо випадає з перевірки
        shlyahy = [Path(f) for f in glob.glob(str(KOREN / "**/*.md"),
                                              recursive=True, include_hidden=True)
                   if "/.git/" not in f and "/plugins/" not in f]
    else:
        shlyahy = [Path(f) for f in args.files]
    if not shlyahy:
        p.error("нема що перевіряти")

    holos_pravyla = holos(Path(args.holos)) if args.holos else None
    slovnyky = zbraty_slovnyky()
    vsoho = sum(len(v) for v in slovnyky.values())
    print(f"Словники: {vsoho} термінів у {len(slovnyky)} групах "
          f"({', '.join(f'{k} {len(v)}' for k, v in slovnyky.items())})\n")

    pomylok = 0
    for shlyah in sorted(shlyahy):
        stat, problemy, vykynuto, chastka_prozy = perevirty(shlyah, slovnyky, holos_pravyla)
        errors = [x for x in problemy if x[0] == "ERROR"]
        pomylok += len(errors)

        try:
            nazva = shlyah.resolve().relative_to(KOREN)
        except ValueError:
            nazva = shlyah

        chastka_kyr = ukrainskyj(shlyah.read_text(encoding="utf-8"))
        if chastka_kyr < 0.5:
            if not args.all:
                print(f"── {nazva}\n   пропущено: кирилиці {chastka_kyr:.0%}, це не український текст\n")
            continue

        print(f"── {nazva}")
        print(f"   {stat['слів']} слів, {stat['речень']} речень, розкид {stat['розкид']}, "
              f"коротких {stat['коротких']}, TTR {stat['TTR']}, "
              f"середнє {stat['середнє']}; викинуто {vykynuto} рядків цитат")

        # Пороги ритму розраховані на суцільну прозу. У словнику чи довіднику,
        # де половина файлу — таблиці, короткі однотипні речення нормальні:
        # міряти там burstiness означає вимагати від переліку звучати як есей.
        dovidnyk = chastka_prozy < 0.35
        if dovidnyk:
            print(f"   (довідник: проза {chastka_prozy:.0%} рядків — пороги ритму не застосовано)")
        if stat["слів"] >= 150 and not dovidnyk:
            if stat["розкид"] <= 20:
                print(f"   ! розкид довжини {stat['розкид']} — речення однакової довжини")
            if not stat["коротких"]:
                print("   ! немає жодного речення на 1–3 слова")
            if stat["TTR"] < 0.35:
                print("   ! TTR під 0.35 — бідна лексика")
        mezha = (holos_pravyla or {}).get("межа") or 45
        if stat["найдовше"] > mezha:
            print(f"   ! речення на {stat['найдовше']} слів, межа {mezha} — розбити")

        if not problemy:
            print("   чисто\n")
            continue
        for riven, grupa, shcho, chomu in problemy:
            znak = "✗" if riven == "ERROR" else "·"
            hvist = f"  ({chomu})" if chomu else ""
            print(f"   {znak} [{grupa}] {shcho}{hvist}")
        print()

    print(f"Помилок рівня ERROR: {pomylok}")
    return 1 if pomylok else 0


if __name__ == "__main__":
    sys.exit(main())
