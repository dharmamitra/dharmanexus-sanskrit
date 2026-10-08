#!/usr/bin/env python3
"""
rename_to_sa.py — Copy files from originals/ to renamed/ with SA_ target names
as specified in the co-located metadata JSONs.

Dry-run by default. Pass --execute to actually copy.
Files already starting with SA_ are skipped.

Assignment is greedy: each source file goes to the highest-scoring JSON only,
so no file is claimed by two different JSONs.

Usage:
  python3 rename_to_sa.py [directory]            # dry run
  python3 rename_to_sa.py [directory] --execute  # copy for real
"""

import json
import re
import shutil
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

MIN_SCORE = 0.70

_args   = [a for a in sys.argv[1:] if not a.startswith('--')]
DIR     = Path(_args[0]) if _args else Path(__file__).parent
DRY_RUN = '--execute' not in sys.argv

_SKTL_SUFFIX = re.compile(
    r'(?:tantra|sutra|dharani|dhrani|kalpa|stotra|stava|sadhana|stavah|'
    r'sastra|shastra|tilaka|panjika|vivarana|samgraha)$'
)

_SCRIPTS = ('show_pairings.py', 'rename_to_sa.py')


# ── normalisation ────────────────────────────────────────────────────────────

def nfc(s):
    return unicodedata.normalize('NFC', str(s))

def stripped(s):
    nfd = unicodedata.normalize('NFD', nfc(s))
    bare = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', bare.lower())

def norm_vowels(s):
    s = re.sub(r'aa', 'a', s)
    s = re.sub(r'ii', 'i', s)
    s = re.sub(r'uu', 'u', s)
    return s

