# Data Directory

- `raw/`: approved source files. The included complaint file is synthetic.
- `processed/`: canonical valid-record extracts and source profiles.
- `rejected/`: redacted rejected-record reports.
- `vector/`: portable vector index.
- `eci_demo.db`: portable SQLite system of record.

Runtime data is ignored by Git except for the included synthetic raw file. Do not place real confidential data in this repository.
