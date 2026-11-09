# -*- coding: utf-8 -*-
"""shops.json（公式サイトの現況）と build_db.py の現在のデータを突き合わせ、
build_db.py の駅ビルセクションを再生成する。

使い方:
    python3 tools/fetch_shops.py                       # 公式サイトから取得
    python3 tools/gen_sections.py                      # 差分サマリだけ表示
    python3 tools/gen_sections.py -o sections.py       # セクションのソースを書き出す

方針:
- 既存の行と同定できた店舗は、既存のジャンル文字列と店名表記をそのまま引き継ぐ。
  これまで積み上げたタグの手当て（SHOP_TAG_OVERRIDES 等）を壊さないため。
- 公式一覧から消えた店舗は「消滅」として表示する。出力には含めないので、
  本当に退店したのかを確認してから build_db.py に反映すること。
- 新規店舗は公式サイトのカテゴリ表記をそのままジャンル文字列として採用する。
  そのままでは不適切なものは MANUAL_GENRE に書く。実行後に
  「未マッピングのジャンル」として出たものは DEFAULT_GENRE_TAGS への追加が必要。

書き出したセクションは build_db.py の該当範囲（最初の `# ============ …駅:` から
タグ付けセクションの直前まで）に貼り替えて使う。貼り替えたら python3 build_db.py を
実行し、docs/data.json と Markdown を再生成する。
"""
import argparse, collections, datetime, json, os, re, runpy, sys, tempfile, unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_current_rows():
    """build_db.py を読み込んで rows を得る。
    build_db.py は docs/data.json と Markdown を書き出すので、
    作業ディレクトリを一時ディレクトリに移してリポジトリを汚さないようにする。"""
    cwd, stdout = os.getcwd(), sys.stdout
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)
        os.chdir(tmp)
        sys.stdout = open(os.devnull, "w")   # build_db.py の進捗表示を抑える
        try:
            ns = runpy.run_path(os.path.join(REPO, "build_db.py"))
        finally:
            sys.stdout.close()
            sys.stdout = stdout
            os.chdir(cwd)
    return ns["rows"]


ROWS = load_current_rows()
EXIST = collections.defaultdict(dict)                # 施設 -> 店名 -> ジャンル
EXIST_FLOOR = collections.defaultdict(dict)          # 施設 -> (店名, フロア) -> ジャンル
CAP = collections.defaultdict(collections.Counter)   # 施設 -> 店名 -> 行数（複数フロア対応）
GLOBAL = {}                                          # 他館の同名店（ジャンル流用元）
for genre, shop, station, building, floor in ROWS:
    EXIST[building][shop] = genre
    EXIST_FLOOR[building][(shop, floor)] = genre
    CAP[building][shop] += 1


def norm(s):
    """店名の表記ゆれを吸収した比較用キー。読みガナの括弧・記号・空白を落とす。"""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[（(][^（()）]*[)）]", "", s)
    s = s.replace("【閉店】", "")
    s = re.sub(r"[・･ー\-−–—/／、。,.\s　’'\"&＆!！]", "", s)
    return s.lower()


for genre, shop, station, building, floor in ROWS:
    GLOBAL.setdefault(norm(shop), (genre, shop))

