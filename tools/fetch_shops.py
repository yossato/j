# -*- coding: utf-8 -*-
"""各駅ビルの公式サイトから店舗一覧を取得して shops.json に保存する。

使い方:
    python3 tools/fetch_shops.py                      # 全施設を取得
    python3 tools/fetch_shops.py --only lumine/fujisawa atre/kawasaki
    python3 tools/fetch_shops.py -o /tmp/shops.json

出力は {ソースキー: [{"floor":…, "cat":…, "name":…}, …]} の JSON。
これを tools/gen_sections.py に渡すと build_db.py のセクションを再生成できる。

注意:
- lumine.ne.jp は HTTP/2 だと接続をリセットされるため curl を --http1.1 で呼んでいる。
- 全施設だと 60 リクエスト以上・数分かかる。サイトに負荷をかけないよう 1 秒間隔を空けている。
"""
import argparse, html, json, re, subprocess, sys, time

clean = lambda x: html.unescape(re.sub("<[^>]+>", "", x)).strip()


def get(url, tries=3):
    """curl で取得する。lumine 系の HTTP/2 リセット対策で --http1.1 固定。"""
    for i in range(tries):
        r = subprocess.run(["curl", "-sSL", "--http1.1", "-m", "40", url],
                           capture_output=True, text=True)
        if r.stdout.strip():
            return r.stdout
        time.sleep(2 * (i + 1))
    raise SystemExit("fetch failed: " + url)


# ---------------- アトレ (atre.co.jp) ----------------
ATRE = re.compile(
    r'<a href="(https://www\.atre\.co\.jp/\w+/shop/\d+/)">.*?'
    r'<div class="floor txt-min"><span>(.*?)</span></div>\s*'
    r'<div class="category txt-min">(.*?)</div>\s*'
    r'<p class="txt-min">\s*(.*?)</p>', re.S)


def atre(site):
    first = get(f"https://www.atre.co.jp/{site}/search_shop/")
    m = re.search(r"1〜\d+件 / 全(\d+)件", first)
    total = int(m.group(1)) if m else None
    pages = [first]
    last_page = max([int(x) for x in re.findall(r"page=(\d+)", first)] or [1])
    for p in range(2, last_page + 1):
        pages.append(get(f"https://www.atre.co.jp/{site}/search_shop/"
                         f"?small-category=&keyword=&page={p}"))
        time.sleep(1)
    rows, seen = [], set()
    for s in pages:
        for url, floor, cat, name in ATRE.findall(s):
            if url in seen:
                continue
            seen.add(url)
            rows.append(dict(floor=clean(floor), cat=clean(cat), name=clean(name)))
    if total and total != len(rows):
        print(f"  !! 件数不一致: 公式表示 {total} / 取得 {len(rows)}", file=sys.stderr)
    return rows


# ---------------- エキュート (ecute.jp) ----------------
ECUTE = re.compile(r'<a href="(/[a-z_/]+/shop/\d+)">.*?'
                   r'<p class="shop_category">(.*?)</p>\s*'
                   r'<p class="shop_name">(.*?)</p>', re.S)


def ecute(path):
    """フロア情報は公式一覧に無いため floor は空になる。"""
    rows, seen, page = [], set(), 1
    while True:
        s = get(f"https://www.ecute.jp{path}/shop" + (f"?page={page}" if page > 1 else ""))
        new = [(u, c, n) for u, c, n in ECUTE.findall(s) if u not in seen]
        for u, c, n in new:
            seen.add(u)
            rows.append(dict(floor="", cat=clean(c), name=clean(n)))
        if not new or f"?page={page+1}" not in s:
            break
        page += 1
        time.sleep(1)
    return rows


# ---------------- グランスタ (gransta.jp) ----------------
GRANSTA = re.compile(
    r'<a\s+href="https://www\.gransta\.jp/mall/(\w+)/([a-z0-9_-]+)/" class="inner">.*?'
    r'<p class="out_wicket[^"]*">(.*?)</p>\s*(?:<p class="in_wicket">(.*?)</p>\s*)?'
    r'<p class="name">\s*(.*?)<span>(.*?)</span>', re.S)


def gransta(slug):
    s = get(f"https://www.gransta.jp/mall/{slug}/")
    rows, seen = [], set()
    for mall, key, floor, _wicket, cat, name in GRANSTA.findall(s):
        if mall != slug or key in seen:
            continue
        seen.add(key)
        rows.append(dict(floor=re.sub(r"\s+", " ", clean(floor)).strip(),
                         cat=clean(cat), name=clean(name)))
    return rows


