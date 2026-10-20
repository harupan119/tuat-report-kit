#!/usr/bin/env python3
"""report.md を spec.json のブロックごとに決定論的に検査する（LLM を使わない）。

本文を書いた後（エージェントでも本人でも）に通す機械検査。合格しないブロックがあれば
終了コード 1 で、どのブロックの何が足りないかを表示する。

usage:
  python report_gate.py spec.json report.md            # 検査
  python report_gate.py spec.json report.md --json out.json
  python report_gate.py spec.json --validate-only      # spec の形式だけ確かめる

report.md は spec の blocks と同じ順で `## 見出し` 区切り、または `<!-- BLK:id -->`
区切りで並んでいること（見出しが spec の heading と一致すれば見出しで対応づける）。

検査項目（fail = 不合格 / warn = 警告）:
  字数（target_chars の expansion_ratio 倍の範囲外は fail）
  用語の保存（spec の terms が本文に無い・「センサ」→「センサー」の表記揺れは fail）
  値の保存（spec の facts が本文に無い・数値や単位が変わったら fail）
  文体（register=academic でです・ます調が混ざれば fail）
  「越える」の誤用（閾値を越える → 超える。fail）
  隣接ブロックの重複（n-gram 重複率。dup_warn_pct で warn、dup_fail_pct で fail）
  簡易 AI 臭（定型の誇張語・「することができ」・全角ダッシュ・太字ラベル。warn のみ）
  英語混入の疑い（日本語の文に紛れた小文字の英単語。warn のみ）
"""
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict

DEFAULT_GATES = {"expansion_ratio": [0.85, 1.4], "dup_warn_pct": 10, "dup_fail_pct": 35}

BAN_WORDS = r'(浮き彫り|注目に値|画期的|多面的|包括的|計り知れ|今後の展開が注目|重要な役割を果た)'
POLITE = r'(です。|ます。|ません。|でしょう。|ますが|ています|ました|でした)'
PLAIN = r'(である。|だ。|ない。|する。|られる。)'
DASH = r'——'
DEKIRU = r'することができ'
BOLD_LBL = r'^\s*[-*]\s*\*\*[^*]+\*\*[:：]'
# 未翻訳の英単語。小文字4字以上に限定し、AI/CNN/ROC 等の略語は拾わない
EN_WORD = re.compile(r'(?<![A-Za-z])[a-z]{4,}(?![A-Za-z])')
# 「閾値を越え」は誤用。越える=境界を渡る / 超える=量が上回る
KOERU = re.compile(r'(閾値|基準値|基準|限界|上限|下限|許容値|許容範囲|水準|平均)を(越え|越す|越える)')


# ---------------------------------------------------------------- spec
class SpecError(ValueError):
    pass


def _str(v, path, allow_empty=False):
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        raise SpecError(f"{path} は空でない文字列である必要がある")
    return v


def _str_list(v, path):
    if not isinstance(v, list):
        raise SpecError(f"{path} は文字列の配列である必要がある")
    for i, item in enumerate(v):
        _str(item, f"{path}[{i}]")
    return v


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise SpecError("spec の最上位は object である必要がある")
    _str(spec.get("title"), "spec.title")
    if spec.get("register", "academic") not in {"academic", "polite"}:
        raise SpecError("spec.register は academic / polite のいずれか")
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise SpecError("spec.blocks は1件以上の配列である必要がある")
    seen = set()
    for i, b in enumerate(blocks):
        path = f"spec.blocks[{i}]"
        if not isinstance(b, dict):
            raise SpecError(f"{path} は object である必要がある")
        bid = _str(b.get("id"), f"{path}.id")
        if bid in seen:
            raise SpecError(f"block id が重複している: {bid}")
        seen.add(bid)
        _str(b.get("role"), f"{path}.role")
        if "heading" in b:
            _str(b["heading"], f"{path}.heading", allow_empty=True)
        t = b.get("target_chars")
        if isinstance(t, bool) or not isinstance(t, int) or t <= 0:
            raise SpecError(f"{path}.target_chars は正の整数である必要がある")
        for key in ("points", "terms", "facts"):
            _str_list(b.get(key, []), f"{path}.{key}")
    gates = spec.get("gates", {})
    if not isinstance(gates, dict):
        raise SpecError("spec.gates は object である必要がある")
    return spec


