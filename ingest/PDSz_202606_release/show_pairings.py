#!/usr/bin/env python3
"""
show_pairings.py — Show pairings between SA_*-metadata.json files and
text/directory files in PDSz_release_ready/.

Usage: python3 show_pairings.py [directory]
"""

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent

_SKTL_SUFFIX = re.compile(
    r'(?:tantra|sutra|dharani|dhrani|kalpa|stotra|stava|sadhana|stavah|'
    r'sastra|shastra|tilaka|panjika|vivarana|samgraha)$'
)

_SCRIPTS = ('show_pairings.py', 'rename_to_sa.py')


def nfc(s):
    return unicodedata.normalize('NFC', str(s))


def stripped(s):
    """Remove diacritical marks, lowercase, alphanumeric only."""
    nfd = unicodedata.normalize('NFD', nfc(s))
    bare = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', bare.lower())


def norm_vowels(s):
    """Collapse ASCII double-vowel transliteration: aa→a, ii→i, uu→u."""
    s = re.sub(r'aa', 'a', s)
    s = re.sub(r'ii', 'i', s)
    s = re.sub(r'uu', 'u', s)
    return s


def file_core(name):
    """Strip file extension and collection prefixes from a filename."""
    name = nfc(name)
    name = re.sub(r'\.(?:txt|tex|doc|rtf)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^D[\d]+(?:[-\d]+)?[ _]', '', name)       # D529-888 / D1118_
    name = re.sub(r'^T\d+[-_]', '', name)                     # T366_ / T366-
    name = re.sub(r'^PDSz[-_]', '', name, flags=re.IGNORECASE)  # PDSz-
    name = re.sub(r'^NAK\s+\S+\s+\S+\s+\S+\s+\S+\s+', '', name)   # NAK 1-1076 NGMPP A 39-8
    return name


def fc_key(filename):
    """Normalised key for matching: stripped + double-vowel collapsed."""
    return norm_vowels(stripped(file_core(filename)))


def file_numbers(filename):
    """Digit sequences in file_core (before stripping) — preserves boundaries."""
    core = file_core(nfc(filename))
    return {n.lstrip('0') or '0' for n in re.findall(r'\d+', core)}


def title_parts(uniformtitle):
    """Split uniformtitle on hyphens → list of stripped parts."""
    return [stripped(p) for p in re.split(r'-', nfc(uniformtitle)) if stripped(p)]


def chapter_num(parts):
    """Return normalised chapter number if any part looks like ch14, else None."""
    for p in parts:
        m = re.match(r'ch0*(\d+)$', p)
        if m:
            return m.group(1).lstrip('0') or '0'
    return None


def qualifiers(parts):
    """Non-title, non-chapter qualifier strings (e.g. 'diplomatic', 'testimonia')."""
    skip = re.compile(r'^ch\d+$|^\d+$')
    return [p for p in parts[1:] if p and not skip.match(p)]


def stem(key):
    """Strip common Sanskrit generic suffix."""
    return _SKTL_SUFFIX.sub('', key)


def _similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def match_score(uniformtitle, filename):
    """Return (score 0.0–1.0, method str)."""
    fk = fc_key(filename)
    ut_key = norm_vowels(stripped(uniformtitle))

    # 1. Exact
    if ut_key == fk:
        return 1.0, 'exact'

    # 2. Substring
    if ut_key in fk:
        return 0.9, 'substr'
    if fk in ut_key:
        return 0.85, 'substr'

    parts  = title_parts(uniformtitle)
    base   = parts[0] if parts else ut_key
    base_s = stem(base)           # with generic Sanskrit suffix stripped
    ch     = chapter_num(parts)
    quals  = qualifiers(parts)
    fnums  = file_numbers(filename)

    # 3. Chapter match
    if ch:
        ch_ok      = ch in fnums
        fk_alpha   = re.sub(r'\d', '', fk)
        prefix_ok  = fk_alpha.startswith(base[:8]) or base.startswith(fk_alpha[:8])
        if ch_ok and prefix_ok:
            return 0.85, 'chapter'
        if ch_ok:
            return 0.55, 'ch-weak'

    # Helper: does a qualifier appear (even partially) in the file key?
    def qual_hit(qs, key):
        return any(q[:4] in key for q in qs if len(q) >= 4)

    # 4. Stem / prefix match
    for b in (base, base_s):
        if not b or len(b) < 5:
            continue
        if fk.startswith(b):
            bonus = 0.03 if qual_hit(quals, fk) else 0
            return min(0.82 + bonus, 0.90), 'stem'
        if b.startswith(fk[:max(8, len(b) // 2)]) and len(fk) >= 5:
            bonus = 0.03 if qual_hit(quals, fk) else 0
            return min(0.78 + bonus, 0.90), 'stem'

    # 5. Shared prefix (at least 8 chars) + qualifier hit
    pfx = min(len(base), len(fk))
    if pfx >= 8 and base[:pfx] == fk[:pfx] and qual_hit(quals, fk):
        return 0.76, 'qual+pfx'

    # 6. High string similarity on base alone
    ratio = _similarity(base, fk[:len(base) + 4])
    if ratio >= 0.88:
        bonus = 0.03 if qual_hit(quals, fk) else 0
        return min(0.72 + ratio * 0.1 + bonus, 0.88), 'simil'

    return 0.0, 'none'


def main():
    json_files = sorted((DIR / 'metadata').glob('SA_*-metadata.json'))
    text_files = [
        p for p in sorted((DIR / 'originals').iterdir(), key=lambda p: nfc(p.name))
        if p.suffix.lower() in ('.txt', '.tex', '.doc', '.rtf')
        and not p.name.startswith('.')
    ]

    matched_texts = set()
    results = []

    for jf in json_files:
        with open(jf, encoding='utf-8') as f:
            meta = json.load(f)
        title  = meta.get('uniformtitle', '')
        target = meta.get('filename', '')

        scored = [(match_score(title, tf.name) + (tf,)) for tf in text_files]
        scored = [(s, m, tf) for s, m, tf in scored if s > 0]
        scored.sort(key=lambda x: -x[0])

        results.append((title, target, jf, scored))
        if scored:
            matched_texts.add(scored[0][2])

    print(f"{'uniformtitle':<52} {'text file':<52} {'score':>5}  method")
    print('-' * 125)

    unmatched_jsons = []
    for title, target, jf, scored in results:
        if scored:
            score, method, tf = scored[0]
            flag = ' ?' if score < 0.70 else ''
            alts = [nfc(m[2].name) for m in scored[1:3]
                    if len(scored) > 1 and score < 0.9]
            alt_str = f"  [alt: {', '.join(alts)}]" if alts else ''
            print(f"{title:<52} {nfc(tf.name):<52} {score:>5.2f}  {method}{flag}{alt_str}")
        else:
            unmatched_jsons.append((title, jf.name))
            print(f"{title:<52} {'NO MATCH':<52} {0:>5.2f}  -")

    unmatched_texts = [f for f in text_files if f not in matched_texts]

    if unmatched_jsons:
        print(f"\n=== JSONs with no text file match ({len(unmatched_jsons)}) ===")
        for title, jname in unmatched_jsons:
            print(f"  {jname}")

    if unmatched_texts:
        print(f"\n=== Text files with no JSON ({len(unmatched_texts)}) ===")
        for f in unmatched_texts:
            print(f"  {nfc(f.name)}")


if __name__ == '__main__':
    main()
