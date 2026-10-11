"""o5c lane C: Nancy/Rossion-lab Letswave 5 SEEG releases on Dryad -> iEEG-BIDS DERIVATIVE dataset (same pattern as
b3w3_convert_jonas.py / NEMAR nm000403).

  lochy   src-generic-45  doi:10.5061/dryad.6s39h64  Lochy et al. 2018 PNAS  (37 patients x 3 conditions, low-pass 40 Hz,
          sequences 2 s..~68 s, merged per condition; per-patient Talairach + MNI contact coordinates xlsx)
  volfart src-generic-44  doi:10.5061/dryad.m8t391m  Volfart et al. 2020 PLoS Biol (Experiment 2 SEEG: 7 patients x 3
          conditions, low-pass 30 Hz; per-patient Talairach coordinates xlsx; the scalp-EEG experiments are averaged
          ERPs and go to sourcedata only)

Letswave pair = .lw5 header (MAT v5 struct 'header') + v7.3 .mat 'data' float32 [sequences x channels x 1 x 1 x 1 x time].
Values are written unchanged as BrainVision IEEE_FLOAT_32, sequences back-to-back (one New Segment marker per sequence);
Letswave events -> events.tsv. Privacy: event codes with a letters+digits prefix before '_' that is not a plain
stimulus word are replaced (tokens never printed); Letswave history dates and MAT text-header dates -> day 01.
Usage: python o5c_C_convert_nancy.py <lochy|volfart> <open500_dir> <bids_root> [probe]
"""
import collections, glob, hashlib, io, json, os, re, shutil, sys
import numpy as np, h5py, scipy.io as sio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b3w3_common import wtsv, wjson, write_vhdr, scrub_mat_header, sha256_file

KIND, SRC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PROBE = len(sys.argv) > 4 and sys.argv[4] == "probe"
X = os.path.join(SRC, "_x")
CFG = {
    "lochy": dict(doi="10.5061/dryad.6s39h64", short="dryad-6s39h64", lp=40.0,
                  glob="Lochy_et_al_PNAS_2018_P*.zip.d/*/lp40 merged*.lw5",
                  rx=re.compile(r"/(\d{3})/lp40 merged[ _](VC|NW|PW)[-_ ]W[ _]10[Hh]z\.lw5$"),
                  task={"VC": "wordspseudofont", "NW": "wordsnonfont", "PW": "wordspseudoword"},
                  taskdesc={"VC": "Fast periodic visual stimulation at 10 Hz of pseudofonts with a word every 5th item (2 Hz) (VC-W; README/article).",
                            "NW": "Fast periodic visual stimulation at 10 Hz of nonwords (non-fonts) with a word every 5th item (2 Hz) (NW-W).",
                            "PW": "Fast periodic visual stimulation at 10 Hz of pseudowords with a word every 5th item (2 Hz) (PW-W)."},
                  sub=lambda m: "P" + m.group(1), coords=lambda d, m: glob.glob(os.path.join(d, "*coordinates*.xlsx"))),
    "volfart": dict(doi="10.5061/dryad.m8t391m", short="dryad-m8t391m", lp=30.0,
                    glob="FaceNameAssociation_Metadata.zip.d/FaceNameAssociation_Metadata/Experiment_2_SEEG/P*/*/merged_*sequences.lw5",
                    rx=re.compile(r"/Experiment_2_SEEG/P(\d+)/(FaceName|FaceOnly|NameOnly)/merged_\2_(\d+)sequences\.lw5$"),
                    task={"FaceName": "facename", "FaceOnly": "faceonly", "NameOnly": "nameonly"},
                    taskdesc={"FaceName": "Crossmodal frequency tagging: pictures of faces and written names of one famous identity at 4 Hz, with a different famous identity (face or name) every 7th item (0.571 Hz) (article).",
                              "FaceOnly": "Unimodal control: faces only at 4 Hz with an identity change every 7th item (0.571 Hz) (article).",
                              "NameOnly": "Unimodal control: written names only at 4 Hz with an identity change every 7th item (0.571 Hz) (article)."},
                    sub=lambda m: "P" + m.group(1).zfill(2), coords=lambda d, m: glob.glob(os.path.join(os.path.dirname(d), "*coordinates*.xlsx"))),
}[KIND]
SD = os.path.join(OUT, "sourcedata", CFG["short"] + "-deidentified")
report = {"kind": KIND, "files": [], "sourcedata": [], "coords": {}, "excluded": []}
TOKENS = set()
# event-code privacy: a leading token of >=3 letters (+digits) followed by '_' and more text is treated as a patient code
PREFIX = re.compile(r"^([A-Za-z]{3,}[-_]?\d*)_")
LETTERS = re.compile(r"^[A-Za-z]{3,}$")
SAFE_WORDS = {"end", "start", "stop", "seq", "begin", "pause", "rest"}
DATE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})")
SAFE_PREFIX = {"merged", "seq", "lp", "ds"}