# 公式の表記ゆれ -> DB の既存表記（既存のジャンル/タグを引き継ぐ）
RENAME = {
    "ニュウマン横浜": {"THE NORTH FACE 3(march)": "3(march)（THE NORTH FACE）"},
    "アトレ川崎": {"TAKUJI STATION ﾀｸｽﾃ": "TAKUJI STATION",
                 "オムライスの店　卵と私": "卵と私",
                 "ふるまいや": "ふるまいや（日本酒）",
                 "ハートアップ": "ハートアップ（コンタクト）"},
}
# 公式一覧には出ないが DB に残す行（施設全体を指す独自エントリなど）
KEEP = {"エキュート品川": ["エキュート品川内 JRE POINTマーク対象ショップ"]}
# 公式サイト側の文字化け・半角カナの修正
NAME_FIX = {"ﾌｫﾝﾃ-ﾇ": "フォンテーヌ"}
# 公式カテゴリが長すぎる/実態と合わない新規店のジャンルを手で決める
MANUAL_GENRE = {
    "アコメヤ トウキョウ": "食品・スーパー・酒",
    "マロリーポークステーキ": "外食・レストラン",
    "Tavernetta Salvatore": "外食・レストラン",
    "京樽": "惣菜・弁当",
    "神戸屋キッチン": "ベーカリー・カフェ",
    "クイーンズ伊勢丹": "食品・スーパーマーケット",
    "吉祥寺菊屋": "生活雑貨",
    "ルミネコンタクト": "コンタクトレンズ",
    "ルミネ藤沢はたの眼科": "病院・クリニック",
    "ルミネ藤沢歯科": "病院・クリニック",
    "湘南矯正歯科クリニック": "病院・クリニック",
    "さとう皮ふ科クリニック": "病院・クリニック",
    "TBC": "ビューティーサロン",
    "三井住友銀行 藤沢支店": "銀行/ATM",
    "大京穴吹不動産": "不動産相談サービス",
    "日能研": "カルチャースクール",
    "駅前留学NOVA(English Lab)": "カルチャースクール",
    "Gabaマンツーマン英会話(English Lab)": "カルチャースクール",
    "湘南ゼミナール 高等部": "カルチャースクール",
    "湘南ゼミナール 個別指導コース": "カルチャースクール",
    "湘南ゼミナール 公立中高一貫コース": "カルチャースクール",
    "湘南ゼミナール 総合進学コース": "カルチャースクール",
    "湘南ゼミナール 横浜翠嵐Vコース": "カルチャースクール",
    # ユニクロは店舗ごとにキッズの取扱が違う。map.uniqlo.com のストアロケーターで
    # productTypeList に KIDS/BABY があるかを確認して決める（ルミネ藤沢店はあり）。
    "ユニクロ": "衣料・子供服",
}


def fix_name(name):
    name = NAME_FIX.get(name, name)
    name = unicodedata.normalize("NFKC", name).replace("　", " ")
    return re.sub(r"\s+", " ", name).strip().replace("−", "ー")


def assign(building, officials):
    """公式店名 -> 既存店名 の対応を一対一で決める。完全一致を優先する。"""
    cands = {s: norm(s) for s in EXIST.get(building, {})}
    cap = CAP.get(building, collections.Counter())
    ren = RENAME.get(building, {})
    used, taken, out = collections.Counter(), set(), {}
    free = lambda shop: used[shop] < cap[shop]

    def take(shop):
        used[shop] += 1
        taken.add(shop)

    for i, (raw, _official) in enumerate(officials):          # 1. 明示的な改称表
        old = ren.get(raw)
        if old and free(old):
            out[i] = old
            take(old)
    for i, (_raw, official) in enumerate(officials):          # 2. 完全一致
        if i in out:
            continue
        n = norm(official)
        for shop, s in cands.items():
            if free(shop) and s == n:
                out[i] = shop
                take(shop)
                break
    for i, (_raw, official) in enumerate(officials):          # 3. 前方/後方一致
        if i in out:
            continue
        n = norm(official)
        if len(n) < 2:
            continue
        for shop, s in cands.items():
            if not free(shop) or len(s) < 2:
                continue
            if s.endswith(n) or n.endswith(s) or s.startswith(n) or n.startswith(s):
                out[i] = shop
                take(shop)
                break
    return out, taken


