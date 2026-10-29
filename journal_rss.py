#!/usr/bin/env python3
"""抓取中文社会学期刊官网最新目录，生成 RSS 2.0 订阅源。

仅使用 Python 标准库。生成三个 feed 文件到 feeds/ 目录：
  - feeds/sociological-studies.xml  《社会学研究》
  - feeds/society-shu.xml           《社会》
  - feeds/sociological-review.xml   《社会学评论》

重复运行时会与已有 feed 合并，保留历史条目（每刊最多保留 60 条）。
"""

import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds")
MAX_ITEMS = 60
CN_TZ = timezone(timedelta(hours=8))


def fetch(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"抓取失败 {url}: {last}")


def strip_tags(html):
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_item(title, link, authors="", description="", pub_date=None, category=""):
    return {
        "title": title,
        "link": link,
        "authors": authors,
        "description": description,
        "pub_date": pub_date,
        "category": category,
    }


def parse_issue_date(html):
    m = re.search(r"刊出日期[：:]\s*(\d{4})-(\d{2})-(\d{2})", html)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        tzinfo=CN_TZ)
    return None


def bimonthly_date(year, issue):
    """双月刊按 期号*2 估算出版月份。"""
    try:
        return datetime(int(year), max(1, min(12, int(issue) * 2)), 1, tzinfo=CN_TZ)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- 《社会》

def fetch_society():
    url = "https://www.society.shu.edu.cn/CN/current"
    html = fetch(url)
    issue_date = parse_issue_date(html)

    token_re = re.compile(
        r'<div class="wenzhanglanmu">(?P<col>.*?)</div>'
        r"|<DIV id='art(?P<aid>\d+)' class=noselectrow>(?P<block>.*?)(?=<DIV id='art|$)",
        re.S,
    )
    art_re = re.compile(
        r'href="(?P<link>https://www\.society\.shu\.edu\.cn/CN/Y\d+/V\d+/I\d+/\d+)"'
        r' class="biaoti">(?P<title>.*?)</a>.*?'
        r'<dd class="zuozhe">(?P<authors>.*?)</dd>.*?'
        r'<dd class="kmnjq">(?P<cite>.*?)</dd>',
        re.S,
    )
    abs_re = re.compile(r'<div id="Abstract(?P<aid>\d+)"[^>]*>(?P<abs>.*?)</div>', re.S)
    abstracts = {m.group("aid"): strip_tags(m.group("abs")) for m in abs_re.finditer(html)}

    items, column = [], ""
    for m in token_re.finditer(html):
        if m.group("col") is not None:
            column = strip_tags(m.group("col"))
            continue
        block = m.group("block")
        a = art_re.search(block)
        if not a:
            continue
        cite = strip_tags(a.group("cite")).replace("\xa0", " ")
        ym = re.search(r"(\d{4}),\s*\d+\((\d+)\)", cite)
        pub = issue_date or (bimonthly_date(*ym.groups()) if ym else None)
        desc_parts = []
        if abstracts.get(m.group("aid")):
            desc_parts.append(abstracts[m.group("aid")])
        desc_parts.append(f"《社会》{cite.strip()}")
        items.append(make_item(
            title=strip_tags(a.group("title")),
            link=a.group("link"),
            authors=strip_tags(a.group("authors")),
            description="\n".join(desc_parts),
            pub_date=pub,
            category=column,
        ))
    return items, "社会", "https://www.society.shu.edu.cn/", "society-shu.xml"


# ------------------------------------------------------------ 《社会学评论》

def fetch_review(with_abstract=True):
    url = "http://src.ruc.edu.cn/CN/current"
    html = fetch(url)
    issue_date = parse_issue_date(html)

    blocks = re.split(r'<li id="art\d+"', html)[1:]
    items = []
    for block in blocks:
        t = re.search(
            r'<div class="j-title-1">\s*<a href="(?P<link>http://src\.ruc\.edu\.cn/CN/Y\d+/V\d+/I\d+/\d+)"[^>]*>(?P<title>.*?)</a>',
            block, re.S)
        if not t:
            continue
        am = re.search(r'<div class="j-author">(?P<a>.*?)</div>', block, re.S)
        cm = re.search(r'<span class="j-volumn">(?P<c>.*?)</span>', block, re.S)
        cite = strip_tags(cm.group("c")) if cm else ""
        ym = re.search(r"(\d{4}),\s*\d+\((\d+)\)", cite)
        pub = issue_date or (bimonthly_date(*ym.groups()) if ym else None)

        abstract = ""
        if with_abstract:
            try:
                page = fetch(t.group("link"), retries=2)
                m = re.search(r'<meta name="citation_abstract" content="(?P<a>.*?)"\s*/?>',
                              page, re.S)
                if m:
                    abstract = re.sub(r"\s+", " ", m.group("a")).strip()
                time.sleep(0.5)
            except Exception:
                pass

        desc_parts = [p for p in (abstract, cite) if p]
        items.append(make_item(
            title=strip_tags(t.group("title")),
            link=t.group("link"),
            authors=strip_tags(am.group("a")) if am else "",
            description="\n".join(desc_parts),
            pub_date=pub,
        ))
    return items, "社会学评论", "http://src.ruc.edu.cn/", "sociological-review.xml"


