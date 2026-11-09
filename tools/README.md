# tools/ — データ更新用スクリプト

各駅ビルの公式サイトから店舗一覧を取得し、`build_db.py` の駅ビルセクションを
再生成するためのスクリプトです。**データの正典は従来どおり `build_db.py`** で、
ここにあるのは更新作業を楽にするための道具です。生成結果はそのまま信用せず、
差分を見て `build_db.py` に反映してください。

## 更新手順

```bash
# 1. 公式サイトから現況を取得（全施設で数分かかります）
python3 tools/fetch_shops.py                 # -> shops.json

# 2. 現在の build_db.py と突き合わせて差分を見る
python3 tools/gen_sections.py

# 3. 問題なければセクションのソースを書き出す
python3 tools/gen_sections.py -o sections.py

# 4. sections.py の中身を build_db.py の該当範囲に貼り替える
#    （最初の「# ============ …駅: …」からタグ付けセクションの直前まで）

# 5. 再生成して確認
python3 build_db.py                          # docs/data.json と Markdown を更新
```

駅を増やしたいときは `tools/fetch_shops.py` の `SOURCES` と
`tools/gen_sections.py` の `JOBS` に 1 行ずつ足します。

一部の施設だけ取り直すこともできます。

```bash
python3 tools/fetch_shops.py --only lumine/fujisawa atre/kawasaki --merge
```

## 突き合わせの方針

- **既存の行と同定できた店舗は、既存のジャンル文字列と店名表記をそのまま引き継ぎます。**
  これまで積み上げたタグの手当て（`SHOP_TAG_OVERRIDES` など）を壊さないためです。
  同定は店名を正規化（読みガナの括弧・記号・空白を除去）した一致で行い、
  完全一致 → 前方/後方一致 の順に、一対一で割り当てます。
- 公式一覧から消えた店舗は「消滅」として表示するだけで、出力には含まれません。
  本当に退店したのか確認してから反映してください（同名の別表記で載っていることもあります）。
- 新規店舗は公式サイトのカテゴリ表記をそのままジャンル文字列にします。
  実態と合わないものは `gen_sections.py` の `MANUAL_GENRE` に書きます。
- 公式が「【閉店】」と表示している店舗は出力しません。

反映後に `build_db.py` を実行して、タグが空の行や未マッピングのジャンル文字列が
無いか確認してください。新しいジャンル文字列は `DEFAULT_GENRE_TAGS` への追加が必要です。

```bash
python3 - <<'EOF'
import runpy
ns = runpy.run_path('build_db.py')
known, ov = set(ns['DEFAULT_GENRE_TAGS']), set(ns['SHOP_TAG_OVERRIDES'])
print('未マッピング:', sorted({g for g, s, _st, _b, _f, _t in ns['rows_tagged']
                              if g not in known and s not in ov}))
print('タグ無し:', [s for _g, s, _st, _b, _f, t in ns['rows_tagged'] if not t])
EOF
```

## 手を入れるときの注意

- `gen_sections.py` の `RENAME` / `KEEP` / `NAME_FIX` / `MANUAL_GENRE` は、
  過去の更新で個別に判断した内容です。消すと次回の差分に揺り戻しが出ます。
- ユニクロのように店舗ごとに取扱商品が違うチェーンは、ジャンル（タグ）も店舗ごとに
  変わります。ユニクロは [map.uniqlo.com](https://map.uniqlo.com/jp/ja/) の
  ストアロケーター API（`/jp/api/storelocator/v1/ja/stores?keyword=…`）が
  `productTypeList` に `KIDS` / `BABY` を返すかどうかで「子供服」タグの有無を決めています。
- `lumine.ne.jp` は HTTP/2 だと接続をリセットされるため、`curl --http1.1` で取得しています。
- エキュート各館の公式一覧にはフロア情報がないため、該当施設の `floor` は空のままです。

## ファイル

| ファイル | 役割 |
|---|---|
| `fetch_shops.py` | 公式サイトを巡回して `shops.json` に保存する |
| `gen_sections.py` | `shops.json` と `build_db.py` を突き合わせ、差分表示とセクション生成を行う |
