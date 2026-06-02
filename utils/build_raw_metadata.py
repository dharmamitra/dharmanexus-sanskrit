#!/usr/bin/env python3
"""Build raw_metadata + raw_metadata_confidence for every SA_files.json entry
from the authoritative skt-files-buddhanexus.json.

Rules:
  - Join SA_files entry to buddhanexus by `filenr` or derived <cat><stem> key.
  - If matched: source + clickable link come from buddhanexus (source of truth).
      GRETIL -> also embed the verbatim local-mirror header (copyright stripped).
  - category == MB        -> Muktabodha (+ muktabodha.org catalog header).
  - SA_GV01_rvsb_*        -> keep existing hand-authored raw_metadata.
  - everything else       -> source "OCR / Dharmamitra".
Writes SA_files.json in place (2-space indent, ensure_ascii=False, no final NL).
"""
import json, re, os, html as H, collections

REPO = '/home/sebastian/data/dharmanexus-sanskrit'
SD = '/home/sebastian/code/sanskrit-dating'
BN_FILE = f'{SD}/skt-files-buddhanexus.json'
GRET_ROOT = '/home/sebastian/data/GRETIL-mirror/gretil.sub.uni-goettingen.de/gretil'
TXT = '/home/sebastian/data/sanskrit-texts/texts'
RVSB = 'SA_GV01_rvsb_'

SOURCE_LABEL = {
    'GRETIL': 'GRETIL (Göttingen Register of Electronic Texts in Indian Languages)',
    'DSBC': 'Digital Sanskrit Buddhist Canon (DSBC)',
    'SC': 'SuttaCentral',
    'BuddhaNexus': 'BuddhaNexus',
}

def https(u):
    u = (u or '').strip()
    return 'https://' + u[7:] if u.startswith('http://') else u

def link(label, url):
    url = https(url)
    if label.startswith('http'):
        label = https(label)
    return f'[{label}]({url})' if url else label

# ---- GRETIL header (from local mirror, copyright stripped) ----
HEADER_END = re.compile(r'FOR REFERENCE PURPOSES|COPYRIGHT AND TERMS OF USAGE'
                        r'|description: ?multibyte sequence|Text converted to Unicode'
                        r'|For a comprehensive list of GRETIL', re.I)
TAIL_JUNK = re.compile(r'^(THIS|GRETIL|TEXT FILE IS.*|PLAIN TEXT VERSION|_+|\W*)$', re.I)
COPYRIGHT = re.compile(r'reference purposes|copyright|terms of usage|all rights reserved'
                       r'|may not.*(?:copied|reproduced|republished|distributed|sold)'
                       r'|may be viewed only|express permission|©', re.I)

def local_from_link(url):
    m = re.search(r'/gretil/(.+\.html?)', url or '')
    if m:
        p = os.path.join(GRET_ROOT, m.group(1))
        if os.path.exists(p):
            return p
    return None

def gretil_header(path):
    raw = open(path, encoding='utf-8', errors='replace').read()
    raw = re.sub(r'(?is)<style.*?</style>|<head.*?</head>', ' ', raw)
    raw = re.sub(r'<[^>]+>', '\n', raw)
    raw = H.unescape(re.sub(r'[ \t]+', ' ', raw))
    lines = [ln.strip() for ln in raw.split('\n') if ln.strip()]
    out = []
    for ln in lines:
        if HEADER_END.search(ln):
            break
        out.append(ln)
    if len(out) >= 2 and out[0] == out[1]:
        out = out[1:]
    while out and TAIL_JUNK.match(out[-1]):
        out.pop()
    dedup = []
    for ln in out:
        if not dedup or dedup[-1] != ln:
            dedup.append(ln)
    kept = [ln for ln in dedup if not COPYRIGHT.search(ln)]
    return '\n'.join(kept).strip()

# ---- Muktabodha catalog header ----
MB_FIELDS = ['Uniform title', 'Author', 'Commentator', 'Editor', 'Description',
             'Notes', 'Publisher', 'Publication year', 'Publication country', 'Revision']
def muktabodha_header(fn):
    p = os.path.join(TXT, fn + '.txt')
    if not os.path.exists(p):
        return None
    raw = open(p, encoding='utf-8', errors='replace').read().replace('\xa0', ' ')
    labels = '|'.join(re.escape(f) for f in MB_FIELDS)
    out = []
    for m in re.finditer(rf'({labels})\s*:\s*(.*?)(?=(?:{labels})\s*:|\n|#)', raw, re.S):
        val = re.sub(r'\s+', ' ', m.group(2)).strip()
        if val:
            out.append(f'**{m.group(1)}:** {val}')
    return '\n'.join(out) if out else None

def derived_key(fn):
    p = fn.split('_', 2)
    return (p[1] + p[2]) if len(p) > 2 else fn.replace('SA_', '').replace('_', '')

