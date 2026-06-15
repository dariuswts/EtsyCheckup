# WF1 EverBee Manual Search Guide

The active EverBee search queue is local runtime data and is intentionally not tracked by Git.

Expected local queue:

`05_DATA_MODEL/sample_intake_tests/WF1_everbee_manual_search_queue.csv`

For each queue phrase:

1. Search it in EverBee Product Analytics.
2. Export the CSV.
3. Place the export in:

`05_DATA_MODEL/raw_everbee/WF1/inbox/`

Queue size and active batch details should be read from the local runtime files.
