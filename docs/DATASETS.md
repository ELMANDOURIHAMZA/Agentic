# Real datasets

The archives in `datasets/` are tracked with Git LFS and are intentionally
separate from application demo/test data.

| Archive | Role | Pipeline | Licence |
|---|---|---|---|
| `archive (3).zip` | PDF candidate profiles | Local profile benchmark | Verify original source licence before redistribution |
| `archive (4).zip` | PDF candidate profiles | Local profile benchmark | Verify original source licence before redistribution |
| `archive (5).zip` | Structured candidate profile records | Local-only structured benchmark | Contains identifying columns; never send raw rows to an external LLM |
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

The generated `datasets/MANIFEST.json` is ignored because it contains local
machine-specific hashes for large binary files.
