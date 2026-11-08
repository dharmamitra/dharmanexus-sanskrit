# Update pipeline: adding new Sanskrit texts

How new texts get from this repository to DharmaNexus (parallels, text view) and Dharmamitra search
(`primary2`). These are the steps run for the Etexts_202610 batch (5–7 Nov 2026) and for
Vasubandhu's *Pañcaskandhaka* (`SA_T06_pskv`, 8 Nov 2026). The paths are those of the processing
workstation; `$PROD` is the production host (ssh `dharmamitra@…`; host and credentials are kept
out of this public repo).

Every run works on a fresh worktree of `origin/master`, never on an old local checkout.
Several tools hard-code `~/data/dharmanexus-sanskrit`. Steps 2, 4, 5 and 6 show how to point
them at the worktree. A stale checkout silently gives wrong results: the 5 Nov multilingual run
read one and skipped all 272 new texts of that batch.

```bash
cd ~/data/dharmanexus-sanskrit && git fetch origin
git worktree add -b <branch> ~/data/dharmanexus-sanskrit-wt/<name> origin/master
W=~/data/dharmanexus-sanskrit-wt/<name>     # used below
D=YYYYMMDD                                   # run date, used in folder names below
```

Keep run artefacts (lists, logs, helper scripts) in `/mnt2/code/dvarapandita/data/sa/pipeline-aux/`,
not in `/tmp`: `/tmp` is a tmpfs and is lost on reboot.

| # | Step | Where | Time (1 text / 270 texts) |
|---|------|-------|------|
| 1 | Catalog entry + segments | local | – |
| 2 | byt5 analysis | local GPU | seconds / ~1 h |
| 3 | dvarapandita sa↔sa matches | local CPU | 7 min / 40 min |
| 4 | Statistical dating | local CPU | ~25 min |
| 5 | sa↔bo / sa↔zh alignment | local GPU | 3 min / ~4 h |
| 6 | Search embeddings (best200) | local GPU | 5 min / hours |
| 7 | PR + merge | GitHub | – |
| 8 | PG: metadata + segments | prod | ~10 min |
| 9 | PG: sa↔sa matches | prod | minutes |
| 10 | PG: multilingual matches | prod | minutes |
| 11 | primary2 search index | prod | minutes / ~20 min |
| 12 | Caches + checks | prod | – |

## 1. Catalog entry and segments

- **Segments** go in `segments/<filename>.json`: a list of
  `{segmentnr: "<fn>:<i>", original, analyzed: "", folio: (i//10)+1, full_analysis: []}`, numbered from 0.
  - Segmentation of e-texts must be lossless: strip only BOM/zero-width characters and blank lines,
    keep `%` comment lines, split lines over ~350 chars at a daṇḍa (`split_long`/`build_segments` in
    `utils/import_ilx_skt.py`; `utils/` is gitignored).
  - OCR'd editions need a cleaning pass: drop the apparatus and running heads, rejoin hyphenated
    words, transliterate to IAST, and use `/` and `//` for daṇḍas (the majority convention).
- **Catalog entry** in `SA_files.json` with these fields:
  - `displayName` ("Author: Title"), `textname` = `filename`, `collection`, `category`, `filenr`,
    `uniformtitle`, `author`
  - `author_id`/`authors` (Dharmamitra person id; copy it from another entry by the same author, or run
    `~/code/sanskrit-prosopography/apply_to_catalog.py`)
  - `source`, `raw_metadata`, `raw_metadata_confidence`, `not_before`/`not_after` (step 4)
- **`metadata/<fn>-metadata.json`** holds the plain catalog fields (`displayName`, `textname`,
  `filename`, `collection`, `category`, `filenr`, `uniformtitle`, `author`, `source`), indent 2.
- **`raw_metadata`** follows the layout of `utils/provenance/format_sa.py`, in this order:
  1. header fields (`DharmaNexus ID`, `Author`, `Author ID`, `Collection / category`, `Source`, `Edition`)
  2. `## Versions in other languages`, linking `BO_…`/`ZH_…` texts that exist in the DharmaNexus
     Tibetan/Chinese catalogs (whole-catalog pass: `utils/provenance/harmonize.py`)
  3. `## Edition and provenance`
  4. `## Contents`
  5. `## Date estimate` (step 4)

  Writing conventions are in `utils/provenance/CONVENTIONS.md`. Bulk provenance for many texts:
  `utils/provenance/gemini_pass.py` + review, merged with `utils/provenance/apply.py`.