def build(building, rows, floor_of):
    """公式の行 -> [(ジャンル, 店名, フロア)] と 新規/消滅のリスト"""
    live = [r for r in rows if "【閉店】" not in r["name"]]
    officials = [(r["name"], fix_name(r["name"])) for r in live]
    mapping, taken = assign(building, officials)
    out, added = [], []
    for i, r in enumerate(live):
        floor = re.sub(r"\s+", " ", floor_of(r)).strip()
        old = mapping.get(i)
        if old is None:          # 同名の既存行がある（同じ店が複数フロアにある）場合
            n = norm(officials[i][1])
            for shop in EXIST.get(building, {}):
                if norm(shop) == n:
                    old = shop
                    break
        if old is not None:
            genre = EXIST_FLOOR[building].get((old, floor), EXIST[building][old])
            out.append((genre, old, floor))
            continue
        name = officials[i][1]
        if name in MANUAL_GENRE:
            out.append((MANUAL_GENRE[name], name, floor))
            added.append((name, MANUAL_GENRE[name] + "〔手動指定〕"))
            continue
        g = GLOBAL.get(norm(name))
        if g:                    # 他館に同名店 -> その表記/ジャンルを流用
            out.append((g[0], g[1], floor))
            added.append((g[1], g[0] + "〔他館から流用〕"))
        else:
            cat = fix_name(r["cat"]) or "その他"
            out.append((cat, name, floor))
            added.append((name, cat))
    for shop in KEEP.get(building, []):
        if shop not in taken:
            out.append((EXIST[building][shop], shop, ""))
            taken.add(shop)
    removed = [s for s in EXIST.get(building, {}) if s not in taken]
    return out, added, removed


# (施設名, 駅, 変数名, 出典URL, ソースキー, フロアの取り出し方)
pre = lambda p: (lambda r: r["floor"].replace(p, "").strip())
asis = lambda r: r["floor"]
none = lambda r: ""
JOBS = [
    ("アトレ品川", "品川", "atre_shinagawa", "https://www.atre.co.jp/shinagawa/search_shop/",
     ("atre/shinagawa", None), pre("品川 ")),
    ("エキュート品川", "品川", "ecute_shinagawa", "https://www.ecute.jp/shinagawa/shop",
     ("ecute/shinagawa", None), none),
    ("アトレ目黒1", "目黒", "atre_meguro1", "https://www.atre.co.jp/meguro/search_shop/",
     ("atre/meguro", "目黒1-"), pre("目黒1-")),
    ("アトレ目黒2", "目黒", "atre_meguro2", "https://www.atre.co.jp/meguro/search_shop/",
     ("atre/meguro", "目黒2-"), pre("目黒2-")),
    ("アトレ川崎", "川崎", "atre_kawasaki", "https://www.atre.co.jp/kawasaki/search_shop/",
     ("atre/kawasaki", None), pre("川崎 ")),
    ("ルミネ横浜", "横浜", "lumine_yokohama", "https://www.lumine.ne.jp/yokohama/floorguide/",
     ("lumine/yokohama", None), asis),
    ("ニュウマン横浜", "横浜", "newoman_yokohama", "https://www.newoman.jp/yokohama/floorguide/",
     ("newoman/yokohama", None), asis),
    ("エキュートエディション横浜", "横浜", "edition_yokohama",
     "https://www.ecute.jp/edition_yokohama/shop", ("ecute/edition_yokohama", None), none),
    ("CIAL横浜", "横浜", "cial_yokohama", "https://www.jryscc.co.jp/cial/yokohama/floorguide/",
     ("cial/yokohama", "B"), asis),
    ("CIAL横浜ANNEX", "横浜", "cial_yokohama_annex",
     "https://www.jryscc.co.jp/cial/yokohama/floorguide/", ("cial/yokohama", "!B"), asis),
    ("アトレ大井町", "大井町", "atre_oimachi", "https://www.atre.co.jp/oimachi/search_shop/",
     ("atre/oimachi", "大井町 "), pre("大井町 ")),
    ("アトレ大井町2", "大井町", "atre_oimachi2", "https://www.atre.co.jp/oimachi/search_shop/",
     ("atre/oimachi", "大井町2-"), pre("大井町2-")),
    ("エキュートエディション有楽町", "有楽町", "edition_yurakucho",
     "https://www.ecute.jp/edition_yurakucho/shop", ("ecute/edition_yurakucho", None), none),
    ("ルミネ有楽町(ルミネ1)", "有楽町", "lumine_yurakucho1",
     "https://www.lumine.ne.jp/yurakucho/floorguide/", ("lumine/yurakucho1", None), asis),
    ("ルミネ有楽町(ルミネ2)", "有楽町", "lumine_yurakucho2",
     "https://www.lumine.ne.jp/yurakucho/floorguide/", ("lumine/yurakucho2", None), asis),
    ("ルミネ有楽町(ルミネストリート)", "有楽町", "lumine_yurakucho_street",
     "https://www.lumine.ne.jp/yurakucho/floorguide/", ("lumine/yurakucho_street", None), none),
    ("グランスタ東京", "東京", "gransta_tokyo", "https://www.gransta.jp/mall/gransta_tokyo/",
     ("gransta/gransta_tokyo", None), asis),
    ("グランスタ丸の内", "東京", "gransta_marunouchi",
     "https://www.gransta.jp/mall/gransta_marunouchi/", ("gransta/gransta_marunouchi", None), asis),
    ("グランスタ八重北", "東京", "gransta_yaekita",
     "https://www.gransta.jp/mall/gransta_yaekita/", ("gransta/gransta_yaekita", None), asis),
    ("グランスタ八重洲", "東京", "gransta_yaesu", "https://www.gransta.jp/mall/gransta_yaesu/",
     ("gransta/gransta_yaesu", None), asis),
    ("グランアージュ", "東京", "granage", "https://www.gransta.jp/mall/granage/",
     ("gransta/granage", None), asis),
    ("ルミネ藤沢", "藤沢", "lumine_fujisawa", "https://www.lumine.ne.jp/fujisawa/floorguide/",
     ("lumine/fujisawa", None), asis),
]