def fmt_year(y):
    try:
        y = int(round(float(y)))
    except (TypeError, ValueError):
        return None
    return f'{abs(y)} BCE' if y < 0 else f'{y} CE'

def dating_lines(rec):
    """Render sanskrit-dating work/edition data (buddhist_ or editions_workitems)."""
    out = []
    if rec.get('edition'):
        out.append(f'**Digitised edition:** {rec["edition"]}')
    med, nb, na = fmt_year(rec.get('cur_med')), fmt_year(rec.get('cur_nb')), fmt_year(rec.get('cur_na'))
    if med or nb or na:
        rng = f' (range {nb}–{na})' if (nb and na) else ''
        out.append(f'**Estimated date (sanskrit-dating):** c. {med or "?"}{rng}')
    eu = rec.get('edition_url')
    if eu and not eu.rstrip().endswith('/'):          # skip truncated dir-only URLs
        out.append('**Edition reference:** ' + link(eu, eu))
    if rec.get('archive_url'):
        out.append('**Archive copy:** ' + link(rec['archive_url'], rec['archive_url']))
    for u in (rec.get('src') or []):
        out.append('**Source scan:** ' + link(u, u))
    return out

def main():
    files = json.load(open(f'{REPO}/SA_files.json'))
    bn_list = json.load(open(BN_FILE))
    bn = {e['filename']: e for e in bn_list}
    edw = {e['id']: e for e in json.load(open(f'{SD}/editions_workitems.json'))}
    bdw = {e['id']: e for e in json.load(open(f'{SD}/buddhist_workitems.json'))}
    cats = {c['category']: c['displayName']
            for c in json.load(open(f'{REPO}/SA_category-names.json'))}

    src_count = collections.Counter()
    for e in files:
        fn = e['filename']
        title = e.get('uniformtitle') or e.get('displayName') or fn
        author = e.get('author')
        coll = e.get('collection', '')
        cat = e.get('category', '')
        catname = cats.get(cat, cat)

        # 0. preserve hand-authored rvsb
        if fn.startswith(RVSB) and e.get('raw_metadata', '').strip():
            e['raw_metadata_confidence'] = 'high'
            src_count['OCR/Dharmamitra (rvsb, preserved)'] += 1
            continue

        b = bn.get(e.get('filenr')) or bn.get(derived_key(fn))
        head = [f'# {title}', '']
        head.append(f'**DharmaNexus ID:** `{fn}`')
        if author:
            head.append(f'**Author:** {author}')
        head.append(f'**Collection / category:** {coll} / {cat} ({catname})')
        head += ['', '## Source']

        if b:  # authoritative buddhanexus entry
            source = b.get('source') or 'unknown'
            url = b.get('link') or ''
            head.append(f'**Source:** {SOURCE_LABEL.get(source, source)}')
            if url:
                head.append('**Link:** ' + link(url, url))
            conf = 'high'
            src_count[source] += 1
            if source == 'GRETIL':
                lp = local_from_link(url)
                if lp:
                    h = gretil_header(lp)
                    if h:
                        head += ['', '## Original GRETIL header', '', '```', h, '```']

        elif cat == 'MB':  # Muktabodha
            head.append('**Source:** Muktabodha Indological Research Institute')
            head.append('**Link:** ' + link('muktabodha.org', 'https://www.muktabodha.org')
                        + ' (Digital Library, search by title)')
            mh = muktabodha_header(fn)
            if mh:
                head += ['', '## Muktabodha catalog metadata', '', mh]
            conf = 'high'
            src_count['Muktabodha'] += 1

        else:  # everything else -> OCR / Dharmamitra (enriched from sanskrit-dating)
            head.append('**Source:** OCR / Dharmamitra')
            head.append('_Not present in the buddhanexus source-of-truth catalogue; '
                        'treated as a Dharmamitra OCR / digitization._')
            tag = e.get('source')
            if tag:
                head.append(f'**Catalog source tag (pre-existing):** {tag}')
            rec = bdw.get(fn) or edw.get(fn)
            dl = dating_lines(rec) if rec else []
            if rec and not author and rec.get('author'):
                head.insert(3, f'**Author:** {rec["author"]}')  # after ID line
            if dl:
                head += ['', '## Work & edition (sanskrit-dating)'] + dl
            conf = 'assumed'
            src_count['OCR/Dharmamitra' + (' (+dating)' if dl else '')] += 1

        head += ['', f'**Provenance confidence:** {conf}']
        e['raw_metadata'] = '\n'.join(head).strip()
        e['raw_metadata_confidence'] = conf

    with open(f'{REPO}/SA_files.json', 'w', encoding='utf-8') as f:
        json.dump(files, f, ensure_ascii=False, indent=2)

    print(f'Wrote raw_metadata to {len(files)} entries.\n\nSource distribution:')
    for k, v in src_count.most_common():
        print(f'  {v:5}  {k}')

if __name__ == '__main__':
    main()