- **Sort and check:**
  - `python sort_catalog.py` puts the catalog in library order. Always run it: the prod DB order is
    the array order. `python sort_catalog.py --check` verifies.
  - Every catalog filename has a segment file.
  - No `\u0000` in the segment files (`grep -l '\\u0000' segments/<fn>.json`): Postgres rejects NUL bytes.
  - Duplicate check against existing segments: a 40-char shingle overlap of ≥ ~88% means the same
    source; skip it. Different editions are kept side by side.
  - Files over 100 MB are rejected by GitHub. Split them at chapter colophons into `<fn>_partN`
    entries ("(part N of M)") before the first push.

## 2. byt5 analysis (`analyzed`, `full_analysis`)

`~/code/sanskrit-authorship-experiments/byt5-analyzer/analyze_new.py` (miniconda3 base python,
ctranslate2 int8 model `ctranslate/ct2-byt5sanskrit-int8`). It fills every segment whose `analyzed` is
empty: mode `S ` gives `analyzed`, mode `SLM ` gives `full_analysis`. It rewrites the files in place
and is resumable. `SEG_DIR` is hard-coded, so point it at the worktree and restrict it to the new files:

```bash
cd ~/code/sanskrit-authorship-experiments/byt5-analyzer
for g in 0 1; do CUDA_VISIBLE_DEVICES=$g python3 -c "import sys; sys.path.insert(0,'.'); import analyze_new as a; \
  a.SEG_DIR='$W/segments'; sys.argv=['analyze_new.py','--shard','$g','--num-shards','2','--file-list','<stems.txt>']; a.main()" & done; wait
```

For a single text, `--num-shards 1 --seg-glob '<fn>.json'` is enough. Speed is ~300 seg/s per GPU.
Check that no segment has a non-empty `original` and an empty `analyzed`; punctuation-only segments
legitimately stay empty.

## 3. dvarapandita sa↔sa matches (incremental)

The script is `/mnt2/code/dvarapandita/data/sa/run_incremental_YYYYMMDD.sh`. Copy the latest one,
`run_incremental_20261108.sh`, and adjust `SEG`/`CAT` (worktree), `NEWLIST`, the bucket number and the
folder names. What it does:

1. Symlink the new segment files into `segments-incrementalN/`.
2. `invoke create-vectorfiles` puts the new `.p` vector files in a new bucket `folder<k>`.
3. Every older bucket becomes a symlink-only folder (`vectors.idx`, `wordlist_*.p`,
   `wordlist_manifest.json`, no `.p`), so only the new texts are queried. Current buckets:
   `work/folder1-4`, `work-incremental/folder5`, `work-incremental2/folder6`,
   `work-incremental3/folder7`. The next run adds folder8 and symlinks folder7 as well.
4. `invoke create-new-index` on the new bucket (new vs new).
5. `invoke get-results-from-index` per bucket (`--index-method=cpu --alignment-method=local`).
6. gzip integrity check.
7. `invoke merge-results-for-db` writes `output-incremental-YYYYMMDD/`.
8. `clean_match_folder.py` with the worktree catalog and `pipeline-aux/renames.tsv` and
   `pipeline-aux/inc_stale.txt`. The old indices still contain removed texts and pre-rename names;
   cleaning renames those and drops matches to texts that are no longer in the catalog.
9. Copy the live DB folder `~/data/dharmanexus-data/matches/sa` to `sa.new-YYYYMMDD`, clean it the
   same way, then `merge_match_folders.py` folds in the increment.
10. `flag_match_types.py` (classify-only, model `boilerplate-flagging/models/sa_model20k.bin`, state
    copied from the previous `flag-state-YYYYMMDD`) adds `match_type` to every record.

Then build the PG increment, i.e. only the records whose root or par text is new:

```python
# matches/sa.new-YYYYMMDD -> matches/sa-incr-YYYYMMDD; one gz per source file, same name;
# keep a record if any root_segnr/par_segnr belongs to a new text; assert 'match_type' in record
```