# ---------------------------------------------------------------- 本文の分割
def split_blocks(md, blocks, level=2):
    """spec の heading と本文の見出しを突き合わせる。heading が無い spec は出現順で割る。"""
    ids = [str(b["id"]) for b in blocks]
    markers = list(re.finditer(r'<!--\s*BLK:\s*([^>]+?)\s*-->', md))
    if markers:
        found = {}
        for i, m in enumerate(markers):
            bid = m.group(1).strip()
            if bid in found:
                sys.exit(f"本文の BLK marker が重複している: {bid}")
            end = markers[i + 1].start() if i + 1 < len(markers) else len(md)
            found[bid] = md[m.end():end].strip()
        missing = [b for b in ids if b not in found]
        extra = [b for b in found if b not in ids]
        if missing or extra:
            sys.exit(f"BLK marker が spec と一致しない: 不足={missing or 'なし'} / 未定義={extra or 'なし'}")
        return [found[b] for b in ids]

    marks = list(re.finditer(r'^#{%d}\s+(.+)$' % level, md, re.M))
    found, sections = defaultdict(list), []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md)
        body = md[m.end():end].strip()
        found[m.group(1).strip()].append(body)
        sections.append(body)

    if all(b.get("heading") for b in blocks):
        want = Counter(b["heading"] for b in blocks)
        bad = {h: (n, len(found.get(h, []))) for h, n in want.items() if len(found.get(h, [])) != n}
        if bad:
            sys.exit("spec と本文の見出しが一致しない:\n  "
                     + "\n  ".join(f"{h}: spec {a} / 本文 {b}" for h, (a, b) in bad.items())
                     + "\n本文にある見出し:\n  " + "\n  ".join(m.group(1).strip() for m in marks[:20]))
        used, parts = Counter(), []
        for b in blocks:
            parts.append(found[b["heading"]][used[b["heading"]]])
            used[b["heading"]] += 1
        return parts

    parts = [s for s in sections if s]
    if len(parts) != len(blocks):
        sys.exit(f"ブロック数が合わない: spec {len(blocks)}個 / 本文 {len(parts)}個")
    return parts


# ---------------------------------------------------------------- ゲート
def body_of(md):
    """フェンスドコードを除いた本文"""
    return re.sub(r'```.*?```', '', md, flags=re.DOTALL)


def n_chars(md):
    return len(re.sub(r'\s', '', body_of(md)))


def fact_present(body, fact):
    """数値・単位の内容は固定し、組版上の空白差（「15 回」と「15回」）だけを同値とする。"""
    return fact in body or re.sub(r'\s+', '', fact) in re.sub(r'\s+', '', body)


def check_block(text, block, spec, gates):
    body = body_of(text)
    n = len(re.sub(r'\s', '', body))
    target = block["target_chars"]
    lo, hi = gates["expansion_ratio"]
    fail, warn, detail = [], [], {"chars": n}

    if n < target * lo:
        fail.append(f"字数不足 {n} < {math.ceil(target * lo)}（目標{target}）")
    elif n > target * hi:
        fail.append(f"字数超過 {n} > {int(target * hi)}（埋め草・根拠の無い記述の温床）")

    # 用語固定表: 概念の保存を担保する。言い換えによるずれはここで捕まる
    lost, drift = [], []
    for t in block.get("terms", []):
        if t not in body:
            lost.append(t)
            continue
        if not t.endswith("ー") and re.search(re.escape(t) + "ー", body) \
                and not re.search(re.escape(t) + r"(?!ー)", body):
            drift.append(f"{t}→{t}ー")
    if lost:
        fail.append(f"用語消失 {lost}")
    if drift:
        fail.append(f"用語の表記揺れ {drift}")

    bad = [f for f in block.get("facts", []) if not fact_present(body, f)]
    if bad:
        fail.append(f"値の改変/欠落 {bad}")

    reg = spec.get("register", "academic")
    pol = len(re.findall(POLITE, body))
    if reg == "academic" and pol:
        fail.append(f"だ・である調違反 ですます{pol}件")
    if reg == "polite" and not pol and len(re.findall(PLAIN, body)) > 3:
        fail.append("ですます調違反")

    ko = [m.group(0) for m in KOERU.finditer(body)]
    if ko:
        fail.append(f"「越える」の誤用 {ko}（量の超過は「超える」）")

    # 簡易 AI 臭。文体の癖を知らせるだけで、合否には使わない
    ai = {"誇張語": re.findall(BAN_WORDS, body), "することができ": re.findall(DEKIRU, body),
          "全角ダッシュ": re.findall(DASH, body), "太字ラベル": re.findall(BOLD_LBL, body, flags=re.M)}
    ai = {k: len(v) for k, v in ai.items() if v}
    if ai:
        warn.append(f"AI臭 {ai}")
    detail["ai_smell"] = ai

    # 英語混入。spec で宣言した用語・値に含まれる語は正当なものとして除外する
    allow = set()
    for s in list(block.get("terms", [])) + list(block.get("facts", [])):
        allow |= set(EN_WORD.findall(s.lower()))
    s = re.sub(r'\$\$.*?\$\$|\$[^$]*\$', '', body, flags=re.DOTALL)   # 数式
    s = re.sub(r'`[^`]*`', '', s)                                      # インラインコード
    s = re.sub(r'\\[A-Za-z]+', '', s)                                  # LaTeX コマンド
    s = re.sub(r'\[[^\]]*\]\([^)]*\)', '', s)                          # リンク・図
    s = re.sub(r'[A-Za-zα-ωΑ-Ω0-9]*_[A-Za-z_0-9]+', '', s)              # 添字・識別子
    en = sorted({w for w in EN_WORD.findall(s) if w not in allow})
    if en:
        warn.append(f"英語混入の疑い {en}")

    return {"id": block["id"], "heading": block.get("heading", ""), "pass": not fail,
            "fail": fail, "warn": warn, "detail": detail}


