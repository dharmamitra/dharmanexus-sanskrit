#!/usr/bin/env python3
"""Generate SA_T01_...-metadata.json files for the 24 stotra texts."""

import json
import unicodedata
import re
import os

OUTDIR = os.path.dirname(os.path.abspath(__file__))

def strip_diacritics(s):
    """Lowercase, strip diacritics, keep only alphanumeric."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def filenr(category, uniformtitle):
    base = uniformtitle.lstrip('*').split('-')[0]  # use part before any hyphen
    return category + strip_diacritics(base)[:10]

def make_json(author, uniformtitle, scholar='Szántó',
              category='T01', collection='Buddhist_Non-Scriptures'):
    clean_author = author.lstrip('*')
    clean_title  = uniformtitle.lstrip('*')
    # Filename-safe uniformtitle: keep hyphens, strip asterisks
    title_for_filename = clean_title
    fname = f"SA_{category}_{clean_author}_{title_for_filename}_{scholar}"
    return {
        "displayName": f"{clean_author}: {clean_title}",
        "textname":    fname + ".tei",
        "filename":    fname,
        "collection":  collection,
        "category":    category,
        "filenr":      filenr(category, uniformtitle),
        "uniformtitle": clean_title,
        "author":      clean_author,
    }

texts = [
    # (author, uniformtitle)
    ("Rādhasvāmin",   "Viśeṣastava"),
    ("Śaṃkarasvāmin", "Devātiśayastotra"),
    ("*Vasudhārā",    "*Buddhastotra"),
    ("Harṣa",         "*Mārajitstotra"),
    ("Nāgārjuna",     "Dharmadhātustava"),
    ("Nāgārjuna",     "Niraupamyastava"),
    ("Nāgārjuna",     "Lokātītastava"),
    ("Nāgārjuna",     "Paramārthastava"),
    ("Nāgārjuna",     "*Trikāyastava"),
    ("Nāgārjuna",     "Sattvārādhanastava-Lévi"),
    ("Nāgārjuna",     "Sattvārādhanastava-Cheung"),
    ("Rāhulabhadra",  "Nirvikalpastuti"),
    ("Nāgārjuna",     "Acintyastava"),
    ("Nāgārjuna",     "Narakoddharastava"),
    ("Mātṛceṭa",      "Varṇārhavarṇastotra"),
    ("Mātṛceṭa",      "Ekottarikastotra"),
    ("Mātṛceṭa",      "Śatapañcāśatka"),
    ("Candragomin",   "Deśanāstava"),
    ("anon",          "Saptajinastava"),
    ("Harṣa",         "Suprabhātastava"),
    ("Harṣa",         "Aṣṭamahācaityavandanā"),
    ("Sugataśrī",     "*Kīrtidhvajapraśasti"),
    ("Āditya",        "Vanaratnastotra"),
    ("Jñānayaśas",    "Jātakastava"),
]

for author, uniformtitle in texts:
    data = make_json(author, uniformtitle)
    outfile = os.path.join(OUTDIR, data['filename'] + '-metadata.json')
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {os.path.basename(outfile)}")

print("done.")
