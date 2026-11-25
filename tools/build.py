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
import shutil
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

SITE_CSS = """
  body { margin: 0; padding: 12px 0; background: #6b8eb3; font: 11px/1.4 Verdana, Tahoma, Arial, sans-serif; color: #000; }
  a { color: #0000cc; } a:visited { color: #551a8b; } a:hover { color: #cc0000; }
  table { border-collapse: collapse; }
  .main { width: 800px; margin: 0 auto; background: #fff; border: 1px solid #003366; }
  .top { background: #003366; padding: 10px 12px 8px; border-bottom: 3px solid #ffcc00; }
  .logo { font: bold 30px "Arial Black", Arial, sans-serif; color: #ffcc00; text-shadow: 2px 2px 0 #000; letter-spacing: -1px; }
  .logo span { color: #fff; }
  .logo small { font: bold 12px Verdana, sans-serif; color: #9fc3e6; text-shadow: none; letter-spacing: 0; }
  .slogan { color: #cfe0f2; font-size: 11px; margin-top: 2px; }
  .navbar { background: #336699; padding: 4px 8px; border-bottom: 1px solid #003366; }
  .navbar a { color: #fff; font-weight: bold; text-decoration: none; } .navbar a:hover { text-decoration: underline; color: #ffcc00; }
  .navbar span { color: #9fc3e6; padding: 0 3px; }
  .ticker { background: #ffffcc; border-bottom: 1px solid #cccc99; padding: 2px 6px; font-size: 11px; }
  .ticker b { color: #cc0000; }
  .left { width: 172px; background: #dde5ee; border-right: 1px solid #99aacc; padding: 8px 6px; vertical-align: top; }
  .box { border: 1px solid #6688aa; background: #f5f8fb; margin-bottom: 8px; }
  .box .bt { background: #336699; color: #fff; font-weight: bold; padding: 2px 5px; }
  .box .bb { padding: 4px 5px; }
  .po { display: block; margin: 3px 0 0; } .po b { float: right; } .po input { margin: 0 3px 0 0; vertical-align: -2px; }
  .bar { height: 7px; background: #fff; border: 1px solid #6688aa; margin-top: 1px; }
  .bar i { display: block; height: 100%; background: #336699; }
  .pt { margin-top: 4px; font-size: 10px; color: #555; }
  .btnv { display: inline-block; margin-top: 4px; padding: 1px 6px; background: #e0e8f0; border: 2px outset #c0c8d8;
          color: #000; text-decoration: none; font-size: 10px; }
  .cnt { display: inline-block; width: 86px; height: 29px; border: 1px solid #000; font: 9px/1.1 Verdana, sans-serif;
         text-align: center; margin: 2px 0; overflow: hidden; vertical-align: top; }
  .cnt b { display: block; font-size: 10px; }
  .cnt.c1 { background: #000; color: #0f0; } .cnt.c2 { background: #ffcc00; color: #003366; }
  .content { padding: 8px 12px 12px; vertical-align: top; }
  .crumbs { font-size: 10px; margin-bottom: 6px; }
  h1 { font: bold 16px Verdana, sans-serif; color: #003366; margin: 4px 0; }
  .info { font-size: 10px; color: #555; margin-bottom: 6px; }
  .intro { margin: 0 0 8px; padding: 5px 7px; background: #f0f4f8; border: 1px dashed #99aacc; }
  .codes { width: 100%; margin: 10px 0 2px; border: 1px solid #99aacc; }
  .codes th, .codes td { border: 1px solid #99aacc; padding: 3px 5px; vertical-align: top; text-align: left; }
  .codes .sech { background: #003366; color: #ffcc00; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
  .codes .colh { background: #e0e8f0; font-size: 10px; color: #333; }
  .codes .sub { background: #fff3cc; font-weight: bold; color: #664400; }
  .codes tr.r1 td { background: #f0f4f8; }
  .codes td.k { width: 38%; font-weight: bold; }
  .tag { color: #336699; }
  .code { font-weight: bold; color: #cc0000; }
  .new { color: #fff; background: #cc0000; font: bold 9px Verdana, sans-serif; padding: 0 3px; margin-left: 3px;
         animation: blink 1s steps(1) infinite; }
  @keyframes blink { 50% { visibility: hidden; } }
  .th { float: right; margin: 0 0 3px 6px; text-align: center; font-size: 9px; color: #555; }
  .th img { display: block; width: 150px; border: 1px solid #000; }
  .up { text-align: right; font-size: 10px; }
  .map { width: 100%; border: 1px solid #000; display: block; }
  .ci { font-family: "Courier New", monospace; }
  .foot { background: #003366; color: #cfe0f2; font-size: 10px; text-align: center; padding: 6px; border-top: 3px solid #ffcc00; }
  .foot a { color: #ffcc00; }
  details { margin-top: 10px; font-size: 10px; }
  summary { cursor: pointer; color: #cc0000; font-weight: bold; }
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
        if e.get("image") and not e.get("image_source"):
            warnings.append(f"{where}: у картинки нет image_source, на сайт она не попадёт")
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


POLL_JS = """
<script>
(function () {
  var R = "Dee0n/leonida-eggs", OWNER = "Dee0n";
  function h(t) { var d = document.createElement("div"); d.textContent = t; return d.innerHTML; }
  var r = document.getElementById("rnd");
  if (r && window.POOL && POOL.length) {
    var p = POOL[Math.floor(Math.random() * POOL.length)];
    r.innerHTML = '<a href="#e-' + p[0] + '">' + h(p[1]) + '</a>';
  }
  var API = "https://abacus.jasoncameron.dev/", NS = "leonida-eggs";
  function cnt(key, hit) {
    return fetch(API + (hit ? "hit/" : "get/") + NS + "/" + key)
      .then(function (x) { return x.ok ? x.json() : { value: 0 }; })
      .then(function (j) { return j.value || 0; }).catch(function () { return 0; });
  }
  Array.prototype.forEach.call(document.querySelectorAll(".poll"), function (box) {
    var id = box.getAttribute("data-poll"), n = +box.getAttribute("data-n");
    var labels = Array.prototype.map.call(box.querySelectorAll(".po"), function (l) { return l.textContent.trim(); });
    function show(mine) {
      var ks = []; for (var i = 0; i < n; i++) ks.push(cnt("p-" + id + "-" + i, mine === i));
      Promise.all(ks).then(function (v) {
        var tot = v.reduce(function (a, b) { return a + b; }, 0), out = "";
        v.forEach(function (c, i) {
          var pc = tot ? Math.round(c * 100 / tot) : 0;
          out += '<div class="po">' + h(labels[i]) + ' <b>' + pc + '%</b><div class="bar"><i style="width:' + pc + '%"></i></div></div>';
        });
        box.querySelector(".pr").innerHTML = out;
        box.querySelector(".pa").innerHTML = '<div class="pt">Всего ответов: ' + tot +
          (localStorage.getItem("poll-" + id) !== null ? "<br>Спасибо, ваш голос учтён!" : "") + "</div>";
      });
    }
    if (localStorage.getItem("poll-" + id) !== null) { show(-1); return; }
    box.querySelector(".vote").onclick = function () {
      var r = box.querySelector("input:checked");
      if (!r) { alert("Выберите вариант ответа!"); return; }
      localStorage.setItem("poll-" + id, r.value);
      show(+r.value);
    };
    box.querySelector(".res").onclick = function (ev) { ev.preventDefault(); show(-1); };
  });
  var st = document.getElementById("stars");
  if (st) fetch("https://api.github.com/repos/" + R).then(function (x) { return x.json(); })
    .then(function (j) { if (j.stargazers_count !== undefined) st.firstChild.innerHTML = "&#9733; " + j.stargazers_count; })
    .catch(function () {});
})();
</script>
"""


def _new_ids(data: dict, days: int = 2) -> set[str]:
    """Записи, добавленные за последние days дней от meta.date — помечаются NEW!"""
    from datetime import date, timedelta
    try:
        ref = date.fromisoformat(str(data["meta"]["date"]))
    except ValueError:
        return set()
    out = set()
    for e in data["entries"]:
        try:
            if ref - date.fromisoformat(str(e.get("added", ""))) < timedelta(days=days):
                out.add(e["id"])
        except ValueError:
            pass
    return out


def render_html(data: dict, links: dict | None = None, img_prefix: str = "../",
                need_credit: bool = False, print_href: str = "") -> str:
    """Обычная версия: сайт с кодами середины 2000-х (таблицы, меню слева, бегущая строка)."""
    links = links or {}
    meta = data["meta"]
    numbered = numbered_entries(data)
    by_section: dict[str, list[tuple[int, dict]]] = {}
    for num, e in numbered:
        by_section.setdefault(e["section"], []).append((num, e))
    fresh = _new_ids(data)
    y, m, d = str(meta["date"]).split("-")

    def lnk(name: str, text: str | None = None) -> str:
        href = links.get(name, "#")
        return f'<a href="{esc(href)}">{esc(text or name)}</a>'

    def thumb(item: dict) -> str:
        rel = item.get("image", "")
        if not rel or not (ROOT / rel).is_file():
            return ""
        src = item.get("image_source")
        if need_credit and not src:
            return ""
        url = f"{img_prefix}{esc(rel)}"
        cap = f'Скрин: <a href="{esc(src["url"])}">{esc(src["name"])}</a><br>' if src else ""
        return (f'<div class="th"><a href="{url}" target="_blank"><img src="{url}" alt=""></a>'
                f'{cap}(нажми для увеличения)</div>')

    title = f"Коды к игре {meta['game']} :: LEONIDA-CHEATS"
    P: list[str] = []
    add = P.append
    add('<!DOCTYPE html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n')
    add(f"<title>{esc(title)}</title>\n<style>{SITE_CSS}{BTN_CSS}</style>\n</head>\n<body>\n<a name=\"top\"></a>\n")
    add('<table class="main"><tr><td colspan="2" class="top">'
        '<div class="logo">LEONIDA<span>-CHEATS</span> <small>.narod.ru</small></div>'
        '<div class="slogan">Коды, секреты и пасхалки к GTA VI. Без спойлеров.</div></td></tr>\n')
    nav = [lnk("Главная"), lnk("Коды"), lnk("Пасхалки"), lnk("Версия для печати"),
           lnk("Файлы", "Скачать PDF"), lnk("Форум"), lnk("Гостевая книга")]
    add('<tr><td colspan="2" class="navbar">' + "<span>|</span>".join(nav) + "</td></tr>\n")

    latest = sorted(data["entries"], key=lambda e: str(e.get("added", "")), reverse=True)[:8]
    tick = " &nbsp;&nbsp;*&nbsp;&nbsp; ".join(
        f'{esc(".".join(reversed(str(e["added"]).split("-"))))}: {esc(e["title"])}' for e in latest)
    add(f'<tr><td colspan="2" class="ticker"><marquee scrollamount="3"><b>Новое на сайте:</b> {tick}</marquee></td></tr>\n')

    # left column
    add('<tr><td class="left">\n')
    add('<div class="box"><div class="bt">Меню</div><div class="bb">'
        + "".join(f"&raquo; {lnk(n, t)}<br>" for n, t in [
            ("Главная", None), ("Версия для печати", None), ("Файлы", "Скачать PDF"),
            ("Прислать пасхалку", None), ("Форум", None)])
        + "</div></div>\n")
    add('<div class="box"><div class="bt">Разделы</div><div class="bb">')
    for sec in data["sections"]:
        if sec.get("type") == "checklist":
            n = len(data["checklists"].get(sec["id"], []))
        else:
            n = len(by_section.get(sec["id"], []))
        if n:
            add(f'&raquo; <a href="#{esc(sec["id"])}">{esc(sec["title"])}</a> ({n})<br>')
    add("</div></div>\n")
    add('<div class="box"><div class="bt">Обозначения</div><div class="bb">'
        + "<br>".join(f'<span class="tag">{CONFIDENCE_TAGS[k]}</span> {esc(CONFIDENCE_NAMES[k])}'
                      for k in CONFIDENCE_TAGS)
        + '<br><span class="new">NEW!</span> свежее, за последние два дня</div></div>\n')
    add(f'<div class="box"><div class="bt">Статистика</div><div class="bb">Записей: <b>{len(numbered)}</b><br>'
        f'Выпуск: <b>№{meta["issue"]}</b><br>Обновлено: <b>{d}.{m}.{y}</b></div></div>\n')
    if links.get("GitHub"):
        add('<div class="box"><div class="bt">Проект на GitHub</div><div class="bb">'
            f'Исходники, данные и история правок:<br>&raquo; <a href="{esc(links["GitHub"])}">{esc(links["GitHub"].replace("https://", ""))}</a><br>'
            f'Адрес сайта:<br>&raquo; <a href="{esc(SITE_URL)}">{esc(SITE_URL.replace("https://", ""))}</a></div></div>\n')
    polls_path = ROOT / "data" / "polls.json"
    polls = json.loads(polls_path.read_text(encoding="utf-8")) if polls_path.is_file() else []
    for k, poll in enumerate(polls[:2]):
        pid = esc(poll["id"])
        opts = "".join(f'<label class="po"><input type="radio" name="p-{pid}" value="{n}"> {esc(o)}</label>'
                       for n, o in enumerate(poll["options"]))
        add(f'<div class="box poll" data-poll="{pid}" data-n="{len(poll["options"])}">'
            f'<div class="bt">{"Наш опрос" if k == 0 else "Опрос"}</div><div class="bb">'
            f'<b>{esc(poll["question"])}</b><div class="pr">{opts}</div>'
            f'<div class="pa"><button type="button" class="btnv vote">Голосовать</button> '
            f'<a href="#" class="res">Результаты</a></div></div></div>\n')
    pool = [[e["id"], e["title"]] for _n, e in numbered if e["section"] != "controls"]
    pool_js = json.dumps(pool, ensure_ascii=False).replace("</", "<\\/")
    add('<div class="box"><div class="bt">Случайная пасхалка</div><div class="bb" id="rnd">'
        '<a href="#keys">Обнови страницу</a></div></div>\n')
    add(f'<span class="cnt c1"><b>{len(numbered):06d}</b>записей</span> '
        f'<span class="cnt c2"><b>LEONIDA</b>TOP 100</span> '
        f'<span class="cnt c1" id="stars"><b>&#9733; ...</b>на GitHub</span> '
        f'<span class="cnt c2"><b>1024x768</b>IE 6.0</span>\n')
    add("<script>var POOL=" + pool_js + ";</script>\n")
    add("</td>\n")

    # content
    add('<td class="content">\n')
    add(f'<div class="crumbs">{lnk("Главная")} &raquo; {lnk("Коды")} &raquo; PS5 / Xbox Series &raquo; '
        f'<b>{esc(meta["game"])}</b></div>\n')
    add(f"<h1>Коды и пасхалки к игре {esc(meta['game'])}</h1>\n")
    pr = f' | {lnk("Версия для печати", "[Версия для печати]")}' if links.get("Версия для печати") else ""
    add(f'<div class="info">Добавлено: {d}.{m}.{y} | Выпуск №{meta["issue"]} | Записей: {len(numbered)}{pr}</div>\n')
    add(f'<p class="intro">{esc(meta["intro"])}</p>\n')

    for sec in data["sections"]:
        sid = esc(sec["id"])
        if sec.get("type") == "checklist":
            items = data["checklists"].get(sec["id"], [])
            if not items:
                continue
            add(f'<a name="{sid}" id="{sid}"></a><table class="codes"><tr><th colspan="2" class="sech">'
                f'{esc(sec["title"])}</th></tr>\n')
            for i, item in enumerate(items, 1):
                add(f'<tr class="r{i % 2}"><td class="ci" style="width:40px">[&nbsp;&nbsp;]</td><td>{i}. {esc(item)}</td></tr>\n')
            if sec.get("image") and (ROOT / sec["image"]).is_file() and (sec.get("image_source") or not need_credit):
                url = f"{img_prefix}{esc(sec['image'])}"
                src = sec.get("image_source")
                cap = f'<br>Скрин: <a href="{esc(src["url"])}">{esc(src["name"])}</a>' if src else ""
                add(f'<tr><td colspan="2"><a href="{url}" target="_blank"><img class="map" src="{url}" alt=""></a>'
                    f'<small>(нажми для увеличения){cap}</small></td></tr>\n')
            add('</table><div class="up"><a href="#top">[наверх]</a></div>\n')
            continue
        rows = by_section.get(sec["id"], [])
        if not rows:
            continue
        add(f'<a name="{sid}" id="{sid}"></a><table class="codes">'
            f'<tr><th colspan="2" class="sech">{esc(sec["title"])}</th></tr>\n'
            '<tr><th class="colh">Где / комбинация</th><th class="colh">Что делать</th></tr>\n')
        poi_started = False
        for i, (_num, e) in enumerate(rows):
            if e.get("kind") == "poi" and not poi_started:
                poi_started = True
                add(f'<tr><td colspan="2" class="sub">{esc(POI_TITLE)}</td></tr>\n')
            new = '<span class="new">NEW!</span>' if e["id"] in fresh else ""
            add(f'<tr class="r{i % 2}" id="e-{esc(e["id"])}"><td class="k"><span class="tag">{CONFIDENCE_TAGS[e["confidence"]]}</span> '
                f'{iconize(esc(e["title"]))}{new}</td><td>{thumb(e)}{render_hint(e["hint"])}</td></tr>\n')
        add('</table><div class="up"><a href="#top">[наверх]</a></div>\n')

    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for e in data["entries"]:
        for src in e.get("sources", []):
            if src["url"] not in seen:
                seen.add(src["url"])
                sources.append((src["name"], src["url"]))
    if sources:
        add("<details><summary>Источники (осторожно: в заголовках статей есть спойлеры)</summary><p>")
        add(" | ".join(f'<a href="{esc(u)}">{esc(n)}</a>' for n, u in sources))
        add("</p></details>\n")
    add("</td></tr>\n")
    add(f'<tr><td colspan="2" class="foot">&copy; 2026 LEONIDA-CHEATS. При копировании материалов ссылка на сайт '
        f'обязательна.<br>Последнее обновление: {d}.{m}.{y} | {lnk("Прислать пасхалку")} | '
        f'{lnk("Форум")}<br>Сайт лучше всего смотрится в Internet Explorer 6.0 при разрешении 1024x768</td></tr>\n')
    add("</table>\n" + POLL_JS + "</body>\n</html>\n")
    return "".join(P)

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
  .fig { float: right; margin: .4mm 0 1.2mm 3mm; text-indent: 0; text-align: right; }
  .fig img { display: block; max-width: 80mm; max-height: 55mm; border: 1px solid #000; margin-left: auto; }
  .cap { font-size: 7pt; margin-top: .4mm; }
  .fig a, .mapfig a { display: block; }
  @media screen { .fig img, .map { cursor: zoom-in; } }
  .mapfig { break-inside: avoid; margin: 2mm 0 0; }
  .clr { clear: both; }
  .map { display: block; max-width: 120mm; max-height: 90mm; border: 1px solid #000; }
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

BUTTON_TOKEN = r"(?:Треугольник|Круг|Квадрат|Крест|[LR][123])"
BUTTON_SEQ_RE = re.compile(r"^((?:" + BUTTON_TOKEN + r",?\s+){3,}" + BUTTON_TOKEN + r")(.*)$", re.S)

BTN_ICONS = {"Треугольник": ("tri", "△"), "Круг": ("cir", "○"), "Квадрат": ("sq", "□"), "Крест": ("crs", "✕")}
BTN_RE = re.compile(r"(?<![\w-])(Треугольник|Круг|Квадрат|Крест)(?![\w-])")
KEY_RE = re.compile(r"(?<![\w-])([LR][123]|Options)(?![\w-])")
BTN_CSS = """
  .btn { display: inline-block; width: 1.3em; height: 1.3em; line-height: 1.25em; border-radius: 50%;
         color: #fff; text-align: center; font-weight: bold; font-size: 1em; vertical-align: -.2em;
         font-family: "Segoe UI Symbol", "Arial Unicode MS", sans-serif; text-transform: none; letter-spacing: 0; text-indent: 0; }
  .btn.tri { background: #17914a; } .btn.cir { background: #d0312d; } .btn.sq { background: #c2489c; } .btn.crs { background: #2f62c9; }
  .key { display: inline-block; padding: 0 .28em; border: 1px solid #222; border-bottom-width: 2px; border-radius: 3px;
         background: #f2f2f2; color: #000; font-weight: bold; font-size: .92em; line-height: 1.2em; text-transform: none; letter-spacing: 0; text-indent: 0; }
"""


def iconize(escaped: str) -> str:
    """Кнопки геймпада в уже экранированном тексте -> значки. В данных и txt они остаются словами."""
    escaped = BTN_RE.sub(lambda m: f'<span class="btn {BTN_ICONS[m.group(1)][0]}" title="{m.group(1)}">'
                                   f'{BTN_ICONS[m.group(1)][1]}</span>', escaped)
    return KEY_RE.sub(lambda m: f'<span class="key">{m.group(1)}</span>', escaped)


def css_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_hint(text: str) -> str:
    """Комбинацию кнопок пишет как код, остальное как пояснение в скобках."""
    seq = BUTTON_SEQ_RE.match(text)
    if seq:
        rest = seq.group(2).lstrip(" —-.").strip()
        tail = f" ({esc(rest)})" if rest else ""
        return f'<span class="code">{iconize(esc(seq.group(1)))}</span>{iconize(tail)}'
    return iconize(esc(text))


def render_print_html(data: dict, images: bool = True, links: dict | None = None,
                      img_prefix: str = "../", need_credit: bool = False, footer_url: str = "") -> str:
    """Версия под печать: A4, сколько нужно листов; вид распечатки сайта с кодами из середины 2000-х.

    images=False — без картинок (публичная версия). links — {подпись: url} для пунктов меню.
    """
    links = links or {}

    def lnk(name: str) -> str:
        if name in links:
            return f'<a href="{esc(links[name])}">{esc(name)}</a>'
        return f'<span class="a">{esc(name)}</span>'

    def pic(item: dict) -> bool:
        rel = item.get("image", "")
        if not (images and rel and (ROOT / rel).is_file()):
            return False
        return bool(item.get("image_source")) or not need_credit

    def cap(item: dict) -> str:
        src = item.get("image_source")
        if not src:
            return ""
        return (f'<div class="cap">Скрин: <a href="{esc(src["url"])}">{esc(src["name"])}</a></div>')

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
        .replace('"__FILE__"', css_string(footer_url or
                 "file://C:\\Documents%20and%20Settings\\User\\Мои%20документы\\" + file_name))
        .replace('"__DATE__"', css_string(f"{d}.{m}.{y}"))
    )

    parts: list[str] = []
    add = parts.append
    add('<!DOCTYPE html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n')
    add(f"<title>{esc(page_title)}</title>\n")
    add("<style>" + css + BTN_CSS + "</style>\n</head>\n<body>\n")
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
            if pic(sec):
                src = f'{img_prefix}{esc(sec["image"])}'
                add(f'<div class="mapfig"><a href="{src}" target="_blank"><img class="map" src="{src}" alt=""></a>'
                    f'{cap(sec)}</div>\n')
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
                f'<span class="k">{iconize(esc(e["title"]))}</span> = {render_hint(e["hint"])}'
            )
            if pic(e):
                src = f'{img_prefix}{esc(e["image"])}'
                add(f'<div class="e pic"><div class="fig"><a href="{src}" target="_blank" title="Открыть в полном размере">'
                    f'<img src="{src}" alt=""></a>'
                    f'{cap(e)}</div>{line}</div>\n')
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
    lines.append(f"{meta['title']} - {meta['subtitle']} №{meta['issue']}")
    lines.append(f"{meta['date']} · {meta['game']}")
    lines.append("")
    lines.append(meta["intro"])
    lines.append("● подтверждено, ○ одно сообщение, ◇ слух")
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
SITE_URL = "https://dee0n.github.io/leonida-eggs/"


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
        "GitHub": REPO_URL,
    }
    index = SITE / "index.html"
    # картинки публикуются только с указанием источника (image_source)
    img_dir = SITE / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir()
    published = 0
    for item in list(data["entries"]) + list(data["sections"]):
        rel = item.get("image")
        if rel and item.get("image_source") and (ROOT / rel).is_file():
            shutil.copy2(ROOT / rel, SITE / rel)
            published += 1
    print(f"Картинок на сайте: {published}")
    print_page = SITE / "print.html"
    print_page.write_text(render_print_html(data, links=links, img_prefix="", need_credit=True,
                                            footer_url=SITE_URL + "print.html"), encoding="utf-8")
    site_links = dict(links, **{"Версия для печати": "print.html"})
    index.write_text(render_html(data, links=site_links, img_prefix="", need_credit=True), encoding="utf-8")
    print(f"Готово: {print_page}")
    (SITE / "leonida_easter_eggs.txt").write_text(render_txt(data), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Готово: {index}")
    if make_pdf(print_page, SITE / pdf_name):
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
        "hint": "Куда идти и что нажать. Без описания того, что увидишь.",
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
