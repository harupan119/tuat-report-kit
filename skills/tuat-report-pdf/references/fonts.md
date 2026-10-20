# フォント（MS 明朝／MS ゴシック）

## 導入

macOS では、MS 明朝・MS ゴシックは Apple 純正ではない。**外部から落とさない。**Office が入っていればその中に実体がある（Windows は標準搭載。下の「Windows」）。

自分のマシンに導入済みの Office から、自分の文書を組むために使う前提の手順である。フォントファイル自体は成果物にも配布物にも入れない。Office のライセンスを持っていない環境では使えないので、その場合はヒラギノや源ノ明朝など手元にあるフォントで組む（フォント列の末尾に置いた代替に自動で切り替わる）。

```bash
ls "/Applications/Microsoft Word.app/Contents/Resources/DFonts/"{msgothic,msmincho}.ttc
```

`~/Library/Fonts/` に複製するとシステムに登録され、Typst と matplotlib の両方から見えるようになる。

```bash
D="/Applications/Microsoft Word.app/Contents/Resources/DFonts"
cp "$D/msgothic.ttc" "$D/msmincho.ttc" ~/Library/Fonts/
chmod 644 ~/Library/Fonts/ms{gothic,mincho}.ttc
typst fonts | rg '^MS '
```

期待する出力：`MS Gothic` / `MS Mincho` / `MS PGothic` / `MS PMincho` / `MS UI Gothic`。

### Windows

MS 明朝・MS ゴシックは Windows に標準で入っている（`C:\Windows\Fonts\msmincho.ttc` / `msgothic.ttc`）。複製は要らない。Typst は `winget install --id Typst.Typst` で入れる。

```powershell
typst fonts | findstr /B "MS"
```

同じく `MS Gothic` / `MS Mincho` などが出れば使える。Times New Roman も標準搭載。変換器のフォント列には macOS 用（Hiragino・Menlo）と Windows 用（Yu Mincho・Yu Gothic・Consolas）の代替を両方並べてあり、`typst fonts` に無いものは変換時に外すので、どちらの OS でも警告は出ない。

`msgothic.ttc` には MS Gothic（等幅）・MS UI Gothic・MS PGothic（プロポーショナル）が、`msmincho.ttc` には MS Mincho・MS PMincho が入っている。レポートで使うのは **P の付かない方**。

## 埋め込み可否の確認

PDF に埋め込めないフォントを使うと、他環境で開いた時に化ける。`OS/2` テーブルの `fsType` を見る。

```python
from fontTools.ttLib import TTCollection
for f in TTCollection("~/Library/Fonts/msmincho.ttc").fonts:
    print([str(r) for r in f['name'].names if r.nameID == 1][0], hex(f['OS/2'].fsType))
```

| fsType 下位4bit | 意味 |
|---|---|
| 0x0000 | Installable。制限なし |
| 0x0002 | Restricted。**埋め込み禁止** |
| 0x0004 | Preview & Print のみ |
| 0x0008 | Editable。編集可能な埋め込みまで可 |

MS 明朝・MS ゴシックは `0x0008` なので提出 PDF への埋め込み・サブセット化とも問題ない。

## Typst の指定

```typst
#set text(
  font: ("Times New Roman", "MS Mincho", "New Computer Modern Math",
         "Hiragino Mincho ProN", "Hiragino Sans"),
  lang: "ja", size: 10.5pt,
)
#show math.equation: set text(font: ("New Computer Modern Math", "MS Mincho"))
#show heading: it => block[ #set text(font: ("MS Gothic", "Hiragino Sans"), weight: "bold") ... ]
#show raw.where(block: true): it => block(text(font: ("Menlo", "MS Gothic"), ...))
```

Typst のフォント指定は**字ごとに前から順に探す**。だから並べる順序が意味を持つ。欧文フォントを先頭に置くと欧文だけがそれで組まれ、和文は次の和文フォントに落ちる。末尾の Hiragino は保険。

---

