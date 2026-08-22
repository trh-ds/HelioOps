# Maritime knowledge base — sources

Ingested by `backend/embeddings/ingest_maritime.py` into `maritime_kb`.

## Why not the IMO GMDSS Manual

`imo_gmdss_2019.pdf` was previously the only maritime source. It is **not** the
GMDSS Manual — it is the 2-page publisher catalogue page advertising it:

| | pages | extractable text |
|---|---|---|
| `imo_gmdss_2019.pdf` | 2 | 3,804 chars |
| `nat_doc_007_2025.pdf` (aviation, for scale) | 160 | 417,478 chars |

It produced 2 chunks, so maritime advisories were grounded on a book listing
while scoring the highest confidence of any industry — the `LOW_COVERAGE` flag
could not fire because it counted the 2 generic impact-matrix chunks toward
industry coverage. Both problems are fixed; the file is retired and purged from
the collection on re-ingest.

**The IMO GMDSS Manual is a paid IMO publication** (IMO Publishing, sale number
IH970E). There is no legitimate free download. If you want it in the corpus,
buy it from <https://www.imo.org/en/publications> or an IMO distributor and drop
the PDF in this directory — then add it to `_DOCS` in `ingest_maritime.py`.

## What is used instead

ITU-R Recommendations: free, and the international standards the GMDSS is
actually built on. Downloaded 2026-08-21, in-force versions.

| File | Rec | Covers | Why it matters for space weather |
|---|---|---|---|
| `itu_r_m541_dsc_operational_procedures.pdf` | M.541-11 (2023-11) | Digital Selective Calling operational procedures | The distress-alerting procedure itself — what a crew does when HF/MF DSC degrades |
| `itu_r_m1467_navtex_coverage_propagation.pdf` | M.1467-1 (2006-03) | NAVTEX / MSI sea-area coverage prediction | Predicts coverage **including skywave propagation** — the direct storm-to-safety link |
| `itu_r_m493_dsc_system.pdf` | M.493-16 (2023-12) | DSC system technical characteristics | Frequencies, call formats, error handling |
| `itu_r_m1173_hf_radiotelephony.pdf` | M.1173-1 (2012-03) | HF radiotelephony, maritime mobile | HF band plan for ship-shore voice |
| `nga_pub117_radio_navigational_aids_2014.pdf` | NGA Pub. 117 (2014) | GMDSS / distress / emergency procedure, **pages 542-581 only** | US Government, public domain. Adds operational depth alongside the ITU-R standards |

### Why Pub 117 is ingested selectively

The document is 710 pages, of which only ~118 are prose; the bulk is a
country-by-country directory of station call signs, frequencies and watch
schedules. Ingesting all of it would add roughly 1,800 chunks of tabular
listings and bury the procedure chunks the ITU-R documents provide — retrieval
would get worse, not better. `ingest_maritime.py` therefore carries a page
range per document and takes only the GMDSS / distress / emergency block.

Obtained from the Internet Archive
(`radio-navigational-aids-publication-no.-117-2014-edition.`) because
`msi.nga.mil` returns HTTP 503 to automated clients. It is a US Government work
and therefore public domain. **The 2014 edition is not current** — replace it
with the latest from NGA when the MSI portal is back up.

## Re-downloading

ITU-R Recommendations resolve by in-force version string. To find the current
one for any rec, read `https://www.itu.int/rec/R-REC-<REC>/en` and take the
version tagged `-I` (in force) rather than `-S` (superseded), then:

```
https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-<REC>-<ver>-<YYYYMM>-I!!PDF-E.pdf
```

Downloads are slow (1–3 min each); set a generous timeout.

After adding or replacing a file:

```
python -m backend.embeddings.ingest_maritime
python -m backend.embeddings.rebuild_kb --verify
```

## Considered and rejected

- **NGA Pub. 117 *Radio Navigational Aids*** — US Government, public domain,
  and the closest free equivalent to the GMDSS Manual's operational content.
  `msi.nga.mil` returned HTTP 503 on every endpoint when this was assembled.
  Worth retrying: it is a good addition if the service comes back.
