# Local Runtime Data

Large marketplace exports, generated batches, AI responses, and historical archives are intentionally excluded from Git.

Expected local paths:

- `05_DATA_MODEL/raw_erank/`
- `05_DATA_MODEL/raw_everbee/`
- `05_DATA_MODEL/sample_intake_tests/batches/`
- `05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`
- `99_ARCHIVE/`

WF1 grouped evidence commands should explicitly provide the local queue when necessary.

These runtime files remain local and in the external backup, but are not included in a fresh Git clone.