Check that every new text has a package and that there are 0 corrupt files. Short quotations stay
below the 30-character match minimum, so a commentary that quotes its root text only as lemmata
(e.g. Sthiramati on the *Pañcaskandhaka*) can legitimately have no direct matches with it.

## 4. Statistical dating

The model lives in `~/code/sanskrit-dating`. `date_gibbs_full.py` is seeded and uses stylometric
chunks from `full_analysis`, root < commentary relations and the anchor/constraint TSVs.

- **Whole-corpus re-run:** `build_meta.py`, `extract_morph.py`, `extract_chunks.py`,
  `extract_relations.py`, `date_gibbs_full.py`, then `utils/provenance/apply.py`. This changes the
  dates of every entry; the published dates come from the 13 Oct 2026 run
  (`rerun.20261013c.log`). `build_meta.py`, `extract_chunks.py` and `extract_morph.py` hard-code
  `~/data/dharmanexus-sanskrit`.
- **Adding a few texts without moving the published dates:**
  1. Copy the model inputs into a scratch dir: `date_gibbs_full.py`, `meta.json`,
     `chunks_dense.tsv`, `chunks_fw.pkl`, `relations_work.tsv`, `translation_taq.tsv`, the anchor
     and constraint TSVs, and `lemma_freq.pkl`.
  2. Run it once unmodified. It must reproduce `dated_gibbs_full.tsv` exactly.
  3. In a second copy, add the new texts:
     - a meta entry in `meta.json`
     - chunk rows in `chunks_dense.tsv`/`chunks_fw.pkl`, computed with `extract_chunks.py`'s
       `chunk_feats` (100 segments per chunk, ≥ 200 tokens)
     - an `anchor` line in `manual_constraints.tsv` for every new text with a securely attributed,
       datable author, using the window of that author's other anchored works (grep the author in
       `manual_constraints.tsv`, `literature_anchors.tsv` and `dated_gibbs_full.tsv`). The model
       does **not** pass an author's date on to their other works; without an anchor a short text is
       dated from stylometry alone, and the result can be centuries off (the Pañcaskandhaka first came
       out as 105 BCE – 532 CE; with the Vasubandhu anchor 350–430 it is 340–438 CE)
     - `order` lines in `manual_constraints.tsv`, e.g. root text before its commentary when the
       title rule in `extract_relations.py` doesn't catch the pair
     - translation termini in `translation_taq.tsv` (`not_after` = date of the Chinese
       translation − 20)
  4. Run it and take only the new texts' rows. Also check how many existing works moved.
- **Write the result to the entry:** `not_before`/`not_after` = `crI_lo95`/`crI_hi95`, plus the
  `## Date estimate` section (format: `date_section()` in `utils/provenance/apply.py`). Keep the new
  constraint lines in `~/code/sanskrit-dating` too, so the next full re-run includes them.

## 5. Sanskrit ↔ Tibetan / Chinese alignment ("multilingual")

This step covers `Buddhist_Scriptures` and `Buddhist_Non-Scriptures` only. The repo is
`/mnt2/code/mitra-multilingual-matching`.

1. **Seed embeddings.** These are gemma windows, 3584-d, the model of the June index; don't mix in
   other models.

   ```bash
   cd ~/code/dharmamitra-vectorizer
   MITRA_EMBED_MODEL=buddhist-nlp/gemma-2-mitra-e CUDA_VISIBLE_DEVICES=0 python3 embedd_for_mitra_search.py \
     --path <dir with symlinks to the new segment files> --files-json $W/SA_files.json --metadata-dir $W/metadata \
     --require-metadata --num-gpus 1 --gpu-util 0.85 --output-dir embeddings/sa-gemma-YYYYMMDD
   ```

2. **Mining.** `src/spanmine/add_sa_works.py` takes these environment variables:
   - `ADD_SA_TAG`: run tag, gives `spanmine-work-<tag>` and `vectorized-data-<tag>`
   - `ADD_SA_REPO=$W`
   - `ADD_SA_EMB=sa-gemma-YYYYMMDD`
   - optionally `ADD_SA_ONLY=<stems.txt>`

   Without `ADD_SA_ONLY`, every Buddhist file that is not in the June index counts as new. Run the
   stages `select`, `vecdir`, `CUDA_VISIBLE_DEVICES=0 … mine`, `manifest`. Check the tier-A spans:
   a full translation should come out as one tier-A span per target, e.g. `SA_T06_pskv` →
   `BO_T06_D4059` and `ZH_T31_1612`.
