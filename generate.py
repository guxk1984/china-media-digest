#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
境外主流媒体涉华监测 · 日报生成器

- 抓取 sources.yaml 中各媒体的公开 RSS
- 关键词粗筛涉华报道（不耗 LLM）
- 主题粗分类（关键词启发式）
- 可选 LLM：生成中文摘要 + 立场标注 + 要点；无 Key 时退化为原文摘要
- 渲染移动端优先的 index.html（GitHub Pages 可直接托管）

不依赖本机：设计为在 GitHub Actions 等云端环境运行。
"""
import os
import json
import html
import hashlib
import datetime
from pathlib import Path

import yaml
import feedparser
import requests

ROOT = Path(__file__).resolve().parent
SOURCES = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
KEYWORDS = [k.lower() for k in SOURCES.get("keywords", [])]
SOURCES_LIST = SOURCES.get("sources", [])
UA = "Mozilla/5.0 (compatible; ChinaMediaDigest/1.0)"

THEME_RULES = [
    ("经济贸易", ["economy", "trade", "tariff", "yuan", "gdp", "market",
                "export", "import", "stock", "business", "finance", "investment", "currency"]),
    ("科技", ["tech", "semiconductor", "chip", " technology", "software",
             "science", "startup", "ai ", "a.i."]),
    ("军事安全", ["military", "army", "navy", "defense", "defence", "missile",
                "war", "security", "troop", "weapon", "drill", "soldier"]),
    ("社会文化", ["culture", "society", "education", "health", "covid",
                "people", "protest", "student", "film", "sport", "school"]),
]
THEME_ORDER = ["地缘政治", "经济贸易", "科技", "军事安全", "社会文化"]


def beijing_now():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)


def is_china(text):
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def classify_theme(text):
    t = text.lower()
    for theme, kws in THEME_RULES:
        if any(k in t for k in kws):
            return theme
    return "地缘政治"


def fetch_feed(src, session):
    try:
        r = session.get(src["rss"], timeout=25, headers={"User-Agent": UA})
        data = feedparser.parse(r.content)
    except Exception as e:
        print(f"[warn] {src['name']} 抓取失败: {e}")
        return []
    items = []
    for e in data.entries:
        title = e.get("title", "")
        summary = e.get("summary", "") or e.get("description", "")
        link = e.get("link", "")
        published = e.get("published", "")
        blob = f"{title} {summary}"
        if not is_china(blob):
            continue
        items.append({
            "title": title.strip(),
            "summary_raw": summary.strip(),
            "link": link,
            "source": src["name"],
            "country": src.get("country", ""),
            "attr": src.get("attr", ""),
            "published": published,
            "theme": classify_theme(blob),
        })
    return items


def llm_process(items):
    """可选：用 OpenAI 兼容接口做中文摘要 + 立场 + 要点。无 Key 则退化。"""
    key = os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not key:
        for it in items:
            raw = it["summary_raw"]
            it["summary"] = (raw[:260] + "…") if raw else it["title"]
            it["stance"] = f"{it['attr']}｜倾向待标注（无 LLM Key）"
            it["points"] = []
        return

    sys_prompt = (
        "你是境外涉华新闻监测助手。对每条英文报道，输出严格 JSON："
        "{\"summary\":\"150-200字简体中文摘要\",\"stance\":\"媒体属性(官方/公营/商业)｜报道倾向(客观/偏正面/偏负面/对抗性)\","
        "\"points\":[\"要点1\",\"要点2\"]}。"
        "涉及台湾、香港、澳门须统一写作中国台湾/中国香港/中国澳门，不作为国家。"
        "只输出 JSON，不要解释。"
    )
    for it in items:
        user = f"媒体：{it['source']}（{it['country']}）\n标题：{it['title']}\n正文：{it['summary_raw'][:2000]}"
        try:
            resp = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user}], "temperature": 0.3},
                timeout=60,
            )
            content = resp.json()["choices"][0]["message"]["content"]
            obj = json.loads(content[content.find("{"):content.rfind("}") + 1])
            it["summary"] = obj.get("summary", it["title"])
            it["stance"] = obj.get("stance", f"{it['attr']}｜倾向待标注")
            it["points"] = obj.get("points", [])
            it["theme"] = obj.get("theme", it["theme"])
        except Exception as e:
            print(f"[warn] LLM 处理失败 {it['source']}: {e}")
            raw = it["summary_raw"]
            it["summary"] = (raw[:260] + "…") if raw else it["title"]
            it["stance"] = f"{it['attr']}｜倾向待标注"
            it["points"] = []


def render(items, date_str):
    groups = {}
    for it in items:
        groups.setdefault(it["theme"], []).append(it)

    theme_blocks = ""
    for th in THEME_ORDER:
        lst = groups.get(th)
        if not lst:
            continue
        cards = ""
        for it in lst:
            points = "".join(f"<li>{html.escape(p)}</li>" for p in it.get("points", []))
            points_html = f'<ul class="points">{points}</ul>' if points else ""
            cards += f"""
      <article class="card">
        <h3><a href="{html.escape(it['link'])}" target="_blank" rel="noopener">{html.escape(it['title'])}</a></h3>
        <div class="meta">{html.escape(it['source'])} · {html.escape(it['country'])}</div>
        <p class="summary">{html.escape(it.get('summary', it['title']))}</p>
        <div class="stance">立场：{html.escape(it.get('stance', ''))}</div>
        {points_html}
      </article>"""
        theme_blocks += f'<section><h2>{th}</h2>{cards}</section>'

    top = items[:3]
    top_html = "".join(
        f"<li>{html.escape(i['title'])}（{html.escape(i['source'])}）</li>" for i in top)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>境外涉华监测日报 · {date_str}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #f5f6f8; color: #1a1a1a; line-height: 1.6; }}
  header {{ position: sticky; top: 0; z-index: 10; padding: 14px 16px;
           background: #c8102e; color: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}
  header h1 {{ margin: 0; font-size: 19px; }}
  header .date {{ font-size: 12px; opacity: .9; margin-top: 2px; }}
  .wrap {{ max-width: 680px; margin: 0 auto; padding: 12px 12px 40px; }}
  .top {{ background: #fff; border-radius: 12px; padding: 12px 14px; margin: 12px 0;
         border-left: 4px solid #c8102e; }}
  .top h2 {{ margin: 0 0 6px; font-size: 15px; color: #c8102e; }}
  .top ul {{ margin: 0; padding-left: 18px; font-size: 14px; }}
  section h2 {{ font-size: 16px; margin: 18px 4px 8px; color: #333; }}
  .card {{ background: #fff; border-radius: 12px; padding: 12px 14px; margin: 10px 0;
          box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .card h3 {{ margin: 0 0 4px; font-size: 15px; line-height: 1.4; }}
  .card h3 a {{ color: #1a1a1a; text-decoration: none; }}
  .card h3 a:visited {{ color: #666; }}
  .meta {{ font-size: 12px; color: #c8102e; font-weight: 600; }}
  .summary {{ font-size: 14px; color: #333; margin: 6px 0; }}
  .stance {{ font-size: 12px; color: #777; }}
  .points {{ margin: 6px 0 0; padding-left: 18px; font-size: 13px; color: #444; }}
  footer {{ text-align: center; font-size: 11px; color: #999; margin-top: 24px; padding: 0 12px; }}
</style>
</head>
<body>
<header>
  <h1>境外涉华监测日报</h1>
  <div class="date">最后更新：{date_str}（北京时间）· 收录 {len(items)} 条</div>
</header>
<div class="wrap">
  <div class="top"><h2>今日要点</h2><ul>{top_html}</ul></div>
  {theme_blocks}
  <footer>本日报由 AI 自动生成，摘要与立场标注仅供参考，重要信息以原文链接为准。</footer>
</div>
</body>
</html>"""


def main():
    now = beijing_now()
    date_str = now.strftime("%Y-%m-%d")
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    seen = set()
    all_items = []
    for src in SOURCES_LIST:
        for it in fetch_feed(src, session):
            h = hashlib.md5(it["link"].encode()).hexdigest()
            if h in seen or not it["link"]:
                continue
            seen.add(h)
            all_items.append(it)

    # 按发布时间倒序（无法解析的排后面）
    def sort_key(x):
        return x.get("published", "")
    all_items.sort(key=sort_key, reverse=True)
    all_items = all_items[:12]

    llm_process(all_items)

    out = render(all_items, date_str)
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(out, encoding="utf-8")
    (docs / f"digest-{date_str}.html").write_text(out, encoding="utf-8")
    (docs / "latest.json").write_text(json.dumps(
        {"date": date_str, "count": len(all_items)}, ensure_ascii=False), encoding="utf-8")

    print(f"[done] 收录 {len(all_items)} 条，已写入 docs/index.html")


if __name__ == "__main__":
    main()