def scrub_code(c):
    m = PREFIX.match(c)
    if m and m.group(1).lower() not in SAFE_PREFIX:
        TOKENS.add(m.group(1))
        return "seq_" + c[m.end():]
    if LETTERS.match(c) and c.lower() not in SAFE_WORDS:
        TOKENS.add(c)
        return "unk"
    return c


def mask(s):
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "#", s))


def chtype(l):
    if re.match(r"^ECG", l, re.I): return "ECG"
    if re.match(r"^s ?[A-Z]", l): return "EEG"
    if re.match(r"^(PULS|BEAT|SpO2|EMG|EOG)", l, re.I): return "MISC"
    if re.match(r"^MKR", l): return "TRIG"
    return "SEEG"


def read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(v is not None and str(v).strip() != "" for v in r)]
    return rows


def isnum(v):
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def parse_coords(path):
    """-> dict name -> {'Talairach': (x,y,z) or None, 'MNI': (x,y,z) or None}, header"""
    rows = read_xlsx(path)
    if len(rows[0]) >= 4 and isnum(rows[0][1]) and isnum(rows[0][2]) and isnum(rows[0][3]):
        # headerless table: name, x, y, z; space from the file name
        sp = "tal" if "tal" in os.path.basename(path).lower() else ("mni" if "mni" in os.path.basename(path).lower() else None)
        assert sp, path
        rows = [["Channel", f"{sp}_x", f"{sp}_y", f"{sp}_z"]] + rows
    hdr = [str(v).strip() if v is not None else "" for v in rows[0]]
    low = [h.lower() for h in hdr]
    def col(prefixes, axis):
        for i, h in enumerate(low):
            for p in prefixes:
                if h in (f"{p}_{axis}", f"{p}{axis}", f"{p} {axis}", f"{axis}_{p}", f"{axis}{p}"):
                    return i
        return None
    tal = [col(("tal", "talairach"), a) for a in "xyz"]
    mni = [col(("mni",), a) for a in "xyz"]
    name_i = next((i for i, h in enumerate(low) if h in ("channel", "contact", "name", "label", "electrode", "channels", "contacts")), 0)
    out = collections.OrderedDict()
    for r in rows[1:]:
        n = r[name_i] if name_i < len(r) else None
        if n is None or str(n).strip() == "":
            continue
        n = str(n).strip().replace(" ", "")
        def trip(idx):
            if any(i is None for i in idx):
                return None
            try:
                v = [float(r[i]) for i in idx]
            except (TypeError, ValueError, IndexError):
                return None
            return v if all(np.isfinite(v)) else None
        out[n] = {"Talairach": trip(tal), "MNI": trip(mni)}
    return out, hdr


files = sorted(glob.glob(os.path.join(X, CFG["glob"])))
assert files, "no lw5 files found"
scans = {}
subj_coords = {}
if PROBE:
    n = files[0]
    h = sio.loadmat(n, squeeze_me=True, struct_as_record=False)["header"]
    print("header fields:", sorted(h.__dict__.keys()))
    print("datasize", h.datasize, "xstep", h.xstep, "xstart", h.xstart, "name(masked)", mask(str(getattr(h, "name", ""))))
    print("chanlocs fields:", sorted(np.atleast_1d(h.chanlocs)[0].__dict__.keys()))
    print("labels:", [str(c.labels) for c in np.atleast_1d(h.chanlocs)][:200])
    ev = np.atleast_1d(getattr(h, "events", []))
    print("n events", len(ev), "event fields:", sorted(ev[0].__dict__.keys()) if len(ev) else None)
    codes = collections.Counter()
    for f in files:
        hh = sio.loadmat(f, squeeze_me=True, struct_as_record=False)["header"]
        for e in np.atleast_1d(getattr(hh, "events", [])):
            codes[mask(str(e.code))] += 1
        for hs in np.atleast_1d(hh.history):
            d = hs.__dict__
            print("  hist:", {k: mask(str(v))[:80] for k, v in d.items() if k != "configuration"}) if f == files[0] else None
    print("masked event codes:", codes.most_common(40))
    for f in files[:3]:
        m = CFG["rx"].search(f)
        print("rx", f[len(X):], "->", m.groups() if m else None)
        cx = CFG["coords"](os.path.dirname(f), m)
        print("  coords files:", [c[len(X):] for c in cx])
        if cx:
            rows = read_xlsx(cx[0])
            print("  xlsx header:", rows[0]); print("  row1:", rows[1]); print("  nrows", len(rows))
    sys.exit(0)

