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

# Manual translation links (authoritative). The Yogācārabhūmi/Śrāvakabhūmi
# complex: each Sanskrit fragment renders too little of the huge T1579 / D40xx
# for the automatic coverage test, so the canonical translations are set here.
#   Chinese: T1579 (Xuanzang's complete Yogācārabhūmi) = ZH_T30_1579
#   Tibetan: D4035 main YBh · D4036 Śrāvakabhūmi · D4037 Bodhisattvabhūmi
MANUAL_TRANSLATIONS = {
    'SA_T06_n1394u':           {'bo': ['BO_T06_D4035'], 'zh': ['ZH_T30_1579']},  # Yogācārabhūmi
    'SA_T06_bsa034':           {'bo': ['BO_T06_D4037'], 'zh': ['ZH_T30_1579']},  # Bodhisattvabhūmi
    'SA_T06_ybh-laukikamarga': {'bo': ['BO_T06_D4036'], 'zh': ['ZH_T30_1579']},  # Śrāvakabhūmi: Laukikamārga
    'SA_T06_-ybh-klesa':       {'bo': ['BO_T06_D4035'], 'zh': ['ZH_T30_1579']},  # YBh kleśa section
    'SA_T06_asycsaru':         {'bo': ['BO_T06_D4035'], 'zh': ['ZH_T30_1579']},  # Śarīrārthagāthā (in YBh)
}

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

    # aggregate aligned-src count per (sa, lang, nexus_id) — merge -1/-2 parts
    agg = collections.defaultdict(int)   # (sa, lang, nid) -> max distinct_src
    for fn in os.listdir(TSV):
        if not fn.endswith('.tsv'):
            continue
        m = re.match(r'(.+?)_([A-Z]+\d+[Dn].*)$', fn[:-4])
        if not m:
            continue
        sa = sa_from_prefix(m.group(1))
        if sa not in ours:
            continue
        lang, nid = canon_id(m.group(2))
        if not nid or nid not in valid:
            continue
        n = distinct_src(os.path.join(TSV, fn))
        k = (sa, lang, nid)
        if n > agg[k]:
            agg[k] = n

    # group by (sa, lang); keep all translations within REL of the longest,
    # provided the longest itself is a genuine alignment
    REL = 0.5
    bylang = collections.defaultdict(list)        # (sa, lang) -> [(n, nid)]
    for (sa, lang, nid), n in agg.items():
        bylang[(sa, lang)].append((n, nid))
    out = collections.defaultdict(dict)
    for (sa, lang), cand in bylang.items():
        cand.sort(reverse=True)
        longest = cand[0][0]
        total = seglen.get(sa, 0)
        if not (longest >= 50 or (total and longest / total >= 0.10)):
            continue
        ids = [nid for n, nid in cand if n >= REL * longest]
        out[sa][lang] = ids

    # apply manual overrides (authoritative; ids validated against nexus list)
    for fn, langs in MANUAL_TRANSLATIONS.items():
        clean = {lg: [i for i in ids if i in valid] for lg, ids in langs.items()}
        out[fn] = {lg: ids for lg, ids in clean.items() if ids}

    json.dump(out, open(f'{REPO}/utils/translations.json', 'w'),
              ensure_ascii=False, indent=2)
    bo = sum(1 for v in out.values() if v.get('bo'))
    zh = sum(1 for v in out.values() if v.get('zh'))
    nbo = sum(len(v.get('bo', [])) for v in out.values())
    nzh = sum(len(v.get('zh', [])) for v in out.values())
    print(f'wrote translations.json: {len(out)} texts | '
          f'Tibetan {bo} texts/{nbo} links | Chinese {zh} texts/{nzh} links')
    for sa in ['SA_T07_vakobhau', 'SA_T06_vmvkbh_u', 'SA_GK19_asvbc_1u',
               'SA_GK16_dkavy12u', 'SA_K01_bhikavau', 'SA_GE07_hv_apppu']:
        print(' ', sa, '->', dict(out.get(sa, {})))

if __name__ == '__main__':
    main()
