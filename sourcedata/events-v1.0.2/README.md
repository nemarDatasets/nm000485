# events.tsv files as published in version 1.0.2

Version 1.0.3 rewrote the 111 `sub-*/ieeg/*_events.tsv` files so that each holds one `sequence_start` row per sequence
(epoch). The per-stimulus rows moved to `derivatives/stimulus_events/` (exact duplicate rows dropped, and the second row of each duplicated trigger), and rows
outside the data are listed in `sourcedata/events-removed-2026-10-17/`. So that no published row is lost, the 111 events.tsv
files of version 1.0.2 are kept here byte for byte, at the same relative path (e.g. `sub-P001/ieeg/sub-P001_task-wordsnonfont_run-1_events.tsv`).
They are not read by BIDS tools.
