#!/usr/bin/env python3
"""Сборка листка пасхалок ЛЕОНИДЫ.

    python tools/build.py check     # проверить данные
    python tools/build.py build     # собрать out/*.html и out/*.txt
    python tools/build.py new "Название" city   # напечатать заготовку записи

Только стандартная библиотека. Без внешних зависимостей и без сети.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "entries.json"
OUT = ROOT / "out"

CONFIDENCE_TAGS = {"confirmed": "●", "single": "○", "rumor": "◇"}
KINDS = ("egg", "poi")
POI_TITLE = "Точки интереса: просто посмотреть"
CONFIDENCE_NAMES = {"confirmed": "подтверждено", "single": "одно сообщение", "rumor": "слух"}

# Слова, которые почти всегда означают, что автор описывает награду, а не путь к ней.
SPOILER_WORDS = [
    "награда", "награду", "получишь", "получите", "выдаст", "окажется",
    "сюрприз", "спойлер", "в итоге ты", "в конце ты",
]

CSS = """
  :root { --ink:#161616; --paper:#f2eee3; --red:#a11f1f; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 28px 16px 48px;
    background: #2b2b2b;
    font-family: "Courier New", Courier, monospace;
    color: var(--ink);
  }
  .sheet {
    max-width: 820px; margin: 0 auto; padding: 34px 38px 28px;
    background: var(--paper);
    background-image: repeating-linear-gradient(0deg, rgba(0,0,0,.025) 0 1px, transparent 1px 3px);
    box-shadow: 0 12px 40px rgba(0,0,0,.55);
    border: 2px solid var(--ink);
    position: relative;
  }
  .stamp {
    position: absolute; top: 18px; right: 24px;
    border: 3px double var(--red); color: var(--red);
    padding: 6px 10px; font-weight: bold; font-size: 12px;
    transform: rotate(-7deg); letter-spacing: 1px; opacity: .85;
  }
  h1 { font-size: 30px; margin: 0 0 2px; letter-spacing: 3px; }
  .sub { font-size: 12px; letter-spacing: 1px; margin-bottom: 18px; }
  .rule { border-top: 3px solid var(--ink); margin: 14px 0 10px; }
  .dash { border-top: 1px dashed var(--ink); margin: 16px 0 10px; }
  h2 { font-size: 14px; letter-spacing: 2px; margin: 22px 0 8px; text-transform: uppercase; }
  ol { margin: 0; padding-left: 24px; }
  li { margin-bottom: 7px; font-size: 14px; line-height: 1.45; }
  .k { font-weight: bold; }
  .tag { font-size: 11px; padding: 0 4px; border: 1px solid var(--ink); margin-left: 4px; white-space: nowrap; }
  .legend { font-size: 12px; border: 1px dashed var(--ink); padding: 8px 10px; margin: 10px 0 4px; }
  .foot { margin-top: 26px; border-top: 3px solid var(--ink); padding-top: 10px; font-size: 12px; }
  .foot p { margin: 4px 0; }
  details { margin-top: 18px; font-size: 11px; }
  summary { cursor: pointer; font-size: 11px; letter-spacing: 1px; }
  a { color: var(--ink); }
  .cut { text-align: center; letter-spacing: 4px; font-size: 11px; margin: 18px 0 0; }
  @media print {
    body { background: #fff; padding: 0; }
    .sheet { box-shadow: none; border: none; max-width: none; }
  }
"""


def load_data(path: Path = DATA) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate(data: dict, strict: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta: отсутствует или не объект")
        meta = {}
    for key in ("title", "subtitle", "issue", "date", "game", "intro"):
        if key not in meta:
            errors.append(f"meta: нет поля {key}")
    if not isinstance(meta.get("issue"), int):
        errors.append("meta.issue: должно быть целым числом")

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections: нужен непустой список")
        sections = []
    section_ids = []
    for i, sec in enumerate(sections):
        sid = sec.get("id")
        if not sid:
            errors.append(f"sections[{i}]: нет id")
            continue
        if not re.fullmatch(r"[a-z0-9-]+", sid):
            errors.append(f"sections[{i}].id: только a-z, 0-9 и дефис")
        if sid in section_ids:
            errors.append(f"sections: повторяется id {sid}")
        section_ids.append(sid)
        if not sec.get("title"):
            errors.append(f"sections[{i}]: нет title")

    checklists = data.get("checklists", {})
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries: нужен непустой список")
        entries = []

    seen_ids = set()
    for i, e in enumerate(entries):
        where = f"entries[{i}] ({e.get('id', '?')})"
        for key in ("id", "section", "title", "hint", "confidence", "sources", "added", "added_by"):
            if key not in e:
                errors.append(f"{where}: нет поля {key}")
        eid = e.get("id", "")
        if eid in seen_ids:
            errors.append(f"{where}: повторяется id")
        seen_ids.add(eid)
        if not re.fullmatch(r"[a-z0-9-]+", str(eid)):
            errors.append(f"{where}: id только из a-z, 0-9 и дефиса")
        if e.get("section") not in section_ids:
            errors.append(f"{where}: неизвестная секция {e.get('section')!r}")
        conf = e.get("confidence")
        if conf not in CONFIDENCE_TAGS:
            errors.append(f"{where}: confidence должен быть confirmed / single / rumor")
        sources = e.get("sources")
        if not isinstance(sources, list):
            errors.append(f"{where}: sources должен быть списком")
            sources = []
        for j, src in enumerate(sources):
            if not isinstance(src, dict) or not src.get("name") or not src.get("url"):
                errors.append(f"{where}: sources[{j}] нужен name и url")
        if conf == "confirmed" and len(sources) < 2:
            msg = f"{where}: confirmed требует минимум 2 источника, есть {len(sources)}"
            (errors if strict else warnings).append(msg)
        if conf == "single" and len(sources) != 1:
            warnings.append(f"{where}: single обычно требует ровно 1 источник, есть {len(sources)}")

        hint = str(e.get("hint", ""))
        if len(hint) > 400:
            errors.append(f"{where}: hint длиннее 400 символов")
        if len(str(e.get("title", ""))) > 80:
            errors.append(f"{where}: title длиннее 80 символов")
        low = hint.lower()
        for word in SPOILER_WORDS:
            if word in low:
                warnings.append(f"{where}: в hint слово «{word}» — похоже на описание награды")
        if not hint.strip():
            errors.append(f"{where}: пустой hint")
        if e.get("kind", "egg") not in KINDS:
            errors.append(f"{where}: kind должен быть egg или poi")
        if e.get("image") and not (ROOT / e["image"]).is_file():
            warnings.append(f"{where}: нет файла картинки {e['image']}, в листок не попадёт")

    for sec in sections:
        if sec.get("image") and not (ROOT / sec["image"]).is_file():
            warnings.append(f"sections ({sec.get('id')}): нет файла картинки {sec['image']}, в листок не попадёт")

    for sid, items in checklists.items():
        if sid not in section_ids:
            errors.append(f"checklists: секции {sid} нет в sections")
        if not isinstance(items, list):
            errors.append(f"checklists.{sid}: должен быть список строк")

    for sec in sections:
        if sec.get("type") == "checklist" and sec["id"] not in checklists:
            errors.append(f"sections: у checklist-секции {sec['id']} нет данных в checklists")

    return errors, warnings


def numbered_entries(data: dict) -> list[tuple[int, dict]]:
    result: list[tuple[int, dict]] = []
    counter = 0
    for sec in data["sections"]:
        if sec.get("type") == "checklist":
            continue
        rows = [e for e in data["entries"] if e["section"] == sec["id"]]
        # сначала пасхалки с действием, потом точки интереса
        rows.sort(key=lambda e: e.get("kind", "egg") == "poi")
        for e in rows:
            counter += 1
            result.append((counter, e))
    return result


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def render_html(data: dict) -> str:
    meta = data["meta"]
    numbered = numbered_entries(data)
    by_section: dict[str, list[tuple[int, dict]]] = {}
    for num, e in numbered:
        by_section.setdefault(e["section"], []).append((num, e))

    parts: list[str] = []
    add = parts.append
    add("<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n")
    add(f"<title>{esc(meta['title'])} — листок пасхалок №{esc(meta['issue'])}</title>\n")
    add("<style>" + CSS + "</style>\n</head>\n<body>\n<div class=\"sheet\">\n")
    add("  <div class=\"stamp\">ХОДЯЧАЯ КОПИЯ</div>\n")
    add(f"  <h1>{esc(meta['title'])}</h1>\n")
    add(
        f"  <div class=\"sub\">{esc(meta['subtitle'])} №{esc(meta['issue'])} &nbsp;·&nbsp; "
        f"{esc(meta['date'])} &nbsp;·&nbsp; {esc(meta['game'])}</div>\n"
    )
    add("  <div class=\"rule\"></div>\n")
    add("  <div class=\"legend\">\n")
    add(f"    {esc(meta['intro'])}<br>\n")
    add("    <span class=\"tag\">●</span> подтверждено несколькими источниками &nbsp;\n")
    add("    <span class=\"tag\">○</span> одно сообщение, не проверено &nbsp;\n")
    add("    <span class=\"tag\">◇</span> слух &nbsp;\n")
    add("    <span class=\"tag\">✂</span> оторви и носи в кармане\n")
    add("  </div>\n")

    # Содержание: только секции с записями, потом чек-листы, потом слухи — в порядке sections.
    for sec in data["sections"]:
        if sec.get("type") == "checklist":
            items = data["checklists"].get(sec["id"], [])
            add(f"  <h2>{esc(sec['title'])}</h2>\n")
            add("  <div class=\"legend\" style=\"border-style:solid\">\n")
            add("    Отмечай найденное, не открывай заранее:\n    <ol style=\"margin-top:8px\">\n")
            for item in items:
                add(f"      <li>{esc(item)}</li>\n")
            add("    </ol>\n  </div>\n")
            continue

        rows = by_section.get(sec["id"], [])
        if not rows:
            continue
        add(f"  <h2>{esc(sec['title'])}</h2>\n")
        add(f"  <ol start=\"{rows[0][0]}\">\n")
        for num, e in rows:
            tag = CONFIDENCE_TAGS[e["confidence"]]
            add(
                f"    <li><span class=\"tag\">{tag}</span> "
                f"<span class=\"k\">{esc(e['title'])}.</span> {esc(e['hint'])}</li>\n"
            )
        add("  </ol>\n")

    total = len(numbered)
    add("  <div class=\"dash\"></div>\n")
    add("  <div class=\"legend\">\n")
    add("    <b>Правила листка.</b> Не спойлери друзьям. Не пости скриншоты в первый день. "
        "Если нашёл что-то новое — впиши в раздел V и передай дальше.\n")
    add("  </div>\n")
    add("  <div class=\"cut\">✂ — — — — — — — — — — — — — — — — — — — — — — — — — — — —</div>\n")
    add("  <div class=\"foot\">\n")
    add(f"    <p>{esc(meta['title'])} · ЛИСТОК №{esc(meta['issue'])} · собрано {esc(meta['date'])}.</p>\n")
    add(f"    <p>Записей: {total}. Полного списка не существует: игре идут дни, игроки находят новое каждый час.</p>\n")
    add("  </div>\n")

    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for e in data["entries"]:
        for src in e.get("sources", []):
            url = src["url"]
            if url not in seen:
                seen.add(url)
                sources.append((src["name"], url))
    if sources:
        add("  <details>\n")
        add("    <summary>ИСТОЧНИКИ — ОСТОРОЖНО, В ЗАГОЛОВКАХ ЕСТЬ СПОЙЛЕРЫ</summary>\n    <p>\n")
        links = [
            f'      <a href="{esc(url)}">{esc(name)}</a>' for name, url in sources
        ]
        add(" ·\n".join(links) + "\n")
        add("    </p>\n  </details>\n")

    add("</div>\n</body>\n</html>\n")
    return "".join(parts)


PRINT_CSS = """
  @page {
    size: A4 portrait; margin: 16mm 13mm 16mm;
    @top-left { content: "__TITLE__"; font: 10pt "Times New Roman", Times, serif; color: #000; vertical-align: bottom; padding-bottom: 3mm; }
    @top-right { content: "Стр. " counter(page) " из " counter(pages); font: 10pt "Times New Roman", Times, serif; color: #000; vertical-align: bottom; padding-bottom: 3mm; }
    @bottom-left { content: "__FILE__"; font: 10pt "Times New Roman", Times, serif; color: #000; vertical-align: top; padding-top: 3mm; }
    @bottom-right { content: "__DATE__"; font: 10pt "Times New Roman", Times, serif; color: #000; vertical-align: top; padding-top: 3mm; }
  }
  html, body { margin: 0; padding: 0; background: #fff; }
  body { font-family: Verdana, Tahoma, sans-serif; color: #000; font-size: 9.6pt; line-height: 1.32; }
  h1 { font: bold 13pt Verdana, Tahoma, sans-serif; margin: 0 0 2mm; }
  .intro { margin: 0 0 1mm; }
  .legend { margin: 0 0 3mm; }
  h3 { font: bold 9.6pt Verdana, Tahoma, sans-serif; margin: 2mm 0 1mm; break-after: avoid; }
  h2 { font: bold 10.5pt Verdana, Tahoma, sans-serif; text-decoration: underline; margin: 3.6mm 0 1.4mm; break-after: avoid; }
  .e { margin: 0 0 .6mm 6mm; text-indent: -6mm; break-inside: avoid; }
  .k { font-weight: bold; text-transform: uppercase; }
  .code { font-weight: bold; letter-spacing: 1pt; }
  .ci { margin: 0 0 .5mm; }
  .e.pic { display: flow-root; margin-bottom: 1.4mm; }
  .e img { float: right; max-width: 80mm; max-height: 55mm; margin: .4mm 0 1.2mm 3mm; border: 1px solid #000; }
  .clr { clear: both; }
  .map { display: block; max-width: 120mm; max-height: 90mm; margin: 2mm 0 0; border: 1px solid #000; break-inside: avoid; }
  .a { color: #0000cc; text-decoration: underline; }
  .site { width: 100%; border-collapse: collapse; border-bottom: 2px solid #000; margin: 0 0 1mm; }
  .site td { padding: 0 0 1mm; vertical-align: bottom; }
  .logo { font: bold 20pt Arial, Helvetica, sans-serif; letter-spacing: -.5pt; }
  .logo i { font-style: normal; font-weight: normal; }
  .logo small { font-size: 9pt; font-weight: normal; letter-spacing: 0; }
  .slogan { text-align: right; font: italic 8.5pt Verdana, Tahoma, sans-serif; }
  .nav { font-size: 8.5pt; margin: 0 0 1.5mm; }
  .crumbs { font-size: 8pt; margin: 0 0 3mm; }
  .info { font-size: 8pt; margin: 0 0 2.5mm; }
  hr { border: 0; border-top: 1px solid #000; margin: 3mm 0 2mm; }
  .bottom { font-size: 8pt; }
  .bottom p { margin: 0 0 1mm; }
  a { color: #0000cc; }
  @media screen { body { max-width: 184mm; margin: 6mm auto 10mm; padding: 0 5mm; } }
"""

BUTTON_TOKEN = r"(?:△|○|×|✕|□|[LR][123])"
BUTTON_SEQ_RE = re.compile(r"^((?:" + BUTTON_TOKEN + r"\s+){3,}" + BUTTON_TOKEN + r")(.*)$", re.S)


def css_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_hint(text: str) -> str:
    """Комбинацию кнопок пишет как код, остальное как пояснение в скобках."""
    seq = BUTTON_SEQ_RE.match(text)
    if seq:
        rest = seq.group(2).lstrip(" —").strip()
        tail = f" ({esc(rest)})" if rest else ""
        return f'<span class="code">{esc(seq.group(1))}</span>{tail}'
    return esc(text)


def render_print_html(data: dict, images: bool = True, links: dict | None = None) -> str:
    """Версия под печать: A4, сколько нужно листов; вид распечатки сайта с кодами из середины 2000-х.

    images=False — без картинок (публичная версия). links — {подпись: url} для пунктов меню.
    """
    links = links or {}

    def lnk(name: str) -> str:
        if name in links:
            return f'<a href="{esc(links[name])}">{esc(name)}</a>'
        return f'<span class="a">{esc(name)}</span>'

    def pic(rel: str) -> bool:
        return images and bool(rel) and (ROOT / rel).is_file()

    meta = data["meta"]
    numbered = numbered_entries(data)
    by_section: dict[str, list[tuple[int, dict]]] = {}
    for num, e in numbered:
        by_section.setdefault(e["section"], []).append((num, e))

    page_title = f"Коды к игре {meta['game']} :: LEONIDA-CHEATS.narod.ru"
    file_name = f"GTA%20VI%20-%20kody%20{meta['issue']}.htm"
    y, m, d = str(meta["date"]).split("-")
    css = (
        PRINT_CSS.replace('"__TITLE__"', css_string(page_title))
        .replace('"__FILE__"', css_string("file://C:\\Documents%20and%20Settings\\User\\Мои%20документы\\" + file_name))
        .replace('"__DATE__"', css_string(f"{d}.{m}.{y}"))
    )

    parts: list[str] = []
    add = parts.append
    add('<!DOCTYPE html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n')
    add(f"<title>{esc(page_title)}</title>\n")
    add("<style>" + css + "</style>\n</head>\n<body>\n")
    nav = ["Главная", "Новости", "Коды", "Пасхалки", "Прохождения", "Карты", "Файлы", "Форум", "Гостевая книга"]
    add('<table class="site"><tr><td class="logo">LEONIDA<i>-CHEATS</i><small>.narod.ru</small></td>'
        '<td class="slogan">коды, секреты, пасхалки, прохождения</td></tr></table>\n')
    add('<div class="nav">' + " | ".join(lnk(n) for n in nav) + "</div>\n")
    add('<div class="crumbs"><span class="a">Главная</span> &raquo; <span class="a">Коды</span> &raquo; '
        f'<span class="a">PS5 / Xbox Series</span> &raquo; <b>{esc(meta["game"])}</b></div>\n')
    add(f"<h1>Коды и пасхалки к игре {esc(meta['game'])}</h1>\n")
    add(f'<div class="info">Добавлено: {d}.{m}.{y} | Выпуск №{meta["issue"]} | Записей: {len(numbered)}</div>\n')
    add(f'<p class="intro">{esc(meta["intro"])}</p>\n')
    add(
        '<p class="legend">'
        + " &nbsp; ".join(f"{CONFIDENCE_TAGS[k]} {esc(CONFIDENCE_NAMES[k])}" for k in CONFIDENCE_TAGS)
        + "</p>\n"
    )

    for sec in data["sections"]:
        if sec.get("type") == "checklist":
            items = data["checklists"].get(sec["id"], [])
            if not items:
                continue
            add(f"<h2>{esc(sec['title'])}</h2>\n")
            for item in items:
                add(f'<div class="ci">[&nbsp;&nbsp;] {esc(item)}</div>\n')
            if pic(sec.get("image", "")):
                add(f'<img class="map" src="../{esc(sec["image"])}" alt="">\n')
            continue

        rows = by_section.get(sec["id"], [])
        if not rows:
            continue
        add(f"<h2>{esc(sec['title'])}</h2>\n")
        poi_started = False
        for _num, e in rows:
            if e.get("kind") == "poi" and not poi_started:
                poi_started = True
                add(f'<h3>{esc(POI_TITLE)}</h3>\n')
            line = (
                f'{CONFIDENCE_TAGS[e["confidence"]]} '
                f'<span class="k">{esc(e["title"])}</span> = {render_hint(e["hint"])}'
            )
            if pic(e.get("image", "")):
                add(f'<div class="e pic"><img src="../{esc(e["image"])}" alt="">{line}</div>\n')
            else:
                add(f'<div class="e">{line}</div>\n')

    add('<div class="clr"></div><hr>\n<div class="bottom">')
    add(f'<p>[ {lnk("Наверх")} ] &nbsp; [ {lnk("Обсудить на форуме")} ] &nbsp; '
        f'[ {lnk("Версия для печати")} ] &nbsp; [ {lnk("Прислать пасхалку")} ]</p>')
    add(f"<p>&copy; 2026 LEONIDA-CHEATS. Последнее обновление: {d}.{m}.{y}</p></div>\n")
    add("</body>\n</html>\n")
    return "".join(parts)


def render_txt(data: dict) -> str:
    meta = data["meta"]
    numbered = numbered_entries(data)
    by_section: dict[str, list[tuple[int, dict]]] = {}
    for num, e in numbered:
        by_section.setdefault(e["section"], []).append((num, e))

    lines: list[str] = []
    lines.append(f"{meta['title']} — {meta['subtitle']} №{meta['issue']}")
    lines.append(f"{meta['date']} · {meta['game']}")
    lines.append("")
    lines.append(meta["intro"])
    lines.append("● — подтверждено, ○ — одно сообщение, ◇ — слух")
    lines.append("=" * 62)

    for sec in data["sections"]:
        if sec.get("type") == "checklist":
            items = data["checklists"].get(sec["id"], [])
            lines.append("")
            lines.append(sec["title"].upper())
            for i, item in enumerate(items, 1):
                lines.append(f"  [ ] {i}. {item}")
            continue
        rows = by_section.get(sec["id"], [])
        if not rows:
            continue
        lines.append("")
        lines.append(sec["title"].upper())
        poi_started = False
        for num, e in rows:
            if e.get("kind") == "poi" and not poi_started:
                poi_started = True
                lines.append(f"  -- {POI_TITLE} --")
            tag = CONFIDENCE_TAGS[e["confidence"]]
            lines.append(f"  {num:>2}. [{tag}] {e['title']}. {e['hint']}")

    lines.append("")
    lines.append("=" * 62)
    lines.append(f"Записей: {len(numbered)}. Полного списка не существует.")
    return "\n".join(lines) + "\n"


def cmd_check(args: argparse.Namespace) -> int:
    try:
        data = load_data()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"НЕ ПРОЧИТАТЬ {DATA}: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(data, strict=args.strict)
    for w in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {w}")
    for e in errors:
        print(f"ОШИБКА: {e}", file=sys.stderr)
    total = len(numbered_entries(data))
    print(f"Записей: {total}. Ошибок: {len(errors)}. Предупреждений: {len(warnings)}.")
    return 1 if errors else 0


def cmd_build(args: argparse.Namespace) -> int:
    try:
        data = load_data()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"НЕ ПРОЧИТАТЬ {DATA}: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(data, strict=args.strict)
    for w in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {w}")
    if errors:
        for e in errors:
            print(f"ОШИБКА: {e}", file=sys.stderr)
        print("Сборка остановлена: сначала исправь данные.", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    issue = data["meta"]["issue"]
    html_path = out_dir / f"leonida_easter_eggs_{issue}.html"
    txt_path = out_dir / f"leonida_easter_eggs_{issue}.txt"
    print_path = out_dir / f"leonida_easter_eggs_{issue}_print.html"
    html_path.write_text(render_html(data), encoding="utf-8")
    txt_path.write_text(render_txt(data), encoding="utf-8")
    print_path.write_text(render_print_html(data), encoding="utf-8")
    print(f"Готово: {html_path}")
    print(f"Готово: {txt_path}")
    print(f"Готово: {print_path}")
    pdf_path = print_path.with_suffix(".pdf")
    if make_pdf(print_path, pdf_path):
        print(f"Готово: {pdf_path}")
    else:
        print("PDF не собран. HTML для печати готов.")
    print(f"Записей: {len(numbered_entries(data))}.")
    return 0


SITE = ROOT / "docs"
REPO_URL = "https://github.com/Dee0n/leonida-eggs"


def cmd_site(args: argparse.Namespace) -> int:
    """Публичная версия для GitHub Pages: docs/index.html и PDF без картинок."""
    data = load_data()
    errors, warnings = validate(data)
    if errors:
        for e in errors:
            print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1
    SITE.mkdir(exist_ok=True)
    pdf_name = "leonida_easter_eggs.pdf"
    links = {
        "Главная": "./",
        "Наверх": "#",
        "Коды": "./",
        "Пасхалки": "./",
        "Версия для печати": pdf_name,
        "Файлы": pdf_name,
        "Форум": f"{REPO_URL}/issues",
        "Гостевая книга": f"{REPO_URL}/issues",
        "Обсудить на форуме": f"{REPO_URL}/issues",
        "Прислать пасхалку": f"{REPO_URL}/issues/new?template=egg.yml",
    }
    index = SITE / "index.html"
    index.write_text(render_print_html(data, images=False, links=links), encoding="utf-8")
    (SITE / "leonida_easter_eggs.txt").write_text(render_txt(data), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Готово: {index}")
    if make_pdf(index, SITE / pdf_name):
        print(f"Готово: {SITE / pdf_name}")
    else:
        print("PDF для сайта не собран.")
    return 0


BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def make_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Печатает HTML в PDF через headless Chrome/Edge. Колонтитулы рисует сам листок (@page)."""
    import subprocess

    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        return False
    try:
        pdf_path.unlink(missing_ok=True)
    except PermissionError:
        print(f"PDF открыт в другой программе, закрой его и запусти build ещё раз: {pdf_path}")
        return False
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
        capture_output=True, timeout=120,
    )
    return pdf_path.exists()


def cmd_new(args: argparse.Namespace) -> int:
    slug = re.sub(r"[^a-z0-9]+", "-", args.id.lower()).strip("-") or "new-entry"
    template = {
        "id": slug,
        "section": args.section,
        "title": args.title,
        "hint": "Куда идти и что нажать — без описания того, что увидишь.",
        "confidence": "single",
        "sources": [{"name": "Название издания", "url": "https://example.com/..."}],
        "added": "2026-11-24",
        "added_by": "agent",
    }
    print(json.dumps(template, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Листок пасхалок ЛЕОНИДЫ")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--strict", action="store_true", help="предупреждения считать ошибками")
    common.add_argument("--out", default=None, help="куда писать результат (по умолчанию out/)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", parents=[common], help="проверить данные")
    p_check.set_defaults(func=cmd_check)

    p_build = sub.add_parser("build", parents=[common], help="собрать html и txt")
    p_build.set_defaults(func=cmd_build)

    p_site = sub.add_parser("site", help="собрать публичную версию в docs/ (без картинок)")
    p_site.set_defaults(func=cmd_site)

    p_new = sub.add_parser("new", help="напечатать заготовку записи")
    p_new.add_argument("title", help="название записи")
    p_new.add_argument("section", help="id секции, например city")
    p_new.add_argument("--id", default="", help="slug для id (по умолчанию из названия)")
    p_new.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
