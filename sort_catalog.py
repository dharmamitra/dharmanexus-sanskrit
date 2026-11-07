#!/usr/bin/env python3
"""Sort SA_files.json in library order: collection -> category -> author (alphabetical) -> work -> part.

* collection: order of SA_collection-names.json
* category:   order of SA_category-names.json (categories missing from it follow, by code)
* author:     the author field as catalogued (several authors: the full "A, B" string, so a root
  text's commentaries file right after the root text's author); works without an author follow
  the authored ones at the end of the category
* work:       alphabetical by title within each author (and among the anonymous works)
* part:       the files of one multi-part work stay together and in part order (see below)

Multi-part works. Entries of one category whose titles share the same work title (the uniform
title up to its first " (", ":" or " with ", or the first hyphen of a filename-style title) and whose
authors are compatible (one author list contains the other, e.g. "Medhātithi" and "Manu, Medhātithi";
anonymous parts join when there is exactly one authored cluster) are filed as one
work. The work is filed under its most frequent author and its first part's title, and its parts
are ordered: the complete/unqualified text first, then the numbered parts by number ("book 3"
before "book 10", "chapter 8, part 1" before "chapter 8, part 3"), then the remaining parts by
title. Without this, parts that were catalogued with different authors (e.g. "Vyāsa" on some
Mahābhārata books only) or different title patterns ("Mahābhārata: Ādiparvan" vs "Mahābhārata
(book 3: Āraṇyakaparvan)") were scattered across the category.

Filing ignores diacritics, case and punctuation (ALA-LC style) and compares numbers numerically
(part 2 before part 10).

Usage: python sort_catalog.py [SA_files.json] [--check]   (--check: exit 1 if not sorted, write nothing)
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fold(s):
    s = unicodedata.normalize('NFD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def filing(s):
    s = re.sub(r'[^0-9a-z ]+', ' ', fold(s))
    s = re.sub(r'\s+', ' ', s).strip()
    return tuple((0, int(x), '') if x.isdigit() else (1, 0, x) for x in re.findall(r'\d+|[a-z]+', s))


def title_of(e):
    return e.get('uniformtitle') or e.get('displayName') or ''


# work title | qualifier separators: " (", ":", " with ", and in filename-style titles
# ("Kṛtyakalpataru-Gṛhasthakāṇḍa", "Mālatīmādhava-w-harihara-anka02") the first hyphen
SEP = re.compile(r'\s*\(|:|\s+with\s+|-w-|-')


def work_title(title):
    """'Mahābhārata (book 3: …)' / 'Mahābhārata: Ādiparvan' / 'X with the commentaries …' -> 'mahabharata'."""
    return ' '.join(w for _, _, w in filing(SEP.split(fold(title), maxsplit=1)[0]))


def author_names(author):
    """Individual author names, folded; spaces dropped too so 'Bhaṭṭoji Dīkṣita' == 'Bhaṭṭojidīkṣita'."""
    out = set()
    for a in (author or '').split(','):
        a = ' '.join(w for _, _, w in filing(a))
        if a:
            out |= {a, a.replace(' ', '')}
    return out


def part_key(e, wtitle):
    """Order of a part inside its work: unqualified text, then by the numbers in the qualifier, then by title."""
    t = fold(title_of(e))
    m = SEP.search(t)
    rest = t[m.start():] if m else ''
    # the qualifier after the work title, minus any "with the commentaries ..." clause before the "("
    if '(' in rest:
        qual = rest[rest.find('('):]
    elif re.match(r'\s+with\s|-w-', rest):
        qual = ''
    else:
        qual = rest
    nums = tuple(int(n) for n in re.findall(r'\d+', qual))
    if not qual.strip(' :'):
        return (0, (), filing(title_of(e)), e['filename'])
    if nums:
        return (1, nums, filing(title_of(e)), e['filename'])
    return (2, (), filing(title_of(e)), e['filename'])


def works(entries):
    """Cluster the entries of one category into works -> list of lists (catalogue input order kept)."""
    by_title = defaultdict(list)
    for e in entries:
        by_title[work_title(title_of(e))].append(e)
    out = []
    for group in by_title.values():
        clusters = []          # [[author-name sets of the members], members]
        anon = []
        for e in group:
            names = author_names(e.get('author'))
            if not names:
                anon.append(e)
                continue
            # same work if one author list contains the other ("Medhātithi" / "Manu, Medhātithi"),
            # not merely a shared root-text author ("Manu, Kullūka" / "Manu, Medhātithi")
            hit = [c for c in clusters if any(names <= n or n <= names for n in c[0])]
            if hit:
                base = hit[0]
                for c in hit[1:]:
                    base[0] += c[0]
                    base[1] += c[1]
                    clusters.remove(c)
                base[0].append(names)
                base[1].append(e)
            else:
                clusters.append([[names], [e]])
        if len(clusters) == 1:
            clusters[0][1] += anon
        elif anon:
            clusters.append([[], anon])
        out += [c[1] for c in clusters]
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path = Path(args[0]) if args else HERE / 'SA_files.json'
    base = path.parent
    colls = [x['collection'] for x in json.loads((base / 'SA_collection-names.json').read_text(encoding='utf-8'))]
    cats = [x['category'] for x in json.loads((base / 'SA_category-names.json').read_text(encoding='utf-8')) if x['category']]
    coll_ix = {c: i for i, c in enumerate(colls)}
    cat_ix = {c: i for i, c in enumerate(cats)}
    cat = json.loads(path.read_text(encoding='utf-8'))

    by_cat = defaultdict(list)
    for e in cat:
        by_cat[(e.get('collection', ''), e.get('category', ''))].append(e)
    keyed = []
    for (coll, c), entries in by_cat.items():
        for w in works(entries):
            wt = work_title(title_of(w[0]))
            parts = sorted(w, key=lambda e: part_key(e, wt))
            authors = Counter(e.get('author') or '' for e in parts if e.get('author'))
            author = authors.most_common(1)[0][0] if authors else ''
            if authors:   # ties: the alphabetically first of the most frequent
                top = max(authors.values())
                author = min((a for a, n in authors.items() if n == top), key=filing)
            wkey = (coll_ix.get(coll, len(coll_ix)), coll, cat_ix.get(c, len(cat_ix)), c,
                    not author, filing(author), filing(title_of(parts[0])), author, parts[0]['filename'])
            keyed += [(wkey, i, e) for i, e in enumerate(parts)]
    out = [e for _, _, e in sorted(keyed, key=lambda t: (t[0], t[1]))]
    assert len(out) == len(cat)

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
