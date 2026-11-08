# Real datasets

The archives in `datasets/` are tracked with Git LFS and are intentionally
separate from application demo/test data. The archive names are known, but
payload contents and source licences must be verified from the downloaded
archives and their original distribution pages before enabling import or
redistribution. No Arabic CV dataset is part of the approved input scope.

| Archive | Role | Pipeline | Licence |
|---|---|---|---|
| `archive (3).zip` | PDF candidate profiles | Local profile benchmark | Not yet verified; inspect source terms before redistribution |
| `archive (4).zip` | PDF candidate profiles | Local profile benchmark | Verify original source licence before redistribution |
| `archive (5).zip` | Candidate dataset (format/content to inspect) | Not enabled pending schema and privacy review | Verify source licence and inspect for personal data before use |
| `jobs.zip` | Job postings, companies, skills and salaries | Job-posting import only | Verify original source licence before redistribution |
| `db_31_0_csv.zip` | O*NET occupational reference tables | Reference lookup only | Preserve the O*NET licence/notice |
| `ESCO dataset - v1.2.1 - classification - fr - csv.zip` | French ESCO occupations and skills | Reference lookup only | Preserve the ESCO licence/notice |

Candidate profiles and job postings must never be imported into the same
benchmark table. Candidate profile imports use `ImportedCandidateProfile`;
public application jobs use `Job`. The profile benchmark is local-only unless
the source text has been anonymised and an integration run is explicitly
authorised.

Run the integrity audit after Git LFS checkout:

```powershell
.\.venv\Scripts\python.exe scripts\verify_datasets.py
```

The expected sizes and SHA-256 values are maintained in
`scripts/verify_datasets.py`; they are checked against the downloaded files.