# ------------------------------------------------------------ 《社会学研究》

def fetch_studies():
    url = "https://shxyj.ajcass.com/"
    html = fetch(url)

    year = re.search(r'id="iYear" value="(\d{4})"', html)
    issue = re.search(r'id="iIsue" value="(\d+)"', html)
    pub = bimonthly_date(year.group(1), issue.group(1)) if year and issue else None

    art_re = re.compile(
        r'<div class="article" id="issue (?P<aid>\d+)">.*?'
        r'<a id="a (?P=aid)" href="(?P<link>/Magazine/Show\?id=\d+)"[^>]*>'
        r'(?P<title>.*?)<span class="hod pop">(?P<authors>.*?)</span></a>.*?'
        r'<p class="hod pop">(?P<cite>.*?):',
        re.S,
    )
    col_re = re.compile(
        r'<span style="font-weight:bold;color:#003a62;font-size: 14px; ">(.*?)</span>'
    )
    columns = [(m.start(), strip_tags(m.group(1))) for m in col_re.finditer(html)]

    # 首页还包含点击排行、下载排行等标签页，同一文章会出现多次，按 ID 去重
    items, seen = [], set()
    for m in art_re.finditer(html):
        if m.group("aid") in seen:
            continue
        seen.add(m.group("aid"))
        column = ""
        for pos, name in columns:
            if pos < m.start():
                column = name
            else:
                break
        cite = strip_tags(m.group("cite"))
        items.append(make_item(
            title=strip_tags(m.group("title")),
            link="https://shxyj.ajcass.com" + m.group("link"),
            authors=strip_tags(m.group("authors")),
            description=f"《社会学研究》{cite}",
            pub_date=pub,
            category=column,
        ))
    return items, "社会学研究", "https://shxyj.ajcass.com/", "sociological-studies.xml"


# ---------------------------------------------------------------- RSS 输出

def item_to_xml(item, indent="    "):
    lines = [f"{indent}<item>"]
    lines.append(f"{indent}  <title>{escape(item['title'])}</title>")
    lines.append(f"{indent}  <link>{escape(item['link'])}</link>")
    lines.append(f'{indent}  <guid isPermaLink="true">{escape(item["link"])}</guid>')
    if item.get("authors"):
        lines.append(f"{indent}  <author>{escape(item['authors'])}</author>")
    if item.get("category"):
        lines.append(f"{indent}  <category>{escape(item['category'])}</category>")
    desc = item.get("description") or ""
    if item.get("authors"):
        desc = f"作者：{item['authors']}\n" + desc
    lines.append(f"{indent}  <description>{escape(desc)}</description>")
    if item.get("pub_date"):
        lines.append(f"{indent}  <pubDate>{format_datetime(item['pub_date'])}</pubDate>")
    lines.append(f"{indent}</item>")
    return "\n".join(lines)


def read_existing_items(path):
    """从已有 feed 中读回旧条目，用于合并。"""
    if not os.path.exists(path):
        return []
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return []
    items = []
    for el in tree.getroot().findall("./channel/item"):
        def txt(tag):
            e = el.find(tag)
            return e.text if e is not None and e.text else ""
        items.append({
            "title": txt("title"),
            "link": txt("link"),
            "authors": txt("author"),
            "description": txt("description"),
            "category": txt("category"),
            "pub_date": None,
            "pub_date_raw": txt("pubDate"),
        })
    return items


def write_feed(path, journal, site_url, items):
    existing = read_existing_items(path)
    new_links = {i["link"] for i in items}
    merged = items + [i for i in existing if i["link"] not in new_links]
    merged = merged[:MAX_ITEMS]

    now = format_datetime(datetime.now(CN_TZ))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{escape(journal)}</title>",
        f"    <link>{escape(site_url)}</link>",
        f"    <description>《{escape(journal)}》最新目录（非官方，抓自期刊官网）</description>",
        "    <language>zh-cn</language>",
        f"    <lastBuildDate>{now}</lastBuildDate>",
    ]
    for item in merged:
        parts.append(item_to_xml(item))
    parts += ["  </channel>", "</rss>", ""]

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return len(items), len(merged)


def main():
    with_abstract = "--no-abstract" not in sys.argv
    sources = [fetch_society, fetch_review, fetch_studies]
    failed = []
    for fn in sources:
        name = fn.__name__
        try:
            if fn is fetch_review:
                items, journal, site, fname = fn(with_abstract=with_abstract)
            else:
                items, journal, site, fname = fn()
            if not items:
                raise RuntimeError("解析到 0 篇文章，页面结构可能已变化")
            n_new, n_all = write_feed(os.path.join(OUT_DIR, fname), journal, site, items)
            print(f"[OK] 《{journal}》当期 {n_new} 篇，feed 共 {n_all} 条 -> feeds/{fname}")
        except Exception as e:
            failed.append(name)
            print(f"[FAIL] {name}: {e}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