for n in files:
    m = CFG["rx"].search(n)
    assert m, n
    pid = CFG["sub"](m); cond = m.group(2)
    h = sio.loadmat(n, squeeze_me=True, struct_as_record=False)["header"]
    ds = [int(v) for v in np.ravel(h.datasize)]; nch, ns = ds[1], ds[5]
    fs = 1.0 / float(h.xstep); x0 = float(h.xstart)
    labels = [str(c.labels) for c in np.atleast_1d(h.chanlocs)]
    assert len(labels) == nch
    with h5py.File(n[:-4] + ".mat", "r") as hf:
        if hf["data"].attrs.get("MATLAB_empty", 0):
            print("EMPTY data in the release (MATLAB_empty):", n[len(X) + 1:], "stated dims", ds, flush=True)
            report.setdefault("empty_in_release", []).append({"file": n[len(X) + 1:], "sub": pid, "cond": cond, "header_datasize": ds})
            continue
        a = hf["data"][()]
    ne = a.shape[-1]  # the .mat data is authoritative (one header stated 0 epochs for a 4-sequence file)
    assert a.shape == (ns, 1, 1, 1, nch, ne), (a.shape, ds)
    assert a.dtype == np.float32
    x = np.concatenate([a[:, 0, 0, 0, :, e] for e in range(ne)], axis=0)
    S = f"sub-{pid}"; D = os.path.join(OUT, S, "ieeg"); os.makedirs(D, exist_ok=True)
    task = CFG["task"][cond]
    stem = f"{S}_task-{task}_run-1"
    np.ascontiguousarray(x).astype("<f4").tofile(os.path.join(D, stem + "_ieeg.eeg"))
    ev = []
    for e in np.atleast_1d(getattr(h, "events", [])):
        ep = int(e.epoch); lat = float(e.latency)
        s0 = int(round((lat - x0) * fs))
        onset = (ep - 1) * ns / fs + (lat - x0)
        ev.append([round(onset, 6), 0, scrub_code(str(e.code)), ep, round(lat, 6), (ep - 1) * ns + s0])
    ev.sort(key=lambda r: r[0])
    segs = [("New Segment", f"sequence {k + 1}", k * ns, 1) for k in range(1, ne)]
    write_vhdr(os.path.join(D, stem + "_ieeg"), nch, fs, labels, ["µV"] * nch,
               comment=f"o5c_C_convert_nancy.py: Letswave {os.path.basename(n)} + .mat, {ne} sequences back-to-back, float32 unchanged", markers=segs)
    wtsv(os.path.join(D, stem + "_events.tsv"), ["onset", "duration", "trial_type", "sequence", "latency_in_sequence", "sample"], ev)
    typ = [chtype(l) for l in labels]
    # coordinates
    cfiles = CFG["coords"](os.path.dirname(n), m)
    if pid not in subj_coords:
        if cfiles:
            cc, hdr = parse_coords(cfiles[0])
            subj_coords[pid] = (cc, hdr, cfiles[0][len(X) + 1:])
        else:
            subj_coords[pid] = (None, None, None)
    cc = subj_coords[pid][0]
    def key(l):
        return l.replace(" ", "")
    def cdesc(l, t):
        if t != "SEEG":
            return "non-SEEG channel recorded with the SEEG (label from the Letswave header)"
        if cc and key(l) in cc and (cc[key(l)]["Talairach"] or cc[key(l)]["MNI"]):
            return "label from the Letswave header; coordinates in electrodes.tsv (release xlsx)"
        return "label from the Letswave header; no coordinates for this contact in the release xlsx"
    wtsv(os.path.join(D, stem + "_channels.tsv"), ["name", "type", "units", "low_cutoff", "high_cutoff", "sampling_frequency", "group", "status", "status_description", "description"],
         [[l, t, "µV", "n/a", CFG["lp"], fs, re.sub(r"[ ]?\d+$", "", l) if t == "SEEG" else "n/a", "good", "n/a", cdesc(l, t)]
          for l, t in zip(labels, typ)])
    hist = [str(getattr(e, "description", "")) for e in np.atleast_1d(h.history)]
    wjson(os.path.join(D, stem + "_ieeg.json"), {
        "TaskName": task, "TaskDescription": CFG["taskdesc"][cond],
        "SamplingFrequency": fs, "PowerLineFrequency": 50,
        "SoftwareFilters": {"Letswave": {"Description": f"Low-pass {CFG['lp']:g} Hz, Butterworth order 4 (README); Letswave history of this file: " + ", ".join(hist)}},
        "HardwareFilters": "n/a",
        "iEEGReference": "n/a (not stated per participant in the release)",
        "Manufacturer": "Micromed",
        "RecordingType": "epoched", "EpochLength": ns / fs, "RecordingDuration": ne * ns / fs,
        "SEEGChannelCount": typ.count("SEEG"), "EEGChannelCount": typ.count("EEG"), "ECGChannelCount": typ.count("ECG"),
        "MiscChannelCount": typ.count("MISC"), "TriggerChannelCount": typ.count("TRIG"), "ECOGChannelCount": 0,
        "ElectricalStimulation": False,
    })
    scans.setdefault(S, []).append([f"ieeg/{stem}_ieeg.vhdr", "n/a"])
    import mne
    rr = mne.io.read_raw_brainvision(os.path.join(D, stem + "_ieeg.vhdr"), preload=False, verbose="error")
    k = min(2000, x.shape[0])
    rt = bool(rr.n_times == x.shape[0] and rr.ch_names == labels and np.allclose(rr.get_data(start=0, stop=k) * 1e6, x[:k].T, rtol=1e-6, atol=1e-6)
              and np.allclose(rr.get_data(start=x.shape[0] - k) * 1e6, x[-k:].T, rtol=1e-6, atol=1e-6))
    report["files"].append(dict(file=n[len(X) + 1:], sub=pid, task=task, cond=cond, sequences=ne, samples_per_sequence=ns, sfreq=fs, nch=nch, n_events=len(ev),
                                types={t: typ.count(t) for t in set(typ)}, history=hist, roundtrip_ok=rt, labels=labels))
    print(stem, ne, nch, ns, fs, "events", len(ev), "rt", rt, flush=True)