def pick(shops, key, filt):
    rows = shops[key]
    if filt is None:
        return rows
    if filt == "B":           # CIAL: 地下フロア = シァル横浜本館
        return [r for r in rows if r["floor"].startswith("B")]
    if filt == "!B":          # CIAL: 地上フロア = JR横浜鶴屋町ビル(ANNEX)
        return [r for r in rows if not r["floor"].startswith("B")]
    return [r for r in rows if r["floor"].startswith(filt)]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--shops", default="shops.json",
                    help="fetch_shops.py の出力（既定: shops.json）")
    ap.add_argument("-o", "--out", help="セクションのソースの書き出し先（省略時は差分のみ表示）")
    args = ap.parse_args()

    shops = json.load(open(args.shops, encoding="utf-8"))
    today = datetime.date.today().isoformat()
    src, n_added, n_removed = [], 0, 0

    for bld, station, var, url, (key, filt), floor_of in JOBS:
        if key not in shops:
            print(f"{bld}: shops.json に {key} が無いのでスキップ", file=sys.stderr)
            continue
        rows, added, removed = build(bld, pick(shops, key, filt), floor_of)
        n_added += len(added)
        n_removed += len(removed)
        print(f"{bld}: {len(rows)}件 (新規{len(added)} / 消滅{len(removed)})")
        for name, cat in added:
            print(f"    + {name}  [{cat}]")
        for shop in removed:
            print(f"    - {shop}")

        src.append(f"# ============ {station}駅: {bld} ============")
        src.append(f"# 出典: {url} （{today}取得・全{len(rows)}件）")
        src.append(f"{var} = [")
        last = object()
        for genre, shop, floor in rows:
            if floor != last:
                src.append(f"# {floor}" if floor else "# フロア情報なし")
                last = floor
            src.append(f"({q(genre)},{q(shop)},{q(floor)}),")
        src.append("]")
        src.append(f"for genre, shop, floor in {var}:")
        src.append(f"    add(genre, shop, {q(station)}, {q(bld)}, floor)")
        src.append("")

    print(f"\n合計: 新規{n_added}件 / 消滅{n_removed}件")
    if args.out:
        open(args.out, "w", encoding="utf-8").write("\n".join(src) + "\n")
        print(f"saved {args.out}")
    else:
        print("（-o を付けるとセクションのソースを書き出します）")


if __name__ == "__main__":
    main()