def dup_ratio(a, b, n=8):
    """隣接ブロック間の n-gram 重複率(%)。水増し・同内容の再掲を検出する。"""
    A = {a[i:i + n] for i in range(len(a) - n + 1)}
    B = {b[i:i + n] for i in range(len(b) - n + 1)}
    return 100 * len(A & B) / max(len(B), 1) if B else 0.0


def main():
    ap = argparse.ArgumentParser(description="spec.json に沿って report.md を機械検査する")
    ap.add_argument("spec")
    ap.add_argument("report", nargs="?")
    ap.add_argument("--level", type=int, default=2, help="ブロックに使う見出しレベル（既定 2 = ##）")
    ap.add_argument("--json", help="結果を JSON で保存する")
    ap.add_argument("--validate-only", action="store_true")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):    # Windows のコンソールでも日本語を崩さない
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    try:
        with open(a.spec, encoding="utf-8") as f:
            spec = validate_spec(json.load(f))
    except (OSError, json.JSONDecodeError, SpecError) as e:
        sys.exit(f"spec を読めない: {e}")
    gates = {**DEFAULT_GATES, **spec.get("gates", {})}
    if a.validate_only:
        print(f"✓ spec OK: {spec['title']}（{len(spec['blocks'])}ブロック）")
        return
    if not a.report:
        sys.exit("report.md を指定する（spec だけ確かめるなら --validate-only）")
    with open(a.report, encoding="utf-8") as f:
        md = f.read()

    parts = split_blocks(md, spec["blocks"], a.level)
    results = [check_block(t, b, spec, gates) for t, b in zip(parts, spec["blocks"])]
    dups = []
    for i in range(1, len(parts)):
        r = dup_ratio(body_of(parts[i - 1]), body_of(parts[i]))
        rec = {"from": spec["blocks"][i - 1]["id"], "to": spec["blocks"][i]["id"], "ratio_pct": round(r, 1),
               "warn": r > gates["dup_warn_pct"],
               "fail": gates.get("dup_fail_pct") is not None and r > gates["dup_fail_pct"]}
        dups.append(rec)

    print(f"■ {spec['title']}")
    for r in results:
        mark = "✓" if r["pass"] else "✗"
        print(f"  {mark} [{r['id']}] {r['heading'][:24]:24} {r['detail']['chars']:5}字")
        for m in r["fail"]:
            print(f"      ✗ {m}")
        for m in r["warn"]:
            print(f"      ⚠ {m}")
    for d in dups:
        if d["warn"] or d["fail"]:
            print(f"  {'✗' if d['fail'] else '⚠'} 重複 [{d['from']}]→[{d['to']}] {d['ratio_pct']}%")
    ok = all(r["pass"] for r in results) and not any(d["fail"] for d in dups)
    print("✓ 全ブロック合格" if ok else "✗ 不合格のブロックがある（上の ✗ を直して再検査する）")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"pass": ok, "blocks": results, "duplicates": dups}, f, ensure_ascii=False, indent=2)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