for S, r in scans.items():
    wtsv(os.path.join(OUT, S, f"{S}_scans.tsv"), ["filename", "acq_time"], sorted(r))

# electrodes.tsv / coordsystem.json per subject and space (from the release xlsx; never invented)
for pid, (cc, hdr, cfile) in sorted(subj_coords.items()):
    S = f"sub-{pid}"; D = os.path.join(OUT, S, "ieeg")
    seeg = []
    for f in report["files"]:
        if f["sub"] == pid:
            for l in f["labels"]:
                if chtype(l) == "SEEG" and l not in seeg:
                    seeg.append(l)
    info = {"xlsx": cfile, "header": hdr, "n_rows": len(cc) if cc else 0, "n_seeg_channels": len(seeg)}
    spaces = []
    if cc:
        for space, lab in (("Talairach", "Talairach"), ("MNI", "Other")):
            have = [n_ for n_ in cc if cc[n_][space]]
            if not have:
                continue
            spaces.append(space)
            rows = []
            matched = 0
            seegk = {n_.replace(" ", "") for n_ in seeg}
            for n_ in seeg:
                v = cc.get(n_.replace(" ", ""), {}).get(space)
                if v: matched += 1
                rows.append([n_, *(["%.3f" % c for c in v] if v else ["n/a"] * 3), "n/a", re.sub(r"[ ]?\d+$", "", n_)])
            extra = [n_ for n_ in have if n_ not in seegk]
            for n_ in extra:
                v = cc[n_][space]
                rows.append([n_, *["%.3f" % c for c in v], "n/a", re.sub(r"[ ]?\d+$", "", n_)])
            info[f"{space}_matched_seeg"] = matched; info[f"{space}_xlsx_only"] = len(extra)
            wtsv(os.path.join(D, f"{S}_space-{lab}_electrodes.tsv"), ["name", "x", "y", "z", "size", "group"], rows)
            if space == "Talairach":
                cs = {"iEEGCoordinateSystem": "Talairach", "iEEGCoordinateUnits": "mm",
                      "iEEGCoordinateSystemDescription": f"Talairach coordinates of the intracerebral contacts as given in the release file {os.path.basename(cfile)} (README: coordinates reported in Talairach and MNI space)."}
            else:
                cs = {"iEEGCoordinateSystem": "Other", "iEEGCoordinateUnits": "mm",
                      "iEEGCoordinateSystemDescription": f"MNI coordinates of the intracerebral contacts as given in the release file {os.path.basename(cfile)} (columns MNI_x/y/z). The MNI template version is not stated in the release, so the system is recorded as Other rather than a specific MNI152 variant."}
            cs["iEEGCoordinateProcessingDescription"] = "Coordinates copied from the authors' xlsx table; no processing. Contacts absent from the table have x/y/z n/a."
            wjson(os.path.join(D, f"{S}_space-{lab}_coordsystem.json"), cs)
    if not spaces:
        wtsv(os.path.join(D, f"{S}_space-Other_electrodes.tsv"), ["name", "x", "y", "z", "size", "group"], [[n_, "n/a", "n/a", "n/a", "n/a", re.sub(r"[ ]?\d+$", "", n_)] for n_ in seeg])
        wjson(os.path.join(D, f"{S}_space-Other_coordsystem.json"), {"iEEGCoordinateSystem": "Other", "iEEGCoordinateUnits": "n/a",
              "iEEGCoordinateSystemDescription": "No coordinate table for this participant in the release; labels only, x/y/z n/a."})
    info["spaces"] = spaces
    report["coords"][pid] = info
    print("coords", pid, info, flush=True)


