#!/usr/bin/env python3
"""Detect successful Tibetan (bo) / Chinese (zh) translation alignments for each
Sanskrit text and emit utils/translations.json  {sa_id: {bo: id, zh: id}}.

Source: mitra-parallel alignment TSVs (src=Sanskrit segments, tgt=bo/zh).
Many alignments are spurious; a real translation covers a substantial share of
the source. Per (text, language) we take the LONGEST alignment and accept it iff
  aligned_src_segments >= 50  OR  aligned_src/total_src >= 0.10
The target's dharmanexus id is constructed and validated against the set of real
nexus files in file_coverage_report.tsv (so we never emit a dead link).
"""
import os, re, glob, json, csv, collections

REPO = '/home/sebastian/data/dharmanexus-sanskrit'
MROOT = os.path.expanduser('~/code/mitra-multilingual-matching')
TSV = f'{MROOT}/mitra-parallel/mitra-parallel/tsv'
COV = f'{MROOT}/file_coverage_report.tsv'

def canon_id(target):
    core = target.split('_')[0]                       # drop _H…, _001 suffixes
    m = re.match(r'([A-Z]+\d+)(D\d+)', core)           # Tibetan Derge
    if m:
        return 'bo', f'BO_{m.group(1)}_{m.group(2)}'
    m = re.match(r'([A-Z]+\d+)n(\d+)$', core)          # Chinese Taishō (clean)
    if m:
        return 'zh', f'ZH_{m.group(1)}_{int(m.group(2)):04d}'
    return None, None

def distinct_src(path):
    s = set()
    with open(path, encoding='utf-8', errors='replace') as f:
        next(f, None)
        for ln in f:
            i = ln.find('\t')
            if i > 0:
                s.add(ln[:i])
    return len(s)

def main():
    files = json.load(open(f'{REPO}/SA_files.json'))
    ours = {e['filename'] for e in files}
    seglen = {}
    for e in files:
        p = f'{REPO}/segments/{e["filename"]}.json'
        if os.path.exists(p):
            try:
                seglen[e['filename']] = len(json.load(open(p)))
            except Exception:
                pass

    # valid nexus file-ids (so we never link to something that isn't in the db)
    valid = set()
    for r in csv.DictReader(open(COV), delimiter='\t'):
        valid.add(r['file_id'])

    def sa_from_prefix(pre):
        m = re.match(r'([A-Z]+\d+)(.+)', pre)
        return f'SA_{m.group(1)}_{m.group(2)}' if m else None

    # candidates: (sa, lang, nexus_id) -> best tsv by size
    best = {}
    for fn in os.listdir(TSV):
        if not fn.endswith('.tsv'):
            continue
        base = fn[:-4]
        # split into source-prefix + target: target starts at last '_<CAT><Dn>'
        m = re.match(r'(.+?)_([A-Z]+\d+[Dn].*)$', base)
        if not m:
            continue
        pre, target = m.group(1), m.group(2)
        sa = sa_from_prefix(pre)
        if sa not in ours:
            continue
        lang, nid = canon_id(target)
        if not nid or nid not in valid:
            continue
        size = os.path.getsize(os.path.join(TSV, fn))
        key = (sa, lang)
        if size > best.get(key, (0,))[0]:
            best[key] = (size, fn, nid)

    out = collections.defaultdict(dict)
    stats = collections.Counter()
    for (sa, lang), (size, fn, nid) in best.items():
        n = distinct_src(os.path.join(TSV, fn))
        total = seglen.get(sa, 0)
        ok = n >= 50 or (total and n / total >= 0.10)
        stats[f'{lang}_{"ok" if ok else "reject"}'] += 1
        if ok:
            out[sa][lang] = nid

    json.dump(out, open(f'{REPO}/utils/translations.json', 'w'),
              ensure_ascii=False, indent=2)
    texts = len(out)
    bo = sum(1 for v in out.values() if 'bo' in v)
    zh = sum(1 for v in out.values() if 'zh' in v)
    print(f'wrote translations.json: {texts} texts | Tibetan={bo} Chinese={zh}')
    print('per-language accept/reject:', dict(stats))
    # spot-check
    for sa in ['SA_GK19_asvbc_1u', 'SA_GK16_dkavy12u', 'SA_GE07_hv_apppu', 'SA_K01_bhikavau']:
        print(' ', sa, '->', dict(out.get(sa, {})))

if __name__ == '__main__':
    main()