def file_core(name):
    name = nfc(name)
    name = re.sub(r'\.(?:txt|tex|doc|rtf)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^D[\d]+(?:[-\d]+)?[ _]', '', name)
    name = re.sub(r'^T\d+[-_]', '', name)
    name = re.sub(r'^PDSz[-_]', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^NAK\s+\S+\s+\S+\s+\S+\s+\S+\s+', '', name)
    return name

def fc_key(filename):
    return norm_vowels(stripped(file_core(filename)))

def file_numbers(filename):
    core = file_core(nfc(filename))
    return {n.lstrip('0') or '0' for n in re.findall(r'\d+', core)}

def title_parts(uniformtitle):
    return [stripped(p) for p in re.split(r'-', nfc(uniformtitle)) if stripped(p)]

def chapter_num(parts):
    for p in parts:
        m = re.match(r'ch0*(\d+)$', p)
        if m:
            return m.group(1).lstrip('0') or '0'
    return None

def qualifiers(parts):
    skip = re.compile(r'^ch\d+$|^\d+$')
    return [p for p in parts[1:] if p and not skip.match(p)]

def stem(key):
    return _SKTL_SUFFIX.sub('', key)


# ── matching ─────────────────────────────────────────────────────────────────

def match_score(uniformtitle, filename):
    fk     = fc_key(filename)
    ut_key = norm_vowels(stripped(uniformtitle))

    if ut_key == fk:
        return 1.0, 'exact'
    if ut_key in fk:
        return 0.9, 'substr'
    if fk in ut_key:
        return 0.85, 'substr'

    parts  = title_parts(uniformtitle)
    base   = parts[0] if parts else ut_key
    base_s = stem(base)
    ch     = chapter_num(parts)
    quals  = qualifiers(parts)
    fnums  = file_numbers(filename)

    if ch:
        ch_ok     = ch in fnums
        fk_alpha  = re.sub(r'\d', '', fk)
        prefix_ok = fk_alpha.startswith(base[:8]) or base.startswith(fk_alpha[:8])
        if ch_ok and prefix_ok:
            return 0.85, 'chapter'
        if ch_ok:
            return 0.55, 'ch-weak'

    def qual_hit(qs, key):
        return any(q[:4] in key for q in qs if len(q) >= 4)

    for b in (base, base_s):
        if not b or len(b) < 5:
            continue
        if fk.startswith(b):
            bonus = 0.03 if qual_hit(quals, fk) else 0
            return min(0.82 + bonus, 0.90), 'stem'
        if b.startswith(fk[:max(8, len(b) // 2)]) and len(fk) >= 5:
            bonus = 0.03 if qual_hit(quals, fk) else 0
            return min(0.78 + bonus, 0.90), 'stem'

    pfx = min(len(base), len(fk))
    if pfx >= 8 and base[:pfx] == fk[:pfx] and qual_hit(quals, fk):
        return 0.76, 'qual+pfx'

    ratio = SequenceMatcher(None, base, fk[:len(base) + 4]).ratio()
    if ratio >= 0.88:
        bonus = 0.03 if qual_hit(quals, fk) else 0
        return min(0.72 + ratio * 0.1 + bonus, 0.88), 'simil'

    return 0.0, 'none'


# ── assignment ───────────────────────────────────────────────────────────────

def build_assignments(json_files, text_files):
    """
    Greedy one-to-one assignment: collect all (score, json, file) triples,
    sort by descending score, then assign each file to the first (highest-
    scoring) JSON that claims it.

    Returns dict: json_path → [(score, method, file_path), ...]
    Also returns set of unmatched json_paths.
    """
    triples = []
    for jf in json_files:
        with open(jf, encoding='utf-8') as f:
            meta = json.load(f)
        title = meta.get('uniformtitle', '')
        for tf in text_files:
            score, method = match_score(title, tf.name)
            if score >= MIN_SCORE:
                triples.append((score, method, jf, tf, meta))

    triples.sort(key=lambda x: -x[0])

    assigned_files = {}   # file_path → json_path (winner)
    assignments    = {jf: [] for jf in json_files}   # json_path → [(score,method,file)]

    for score, method, jf, tf, meta in triples:
        if tf in assigned_files:
            continue   # already claimed by a higher-scoring JSON
        assigned_files[tf] = jf
        assignments[jf].append((score, method, tf, meta))

    return assignments


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if DRY_RUN:
        print("DRY RUN — pass --execute to actually rename\n")

    json_files = sorted((DIR / 'metadata').glob('SA_*-metadata.json'))
    text_files = [
        p for p in sorted((DIR / 'originals').iterdir(), key=lambda p: nfc(p.name))
        if p.suffix.lower() in ('.txt', '.tex', '.doc', '.rtf')
        and not p.name.startswith('.')
        and not nfc(p.name).startswith('SA_')
    ]

    assignments = build_assignments(json_files, text_files)

    # Group text files by their file_core key so .tex+.txt pairs are detected
    core_groups = {}   # fc_key → [path, ...]
    for tf in text_files:
        k = fc_key(tf.name)
        core_groups.setdefault(k, []).append(tf)

    renamed = skipped = 0
    errors  = []

    for jf in json_files:
        matches = assignments[jf]
        if not matches:
            print(f"  SKIP (no match)  {jf.name}")
            skipped += 1
            continue

        score, method, primary, meta = matches[0]
        target_base = meta.get('filename', '')

        # Find the full group of same-base files (e.g. .tex + .txt siblings)
        primary_core = fc_key(primary.name)
        siblings = core_groups.get(primary_core, [primary])

        for src in siblings:
            ext    = src.suffix if src.is_file() else ''
            target = DIR / 'renamed' / (target_base + ext)

            if nfc(target.name) == nfc(src.name):
                skipped += 1
                continue

            if target.exists():
                print(f"  SKIP (exists)    {nfc(src.name)}")
                print(f"                 → {nfc(target.name)}")
                skipped += 1
                continue

            flag = '  [low confidence]' if score < 0.80 else ''
            verb = 'COPY' if not DRY_RUN else 'would copy'
            print(f"  {verb:<14} {nfc(src.name)}")
            print(f"               → {nfc(target.name)}  ({score:.2f} {method}){flag}")

            if not DRY_RUN:
                try:
                    shutil.copy2(src, target)
                    renamed += 1
                except Exception as e:
                    print(f"                 ERROR: {e}")
                    errors.append((src, e))
            else:
                renamed += 1

    label = 'Would copy' if DRY_RUN else 'Copied'
    print(f"\n{label}: {renamed}, skipped: {skipped}" +
          (f", errors: {len(errors)}" if errors else ""))


if __name__ == '__main__':
    main()