# 落とし穴

3つとも `pdffonts <pdf>` に想定外のフォント名が並ぶことで気づける。**組み終わったら必ず見る。**

## 1. 数式の中の日本語が中国語フォントで描かれる

番号付き数式は本文と**別のフォント列**で組まれる。数式フォント（New Computer Modern Math）に和文が無いため、指定しないと処理系任せの代替に落ちる。macOS では `SIL-Hei-Med-Jian`（簡体字中国語）や `Osaka` が選ばれる。

式(1)「成功探索の平均キー比較回数」のように**式の中に和文のラベルを置く書き方をすると必ず踏む**。字形が中国語のものになり、太さも本文と揃わない。

```typst
#show math.equation: set text(font: ("New Computer Modern Math", "MS Mincho"))
```

数式フォントを先頭に置くのは、Typst が数式の組版に「MATH テーブルを持つ最初のフォント」を使うため。順序を逆にすると数式の組み方が変わる。

同じ理屈でコードブロックも踏む。Menlo に和文が無いので、日本語コメントが `Osaka-Mono` に落ちる。

```typst
#show raw.where(block: true): it => block(text(font: ("Menlo", "MS Gothic"), ...))
```

## 2. `⌈ ⌉ ⌊ ⌋` が同じ角括弧に化ける

天井・床記号は **MS 明朝・MS ゴシック・Times New Roman・Century・Hiragino のいずれにも字形が無い**。放置すると処理系任せの代替に落ち、フォントによっては両方とも普通の角括弧 `[ ]` で描かれる。

`⌊log₂N⌋` と `⌈log₂(N+1)⌉` を対比させる文で踏むと、**対比そのものが読者に見えなくなる**。文章としては正しいのに図版だけ間違っているのと同じで、見つけにくい。

フォント列に数式フォントを入れて字形を固定する。本文の記号が、数式ブロックで組んだ式と同じ字形に揃う。

```typst
font: ("Times New Roman", "MS Mincho", "New Computer Modern Math", ...)
```

`scripts/font_coverage.py` で事前に洗い出せる。

## 3. matplotlib で MS ゴシックの文字が消える

**MS ゴシックは 7〜22 ppem の埋め込みビットマップ（`EBDT` / `EBLC`）を持つ。**この範囲では FreeType がビットマップを返し、matplotlib の Agg バックエンドがそれを描かないため、文字が丸ごと消える。

図の文字は 7〜9pt。140 dpi なら `ppem = pt × 140/72` で 13.6〜17.5 ppem となり、**全部この範囲に入る**。タイトル（12pt 以上 = 23 ppem 以上）だけが残るので、「タイトルは出るのに軸ラベルと凡例だけ真っ白」という形で現れる。

確認方法：

```python
# 6/8/10/12/14/18pt を描いて、黒画素が出る行帯を数える。
# 期待6本のうち3本しか出なければこの症状。
```

回避は、ビットマップ表を外した複製を実行時に作ってそれを登録する。フォント本体は配布物に入れず、手元の導入済みフォントから毎回導出する。

```python
from fontTools.ttLib import TTCollection
for font in TTCollection(src).fonts:
    if "MS Gothic" in {str(r) for r in font["name"].names if r.nameID == 1}:
        for tag in ("EBDT", "EBLC", "EBSC"):
            if tag in font:
                del font[tag]
        font.save(dst)
```

`fontTools` は matplotlib の依存なので追加インストールは要らない。

Typst 側はこの影響を受けない。PDF 埋め込みはアウトラインを使うため。

## 図の記号

MS ゴシックにも `⌈ ⌉ ⌊ ⌋` は無い。**凡例や軸ラベルに使わない。**語で書く（「log₂(N+1) の切り上げ +1」）。本文の式は数式フォントで組むので記号のままでよい。

`₂`（U+2082）や `⁶`（U+2076）は MS ゴシックにある。Hiragino Sans には無いものがあるので、Hiragino から MS に替えると使える文字が増える。
