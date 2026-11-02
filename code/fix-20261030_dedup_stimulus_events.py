#!/usr/bin/env python3
"""nm000485 fix-20261030: drop near-duplicate trigger rows in derivatives/stimulus_events and type EMG channels.

1. Every Letswave trigger of the release appears twice, 1-50 us apart (both rows give the same sample, sequence and
   trial_type; only `onset`/`latency_in_sequence` differ in the 6th decimal). At 512 Hz (one sample = 1953 us) the two
   rows are one trigger. For each derivatives/stimulus_events/*_events.tsv, a row whose (sequence, sample, trial_type)
   equals that of an earlier row is dropped; the first row is kept unchanged. Counts go to
   derivatives/stimulus_events/stimulus_events_summary.tsv (new column near_duplicates_removed_20261030, rows_here).
2. Channels labelled `EMG1`/`EMG2` in the Letswave header (sub-P013) were typed MISC; they are typed EMG, and the
   EMGChannelCount/MiscChannelCount of the matching *_ieeg.json are updated.
Usage: python3 code/fix-20261030_dedup_stimulus_events.py <dataset root>
"""
import csv, glob, io, json, os, re, sys

root = sys.argv[1]
D = os.path.join(root, "derivatives", "stimulus_events")
counts = {}
for f in sorted(glob.glob(f"{D}/sub-*/ieeg/*_events.tsv")):
    lines = open(f, newline="").read().split("\n")
    trail = lines[-1] == ""
    if trail:
        lines = lines[:-1]
    hdr = lines[0].split("\t")
    si, qi, ti = hdr.index("sample"), hdr.index("sequence"), hdr.index("trial_type")
    seen, out, drop = set(), [lines[0]], 0
    for l in lines[1:]:
        c = l.split("\t")
        k = (c[qi], c[si], c[ti])
        if k in seen:
            drop += 1
            continue
        seen.add(k); out.append(l)
    open(f, "w", newline="").write("\n".join(out) + ("\n" if trail else ""))
    counts[os.path.relpath(f, D)] = (drop, len(out) - 1)

S = os.path.join(D, "stimulus_events_summary.tsv")
rows = list(csv.reader(open(S, newline=""), delimiter="\t"))
h = rows[0]
h += ["near_duplicates_removed_20261030", "rows_here_20261030"]
fi = h.index("file")
for r in rows[1:]:
    d, n = counts.get(r[fi], ("n/a", "n/a"))
    r += [str(d), str(n)]
buf = io.StringIO(); csv.writer(buf, delimiter="\t", lineterminator="\n").writerows(rows)
open(S, "w", newline="").write(buf.getvalue())

emg = []
for f in sorted(glob.glob(f"{root}/sub-*/ieeg/*_channels.tsv")):
    txt = open(f, newline="").read()
    rows = list(csv.reader(io.StringIO(txt), delimiter="\t"))
    ni, ti = rows[0].index("name"), rows[0].index("type")
    ch = 0
    for r in rows[1:]:
        if re.fullmatch(r"EMG\d*", r[ni]) and r[ti] == "MISC":
            r[ti] = "EMG"; ch += 1
    if ch:
        buf = io.StringIO(); csv.writer(buf, delimiter="\t", lineterminator="\n").writerows(rows)
        open(f, "w", newline="").write(buf.getvalue())
        j = f.replace("_channels.tsv", "_ieeg.json")
        s = open(j).read(); d = json.loads(s)
        s = re.sub(r'("MiscChannelCount":\s*)\d+', r"\g<1>%d" % (d["MiscChannelCount"] - ch), s, count=1)
        if "EMGChannelCount" in d:
            s = re.sub(r'("EMGChannelCount":\s*)\d+', r"\g<1>%d" % (d["EMGChannelCount"] + ch), s, count=1)
        else:
            s = re.sub(r'("MiscChannelCount":\s*\d+)', r'"EMGChannelCount": %d,\n  \1' % ch, s, count=1)
        json.loads(s); open(j, "w").write(s)
        emg.append((os.path.relpath(f, root), ch))
print("stimulus files", len(counts), "near-duplicate rows removed", sum(v[0] for v in counts.values()),
      "rows kept", sum(v[1] for v in counts.values()))
print("EMG retyped", emg)