def scrub_lw5(b):
    m = sio.loadmat(io.BytesIO(b), squeeze_me=False, struct_as_record=True)
    H = m["header"][0, 0]
    nchg = 0
    if "events" in H.dtype.names and H["events"].size:
        E = H["events"]
        for i in range(E.size):
            c = str(np.ravel(E.flat[i]["code"])[0]) if E.flat[i]["code"].size else ""
            nc = scrub_code(c)
            if nc != c:
                E.flat[i]["code"] = np.array([nc]); nchg += 1
    if "history" in H.dtype.names:
        Hs = H["history"]
        for i in range(Hs.size):
            if "date" not in Hs.dtype.names:
                break
            d = Hs.flat[i]["date"]
            if d.size:
                s = str(np.ravel(d)[0])
                ns_ = DATE.sub(lambda mm: f"01-{mm.group(2)}-{mm.group(3)}", s)
                if ns_ != s:
                    Hs.flat[i]["date"] = np.array([ns_]); nchg += 1
    if "name" in H.dtype.names and H["name"].size:
        H["name"] = np.array(["deidentified"]); nchg += 1
    nchg += scrub_paths(H["history"]) if "history" in H.dtype.names else 0
    bio = io.BytesIO()
    sio.savemat(bio, {"header": m["header"]}, format="5", do_compression=True)
    nb, _ = scrub_mat_header(bio.getvalue())
    return nb, nchg


PATHRX = re.compile(r"[\\/]|^[A-Za-z]:")


def scrub_paths(a):
    """Recursively replace char arrays that look like file paths (drive letters, slashes) inside a MAT struct/cell array."""
    n = 0
    if not isinstance(a, np.ndarray):
        return 0
    if a.dtype.names:
        for i in range(a.size):
            for f in a.dtype.names:
                v = a.flat[i][f]
                if isinstance(v, np.ndarray) and v.dtype.kind in "US":
                    s = str(np.ravel(v)[0]) if v.size else ""
                    if PATHRX.search(s):
                        a.flat[i][f] = np.array(["path removed"]); n += 1
                else:
                    n += scrub_paths(v)
    elif a.dtype == object:
        for i in range(a.size):
            v = a.flat[i]
            if isinstance(v, np.ndarray) and v.dtype.kind in "US":
                s = str(np.ravel(v)[0]) if v.size else ""
                if PATHRX.search(s):
                    a.flat[i] = np.array(["path removed"]); n += 1
            else:
                n += scrub_paths(v)
    return n


