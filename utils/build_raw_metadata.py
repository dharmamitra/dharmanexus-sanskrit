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

_LOWER_WORDS = {'a', 'an', 'and', 'or', 'the', 'to', 'of', 'in', 'on', 'for',
                'by', 'with', 'from', 'as', 'at', 'attributed', 'thru', 'through',
                'nama', 'nāma', 'cum', 'et'}

def _cap_first(tok):
    for i, ch in enumerate(tok):
        if ch.isalpha():
            return tok[:i] + ch.upper() + tok[i + 1:]
    return tok

def titlecase(s):
    """Capitalise titles/authors, IAST-aware; keep connector words lowercase.
    Only the first letter of each word is touched (internal capitals preserved)."""
    if not s:
        return s
    out, after_break = [], True   # start of string / after ':' = capitalise
    for tok in re.split(r'(\s+)', s):
        if not tok.strip():
            out.append(tok)
            continue
        core = re.sub(r'[^\w]', '', tok).lower()
        out.append(tok if (not after_break and core in _LOWER_WORDS) else _cap_first(tok))
        after_break = tok.rstrip().endswith(':')
    return ''.join(out)

def _norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def _canon(s):
    """normalised key tolerant of a trailing 'u' (buddhanexus stems vary by ±u)."""
    n = _norm(s)
    return n[:-1] if n.endswith('u') else n

def gibbs_section(r):
    """not-before / not-after + posterior date from the Gibbs sampler TSV."""
    if not r:
        return None
    med = fmt_year(r.get('post_median'))
    lo, hi = fmt_year(r.get('crI_lo95')), fmt_year(r.get('crI_hi95'))
    out = ['## Date estimate (Gibbs model)']
    if lo and hi:
        out.append(f'**95% credible interval:** {lo} – {hi}')
    if med:
        out.append(f'**Posterior median:** {med}')
    return '\n'.join(out) if len(out) > 1 else None

# headings of the appended sections (used to strip on re-run, for idempotency)
APPENDED = re.compile(r'\n+#{1,3} (?:Date estimate\b|Web Summary\b)')
def core_only(body):
    m = APPENDED.search(body or '')
    return body[:m.start()].rstrip() if m else (body or '').rstrip()

def web_summary(rec):
    """Render the text-information.json record as a Web Summary section."""
    if not rec:
        return None
    out = ['## Web Summary']
    for label, key in [('Tradition', 'tradition'), ('Genre', 'genre'),
                       ('Estimated date', 'date_estimate')]:
        if rec.get(key):
            out.append(f'**{label}:** {rec[key]}')
    if rec.get('summary'):
        out += ['', rec['summary']]
    if rec.get('history'):
        out += ['', f'**History:** {rec["history"]}']
    rw = rec.get('related_works') or []
    rw = [w if isinstance(w, str) else (w.get('title') or w.get('id') or str(w))
          for w in rw]
    if rw:
        out += ['', '**Related works:** ' + ', '.join(rw)]
    if rec.get('confidence'):
        out += ['', f'_Web summary confidence: {rec["confidence"]}_']
    return '\n'.join(out).strip()

def fmt_year(y):
    try:
        y = int(round(float(y)))
    except (TypeError, ValueError):
        return None
    return f'{abs(y)} BCE' if y < 0 else f'{y} CE'

