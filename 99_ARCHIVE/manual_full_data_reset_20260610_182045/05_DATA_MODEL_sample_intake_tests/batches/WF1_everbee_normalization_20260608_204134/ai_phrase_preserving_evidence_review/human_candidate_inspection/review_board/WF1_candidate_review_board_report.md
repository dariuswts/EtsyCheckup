# WF1 Candidate Review Board Report

## Scope

Created a static local browser review board for the 63 WF1 AI-reviewed candidate evidence rows. The board supports manual evidence routing decisions for later WF2 hypothesis drafting.

## Guardrails Confirmed

- No AI was run.
- No OpenAI API call was made.
- No scraping was performed.
- No scoring or `opportunity_score` was created.
- No product concepts or design briefs were created.
- No generated designs were created.
- No Etsy or Printify actions were taken.
- No n8n workflows were created.
- No database files were created.
- No candidates were auto-approved.
- Raw EverBee CSVs were not moved, renamed, or modified.

## Inputs

- Input queue: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/WF1_candidate_human_inspection_queue.csv`
- Input candidate rows: `63`

## Outputs

- Review board HTML: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/review_board/WF1_candidate_review_board.html`
- Review board data JSON: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/review_board/WF1_candidate_review_board_data.json`
- Guide: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/review_board/WF1_candidate_review_board_guide.md`
- Report: `05_DATA_MODEL/sample_intake_tests/batches/WF1_everbee_normalization_20260608_204134/ai_phrase_preserving_evidence_review/human_candidate_inspection/review_board/WF1_candidate_review_board_report.md`

## Method

The script reads the WF1 human inspection CSV, removes forbidden/approval-named columns, resets human decision fields to blank, writes an adjacent JSON data file, and writes a self-contained local HTML review board with embedded candidate data.

The board groups cards by `queue_phrase`, sorts strong candidates before possible candidates, provides filters, stores markings in browser local storage, and exports manual decisions as CSV.

## Row Counts

- Review board candidates: `63`
- Queue phrases: `11`

## Candidate Decision Summary

- `possible_wf2_candidate`: 37
- `strong_wf2_candidate`: 26

## Phrase Summary

- `crochet t shirt`: 2
- `dance mom sweatshirt`: 10
- `furry shirts for gifts`: 2
- `gardening shirt`: 8
- `halloween nurse shirt`: 5
- `kpop demon hunters birthday cards`: 1
- `mechanic hoodies`: 7
- `mechanic stickers for gifts`: 5
- `plant shirt`: 8
- `sourdough shirt`: 10
- `tea cup gift for him`: 5

## Validation Performed

- `all_four_outputs_exist`: True
- `source_candidate_count_is_63`: True
- `review_board_json_count_is_63`: True
- `html_contains_embedded_candidates`: True
- `no_forbidden_columns_in_data`: True
- `forbidden_columns_found`: []
- `human_fields_blank_in_data`: True
- `raw_everbee_inbox_csv_count`: 17

## Risks

- Browser markings are stored locally in that browser until exported. Export the CSV when finished.
- The board is a manual review aid, not a durable database.
- Input AI review came from in-chat review output, so human judgment remains required before WF2.

## Recommended Next Step

Open the board locally, review the 63 cards, export the decisions CSV, and use only human-marked rows for a later WF2 hypothesis-drafting task.