# sourcedata: every extracted file except stimuli images (which go to stimuli/ for lochy) and .done markers
os.makedirs(SD, exist_ok=True)
STIM = os.path.join(OUT, "stimuli")
for root, _, fs_ in os.walk(X):
    for fn in sorted(fs_):
        p = os.path.join(root, fn); rel = os.path.relpath(p, X)
        if fn.endswith(".done") or fn == ".DS_Store":
            continue
        rel2 = re.sub(r"\.zip\.d/", "/", rel)
        if "/Stimuli/" in "/" + rel or rel.endswith("stimuli_bigram_frequency.txt"):
            if KIND == "lochy":
                t = os.path.join(STIM, os.path.basename(fn)); os.makedirs(STIM, exist_ok=True)
                if not os.path.exists(t):
                    shutil.copy(p, t)
                report["excluded"].append(rel)  # listed as moved to stimuli/
                continue
        b = open(p, "rb").read(); o = hashlib.sha256(b).hexdigest()
        if fn.endswith(".lw5"):
            nb, k = scrub_lw5(b); note = f"Letswave header rewritten (scipy savemat): {k} fields changed (event-code prefix removed, history dates day -> 01)"
        elif fn.endswith(".mat"):
            nb, ch = scrub_mat_header(b); note = "MAT text header date -> Mmm 01 yyyy" if ch else "unchanged"
        else:
            nb, note = b, "unchanged"
        t = os.path.join(SD, rel2); os.makedirs(os.path.dirname(t), exist_ok=True)
        open(t, "wb").write(nb)
        report["sourcedata"].append([rel2, len(b), o, hashlib.sha256(nb).hexdigest(), note])
for f in sorted(os.listdir(os.path.join(SRC, "files"))):
    p = os.path.join(SRC, "files", f)
    if f.lower().endswith((".txt", ".md")) and os.path.isfile(p):
        shutil.copy(p, os.path.join(SD, f))
        report["sourcedata"].append([f, os.path.getsize(p), sha256_file(p), sha256_file(os.path.join(SD, f)), "unchanged"])
wtsv(os.path.join(SD, "DEIDENTIFICATION_MANIFEST.tsv"), ["path", "bytes_original", "sha256_original", "sha256_here", "change"], report["sourcedata"])
# token check over everything written
hits = 0
HITLOG = []
TB = [t.encode() for t in TOKENS]
print("tokens (masked):", sorted({mask(t) for t in TOKENS}))
if TB:
    for root, _, fs_ in os.walk(OUT):
        for fn in fs_:
            p = os.path.join(root, fn)
            if fn.endswith(".lw5"):
                hh = sio.loadmat(p, squeeze_me=True, struct_as_record=False)["header"]
                txt = repr(hh.__dict__).encode() + repr([str(e.code) for e in np.atleast_1d(getattr(hh, "events", []))]).encode()
            elif fn.endswith((".eeg", ".bmp", ".jpg", ".png")):
                continue
            else:
                txt = open(p, "rb").read()
            binary = fn.endswith(".mat")
            for t in TB:
                if binary and len(t) < 5:
                    continue  # 3-4 letter tokens match binary HDF5 content by chance; checked in text files only
                if t in txt:
                    hits += 1
                    if len(HITLOG) < 30:
                        HITLOG.append((os.path.relpath(p, OUT), mask(t.decode()), len(t)))
print("token hits (file, masked token, len):", HITLOG)
cc_ = collections.Counter()
for fe in glob.glob(os.path.join(OUT, "sub-*", "ieeg", "*_events.tsv")):
    for line in open(fe).read().splitlines()[1:]:
        cc_[line.split("\t")[2]] += 1
report["event_codes_after_scrub"] = dict(cc_)
print("event codes after scrub:", sorted(cc_.items(), key=lambda kv: -kv[1])[:30])
report["privacy"] = {"patient_code_tokens_removed": len(TOKENS), "token_hits_after_scrub": hits}
report["stimuli_moved"] = len(report["excluded"])
os.makedirs(os.path.join(OUT, "code"), exist_ok=True)
for f in (__file__, os.path.join(os.path.dirname(os.path.abspath(__file__)), "b3w3_common.py")):
    shutil.copy(f, os.path.join(OUT, "code", os.path.basename(f)))
rep2 = dict(report); rep2["excluded"] = sorted({os.path.dirname(e) for e in report["excluded"]})
json.dump(rep2, open(os.path.join(OUT, "code", "conversion_report.json"), "w"), indent=1)
print(json.dumps({"files": len(report["files"]), "rt_all": all(f["roundtrip_ok"] for f in report["files"]), "privacy": report["privacy"],
                  "subjects": len(scans), "coords": {p: v["spaces"] for p, v in report["coords"].items()}}, indent=1))
assert hits == 0, "patient-code tokens remain"
print("CONVERT_DONE")