# Manual provenance corrections (authoritative; override all automatic logic).
# Each: edition citation (text only) + optional digitisation basis.
MANUAL_OVERRIDES = {
    'SA_T06_sambhu': {
        'edition': 'Martin Delhey (ed.), Samāhitā Bhūmiḥ: Das Kapitel über die '
        'meditative Versenkung im Grundteil der Yogācārabhūmi, Wiener Studien zur '
        'Tibetologie und Buddhismuskunde 73, Vienna: Arbeitskreis für Tibetische '
        'und Buddhistische Studien, 2009.',
        'digitised_from': 'Google Books'},
    'SA_T06_sthmavt': {
        'edition': 'Ramchandra Pandeya (ed.), Madhyānta-vibhāga-śāstra (containing '
        'the Kārikās of Maitreya, Bhāṣya of Vasubandhu and Ṭīkā of Sthiramati), '
        'Delhi: Motilal Banarsidass, 1971.'},
    'SA_T06_sthmavtyg': {
        'edition': 'Susumu Yamaguchi (ed.), Madhyāntavibhāgaṭīkā: Exposition '
        'systématique du Yogācāravijñaptivāda, Nagoya: Librairie Hajinkaku, 1934.'},
    'SA_T06_sthmavt1': {
        'edition': 'Th. Stcherbatsky (ed.), Madhyānta-vibhaṅga: Discourse on '
        'Discrimination between Middle and Extremes, Bibliotheca Buddhica XXX, '
        'Moscow–Leningrad: Academy of Sciences USSR, 1936.',
        'digitised_from': 'Google Books'},
    'SA_T07_vakobhau1': {
        'edition': 'Yasunori Ejima (ed.), Abhidharmakośabhāṣya of Vasubandhu, '
        'Chapter I: Dhātunirdeśa, Bibliotheca Indologica et Buddhologica 1, '
        'Tokyo: Sankibo Press, 1989.',
        'digitised_from': 'Google Books'},
    'SA_T07_vakobhau9': {
        'edition': 'Jong Cheol Lee (ed.), Abhidharmakośabhāṣya of Vasubandhu, '
        'Chapter IX: Ātmavādapratiṣedha, Bibliotheca Indologica et Buddhologica 11, '
        'Tokyo: Sankibo Press, 2005.',
        'digitised_from': 'Google Books'},
    'SA_T06_-ybh-klesa': {
        'title': 'Yogācārabhūmi: Kleśa Section',
        'author': 'Asaṅga (traditional attribution)',
        'edition': 'Sung Doo Ahn (ed.), Die Lehre von den Kleśas in der '
        'Yogācārabhūmi, Alt- und Neu-Indische Studien 55, Stuttgart: Franz Steiner '
        'Verlag, 2003 (Hamburg dissertation, supervised by Lambert Schmithausen).',
        'web_summary': {
            'tradition': 'Buddhist (Yogācāra / Vijñānavāda)',
            'genre': 'śāstra (Abhidharma–Yogācāra doctrinal treatise)',
            'date_estimate': 'c. 4th century CE',
            'summary': 'The section of the Yogācārabhūmi treating the defilements '
            '(kleśa): their nature, enumeration and classification, modes of '
            'operation, latent tendencies (anuśaya), and the path to their '
            'abandonment, within the school’s encyclopaedic account of the '
            'stages of yogic practice.',
            'history': 'The Yogācārabhūmi is the foundational compendium of the '
            'Yogācāra school, traditionally ascribed to Asaṅga (or revealed by '
            'Maitreya) and compiled around the 4th century CE. The Sanskrit text of '
            'its treatment of the kleśas was critically edited and studied by Sung '
            'Doo Ahn in a Hamburg dissertation supervised by Lambert Schmithausen.',
            'confidence': 'high'}},
    'SA_T06_ybh-laukikamarga': {
        'title': 'Śrāvakabhūmi: Laukikamārga',
        'edition': 'Florin Deleanu (ed.), The Chapter on the Mundane Path '
        '(Laukikamārga) in the Śrāvakabhūmi: A Trilingual Edition (Sanskrit, Tibetan, '
        'Chinese), Annotated Translation, and Introductory Study, 2 vols., Studia '
        'Philologica Buddhica Monograph Series XX, Tokyo: The International Institute '
        'for Buddhist Studies, 2006.',
        'digitised_from': 'Google Books'},
    'SA_T07_vakobha9': {
        'edition': 'Jong Cheol Lee (ed.), Abhidharmakośabhāṣya of Vasubandhu, '
        'Chapter IX: Ātmavādapratiṣedha, Bibliotheca Indologica et Buddhologica 11, '
        'Tokyo: Sankibo Press, 2005.',
        'digitised_from': 'Google Books'},
}