# ---------------- ルミネ / ニュウマン（同一CMS） ----------------
CARD = re.compile(r'detail/\?scd=(\d+)".*?c-card02__txt01">(.*?)</div>.*?'
                  r'c-card02__txt02">(.*?)</div>', re.S)


def lumine_cms(base, area, floors):
    rows, seen = [], set()
    for fl in floors:
        s = get(f"{base}/floorguide/?area={area}&floor={fl}")
        for scd, name, cat in CARD.findall(s):
            if scd in seen:
                continue
            seen.add(scd)
            rows.append(dict(floor=fl.upper(), cat=clean(cat), name=clean(name)))
        time.sleep(1)
    return rows


# ---------------- シァル横浜 (jryscc.co.jp) ----------------
CIAL = re.compile(r'<div class="card-shop_num">(.*?)</div>.*?'
                  r'<h3 class="card-shop_name">(.*?)</h3>\s*'
                  r'<p class="card-shop_cat">(.*?)</p>', re.S)


def cial():
    s = get("https://www.jryscc.co.jp/cial/yokohama/floorguide/")
    return [dict(floor=clean(f), name=clean(n), cat=clean(c)) for f, n, c in CIAL.findall(s)]


L = "https://www.lumine.ne.jp"
# ソースキー -> 取得関数。キーは gen_sections.py の JOBS と対応する。
SOURCES = {
    "atre/shinagawa":   lambda: atre("shinagawa"),
    "atre/kawasaki":    lambda: atre("kawasaki"),
    "atre/oimachi":     lambda: atre("oimachi"),
    "atre/meguro":      lambda: atre("meguro"),
    "ecute/shinagawa":        lambda: ecute("/shinagawa"),
    "ecute/edition_yokohama": lambda: ecute("/edition_yokohama"),
    "ecute/edition_yurakucho": lambda: ecute("/edition_yurakucho"),
    "gransta/gransta_tokyo":      lambda: gransta("gransta_tokyo"),
    "gransta/gransta_marunouchi": lambda: gransta("gransta_marunouchi"),
    "gransta/gransta_yaekita":    lambda: gransta("gransta_yaekita"),
    "gransta/gransta_yaesu":      lambda: gransta("gransta_yaesu"),
    "gransta/granage":            lambda: gransta("granage"),
    "lumine/yokohama": lambda: lumine_cms(f"{L}/yokohama", "area01store01",
        ["b2f", "b1f", "1f", "2f", "3f", "4f", "5f", "6f", "7f", "8f", "9f"]),
    "lumine/yurakucho1": lambda: lumine_cms(f"{L}/yurakucho", "area01store01",
        ["b1f", "1f", "2f", "3f", "4f", "5f", "6f", "7f", "8f"]),
    "lumine/yurakucho2": lambda: lumine_cms(f"{L}/yurakucho", "area02store01",
        ["b2f", "b1f", "1f", "2f", "3f", "4f"]),
    "lumine/yurakucho_street": lambda: lumine_cms(f"{L}/yurakucho", "area03store01", ["200f"]),
    "lumine/fujisawa": lambda: lumine_cms(f"{L}/fujisawa", "area01store01",
        ["1f", "2f", "3f", "4f", "5f", "6f", "7f", "8f", "9f"]),
    "newoman/yokohama": lambda: lumine_cms("https://www.newoman.jp/yokohama", "area01nman01",
        ["1f", "2f", "3f", "4f", "5f", "6f", "7f", "8f", "9f", "10f"]),
    "cial/yokohama": cial,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", metavar="KEY",
                    help="取得するソースキー（既定: 全部）。例: lumine/fujisawa")
    ap.add_argument("-o", "--out", default="shops.json", help="出力先 JSON（既定: shops.json）")
    ap.add_argument("--merge", action="store_true",
                    help="--only と併用し、既存の出力ファイルに取得分だけ上書きする")
    args = ap.parse_args()

    keys = args.only or list(SOURCES)
    unknown = [k for k in keys if k not in SOURCES]
    if unknown:
        raise SystemExit("未知のソースキー: " + ", ".join(unknown)
                         + "\n指定できるのは:\n  " + "\n  ".join(SOURCES))

    out = {}
    if args.merge:
        try:
            out = json.load(open(args.out, encoding="utf-8"))
        except FileNotFoundError:
            pass
    for key in keys:
        rows = SOURCES[key]()
        out[key] = rows
        print(f"{key}: {len(rows)}件", file=sys.stderr)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"saved {args.out} ({sum(len(v) for v in out.values())}件)", file=sys.stderr)


if __name__ == "__main__":
    main()
