#!/usr/bin/env python3
"""本文に出る文字のうち、指定フォントに字形が無いものを洗い出す。

字形が無い文字は処理系任せの代替フォントに落ちる。豆腐（□）になれば気づけるが、
別の字形で描かれると気づけない。実例として `⌈ ⌉ ⌊ ⌋` は和文・欧文フォントの
どれにも無く、代替先によっては両方とも普通の角括弧で描かれ、天井と床の対比が
消える。組む前にこれを潰す。

使い方:
    python font_coverage.py report.md --font "~/Library/Fonts/msmincho.ttc:MS Mincho"
    python font_coverage.py report.md --font "C:/Windows/Fonts/msmincho.ttc:MS Mincho"   # Windows
    python font_coverage.py report.md \
        --font "~/Library/Fonts/msmincho.ttc:MS Mincho" \
        --font "/Applications/Microsoft Word.app/Contents/Resources/DFonts/times.ttf:*" \
        --skip-code

--font は `パス:ファミリ名` の形。`.ttc` の中から名前で選ぶ。ファミリ名に `*` を
渡すと最初のフェイスを使う（単一フェイスの .ttf 用）。
複数指定した場合は「どれか1つにあれば足りている」と判定する（フォント列と同じ）。

依存: fontTools（matplotlib の依存なので通常は入っている）
"""
import argparse
import os
import re
import sys
import unicodedata


def load_cmap(spec):
    """`パス:ファミリ名` から、そのフォントが持つ符号位置の集合を返す。"""
    from fontTools.ttLib import TTFont, TTCollection

    path, _, want = spec.rpartition(":")
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise SystemExit(f"フォントが無い: {path}")

    if path.lower().endswith(".ttc"):
        faces = TTCollection(path).fonts
    else:
        faces = [TTFont(path, fontNumber=0)]

    for face in faces:
        names = {str(r) for r in face["name"].names if r.nameID == 1}
        if want == "*" or want in names:
            return want if want != "*" else sorted(names)[0], set(face.getBestCmap())
    raise SystemExit(f"{path} に {want!r} が無い。含まれるのは "
                     f"{sorted({str(r) for f in faces for r in f['name'].names if r.nameID == 1})}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="調べる本文（.md / .txt）")
    ap.add_argument("--font", action="append", required=True,
                    help="パス:ファミリ名。複数指定するとフォント列として扱う")
    ap.add_argument("--skip-code", action="store_true",
                    help="``` で囲まれたコードブロックを除く（別フォントで組む場合）")
    args = ap.parse_args()

    text = open(os.path.expanduser(args.source), encoding="utf-8").read()
    if args.skip_code:
        text = re.sub(r"```.*?```", "", text, flags=re.S)

    covered = set()
    print("=== 調べるフォント ===")
    for spec in args.font:
        name, cmap = load_cmap(spec)
        print(f"  {name}: {len(cmap)} 字")
        covered |= cmap

    missing = sorted({c for c in text if ord(c) > 0x7F and ord(c) not in covered})
    print(f"\n=== どのフォントにも字形が無い文字: {len(missing)} 種 ===")
    for c in missing:
        print(f"  {c}  U+{ord(c):04X}  {unicodedata.name(c, '?')}  本文中 {text.count(c)} 回")

    if missing:
        print("\n代替先を明示するか、字面を変える。数式記号なら本文のフォント列に")
        print("数式フォント（New Computer Modern Math など）を足すと固定できる。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
