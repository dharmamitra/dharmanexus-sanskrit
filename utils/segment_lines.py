#!/usr/bin/env python3
"""Create line-segmented JSON files from raw .txt sources.

Matches the existing corpus convention (segments/*.json) exactly:
  - each non-blank source line becomes one segment (blank lines dropped)
  - original = line.strip()
  - analyzed = ""               (left blank per request)
  - folio    = (index // 10) + 1
  - full_analysis = []

Usage: python segment_sentences.py <src_txt_dir> <out_dir> <name> [<name> ...]
"""
import json
import sys
from pathlib import Path


def build_segments(filename, lines):
    segs = []
    i = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        segs.append({
            "segmentnr": f"{filename}:{i}",
            "original": s,
            "analyzed": "",
            "folio": (i // 10) + 1,
            "full_analysis": [],
        })
        i += 1
    return segs


def segment_file(name, src_dir, out_dir):
    raw = (Path(src_dir) / f"{name}.txt").read_text(encoding='utf-8')
    segs = build_segments(name, raw.split('\n'))
    out = Path(out_dir) / f"{name}.json"
    out.write_text(json.dumps(segs, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    return len(segs)


def main():
    src_dir, out_dir = sys.argv[1], sys.argv[2]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for name in sys.argv[3:]:
        n = segment_file(name, src_dir, out_dir)
        print(f"{name:22} -> {n} segments")


if __name__ == "__main__":
    main()
