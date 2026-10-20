#!/usr/bin/env python3
"""skills/ の各スキルを Claude Code / Codex のスキルフォルダへリンクする（macOS / Windows 共通）。

usage:
  python install_skills.py                  # ~/.claude/skills と ~/.codex/skills（あるもの）へ
  python install_skills.py --target <dir>   # 置き場所を指定（複数可）
  python install_skills.py --dry-run        # 何をするかだけ表示

macOS / Linux は symlink、Windows はジャンクション（管理者権限・開発者モード不要）で張る。
既にある実フォルダや、別の場所を指すリンクは上書きしない（--force で別の場所を指すリンクだけ張り直す）。
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "skills"


def link(src, dst):
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(src), str(dst))
    else:
        os.symlink(src, dst, target_is_directory=True)


def is_link(p):
    return p.is_symlink() or (os.name == "nt" and hasattr(p, "is_junction") and p.is_junction())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    targets = [Path(t).expanduser().resolve() for t in a.target]
    if not targets:
        home = Path.home()
        targets = [d for d in (home / ".claude/skills", home / ".codex/skills") if d.exists()] or [home / ".claude/skills"]
    skills = sorted(d for d in ROOT.iterdir() if (d / "SKILL.md").exists())

    made = skipped = 0
    for target in targets:
        if not a.dry_run:
            target.mkdir(parents=True, exist_ok=True)
        print(f"▶ {target}")
        for src in skills:
            dst = target / src.name
            exists = dst.exists() or is_link(dst)
            if exists and dst.resolve() == src.resolve():
                print(f"  = {src.name}")
                continue
            if exists and not is_link(dst):
                print(f"  ⚠ {src.name}: 実フォルダがあるので飛ばした（中身を確かめてから手で退避して）")
                skipped += 1
                continue
            if exists and not a.force:
                print(f"  ⚠ {src.name}: 別の場所へのリンクがあるので飛ばした（--force で張り直す）")
                skipped += 1
                continue
            print(f"  + {src.name}")
            if a.dry_run:
                continue
            if exists:
                os.unlink(dst) if not dst.is_dir() or dst.is_symlink() else os.rmdir(dst)
            link(src, dst)
            made += 1
    print(f"{'（dry-run）' if a.dry_run else ''}✓ 作成 {made} / 飛ばした {skipped} / 対象スキル {len(skills)}")


if __name__ == "__main__":
    main()
