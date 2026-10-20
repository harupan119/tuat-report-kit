# tuat-report-kit

東京農工大（TUAT）の演習・実験レポートを、Claude Code / Codex と一緒に作るためのスキル集です。
**設計図（spec.json）→ ブロックごとの執筆 → 機械検査（ゲート）→ 提出前チェック → PDF** の順で進めます。
macOS と Windows のどちらでも動きます（Python 3 と Typst）。

| スキル | 役割 |
|---|---|
| `tuat-report` | spec.json で節ごとの要点・用語・数値・字数を決め、本文を書き（エージェントでも本人でも）、`report_gate.py` で機械検査する。構成・体裁・引用の規約と提出前チェック付き |
| `tuat-report-pdf` | `report.md` を正本にしたまま Typst で日本語 PDF を組む。MS 明朝／MS ゴシック、代替フォント混入と再現性の検算付き。**表紙は作らない** |

## できること・できないこと

| できる | できない（このキットに含めない） |
|---|---|
| 節ごとの設計図づくりと、既存の下書きからの設計図の自動作成 | 表紙の生成（課題が求める場合は別途用意する） |
| 本文の執筆（エージェント / 本人）と、字数・用語・数値・文体・重複・簡易 AI 臭の機械検査 | DOCX（Word）出力 |
| 構成・体裁・引用規約にもとづく提出前チェック | 文体を「人間らしく」書き換える処理 |
| Markdown から PDF までの組版と、フォント・再現性の検算 | 科目ごとの知見（各自の科目メモに書いていく。雛形あり） |

> ⚠️ 生成AIでレポート本文を書くことを、課題・科目・所属の規程が禁じている場合があります。
> 着手前に必ず確認し、禁じられていればエージェントには構成の相談と検査だけをさせてください。利用記録を求められたら事実どおりに書きます。

## 導入

```bash
git clone https://github.com/harupan119/tuat-report-kit.git
cd tuat-report-kit
python install_skills.py            # ~/.claude/skills と ~/.codex/skills（あるもの）へリンク（macOS は python3）
python install_skills.py --dry-run  # 何をするかだけ表示
```

macOS は symlink、Windows はジャンクション（管理者権限不要）で張ります。既にある同名の実フォルダは上書きしません。

PDF を作るなら:

| | macOS | Windows |
|---|---|---|
| Typst | `brew install typst` | `winget install --id Typst.Typst` |
| MS 明朝 / MS ゴシック | Office から `~/Library/Fonts` へ複製（`skills/tuat-report-pdf/references/fonts.md`） | 標準搭載 |
| 検算用 poppler（任意） | `brew install poppler` | `winget install oschwartz10612.Poppler` |

## 使い方の流れ

```bash
# 1. 設計図を作る（雛形を写して埋める）
cp skills/tuat-report/templates/spec.example.json work/spec.json
python skills/tuat-report/scripts/report_gate.py work/spec.json --validate-only

# 2. report.md を書く（spec の heading と同じ ## 見出しで節を並べる）

# 3. 機械検査（✗ があれば該当の節を直して再検査）
python skills/tuat-report/scripts/report_gate.py work/spec.json work/report.md

# 4. PDF（変換器を作業フォルダに写して組む）
cp skills/tuat-report-pdf/assets/md_to_typst.py work/
cd work && python md_to_typst.py --compile
```

エージェントに頼む時は「レポート書いて」「PDFにして」で各スキルが呼ばれます。

## ゲートが見るもの

| 不合格（✗） | 警告（⚠） |
|---|---|
| 字数が目標の 0.85〜1.4 倍の外 / 用語の消失・表記揺れ / 実測値（facts）の改変・欠落 / だ・である調に です・ます調が混入 / 「閾値を越える」型の誤用 / 隣の節との重複が多すぎる | 定型の誇張語・「することができ」・全角ダッシュ・太字ラベル / 英語混入の疑い / 重複がやや多い |

LLM は使わず、正規表現と字数で決定論的に判定します。

## 関連リポジトリ

- [tuat-fetch](https://github.com/harupan119/tuat-fetch) — SIRIUS / Sakai / Google Classroom から時間割・課題・教材を取得し、提出・出席・フォーム入力を手前まで自動化するツールとスキル。課題PDFや実験資料の取得に使える。

## ライセンス

MIT
