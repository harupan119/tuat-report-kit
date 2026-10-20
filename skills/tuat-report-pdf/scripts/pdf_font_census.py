#!/usr/bin/env python3
"""PDF 内でどのフォントがどの文字を描いたかを数える。

代替フォント混入の特定に使う。`pdffonts` は使われたフォントの一覧しか出さないので、
知らない名前が出た時に「何がそのフォントに落ちたのか」が分からない。この道具は
文字まで割り出すので、原因の箇所を直接たどれる。

代替フォントの意味（macOS で出やすいもの。Windows では SimSun / MS UI Gothic などが同じ役になる）:
  SIL-Hei-Med-Jian  簡体字中国語。和文が落ちている。字形が日本語と違う
  Osaka / Osaka-Mono  macOS の代替。指定漏れ
  LastResort        どのフォントにも字形が無い。豆腐になる直前

使い方:
    python pdf_font_census.py report.pdf
    python pdf_font_census.py report.pdf --expect "MS-Mincho,MS-Gothic,TimesNewRoman"

--expect を渡すと、そこに無いフォントが使われていた場合に終了コード 1 を返す。
提出前の検算をスクリプトに組み込む時に使う。

依存: pdfminer.six（pip install pdfminer.six）
"""
import argparse
import sys
from collections import defaultdict


def census(path):
    """{フォント名: {文字: 出現数}} を返す。"""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar

    used = defaultdict(lambda: defaultdict(int))

    def walk(obj):
        for child in getattr(obj, "_objs", None) or []:
            if isinstance(child, LTChar):
                # サブセット埋め込みの接頭辞（ABCDEF+）を落とす
                used[child.fontname.split("+")[-1]][child.get_text()] += 1
            walk(child)

    for page in extract_pages(path):
        walk(page)
    return used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--expect", default="",
                    help="想定するフォント名の部分一致リスト（カンマ区切り）")
    ap.add_argument("--samples", type=int, default=20, help="表示する文字の種類数")
    args = ap.parse_args()

    used = census(args.pdf)
    expect = [s.strip() for s in args.expect.split(",") if s.strip()]
    unexpected = []

    print(f"=== {args.pdf} が使ったフォント ===")
    for font in sorted(used, key=lambda k: -sum(used[k].values())):
        chars = used[font]
        total = sum(chars.values())
        top = sorted(chars.items(), key=lambda x: -x[1])[:args.samples]
        ok = not expect or any(e in font for e in expect)
        mark = "  " if ok else "??"
        if not ok:
            unexpected.append(font)
        print(f"{mark} {font:30s} {total:6d}字 {len(chars):4d}種")
        print(f"     例: {' '.join(c for c, _ in top)}")

    if expect:
        print()
        if unexpected:
            print("=== 想定外のフォントが使われている ===")
            for font in unexpected:
                chars = sorted(used[font].items(), key=lambda x: -x[1])
                print(f"  {font}")
                print("    " + " ".join(f"{c!r}×{n}" for c, n in chars[:40]))
            print("\nフォント列の指定漏れを疑う。数式・コードブロック・記号は")
            print("本文と別のフォント列で組まれるため、個別に指定が要る。")
            return 1
        print("=== 想定外のフォントは無い ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