3. **Stage 5b, sentence alignment.** Export `SPANMINE_WORK=$PWD/spanmine-work-<tag>` and
   `SA_SEGMENTS_DIR=$W/segments`, then run
   `~/venvs/qwen35align/bin/python src/spanmine/span_reconstruct.py $SPANMINE_WORK/spans/recon_new_sa.parquet --part k --nparts N`
   once per GPU.
4. **Stage 6, postcorrection.** With the same variables and
   `BOEN_WORK_FILES=$SPANMINE_WORK/work_files.json` (a JSON map from work id to segment files; only
   needed for filenames ending in `-N-M`), run
   `~/venvs/vllm028/bin/python src/spanmine/postcorrect.py --gpu 0 --gpu-mem 0.5 --recon $SPANMINE_WORK/recon_qwen2b-sa --out $PWD/recon-postcorrected-<tag>`.
5. **Release.** In `~/code/segmentation-postcorrection`, with the same `SA_SEGMENTS_DIR` and
   `BOEN_WORK_FILES`, run `python3 build_release.py --only --extra …/recon-postcorrected-<tag> --out …/mitra-parallel-<tag>`.
   Then write `all_ids.txt` (record ids) and `all_segnrs.txt` (every root and par segnr). They are
   used for the prod pre-check and for rollback.

`SA_SEGMENTS_DIR` is honoured by `align_pairs.py`, `spanmine/postcorrect.py` and
`segmentation-postcorrection/build_eval.py`. Without it they read `~/data/dharmanexus-sanskrit/segments`.

## 6. Search embeddings for primary2

```bash
cd ~/code/dharmamitra-vectorizer
MITRA_EMBED_MODEL=/mnt/staging/models/mitra-qwen35-embedder-mm CUDA_VISIBLE_DEVICES=0 python3 embedd_for_mitra_search.py \
  --path <dir with symlinks: new files + control files> --files-json $W/SA_files.json --metadata-dir $W/metadata \
  --require-metadata --best200 --num-gpus 1 --gpu-util 0.3 --load-workers 16 --output-dir embeddings/sa-best200-YYYYMMDD
```

- `--best200` is mandatory. It embeds IAST with the previous + current + next segment. Without it
  the vectorizer embeds Devanagari windows, which don't match the IAST query path.
- Don't run it with `python -I`: that breaks its local imports.
- **Control:** include the texts in `pipeline-aux/embed_control.txt` and compare their vectors with
  an earlier run that was verified against prod. Mean cosine must be ≈ 1.000 (2026-11-08: mean
  1.0000, p1 1.0000).
- Write the new texts' rows (without the controls) to the pickle that gets loaded, and strip NUL
  bytes.

## 7. Pull request

Commit only the new files (segments, metadata, `SA_files.json`). Then:

```bash
gh pr create -R dharmamitra/dharmanexus-sanskrit --base master …
gh pr merge <N> -R dharmamitra/dharmanexus-sanskrit --merge
```

`gh pr edit` fails with a GraphQL error; use `gh api -X PATCH repos/…/pulls/N` instead.

## 8. Prod: metadata and segments

```bash
ssh $PROD
cd ~/data/dharmanexus-data/segments/dharmanexus-sanskrit && git pull --ff-only
nohup docker exec dataloader-pg sh -c "cd /opt/buddhanexus/dataloader && invoke load-metadata --lang=sa && invoke load-text-segments --lang=sa" > ~/sa_pg_meta_segments_YYYYMMDD.log 2>&1
```

This takes ~10 min. "`*_analyzed` not in metadata" errors are normal. Run it before the match loads:
the parallels need the segments.

## 9. Prod: sa↔sa matches

1. Copy the increment and the full new folder to prod:
   `rsync -a ~/data/dharmanexus-data/matches/{sa-incr-$D,sa.new-$D} $PROD:/mnt2/dharmanexus-matches-flagged/`
   (inside `dataloader-pg` this folder is `/data/matches`).
