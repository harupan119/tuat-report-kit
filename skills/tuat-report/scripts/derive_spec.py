#!/usr/bin/env python3
"""既存の report.md から spec.json を導出する。
spec を人手で書くと用語リストを推測してしまい誤検出を生むため、文書から取る。

usage: python derive_spec.py <report.md> [-o spec.json] [--level 2] [--min-chars 200]

書いた本文の用語・字数を固定して、改稿時のずれを report_gate.py で捕まえるために使う。
"""
import re, json, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_gate import n_chars
from collections import Counter

# 本文から除くもの
def strip_noise(t):
    t = re.sub(r'```.*?```', '', t, flags=re.DOTALL)     # コード
    t = re.sub(r'^\s*\|.*\|\s*$', '', t, flags=re.M)     # 表
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t)           # 図
    t = re.sub(r'^\s*[-*]\s.*$', '', t, flags=re.M)      # 箇条書き
    return re.sub(r'\n{3,}', '\n\n', t).strip()

# 役割の推定。見出し語から当てる
ROLE = [(r'要旨|概要|抄録|abstract', "要旨"),
        (r'はじめに|序論|序説|背景|緒言|導入', "序論"),
        (r'設計|方式|手法|方法|実現|実装|アプローチ', "手法"),
        (r'環境|条件', "実験条件"),
        (r'結果', "結果"),
        (r'考察|検討|議論|分析|評価', "考察"),
        (r'おわり|結論|まとめ|結び|結語|総括|展望|提言|所感|私見', "結論"),
        (r'参考文献|引用|文献', "参考文献"),
        (r'付録|appendix', "付録")]

def role_of(h):
    for pat, r in ROLE:
        if re.search(pat, h, re.I):
            return r
    return "本文"

# 用語候補: 漢字/カタカナの複合語で、複数ブロックにまたがって高頻度のもの
TERM = re.compile(r'[一-龥]{2,}[ぁ-ん]?[一-龥]*法|[ァ-ヶー]{3,}|[一-龥]{3,}')
STOP = set("場合 実験 結果 考察 本節 本章 以下 上記 図表 参照 我々 今回 一般 部分 全体 方法 場所 状態 内容 関係 影響 可能 必要 重要 使用 利用 実施 検討".split())

def terms_of(body, allbodies, min_hits=3):
    c = Counter(w for w in TERM.findall(body) if w not in STOP and len(w) >= 3)
    out = []
    for w, n in c.most_common(40):
        if n < min_hits:
            break
        # 他ブロックにも出る語＝文書全体の用語。1ブロック限定の語は拾わない
        if sum(1 for b in allbodies if w in b) >= 2:
            out.append(w)
    return out[:8]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report"); ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--level", type=int, default=2, help="ブロックに使う見出しレベル")
    ap.add_argument("--min-chars", type=int, default=200, help="これ未満の節は除く")
    ap.add_argument("--skip", default=r'参考文献|付録|目次', help="除外する見出しの正規表現")
    a = ap.parse_args()

    with open(a.report, encoding="utf-8") as f:
        md = f.read()
    pat = re.compile(r'^#{%d}\s+(.+)$' % a.level, re.M)
    marks = list(pat.finditer(md))
    if not marks:
        sys.exit(f"レベル{a.level}の見出しが無い")

    raw = []
    for i, m in enumerate(marks):
        end = marks[i+1].start() if i+1 < len(marks) else len(md)
        sec = md[m.end():end]
        raw.append((m.group(1).strip(), sec, strip_noise(sec)))

    # 字数は report_gate と同じ数え方で測る（別々に数えると導出specが自分で超過する）
    # 目標字数は report_gate 側と同じく「生の本文」を n_chars で測る。
    # 除去後の本文は用語抽出にだけ使う（測り方が違うと導出specが自分で超過する）。
    # min_chars は些末な節を弾くための閾値。役割が見出しで明示されている節
    # （要旨・結論など）は短くても実在の節なので落とさない。結論は短いのが普通で、
    # 落とすと検査対象から消える。
    def keep(h, raw_b):
        if re.search(a.skip, h):
            return False
        if role_of(h) != "本文":
            return n_chars(raw_b) > 0
        return n_chars(raw_b) >= a.min_chars

    kept = [(h, raw_b, clean_b) for h, raw_b, clean_b in raw if keep(h, raw_b)]
    if not kept:
        raise SystemExit(
            f"採用できる節が無い（見出し{len(raw)}件すべてが "
            f"{a.min_chars}字未満または除外対象）。spec は生成しない。")
    bodies = [c for _, _, c in kept]

    # 見出しで役割が決まらない文書（「問1」「問2」等）がある。当てずっぽうで
    # 埋めると 役割ごとの判定が誤って効くので、末尾の短い節だけ控えめに補い、
    # 残りは「本文」のまま利用者に知らせる。
    def with_fallback(pairs):
        roles = [role_of(h) for h, _, _ in pairs]
        sources = ["heading" if role != "本文" else "unknown" for role in roles]
        if len(pairs) >= 4 and "結論" not in roles:
            last_n = n_chars(pairs[-1][1])
            if last_n < 1200 and roles[-1] == "本文":
                roles[-1] = "結論"
                sources[-1] = "heuristic"
        return roles, sources

    roles, role_sources = with_fallback(kept)
    blocks = []
    for i, (h, raw_b, clean_b) in enumerate(kept, 1):
        blocks.append({"id": f"{i:02d}", "role": roles[i-1], "heading": h,
                       "role_source": role_sources[i-1],
                       "target_chars": n_chars(raw_b), "points": [],
                       "terms": terms_of(clean_b, bodies), "facts": []})

    title = (re.search(r'^#\s+(.+)$', md, re.M) or [None, os.path.basename(a.report)])[1]
    spec = {"title": title.strip(), "register": "academic",
            "source": os.path.abspath(a.report), "blocks": blocks}
    out = a.out or (os.path.splitext(a.report)[0] + ".spec.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    print(f"■ {spec['title']}")
    print(f"  見出しレベル{a.level}: {len(raw)}節 → 採用 {len(kept)}節"
          f"（{len(raw)-len(kept)}節を除外: 短小 or {a.skip}）")
    for b in blocks:
        print(f"  [{b['id']}] {b['role']:6} {b['target_chars']:5}字  {b['heading'][:28]}")
        print(f"        用語: {', '.join(b['terms']) or '(なし)'}")
    unknown = [b for b in blocks if b["role"] == "本文"]
    heuristic = [b for b in blocks if b["role_source"] == "heuristic"]
    if unknown:
        print(f"  ※ 役割を判定できなかった節が {len(unknown)}件あります: "
              + ", ".join(f"[{b['id']}]{b['heading'][:16]}" for b in unknown))
        print("     要旨・結論に当たる節があれば spec の role を手で直してください。")
        print("     役割が違うと、執筆時の指示（何を書く節か）がずれます。")
    if heuristic:
        print("  ※ 末尾位置から結論と推測した節があります: "
              + ", ".join(f"[{b['id']}]{b['heading'][:16]}" for b in heuristic))
    print(f"  → {out}")

if __name__ == "__main__":
    main()