def main():
    files = json.load(open(f'{REPO}/SA_files.json'))
    bn_list = json.load(open(BN_FILE))
    bn_exact = {b['filename']: b for b in bn_list}
    bn_canon = {}
    for b in bn_list:
        bn_canon.setdefault(_canon(b['filename']), b)

    def bn_lookup(e):
        fn = e['filename']
        return (bn_exact.get(e.get('filenr')) or bn_exact.get(derived_key(fn))
                or bn_canon.get(_canon(derived_key(fn)))
                or bn_canon.get(_canon(e.get('filenr') or '')))
    import csv
    edw = {e['id']: e for e in json.load(open(f'{SD}/editions_workitems.json'))}
    bdw = {e['id']: e for e in json.load(open(f'{SD}/buddhist_workitems.json'))}
    tinfo = json.load(open(f'{SD}/text-information.json'))
    gibbs = {r['work']: r for r in
             csv.DictReader(open(f'{SD}/dated_gibbs_full.tsv'), delimiter='\t')}
    cats = {c['category']: c['displayName']
            for c in json.load(open(f'{REPO}/SA_category-names.json'))}

    src_count = collections.Counter()
    for e in files:
        fn = e['filename']
        ov = MANUAL_OVERRIDES.get(fn)
        title = ((ov or {}).get('title') or e.get('uniformtitle')
                 or e.get('displayName') or fn)
        if title == 'nan':
            title = fn
        else:
            title = titlecase(title)
        author = titlecase((ov or {}).get('author') or e.get('author'))
        coll = e.get('collection', '')
        cat = e.get('category', '')
        catname = cats.get(cat, cat)

        # 0. preserve hand-authored rvsb body (strip any previously-appended sections)
        if fn.startswith(RVSB) and e.get('raw_metadata', '').strip():
            core = core_only(e['raw_metadata'])
            conf = 'high'
            src_count['OCR/Dharmamitra (rvsb, preserved)'] += 1
            extras = [s for s in (gibbs_section(gibbs.get(fn)),
                                  web_summary(tinfo.get(fn))) if s]
            e['raw_metadata'] = '\n\n'.join([core] + extras)
            e['raw_metadata_confidence'] = conf
            continue

        b = bn_lookup(e)
        head = [f'# {title}', '']
        head.append(f'**DharmaNexus ID:** `{fn}`')
        if author:
            head.append(f'**Author:** {author}')
        head.append(f'**Collection / category:** {coll} / {cat} ({catname})')
        head += ['', '## Source']
        has_header = False  # True once an embedded edition-bearing header is added

        if ov:  # manual correction wins over everything
            head.append('**Source:** OCR / Dharmamitra')
            head.append(f'**Edition:** {ov["edition"]}')
            if ov.get('digitised_from'):
                head.append(f'**Digitised from:** {ov["digitised_from"]}')
            conf = 'high'
            src_count['manual-override'] += 1

        elif b:  # authoritative buddhanexus entry
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
                        has_header = True

        elif cat == 'MB':  # Muktabodha
            head.append('**Source:** Muktabodha Indological Research Institute')
            head.append('**Link:** ' + link('muktabodha.org', 'https://www.muktabodha.org')
                        + ' (Digital Library, search by title)')
            mh = muktabodha_header(fn)
            if mh:
                head += ['', '## Muktabodha catalog metadata', '', mh]
                has_header = True
            conf = 'high'
            src_count['Muktabodha'] += 1

        else:  # everything else -> OCR / Dharmamitra
            head.append('**Source:** OCR / Dharmamitra')
            # backfill author only (our catalog `source` tag is unreliable -> never used)
            rec = bdw.get(fn) or edw.get(fn)
            if rec and not author and rec.get('author'):
                head.insert(3, f'**Author:** {rec["author"]}')
            conf = 'assumed'
            src_count['OCR/Dharmamitra'] += 1

        # valuable edition citation from sanskrit-dating (text only, no patchwork URLs);
        # skip when overridden or when an embedded header already states the edition
        edition = (bdw.get(fn) or {}).get('edition')
        if edition and not has_header and not ov:
            head.append(f'**Edition:** {edition}')

        head += ['', f'**Provenance confidence:** {conf}']
        core = '\n'.join(head).strip()
        ws_rec = (ov or {}).get('web_summary') or tinfo.get(fn)
        extras = [s for s in (gibbs_section(gibbs.get(fn)),
                              web_summary(ws_rec)) if s]
        e['raw_metadata'] = '\n\n'.join([core] + extras)
        e['raw_metadata_confidence'] = conf

    with open(f'{REPO}/SA_files.json', 'w', encoding='utf-8') as f:
        json.dump(files, f, ensure_ascii=False, indent=2)

    print(f'Wrote raw_metadata to {len(files)} entries.\n\nSource distribution:')
    for k, v in src_count.most_common():
        print(f'  {v:5}  {k}')

if __name__ == '__main__':
    main()
