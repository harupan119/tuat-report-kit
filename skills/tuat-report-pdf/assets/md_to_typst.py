#!/usr/bin/env python3
"""report.md から Typst ソース（report.typ）を生成し、PDF まで組む。

report.md を正本とし、PDF はそこから機械的に作る。本文を直接 Typst で書くと
正本と提出物が乖離するため、変換を挟む。

------------------------------------------------------------------------
これは tuat-report-pdf スキルの実装例である。作業フォルダに写して使う。
表紙は作らない（課題が表紙を求める場合は別途用意する）。
調整対象は次の2点である。

1. EQUATIONS  — 本文の `$$…\\tag{n}$$` に対応する Typst の数式。番号をキーにする。
                文書順と番号の一致は変換時に検査するので、抜けや順序違いは
                その場で落ちる。
2. PREAMBLE のフォント — 既定は本文 MS 明朝／見出し MS ゴシック／欧文
                Times New Roman。替える時は references/fonts.md の落とし穴を
                先に読む。数式とコードブロックは本文と別のフォント列で
                組まれるため、個別の指定が要る。

report.meta.json（任意）で次を指定できる。無ければ既定値で組む。
  output_basename  … PDF のファイル名（拡張子なし。既定 report）
  body_sha256      … 指定すると report.md の SHA-256 と一致しない限り組まない（改変検知）
  layout.chapter_pagebreak … auto / always / never（章頭の改ページ）
  expected_equation_tags   … 本文の式番号の並びの期待値（例 [1, 2, 3]）

想定する report.md の書き方:
  - 先頭の `# タイトル` は1ページ目の先頭に題名として置く（表紙ではない）
  - 章見出しは `##`（章）〜`####`
  - 表は GFM のパイプ表。直前の行に `**表n: …**` の形でキャプションを書く
  - 図は `![…](figures/xxx.png)`、直後の行に `**図n: …**` でキャプション
  - 数式は `$$…\\tag{n}$$` を単独行に置く
  - コードは ``` のフェンス

1コマンドでPDFまで生成する:
  python md_to_typst.py --compile      （macOS は python3）

既存PDFは既定で上書きしない。承認を得た場合だけ --force を付ける。
------------------------------------------------------------------------
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "report.md")
DEFAULT_DST = os.path.join(HERE, "report.typ")
DEFAULT_METADATA = os.path.join(HERE, "report.meta.json")



def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

# 数式は LaTeX から Typst 構文へ手で対応させる（tag 番号をキーにする）。
# Typst 側は #set math.equation(numbering: "(1)") で自動採番するため、
# 文書順が tag 番号と一致していることを変換時に検査する。
EQUATIONS = {
    # 例: 1: '"平均比較回数" = (N+1)/2',
    #     2: 'h(k) = k mod m',
}

PREAMBLE_TEMPLATE = r'''// report.md から md_to_typst.py が生成する。直接編集しない。
#set page(
  paper: "a4",
  margin: (top: 25mm, bottom: 22mm, left: 20mm, right: 20mm),
  numbering: "1",
)
// 和文は MS 明朝、欧文は Times New Roman、見出しは MS ゴシック。
// 3番目以降は代替である。⌈ ⌉ ⌊ ⌋ はどの本文用フォントにも字形が無く、
// 指定しないと処理系任せの代替に落ちて床と天井の区別が失われるため、
// 数式フォントを明示して数式と同じ字形に固定する。
#set text(
  font: ("Times New Roman", "MS Mincho", "New Computer Modern Math",
         "Hiragino Mincho ProN", "Yu Mincho", "Hiragino Sans"),
  lang: "ja", size: 10.5pt,
)
#set par(justify: true, leading: 0.8em, first-line-indent: (amount: 1em, all: true))
#set math.equation(numbering: "(1)", supplement: none)
// 数式は本文と別のフォント列で組まれる。数式フォントに和文が無いため、指定しないと
// 式中の和文ラベルが処理系任せの代替（中国語フォント等）で描かれる。
#show math.equation: set text(font: ("New Computer Modern Math", "MS Mincho"))
#show heading: it => block(above: 1.4em, below: 0.7em)[
  #set text(font: ("MS Gothic", "Hiragino Sans", "Yu Gothic"), weight: "bold")
  #it.body
]
#show heading.where(level: 1): it => block(above: 1.6em, below: 0.9em)[
  #set text(font: ("MS Gothic", "Hiragino Sans", "Yu Gothic"), weight: "bold", size: 14pt)
  #it.body
]
#show heading.where(level: 2): it => block(above: 1.4em, below: 0.7em)[
  #set text(font: ("MS Gothic", "Hiragino Sans", "Yu Gothic"), weight: "bold", size: 12pt)
  #it.body
]
#show heading.where(level: 3): it => block(above: 1.2em, below: 0.6em)[
  #set text(font: ("MS Gothic", "Hiragino Sans", "Yu Gothic"), weight: "bold", size: 11pt)
  #it.body
]
#show raw.where(block: true): it => block(
  fill: rgb("#f5f5f5"), inset: 7pt, radius: 2pt, width: 100%,
  text(font: ("Menlo", "Consolas", "MS Gothic"), size: 8.5pt, it),
)
#show raw.where(block: false): it => text(font: ("Menlo", "Consolas", "MS Gothic"), size: 9pt, it)
#set table(stroke: 0.5pt + rgb("#666666"), inset: 4pt)
// 表のキャプションは表の上、図のキャプションは図の下に置く。
// figure を breakable にして、長い表でもキャプションと本体が別ページに分かれないようにする。
#show figure: set block(breakable: true)
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.caption: it => text(size: 9.5pt, it.body)


'''

# --------------------------------------------------------------------------
# インライン記法の変換
# --------------------------------------------------------------------------
SPECIAL = "\\#$*_`<>@[]~"


def esc(s):
    """Typst マークアップの特殊文字を退避する。"""
    out = []
    for ch in s:
        if ch in SPECIAL:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def inline(s):
    """`コード` と **太字** を保ったまま、残りをエスケープする。"""
    slots = []

    def stash(text):
        slots.append(text)
        return "\x00%d\x00" % (len(slots) - 1)

    # 1. インラインコード
    s = re.sub(r"`([^`]+)`", lambda m: stash("`" + m.group(1) + "`"), s)
    # 2. 太字（Typst は *…*）
    s = re.sub(r"\*\*([^*]+)\*\*", lambda m: stash("*" + esc(m.group(1)) + "*"), s)
    # 3. 残りをエスケープ
    s = esc(s)
    # 4. 退避した部分を戻す（エスケープで \x00 は壊れないが順序に注意）
    s = re.sub(r"\\?\x00(\d+)\\?\x00", lambda m: slots[int(m.group(1))], s)
    return s


def load_metadata(path):
    """report.meta.json があれば読んで検証する。無ければ空の dict（既定値で組む）。"""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        metadata = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit("メタデータJSONが不正: %s" % exc)
    name = metadata.get("output_basename")
    if name is not None and not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]*", str(name)):
        sys.exit("output_basenameが安全なファイル名ではない: %s" % name)
    digest = metadata.get("body_sha256")
    if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
        sys.exit("body_sha256は小文字16進64桁で指定する")
    return metadata


def installed_fonts():
    """typst が見つけられるフォントファミリー名（小文字）。typst が無ければ None。"""
    try:
        out = subprocess.run(["typst", "fonts"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line.strip().lower() for line in out.splitlines() if line.strip()}


def prune_fonts(preamble):
    """フォント列から未導入のものを外す。macOS 用（Hiragino・Menlo）と Windows 用
    （Yu Mincho・Consolas）を両方並べてあるので、そのままだと必ず警告が出る。
    列が空になる場合は元の列を残す（typst の代替に任せる）。"""
    have = installed_fonts()
    if have is None:
        return preamble

    def keep(m):
        names = re.findall(r'"([^"]+)"', m.group(1))
        kept = [n for n in names if n.lower() in have] or names
        return "font: (" + ", ".join('"%s"' % n for n in kept) + ("," if len(kept) == 1 else "") + ")"
    return re.sub(r"font: \(([^)]*)\)", keep, preamble)


def make_preamble(title):
    """書式の前置き。題名があれば1ページ目の先頭に置く（表紙は作らない）。"""
    if not title:
        return prune_fonts(PREAMBLE_TEMPLATE)
    return prune_fonts(PREAMBLE_TEMPLATE + (
        '#align(center)[#text(font: ("MS Gothic", "Hiragino Sans", "Yu Gothic"), '
        'size: 15pt, weight: "bold")[%s]]\n#v(6mm)\n' % inline(title)))


def chapter_pagebreak_enabled(metadata, source_text):
    """長い正式レポートだけ章改ページし、短い受入本文の水増しを避ける。"""
    layout = metadata.get("layout", {})
    mode = layout.get("chapter_pagebreak", "auto") if isinstance(layout, dict) else "auto"
    if mode is True or mode == "always":
        return True
    if mode is False or mode == "never":
        return False
    if mode != "auto":
        sys.exit("layout.chapter_pagebreakはauto / always / neverで指定する")
    compact_chars = len(re.sub(r"\s+", "", source_text))
    structural_blocks = (
        len(re.findall(r"^!\[", source_text, re.MULTILINE))
        + len(re.findall(r"^\|", source_text, re.MULTILINE))
        + len(re.findall(r"^```", source_text, re.MULTILINE)) // 2
        + len(re.findall(r"^\$\$.*\\tag\{\d+\}\$\$$", source_text, re.MULTILINE))
    )
    return compact_chars >= 4000 or structural_blocks >= 4


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def png_size(path):
    """PNG の IHDR から (幅, 高さ) を読む。Pillow に依存しない。"""
    import struct
    with open(os.path.join(HERE, path), "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def image_width(path):
    """縦横比から本文中の幅を決める。横長（2枚組）は大きく、単独図は小さくする。"""
    size = png_size(path)
    if not size:
        return "80%"
    w, h = size
    return "96%" if w / h >= 1.8 else "76%"


def table_end(lines, start):
    """表の直後の行番号を返す（start は見出し行）。"""
    j = start + 2
    while j < len(lines) and lines[j].startswith("|"):
        j += 1
    return j


def emit_table(lines, start, caption):
    """見出し行 start から表を Typst の figure として組み立てる。"""
    header = split_row(lines[start])
    ncol = len(header)
    rows = [split_row(lines[j]) for j in range(start + 2, table_end(lines, start))]
    size = 8 if ncol >= 6 else 9
    buf = ["#figure("]
    buf.append("  text(size: %dpt)[#table(" % size)
    buf.append("    columns: %d," % ncol)
    buf.append("    align: %s," % ("center + horizon" if ncol >= 4 else "left + horizon"))
    buf.append("    table.header(%s)," % ", ".join("[*%s*]" % inline(c) for c in header))
    for r in rows:
        cells = (r + [""] * ncol)[:ncol]
        buf.append("    %s," % ", ".join("[%s]" % inline(c) for c in cells))
    buf.append("  )],")
    if caption:
        buf.append("  caption: [%s]," % inline(caption))
    buf.append("  kind: table, supplement: none, numbering: none,")
    buf.append(")\n")
    return "\n".join(buf)


def main():
    parser = argparse.ArgumentParser(
        description="report.md（と任意の report.meta.json）からTypst/PDFを生成する"
    )
    parser.add_argument("--source", default=DEFAULT_SRC)
    parser.add_argument("--metadata", default=DEFAULT_METADATA)
    parser.add_argument("--typst-output", default=DEFAULT_DST)
    parser.add_argument("--compile", action="store_true", help="Typst生成後にPDFまで組む")
    parser.add_argument("--pdf", help="PDF出力先。省略時は output_basename.pdf（既定 report.pdf）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存PDFを置換する。実行前に上書き承認を得ること",
    )
    args = parser.parse_args()

    source = Path(args.source)
    typst_output = Path(args.typst_output)
    metadata = load_metadata(args.metadata)
    if not source.is_file():
        sys.exit("本文が見つからない: %s" % source)
    if metadata.get("body_sha256"):
        actual_body_sha256 = file_sha256(source)
        if actual_body_sha256 != metadata["body_sha256"]:
            sys.exit(
                "report.mdがmetadata固定後に変化した: actual=%s expected=%s"
                % (actual_body_sha256, metadata["body_sha256"])
            )
    text = source.read_text(encoding="utf-8")
    lines = text.split("\n")
    title_match = next((re.match(r"^#\s+(.+)$", l) for l in lines if re.match(r"^#\s+", l)), None)
    out = [make_preamble(title_match.group(1).strip() if title_match else None)]
    chapter_pagebreak = chapter_pagebreak_enabled(metadata, text)
    i = 0
    eq_seen = 0
    equation_tags = []
    n_tables = n_figs = n_code = 0
    # 最初の章見出しより前（題名ブロック）は前置きで題名として出したので読み飛ばす。
    while i < len(lines) and not re.match(r"^##\s+", lines[i]):
        i += 1
    if i == len(lines):
        sys.exit("本文の章見出し（##）が見つからない: %s" % source)

    while i < len(lines):
        line = lines[i]

        # 見出し
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1)) - 1
            body = inline(m.group(2))
            # 章頭で改ページする。ただし付録は参考文献に続けて置く（短いので1章1ページは無駄）。
            if chapter_pagebreak and level == 1 and not m.group(2).startswith("付録"):
                out.append("#pagebreak(weak: true)")
            out.append("=" * level + " " + body + "\n")
            i += 1
            continue

        # 水平線は章の区切りなので落とす（章頭で改ページする）
        if line.strip() == "---":
            i += 1
            continue

        # コードブロック
        if line.startswith("```"):
            lang = line[3:].strip()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            body = "\n".join(buf)
            fence = "`" * max(4, (max((len(x) for x in re.findall(r"`+", body)), default=0) + 1))
            out.append(fence + lang + "\n" + body + "\n" + fence + "\n")
            n_code += 1
            i = j + 1
            continue

        # 数式
        m = re.match(r"^\$\$(.*)\\tag\{(\d+)\}\$\$$", line.strip())
        if m:
            tag = int(m.group(2))
            eq_seen += 1
            if tag != eq_seen:
                sys.exit("式の順序が番号と一致しない: %d 番目に tag=%d" % (eq_seen, tag))
            if tag not in EQUATIONS:
                sys.exit("式 %d の Typst 変換が未定義" % tag)
            equation_tags.append(tag)
            out.append("$ " + EQUATIONS[tag] + " $\n")
            i += 1
            continue

        # 画像（直後の **図N: …** をキャプションとして扱う）
        m = re.match(r"^!\[[^\]]*\]\(([^)]+)\)\s*$", line)
        if m:
            path = m.group(1)
            cap = None
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                cm = re.match(r"^\*\*(図\d+:.*)\*\*$", lines[j].strip())
                if cm:
                    cap = cm.group(1)
                    i = j
            width = image_width(path)
            out.append("#figure(")
            out.append('  image("%s", width: %s),' % (path, width))
            if cap:
                out.append("  caption: [%s]," % inline(cap))
            out.append("  kind: image, supplement: none, numbering: none,")
            out.append(")\n")
            n_figs += 1
            i += 1
            continue

        # 表のキャプション（**表N: …**）→ 直後の表と1つの figure にまとめる。
        # キャプションだけが前ページに残るのを防ぐ。
        m = re.match(r"^\*\*(表\d+:.*)\*\*$", line.strip())
        if m:
            cap = m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if (j + 1 < len(lines) and lines[j].startswith("|")
                    and re.match(r"^\|[\s:\-|]+\|$", lines[j + 1])):
                out.append(emit_table(lines, j, cap))
                n_tables += 1
                i = table_end(lines, j)
                continue
            out.append("#block(above: 1.1em, below: 0.4em)[%s]" % inline(cap))
            i += 1
            continue

        # キャプションのない表
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1]):
            out.append(emit_table(lines, i, None))
            n_tables += 1
            i = table_end(lines, i)
            continue

        # 箇条書き
        m = re.match(r"^(\s*)- (.*)$", line)
        if m:
            out.append(m.group(1) + "- " + inline(m.group(2)))
            i += 1
            continue
        m = re.match(r"^(\s*)(\d+)\. (.*)$", line)
        if m:
            out.append(m.group(1) + m.group(2) + ". " + inline(m.group(3)))
            i += 1
            continue

        # 空行・本文
        if not line.strip():
            out.append("")
        else:
            out.append(inline(line))
        i += 1

    expected_tags = metadata.get("expected_equation_tags")
    if expected_tags is not None and equation_tags != expected_tags:
        sys.exit(
            "式タグがmetadataの期待値と合わない: 本文 %r / 期待 %r"
            % (equation_tags, expected_tags)
        )

    typst_output.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("→ %s を生成した" % typst_output)
    print("   数式 %d 本 / 表 %d 件 / 図 %d 件 / コードブロック %d 件" %
          (eq_seen, n_tables, n_figs, n_code))
    print("   章改ページ: %s" % ("有効" if chapter_pagebreak else "無効（auto最適化）"))

    if args.compile:
        if args.pdf:
            pdf = Path(args.pdf)
            if not pdf.is_absolute():
                pdf = Path(HERE) / pdf
        else:
            pdf = Path(HERE) / (str(metadata.get("output_basename") or "report") + ".pdf")
        if pdf.exists() and not args.force:
            sys.exit("既存PDFを上書きしない: %s（承認後に--force）" % pdf)
        try:
            subprocess.run(
                ["typst", "compile", str(typst_output), str(pdf)],
                cwd=HERE,
                check=True,
            )
        except FileNotFoundError:
            sys.exit("typstコマンドが見つからない")
        except subprocess.CalledProcessError as exc:
            sys.exit("typst compileが失敗: exit %d" % exc.returncode)
        print("→ %s を生成した" % pdf)


if __name__ == "__main__":
    main()
