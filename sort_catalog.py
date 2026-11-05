#!/usr/bin/env python3
"""Sort SA_files.json in library order: collection -> category -> author (alphabetical) -> title (alphabetical).

* collection: order of SA_collection-names.json
* category:   order of SA_category-names.json (categories missing from it follow, by code)
* author:     the author field as catalogued (several authors: the full "A, B" string, so a root
  text's commentaries file right after the root text's author); works without an author follow
  the authored ones at the end of the category
* title:      alphabetical within each author (and among the anonymous works), then filename.
Filing ignores diacritics, case and punctuation (ALA-LC style) and compares numbers numerically
(part 2 before part 10).

Usage: python sort_catalog.py [SA_files.json] [--check]   (--check: exit 1 if not sorted, write nothing)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent


def filing(s):
    s = unicodedata.normalize('NFD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^0-9a-z ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return tuple((0, int(x), '') if x.isdigit() else (1, 0, x) for x in re.findall(r'\d+|[a-z]+', s))


def sort_key(e, coll_ix, cat_ix):
    title = e.get('uniformtitle') or e.get('displayName') or ''
    author = e.get('author') or ''
    cat = e.get('category', '')
    return (coll_ix.get(e.get('collection'), len(coll_ix)), e.get('collection', ''),
            cat_ix.get(cat, len(cat_ix)), cat,
            not author, filing(author), filing(title), author, title, e['filename'])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path = Path(args[0]) if args else HERE / 'SA_files.json'
    base = path.parent
    colls = [x['collection'] for x in json.loads((base / 'SA_collection-names.json').read_text(encoding='utf-8'))]
    cats = [x['category'] for x in json.loads((base / 'SA_category-names.json').read_text(encoding='utf-8')) if x['category']]
    coll_ix = {c: i for i, c in enumerate(colls)}
    cat_ix = {c: i for i, c in enumerate(cats)}
    cat = json.loads(path.read_text(encoding='utf-8'))
    out = sorted(cat, key=lambda e: sort_key(e, coll_ix, cat_ix))
    unlisted = sorted({e.get('category') for e in cat} - set(cat_ix))
    if unlisted:
        print('categories not in SA_category-names.json (filed last in their collection):', unlisted)
    if '--check' in sys.argv:
        ok = [e['filename'] for e in out] == [e['filename'] for e in cat]
        print('sorted' if ok else 'NOT sorted')
        sys.exit(0 if ok else 1)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'sorted {len(out)} entries')


if __name__ == '__main__':
    main()
