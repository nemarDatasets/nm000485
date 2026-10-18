[![DOI](https://img.shields.io/badge/DOI-10.82901%2Fnemar.nm000485-blue)](https://doi.org/10.82901/nemar.nm000485)

# s500-generic-45: Letter and word selective SEEG responses in the ventral occipito-temporal cortex, fast periodic visual stimulation (Lochy et al., 2018) (derivative)

SEEG from 37 patients with refractory epilepsy (University Hospital of Nancy) viewing fast periodic visual stimulation:
pseudofonts, nonwords (non-fonts) or pseudowords at 10 Hz with a real word every fifth item (2 Hz). Selective responses to
letters and words are measured at 2 Hz and its harmonics (article).

THIS IS A DERIVATIVE DATASET: the release contains the authors' Letswave files, low-pass filtered at 40 Hz
(Butterworth order 4) and cut into sequences, not the raw Micromed recordings.

## Source
- Dryad: Aliette Lochy, Corentin Jacques, Louis Maillard, Sophie Colnat-Coulbois, Bruno Rossion, Jacques Jonas. Data from: Selective visual representation of letters and words in the left ventral occipito-temporal cortex with intracerebral recordings. doi:10.5061/dryad.6s39h64 (version 1, 2019-07-09). License: CC0 1.0 (Dryad record).
- Article: Lochy A, Jacques C, Maillard L, Colnat-Coulbois S, Rossion B, Jonas J (2018) Selective visual representation of letters and words in the left ventral occipito-temporal cortex with intracerebral recordings. PNAS 115(32):E7595-E7604, doi:10.1073/pnas.1718987115.
- Dryad files: 3 zips (participants P001-P012, P013-P024, P025-P037) + 3 READMEs, verified against the Dryad md5 digests by the download lane.

## Contents
- `sub-<id>/ieeg/sub-<id>_task-<task>_run-1_ieeg.*`: 111 files, 37 participants, 6.11 h. Each file holds the
  sequences of one condition back-to-back (one BrainVision segment per sequence; `RecordingType` epoched, `EpochLength` =
  sequence length). Values are the release's float32 values, unchanged (MNE read-back matches). Sampling rate from the
  Letswave header. Tasks:
  - `task-wordspseudofont`: VC-W: words at 2 Hz among pseudofonts at 10 Hz
  - `task-wordsnonfont`: NW-W: words at 2 Hz among nonwords (non-fonts) at 10 Hz
  - `task-wordspseudoword`: PW-W: words at 2 Hz among pseudowords at 10 Hz
- Channels: labels from the Letswave header. Intracerebral contacts are typed SEEG; scalp electrodes recorded with the
  SEEG (labels `s<10-20 name>`) EEG; ECG, physiological monitors (MISC) and marker inputs (TRIG) as labelled. Unit µV is
  assumed (Letswave import of Micromed TRC; not stated in the release). The reference is not stated per participant.
- Electrode coordinates: each participant's folder has an xlsx table (Channel, Tal_x/y/z, MNI_x/y/z). They are written to `space-Talairach_electrodes.tsv` (37 participants) and `space-Other_electrodes.tsv` (MNI, 37 participants; the MNI template version is not stated in the release so the system is recorded as Other, see coordsystem.json). Contacts not present in the table have x/y/z n/a.
- `events.tsv`: the Letswave events (code, sequence, latency) of each file that has any (0 files have no Letswave
  events and no events.tsv); most frequent codes: [('s1', 501795), ('seq_stimuli_to_use_sinstim_Localiser_10Hz_VisualcontrolWords_Per_1', 10), ('seq_stimuli_to_use_sinstim_Localiser_10Hz_NonwordsWords_Per_1', 6), ('seq_stimuli_to_use_sinstim_Localiser_10Hz_PseudowordsWords_Per_1', 6), ('1', 5), ('unk', 2), ('NW_W', 2), ('seq_PW-W', 1)].
- Letswave history per file is in each `ieeg.json` (`SoftwareFilters`).
- `sourcedata/dryad-6s39h64-deidentified/`: the release's files, de-identified (below);
  `DEIDENTIFICATION_MANIFEST.tsv` lists original and new sha-256 per file.
- `stimuli/`: the stimulus images (BMP) and `stimuli_bigram_frequency.txt` from the first zip's Stimuli folder (released by the authors with the data).

## Privacy
- Letswave event codes with a leading participant-code token were replaced by 'seq' in events.tsv and in the
  de-identified .lw5 headers (26 distinct tokens; a byte search of the whole output found
  0 remaining occurrences). Letswave history dates and MAT text-header dates in sourcedata are reduced to
  month and year (day -> 01). The .lw5 headers were rewritten with scipy (savemat, MATLAB v5, compressed); their content is
  otherwise unchanged.
- Age and sex are not given per participant in the release.

## Events outside the data (corrected 2026-10-17, version 1.0.3)

Up to version 1.0.2, three `events.tsv` files of sub-P013 (wordsnonfont, wordspseudofont, wordspseudoword) each held
one or two Letswave sequence-name events (`seq_NW-W_10Hz_3`, `seq_NW-W_10Hz_5`, `seq_VC-W_10Hz_4`, `seq_PW-W_10Hz_2`,
`seq_PW-W_10Hz_6`) whose onsets lay after the end of the recording (372-896 s in 74-148 s files): their
`latency_in_sequence` (370-820 s) is longer than the sequence itself (`EpochLength` 74 s), so they cannot belong to
the sequence they are listed in. These 5 rows are removed. The rule: a row is removed when its position within its
own sequence (`onset` - (`sequence` - 1) x `EpochLength`) is negative or not shorter than `EpochLength`. No other row
of the 111 files met it, and no row inside the data was changed. The removed rows are kept, with the file name, in
`sourcedata/events-removed-2026-10-17/removed_events.tsv`.

## Events and epochs (18 Oct 2026)

Each epoched data file stores its epochs back to back, each `EpochLength` long. `mne_bids.read_epochs_bids` cuts one epoch of `EpochLength` at EVERY row of `events.tsv`, so files whose `events.tsv` also held within-epoch events (or no row at all) could not be read (Event time samples were not unique; No matching events found). Since 18 Oct 2026 the `events.tsv` of the 111 epoched files holds exactly one `sequence_start` row per sequence: `onset` = (k - 1) x `EpochLength`, `duration` = `EpochLength`, `sequence` = k, `latency_in_sequence` = `SequenceStartTime` (n/a when the json has none), `sample` = (k - 1) x round(`EpochLength` x sampling rate). The number of epochs of every file comes from its data header (number of samples / samples per epoch) and agrees with the .vmrk `New Segment` markers where present (331 epochs in total).

The other rows of the 111 files that had them (408335 rows) are in `derivatives/stimulus_events/` under the same relative path (for example `derivatives/stimulus_events/sub-P001/ieeg/sub-P001_task-wordsnonfont_run-1_events.tsv`), unchanged: same columns, line text and order, `onset` and `sample` relative to the start of the recording. Only rows identical in every column to an earlier row were dropped (93495 rows). 0 of them lie outside the recording or their epoch and are kept as delivered. Per-file counts: `derivatives/stimulus_events/stimulus_events_summary.tsv`; code: `code/fix-20261018_split_stimulus_events.py`. Signal files are unchanged.

```python
import mne_bids, pandas as pd
epochs = mne_bids.read_epochs_bids(bids_path)        # one epoch per events.tsv row
stim = pd.read_csv(root / 'derivatives' / 'stimulus_events' / events_relpath, sep='\t')
n_per = round(epoch_length * sfreq)
stim['epoch_index'] = stim['sample'] // n_per          # 0-based epoch
stim['time_in_epoch'] = (stim['sample'] % n_per) / sfreq
```
