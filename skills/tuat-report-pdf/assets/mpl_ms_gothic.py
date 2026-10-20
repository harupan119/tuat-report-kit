#!/usr/bin/env python3
"""matplotlib で MS ゴシックを使えるようにする。

MS ゴシックは 7〜22 ppem の埋め込みビットマップ（EBDT / EBLC）を持つ。この範囲
では FreeType がビットマップを返し、matplotlib の Agg バックエンドがそれを描かない
ため、文字が丸ごと消える。図の文字は 7〜9pt で、140 dpi なら 13.6〜17.5 ppem と
なり全部この範囲に入る。タイトル（12pt 以上）だけが残るので「タイトルは出るのに
軸ラベルと凡例が真っ白」という形で現れる。

ビットマップ表を外した複製を実行時に作り、それを登録して回避する。フォント本体は
配布物に入れず、手元の導入済みフォントから毎回導出する。

make_figures.py の先頭で次のように使う:

    from mpl_ms_gothic import use_ms_gothic
    plt = ...  # matplotlib.pyplot
    use_ms_gothic(plt, cache_dir=os.path.join(HERE, ".fontcache"))

MS ゴシックが導入されていなければ False を返し、rcParams は触らない。呼び出し側で
既定の日本語フォントに退避する。
"""
import os

# 導入済みの MS ゴシックを探す。macOS は ~/Library/Fonts に複製したもの、Windows は標準搭載のもの。
# 環境変数 MS_GOTHIC_PATH で明示もできる。
_CANDIDATES = [os.environ.get("MS_GOTHIC_PATH", ""),
               os.path.expanduser("~/Library/Fonts/msgothic.ttc"),
               os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msgothic.ttc")]
SRC = next((p for p in _CANDIDATES if p and os.path.exists(p)), _CANDIDATES[1])
FAMILY = "MS Gothic"


def outline_only(cache_dir, src=SRC, family=FAMILY):
    """埋め込みビットマップを外した複製を作り、その場所を返す。無ければ None。"""
    if not os.path.exists(src):
        return None
    dst = os.path.join(cache_dir, family.replace(" ", "") + "-outline.ttf")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        # fontTools は matplotlib の依存なので通常は入っている
        return None

    faces = TTCollection(src).fonts if src.lower().endswith(".ttc") else [TTFont(src)]
    for font in faces:
        if family not in {str(r) for r in font["name"].names if r.nameID == 1}:
            continue
        for tag in ("EBDT", "EBLC", "EBSC"):
            if tag in font:
                del font[tag]
        os.makedirs(cache_dir, exist_ok=True)
        font.save(dst)
        return dst
    return None


def use_ms_gothic(plt, cache_dir):
    """rcParams['font.family'] を MS ゴシックにする。できたかを返す。"""
    from matplotlib import font_manager

    path = outline_only(cache_dir)
    if not path:
        return False
    font_manager.fontManager.addfont(path)
    if not any(f.name == FAMILY for f in font_manager.fontManager.ttflist):
        return False
    plt.rcParams["font.family"] = FAMILY
    return True


def missing_glyphs(text, src=SRC, family=FAMILY):
    """text のうち MS ゴシックに字形が無い文字を返す。凡例を書く前に確認する。

    `⌈ ⌉ ⌊ ⌋` は MS ゴシックにも Hiragino Sans にも無い。図では語で書く
    （「log2(N+1) の切り上げ +1」）。下付き（₂）や上付き（⁶）は MS ゴシックにある。
    """
    from fontTools.ttLib import TTCollection

    for font in TTCollection(src).fonts:
        if family in {str(r) for r in font["name"].names if r.nameID == 1}:
            cmap = font.getBestCmap()
            return sorted({c for c in text if ord(c) > 0x7F and ord(c) not in cmap})
    return []
