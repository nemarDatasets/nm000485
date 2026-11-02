# nm000485 stimulus-level events

Within-epoch event rows of the epoched recordings of nm000485, moved here on 18 Oct 2026 from the raw `events.tsv`, which now holds one `sequence_start` row per sequence (onset (k-1) x EpochLength, duration EpochLength, sequence k) so that `mne_bids.read_epochs_bids` loads each file as its epochs.

- 111 files, 408335 rows; same file names, columns, line text and order as the raw files before the move; `onset`/`sample` are relative to the start of the recording.
- Rows identical in every column to an earlier row were dropped (93495 rows).
- 30 Oct 2026 (branch fix-20261030): every Letswave trigger of the release is stored twice, 1-50 us apart (median 25 us):
  both rows have the same `sample`, `sequence` and `trial_type`, and only `onset`/`latency_in_sequence` differ in the 6th
  decimal. One sample is 1953 us at 512 Hz, so the pair is one trigger. The second row of each pair was dropped
  (156,902 rows; 251,433 remain), keeping the first row unchanged (`code/fix-20261030_dedup_stimulus_events.py`).
  `stimulus_events_summary.tsv` gives the per-file counts (`near_duplicates_removed_20261030`, `rows_here_20261030`).
- 0 rows lie outside the recording or outside the sequence they name (kept as delivered).
- `stimulus_events_summary.tsv`: per raw file, epochs, rows before, duplicates dropped, rows here.
