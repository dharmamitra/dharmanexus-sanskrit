# Prosopography of the SA corpus (draft)

A person authority file for the authors of the texts in `SA_files.json`. It extends the ATII Indic persons list and is cross-linked to the Pandit prosopographical database.

**Status: LLM-generated draft, checked automatically but not yet by a specialist.** Records with status `X`, and everything in `review_queue.tsv`, still need review.

## Licence

The person records are cross-linked to Pandit data, taken from the [Pāṇḍitya export](https://github.com/tylergneill/panditya), which is CC BY-NC-SA 4.0. The files in this directory therefore inherit **CC BY-NC-SA 4.0**. That includes Pandit ids, years and work relations used for linking and checking.

## Files

| file | content |
|---|---|
| `persons.json` | one record per person, full detail: names, floruit, ATII/Pandit ids, texts, flags, justification, models used |
| `persons_atii_schema.tsv` | the same records in the ATII column layout, plus `pandit_id`, `existing_atii_record`, `confidence`, `candidate_corrections`, `label`. ID = the existing ATII id where linked, otherwise a new `P0SA####` |
| `text_person_links.tsv` | one row per author slot of an SA text: text → person, role (mūla, ṭīkā, bhāṣya, …), attribution status (`secure` / `traditional` / `disputed` / `pseudepigraphic`), confidence |
| `attestations.tsv` | evidence per person. `kind=literature`: verbatim quote from the secondary literature (reference-literature, hamburg-ardi, dharmanexus-modern-japanese); `verified` = quote found verbatim in the retrieved passage. `kind=web`: claim tied to a Google Search result by the grounding metadata; `reliable_source` = reference-grade source (academic publisher, university repository, archive.org, catalogues, Wikipedia) |
| `crosswalk.tsv` | person ↔ ATII ids ↔ Pandit ids |
| `review_queue.tsv` | persons needing review (status X, confidence < 0.75, or several soft flags), lowest confidence first |
| `authority_corrections.tsv` | proposed corrections to ATII, Pandit and ilx_skt: records that lump several persons, duplicate records, dates that disagree, wrong names (e.g. ATII P7641 Kamalaśīla has `names_skt` = "Jayasena") |
| `validation.tsv`, `validation_summary.json` | checks against `raw_metadata` and dating evidence (below) |
| `eval_pandit_holdout.tsv` | evaluation against Pandit e-text links that were hidden from the model |
| `summary.json` | counts and token usage |

Person records follow ATII conventions. Status `OK` means identity and floruit (to within about a century) are settled; otherwise `X`. Pseudepigraphic attributions are collected under separate `pseudo-<Name> (attributions)` persons; Śaṅkara, for example, splits into 31 secure texts and 88 pseudepigraphic ones. Anonymous texts (empty `author` field) are not covered.

## Numbers

**Persons**
- 906 persons:
  - 282 linked to an existing ATII record;
  - 624 new;
  - 400 linked to Pandit;
  - 39 pseudo-persons.
- 684 have status OK.
- 47 non-pseudo persons have no date.

**Links**
- 2,406 text–person links:
  - secure 1,913;
  - traditional 228;
  - disputed 132;
  - pseudepigraphic 133.

**Evidence**
- 2,654 attestations, 2,590 of them verified.
- 819 persons have at least one verified attestation.

**Evaluation**
- **Pandit holdout:** 212/221 held-out links agree. The rest:
  - 5 have no Pandit link;
  - 4 are a different person. These are mostly contested cases: Maitreya vs Asaṅga, and Kambalapāda of the *Navaślokī* vs the earlier Kambala.
- **ilx_skt ATII author ids in `raw_metadata`:**
  - The raw model output agreed on 216/284 links. After the link rescue step it agreed on 244/284; those ids had not yet been used as input.
  - They are an input now, which gives 269/284. Most of the remaining 15 are errors in ilx_skt or ATII.

## How it was made

Pipeline code: `~/code/sanskrit-prosopography` (not in this repository; `run.sh` reruns everything).

1. **Author slots and name clusters.** Author slots come from the `author` field, and names are grouped by spelling (diacritics folded). Each cluster gets candidates from ATII and Pandit. SA texts are joined to Pandit works via SETI e-text URLs; half of these links are held out for evaluation.
2. **Literature passages.** Passages are retrieved from the three secondary-literature corpora: name + work-title co-occurrence first, then name + a dating cue.
3. **Model resolution.** There is one model call per cluster, first with Gemini Flash on all 882 clusters, then with Gemini Pro on the flagged ones. Each call:
   - splits the cluster into persons;
   - links each person to ATII or Pandit records;
   - assigns roles, attribution status and a floruit;
   - gives quotes, which are checked verbatim in code.
4. **Merge and checks.** Persons are merged across clusters on shared ATII, Pandit or Muktabodha ids or declared spelling variants, unless their floruits differ by more than 250 years. Each ATII id belongs to one person only. The merged records are checked against:
   - ATII and Pandit dates;
   - the statistical text dates;
   - commentary order (a commentator cannot predate the base-text author);
   - Pandit links.
5. **Validation against `raw_metadata`** (`validation.tsv`):
   - dating anchors from `sanskrit-dating`;
   - the "Works in this e-text" roles;
   - ilx_skt author ids (ATII and Muktabodha);
   - doubt wording in the attribution notes.
6. **Round 2.** Gemini Pro was re-run on the 213 clusters with contradictions, validation issues, disputed links or cross-cluster merges. It got review notes and the relevant `raw_metadata` lines.
7. **Search pass.** Gemini Pro with Google Search grounding ran on the 263 unresolved persons, one person at a time; it never regroups texts.
   - A floruit replaces an existing one only if a date claim is grounded in a reference-grade source.
   - A move of more than 150 years becomes a hard flag.
   - A record becomes OK only with a reliable date claim plus a grounded identity claim.

Total API cost was about $67.

## Known issues

- **Moved dates:** the search pass moved 9 floruits by more than 150 years, and they are flagged for review. At least one is a homonym mix-up: Śivānandācārya of the *Kulapradīpa* was dated by the 1674 author of the *Siṃhasiddhāntasindhu*.
- **Contested identifications:** some merges follow traditional identifications that scholars reject, e.g. Kātyāyana = Vararuci, Buddhajñānapāda = Buddhaśrījñāna, Bilvamaṅgala = Līlāśuka.
- **Statistical dates:** these often date the root text inside a commentary e-text, so disagreement with a commentator's floruit is a soft flag only.
- **Source quality:** about 40% of the web claims come from weak sources (Scribd, blogs, stotra sites); see `reliable_source`.
- **Upstream metadata errors found** (not fixed here):
  - the ilx_skt file name of `SA_GK19_ilx_ws_bhavaprakasah_saradatanayah` names Śāradātanaya, but the text is Bhāvamiśra's medical *Bhāvaprakāśa*, filed under GK19 Poetry;
  - several `sanskrit-dating` anchors give a modern composition the date of a classical work with the same title (Yaśodharācarita, Abhisamayālaṅkāra manual, Caryāgītikoṣa Upodghāta);
  - the catalogue attribution note for the Bhāvanākrama copies ATII's wrong name "Jayasena".