2. Create the loader from the previous one:
   `sed 's/sa-incr-<prev>/sa-incr-<new>/; s/<prev date>/<new date>/' ~/load_sa_incr_<prev>.py > ~/load_sa_incr_<new>.py`
3. Run it: `docker cp` it to `dataloader-pg:/tmp/`, then
   `nohup docker exec dataloader-pg python3 /tmp/load_sa_incr_<new>.py > ~/sa_incr_pg_load_<new>.log`.
   It is insert-only (ON CONFLICT DO NOTHING); wait for `INCR DONE`.
4. If texts were removed or renamed, delete their parallels: create a temp table, `\copy` the list
   into it in a `psql -At` heredoc (the `-c` form fails on `\copy`), then delete.
5. Swap the folders, keeping the old one, both on prod and locally:
   `mv sa sa.pre-$D && mv sa.new-$D sa` (prod: `/mnt2/dharmanexus-matches-flagged`; local:
   `~/data/dharmanexus-data/matches`).
6. Check `select count(*) from parallels_sa` and the per-file counts for the new texts.

## 10. Prod: multilingual matches

1. `rsync` `mitra-parallel-<tag>/` to `$PROD:/mnt2/dharmanexus-matches-flagged/multilingual-<tag>-staging/`.
2. Pre-check: every segnr in `all_segnrs.txt` exists in `segments`, and no id in `all_ids.txt`
   exists in `parallels` yet.
3. Run the loader. The template is `~/load_<tag>_YYYYMMDD.sh`; copy `~/load_sa2611_20261106.sh` and
   change `STG`. It does an insert-only `load_parallels.process_file` in `dataloader-pg`, prints
   counts before and after, installs the files as `multilingual/*_<tag>_000.ndjson.gz` (picked up by
   future full loads) and flushes redis.
4. Backfill NULL `root_collection`/`par_collection` (from `files.filename`). The loader's
   `_build_files_lookup` misses filenames with diacritics.
5. Rollback: delete by `all_ids.txt`.

## 11. Prod: primary2 search index

- **Disk:** ES data is bind-mounted from `/mnt2/elasticsearch`, so stage pickles on
  `/mnt3/dharmamitra-staging/<dir>`, never on `/mnt2`. Check `df /mnt2` first: above 95%, ES sets
  every index read-only.
- **Load** with `~/replace_sa_best200.py` (in `~/code/dharmamitra-main-backend/dataloader`, env
  `/mnt2/miniconda/envs/dharmamitra_search_backend`). Its options:
  - `--pattern` selects the pickles (default `SA_20261105_*.p`)
  - `--dry-run`
  - `--drop <list>` deletes texts that left the catalog
  - `--no-prune`

  It applies the prod PCA (4096 → 1024), upserts with `_id` = segmentnr, prunes old docs of the
  same texts, and stops if ES has less than 45 GB free. The stock
  `invoke load-primary-data-es-incremental-replace` is unusable: it assumes one text per pickle.
- **Check:** the doc count for the new texts equals their number of windows, a few stored vectors
  match the local embeddings after PCA, and a semantic probe works (`~/semantic_probe.py`; allow
  ~6 s between queries for the rate limit).

## 12. Caches and final checks

- `docker exec dharmanexus-postgresql-redis-1 redis-cli FLUSHALL`
- `docker restart frontend-prod`: the frontend's 24 h in-process menu cache ignores redis. Then
  load `127.0.0.1:3100/db/sa/texts` twice; the first response is stale. (Cloudflare returns 403 to
  curl on the public URL.)
- `curl localhost:8011/menudata/?language=sa` lists the new texts.
- Open the new text in the reader. Its parallels and its bo/zh alignment should show.

## Known gaps (as of 2026-11-08)

- The 272 texts of Etexts_202610 still have no dating, no versions section and no full provenance
  write-up. They also never went through step 5, because the 5 Nov run read a stale checkout.
- The backend's own `metadata/SA_files.json` on prod dates from April 2026;
  `backfill-primary-metadata-task --lang=sa` has not been run.
- Older prod rows (~4.5M sa-sa, ~66k sa-bo, ~7k sa-zh) still have NULL `root_collection`/`par_collection`.
