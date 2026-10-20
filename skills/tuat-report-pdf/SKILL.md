---
name: tuat-report-pdf
description: "TUATレポートの report.md を正本にしたまま、Typst で日本語の提出用 PDF を組む（表紙は作らない）。変換スクリプトを挟んで本文と PDF の乖離を防ぎ、MS 明朝／MS ゴシックで組み、代替フォント混入と再現性を検算する。macOS / Windows 両対応。『PDFにして』『PDFまで作って』『Typstで組んで』『レポートのPDF作り直して』等で使う。本文の作成は tuat-report。"
---

# TUAT レポート PDF 化（Typst）

## 概要

`report.md` を本文の正本とし、変換スクリプト `md_to_typst.py` で Typst ソースと PDF を生成する。**表紙は作らない**（本文1ページ目の先頭に `# 題名` を置くだけ。課題が表紙を求める場合は別途用意する）。

**Typst を直接書かない。** 正本 `report.md` と提出 PDF が乖離し、提出版が正になってしまう保守負債が実際に生じた。変換を挟めば本文を直すだけで PDF が追従する。

## 前提

- `typst`（macOS: `brew install typst` / Windows: `winget install --id Typst.Typst`）
- Python 3（macOS は `python3`、Windows は `python`）。変換器は標準ライブラリだけで動く
- 図を作るなら matplotlib（作業フォルダの仮想環境に入れる）
- MS 明朝／MS ゴシック: Windows は標準搭載。macOS は Office から複製する → `references/fonts.md`
- 検算に poppler（`pdffonts` / `pdftotext`。macOS: `brew install poppler` / Windows: `winget install oschwartz10612.Poppler`）

## 手順

1. **本文を確定させる。** `report.md` は `tuat-report` のゲートを通したもの。以降、`report.typ` は手で編集しない。
2. **フォントを用意する。** 初回のみ。`references/fonts.md`。
3. **変換スクリプトを作業フォルダに置く。** `assets/md_to_typst.py` を写す。数式があるレポートだけ `EQUATIONS` に式を足す。
4. **（任意）report.meta.json を置く。** 出力名・改変検知・章改ページを指定したい時だけ:
   ```json
   {"output_basename": "<学籍番号>_report", "body_sha256": "<report.md の SHA-256>",
    "layout": {"chapter_pagebreak": "auto"}}
   ```
   `body_sha256` を入れると、本文が1 byteでも変わった時に組むのを止める（提出版と正本のずれを防ぐ）。値は macOS `shasum -a 256 report.md` / Windows `certutil -hashfile report.md SHA256`（小文字にする）。
5. **図を作る。** `make_figures.py` など。図中の日本語は本文と字種を揃える（本文が明朝なら図はゴシック）。MS ゴシックで図の文字が消える問題は `assets/mpl_ms_gothic.py` で避ける。
6. **組む。** `python md_to_typst.py --compile`。出力は `output_basename.pdf`（既定 `report.pdf`）。既存PDFは上書きしないので、更新は差分確認・承認後だけ `--force`。
7. **検算する。** 下の「提出前の検算」を全部通す。
8. **梱包する（提出物に再現用ファイルが要る時）。** `report.md`、変換器、図表など再現に要るファイルだけを zip へ入れ、**展開した副本だけで** PDF 再生成が通ることを確かめる。

## report.md の書き方（変換器が拾う形）

- 先頭の `# 題名` → 1ページ目の先頭に題名。章は `##`、節は `###`、項は `####`
- 表: 直前の行に `**表1: …**`、続けて GFM のパイプ表
- 図: `![…](figures/xxx.png)`、直後の行に `**図1: …**`
- 数式: `$$…\tag{n}$$` を単独行に置き、`EQUATIONS[n]` に Typst の式を書く
- コード: ``` のフェンス

## 変換で要る工夫

いずれも `assets/md_to_typst.py` に実装済み。写して使うなら中身を読んでから直す。

- **数式**: LaTeX から Typst 構文へ、`\tag{n}` の番号をキーにした対応表で写す。`#set math.equation(numbering: "(1)")` の自動採番と文書順が一致するかを変換時に検査し、ずれたら終了する。
- **表**: `#figure(kind: table)` にしてキャプションを上に置く。`breakable: true` で、長い表でもキャプションだけが前ページに取り残されない。
- **図幅**: PNG の IHDR を読んで縦横比で振り分ける（横長の2枚組は 96%、単独図は 76%）。Pillow に依存しない。
- **エスケープ**: Typst マークアップの特殊文字 `\#$*_`<>@[]~` を退避する。特に `α_build` の `_`、参考文献の `[1]`、`#define` の `#` が壊れやすい。
- **章改ページ**: `layout.chapter_pagebreak=auto` では本文量と図表・コード・数式の量から決める。課題指定があれば `always` / `never`。付録は参考文献に続けて置く。
- **フォント列**: macOS 用と Windows 用の代替を両方並べ、`typst fonts` に無いものは変換時に外す（未導入フォントの警告を出さない）。

## フォント

| 用途 | フォント |
|---|---|
| 本文の和文 | MS 明朝 |
| 見出し・図・コード内の和文 | MS ゴシック |
| 欧文 | Times New Roman |
| 数式と `⌈ ⌉ ⌊ ⌋` | New Computer Modern Math |

**MS 明朝は固定ピッチなので、欧文まで任せると地の文がタイプライター体になる。** 必ず欧文用フォントを先頭に置く。詳細と落とし穴は `references/fonts.md`。

## 提出前の検算

「できた」と書く前に全部通す。

1. **フォント検算** — `pdffonts <pdf>` に意図したフォントだけが並ぶこと。知らない名前は代替フォントに落ちている（`SIL-Hei-*` は簡体字中国語、`Osaka` は macOS の代替）。`scripts/pdf_font_census.py` でどの文字がどのフォントで描かれたか数えられる。
2. **字形の欠け** — `scripts/font_coverage.py` で、本文の文字が指定フォントに全部あるか調べる。
3. **図の警告** — 作図で `Glyph ... missing` の警告が出ないこと。
4. **キャプションの分離・端物ページ** — 各ページの末尾行が「表n」「図n」で終わっていないか、3行以下のページが無いか。
5. **PDF の再現性** — 展開した副本で `python md_to_typst.py --compile` を回し、`pdftotext` の出力が提出 PDF と一致すること。通らないなら、正本と提出物が既に乖離している。

## 同梱物

zip に入れないもの: `.venv`、`__pycache__`、`*.dSYM`、ビルド済みバイナリ、生成した巨大入力、`.fontcache`、作業メモ、PDF 本体（課題が求めない限り）。フォントファイルは同梱しない。
