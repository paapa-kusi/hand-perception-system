import sys
import csv
import re
import glob
import math
import argparse
import statistics
from collections import defaultdict, OrderedDict

# Substrings / exact names used to recognise single-value columns.
# Order matters: first match wins.
COLUMN_HINTS = {
    "timestamp": ["timestamp", "time_s", "time_ms", "time", "t_capture", "t"],
    "frame":     ["frame_id", "frame_idx", "frame", "idx"],
    "detected":  ["hand_detected", "is_detected", "detected", "detection",
                  "found", "tracking", "has_hand"],
    "confidence":["confidence", "score", "conf", "presence"],
    "fps":       ["fps", "frame_rate", "framerate"],
    "latency":   ["latency_ms", "latency", "proc_time", "processing_time",
                  "process_ms", "infer_ms", "inference_time", "compute_ms"],
    "condition": ["test_condition", "condition", "scenario", "label", "tag"],
}

# Landmark column patterns -> (index, axis). Tried in order.
LANDMARK_PATTERNS = [
    re.compile(r"^(?:lm|landmark|kp|point|joint)_?(\d+)_?([xyz])$", re.I),
    re.compile(r"^([xyz])_?(\d+)$", re.I),          # x0, y_0
    re.compile(r"^(\d+)_([xyz])$", re.I),           # 0_x
]

# Angle columns: anything with "angle", or finger-joint names.
ANGLE_HINTS = ["angle", "mcp", "pip", "dip", "curl", "flex", "abduction"]

# Detection thresholds
CONF_THRESHOLD = 0.5            # if only a confidence column exists
LOW_MOTION_PCTL = 0.34          # frames below this motion percentile = "held still"
RADIAN_GUESS_MAX = 3.25         # if 95th-pctl angle <= this, values look like radians


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_truthy(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "detected", "found"):
        return True
    if s in ("0", "false", "f", "no", "n", "", "none", "nan", "lost"):
        return False
    f = _to_float(v)
    if f is not None:
        return f > 0.5
    return None


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)



def detect_columns(header, overrides=None):
    overrides = overrides or {}
    used = set(overrides.values())
    roles = {}

    # explicit overrides first (name=role)
    inv = {}
    for name, role in overrides.items():
        inv.setdefault(role, name)

    lower = {h.lower(): h for h in header}

    for role, hints in COLUMN_HINTS.items():
        if role in inv:
            roles[role] = inv[role]
            continue
        for hint in hints:
            if hint in lower and lower[hint] not in used:
                roles[role] = lower[hint]
                used.add(lower[hint])
                break

    # landmarks
    landmarks = defaultdict(dict)  # index -> {axis: colname}
    for h in header:
        if h in used:
            continue
        for pat in LANDMARK_PATTERNS:
            m = pat.match(h)
            if not m:
                continue
            g = m.groups()
            if g[0].lower() in ("x", "y", "z"):
                axis, idx = g[0].lower(), int(g[1])
            else:
                idx, axis = int(g[0]), g[1].lower()
            landmarks[idx][axis] = h
            used.add(h)
            break

    # angles (anything left that smells like an angle)
    angles = []
    for h in header:
        if h in used:
            continue
        hl = h.lower()
        if any(hint in hl for hint in ANGLE_HINTS):
            angles.append(h)
            used.add(h)

    roles["landmarks"] = dict(landmarks)
    roles["angles"] = angles
    return roles


def _detected_series(rows, roles):
    """Return list of bool (or None) per row indicating hand present."""
    if "detected" in roles:
        return [_is_truthy(r.get(roles["detected"])) for r in rows]
    if "confidence" in roles:
        out = []
        for r in rows:
            c = _to_float(r.get(roles["confidence"]))
            out.append(None if c is None else c >= CONF_THRESHOLD)
        return out
    # No explicit signal: treat a row as "detected" if any landmark is non-empty.
    if roles["landmarks"]:
        idx0 = sorted(roles["landmarks"])[0]
        cols = list(roles["landmarks"][idx0].values())
        out = []
        for r in rows:
            out.append(any(_to_float(r.get(c)) is not None for c in cols))
        return out
    return [True] * len(rows)  # assume always detected


def _fps(rows, roles):
    # Prefer effective FPS from timestamps; fall back to fps column.
    ts_col = roles.get("timestamp")
    eff = None
    unit_note = ""
    if ts_col:
        ts = [_to_float(r.get(ts_col)) for r in rows]
        ts = [t for t in ts if t is not None]
        if len(ts) >= 2:
            deltas = [b - a for a, b in zip(ts, ts[1:]) if b - a > 0]
            if deltas:
                med = statistics.median(deltas)
                # Guess units from typical per-frame delta.
                if med > 5:            # ~33 -> milliseconds
                    scale, unit_note = 1000.0, " (ts read as ms)"
                elif med < 1:          # ~0.033 -> seconds
                    scale, unit_note = 1.0, ""
                else:                  # ambiguous
                    scale, unit_note = 1.0, " (ts units uncertain)"
                span = (ts[-1] - ts[0]) / scale
                if span > 0:
                    eff = (len(ts) - 1) / span
    if eff is None and "fps" in roles:
        vals = [_to_float(r.get(roles["fps"])) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            eff = statistics.mean(vals)
            unit_note = " (from fps col)"
    return eff, unit_note


def _frame_motion(rows, roles, detected):
    """Per-transition mean landmark displacement (only when both frames detected)."""
    lms = roles["landmarks"]
    if not lms:
        return []
    indices = sorted(lms)
    motions = []
    for i in range(1, len(rows)):
        if not (detected[i] and detected[i - 1]):
            motions.append(None)
            continue
        disps = []
        for idx in indices:
            axes = lms[idx]
            sq = 0.0
            ok = True
            for ax, col in axes.items():
                a = _to_float(rows[i - 1].get(col))
                b = _to_float(rows[i].get(col))
                if a is None or b is None:
                    ok = False
                    break
                sq += (b - a) ** 2
            if ok:
                disps.append(math.sqrt(sq))
        motions.append(statistics.mean(disps) if disps else None)
    return motions


def _landmark_jitter(motions):
    """Noise floor = mean motion among lowest-motion (held-still) transitions."""
    vals = sorted(m for m in motions if m is not None)
    if not vals:
        return None, None
    overall = statistics.mean(vals)
    cutoff = _percentile(vals, LOW_MOTION_PCTL)
    still = [m for m in vals if m <= cutoff]
    jitter = statistics.mean(still) if still else overall
    return jitter, overall


def _angle_jitter(rows, roles, detected):
    angle_cols = roles["angles"]
    if not angle_cols:
        return None, ""
    # Detect radians vs degrees from value spread.
    sample = []
    for r in rows:
        for c in angle_cols:
            v = _to_float(r.get(c))
            if v is not None:
                sample.append(abs(v))
    note = ""
    scale = 1.0
    if sample:
        p95 = _percentile(sorted(sample), 0.95)
        if p95 is not None and p95 <= RADIAN_GUESS_MAX:
            scale = 180.0 / math.pi
            note = " (rad->deg)"
    # Frame-to-frame absolute change per angle channel, low-motion only.
    per_channel = []
    for c in angle_cols:
        deltas = []
        for i in range(1, len(rows)):
            if not (detected[i] and detected[i - 1]):
                continue
            a = _to_float(rows[i - 1].get(c))
            b = _to_float(rows[i].get(c))
            if a is None or b is None:
                continue
            deltas.append(abs(b - a) * scale)
        if deltas:
            deltas.sort()
            cutoff = _percentile(deltas, LOW_MOTION_PCTL)
            still = [d for d in deltas if d <= cutoff]
            per_channel.append(statistics.mean(still) if still else statistics.mean(deltas))
    if not per_channel:
        return None, note
    return statistics.mean(per_channel), note


def _lost_events(detected):
    events = 0
    lost_frames = 0
    longest_gap = 0
    cur_gap = 0
    seen_detect = False
    for d in detected:
        if d:
            seen_detect = True
            cur_gap = 0
        elif d is False:
            if seen_detect:
                lost_frames += 1
                cur_gap += 1
                longest_gap = max(longest_gap, cur_gap)
        # rising edge: previous lost, now found -> counted via transitions below
    # count detect->lost transitions
    for a, b in zip(detected, detected[1:]):
        if a is True and b is False:
            events += 1
    return events, lost_frames, longest_gap


def _latency(rows, roles):
    col = roles.get("latency")
    if not col:
        return None, None, ""
    vals = [_to_float(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None, ""
    vals_sorted = sorted(vals)
    med = statistics.median(vals_sorted)
    p95 = _percentile(vals_sorted, 0.95)
    # Guess units: seconds vs ms.
    note = ""
    if statistics.median(vals_sorted) < 1.0:
        med *= 1000.0
        p95 *= 1000.0
        note = " (s->ms)"
    return med, p95, note


def compute_metrics(rows, roles):
    detected = _detected_series(rows, roles)
    det_known = [d for d in detected if d is not None]
    det_rate = (sum(1 for d in det_known if d) / len(det_known)) if det_known else None

    fps, fps_note = _fps(rows, roles)
    motions = _frame_motion(rows, roles, detected)
    lm_jit, lm_overall = _landmark_jitter(motions)
    ang_jit, ang_note = _angle_jitter(rows, roles, detected)
    lost_events, lost_frames, longest_gap = _lost_events(detected)
    lat_med, lat_p95, lat_note = _latency(rows, roles)

    return OrderedDict(
        frames=len(rows),
        fps=fps,
        fps_note=fps_note,
        detection_rate=det_rate,
        landmark_jitter=lm_jit,
        landmark_motion=lm_overall,
        angle_jitter=ang_jit,
        angle_note=ang_note,
        lost_events=lost_events,
        lost_frames=lost_frames,
        longest_gap=longest_gap,
        latency_med=lat_med,
        latency_p95=lat_p95,
        latency_note=lat_note,
    )



def load_csv(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames or []
    return header, rows


def group_rows(rows, roles):
    """Yield (label, rows). Split by condition column if present."""
    cond = roles.get("condition")
    if not cond:
        return [(None, rows)]
    groups = OrderedDict()
    for r in rows:
        key = (r.get(cond) or "unlabeled").strip() or "unlabeled"
        groups.setdefault(key, []).append(r)
    return list(groups.items())


def _fmt(v, spec):
    if v is None:
        return "—"
    return format(v, spec)


def build_matrix(records):
    """records: list of (condition_label, metrics dict)."""
    header = ("| Condition | FPS | Detection Rate | Landmark Jitter | "
              "Angle Jitter (°) | Lost-Track Events | Latency p50/p95 (ms) | Frames |")
    sep = "|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for label, m in records:
        fps = _fmt(m["fps"], ".1f")
        det = _fmt(m["detection_rate"] * 100 if m["detection_rate"] is not None else None, ".1f")
        det = det + "%" if det != "—" else det
        ljit = _fmt(m["landmark_jitter"], ".5f")
        ajit = _fmt(m["angle_jitter"], ".2f")
        lost = f'{m["lost_events"]} ({m["lost_frames"]}f)'
        if m["latency_med"] is not None:
            lat = f'{m["latency_med"]:.1f}/{_fmt(m["latency_p95"], ".1f")}'
        else:
            lat = "—"
        lines.append(
            f"| {label} | {fps} | {det} | {ljit} | {ajit} | {lost} | {lat} | {m['frames']} |"
        )
    return "\n".join(lines)


def describe_columns(roles):
    out = ["Columns detected:"]
    for role in ("timestamp", "frame", "detected", "confidence", "fps",
                 "latency", "condition"):
        if role in roles:
            out.append(f"  {role:11s}-> {roles[role]}")
    nlm = len(roles["landmarks"])
    out.append(f"  {'landmarks':11s}-> {nlm} found")
    out.append(f"  {'angles':11s}-> {len(roles['angles'])} found"
               + (": " + ", ".join(roles["angles"][:6]) if roles["angles"] else ""))
    return "\n".join(out)



def parse_args():
    ap = argparse.ArgumentParser(description="Build a robustness test matrix from telemetry CSVs.")
    ap.add_argument("paths", nargs="+", help="CSV file(s) or glob(s)")
    ap.add_argument("-o", "--out", help="also write the markdown matrix here")
    ap.add_argument("--map", action="append", default=[],
                    help="override column mapping, e.g. --map ts=timestamp --map hit=detected")
    ap.add_argument("--label", help="label to use when a file has no condition column "
                    "(defaults to the filename)")
    ap.add_argument("--angle-cols", help="comma-separated columns to treat as the "
                    "jitter/angle channels, e.g. thumb_curl,index_curl,middle_curl,ring_curl,pinky_curl")
    return ap.parse_args()


def main():
    args = parse_args()

    overrides = {}
    for item in args.map:
        if "=" in item:
            name, role = item.split("=", 1)
            overrides[name.strip()] = role.strip()

    files = []
    for p in args.paths:
        files.extend(sorted(glob.glob(p)) or [p])
    if not files:
        print("No CSV files matched.", file=sys.stderr)
        sys.exit(1)

    records = []
    diagnostics = []
    for path in files:
        try:
            header, rows = load_csv(path)
        except OSError as e:
            print(f"Skipping {path}: {e}", file=sys.stderr)
            continue
        if not rows:
            print(f"Skipping {path}: empty", file=sys.stderr)
            continue
        roles = detect_columns(header, overrides)
        if args.angle_cols:
            roles["angles"] = [c.strip() for c in args.angle_cols.split(",")]
        diagnostics.append((path, describe_columns(roles)))
        base = args.label or path.split("/")[-1]
        for label, grp in group_rows(rows, roles):
            name = label if label else base
            records.append((name, compute_metrics(grp, roles)))

    # diagnostics to stderr so the matrix on stdout stays clean
    for path, desc in diagnostics:
        print(f"\n[{path}]\n{desc}", file=sys.stderr)

    matrix = build_matrix(records)
    print("\n" + matrix + "\n")
    print("Jitter = noise floor on held-still frames (lower is better). "
          "Landmark jitter is in the landmark coordinate units (normalised 0-1 if "
          "your tracker outputs image-normalised coords).", file=sys.stderr)

    if args.out:
        with open(args.out, "w") as f:
            f.write("# Robustness Test Matrix\n\n")
            f.write(matrix + "\n\n")
            f.write("_Jitter = mean frame-to-frame movement on held-still frames "
                    "(noise floor; lower is better). Lost-Track Events = "
                    "detect→lost transitions, with total lost frames in parentheses._\n")
        print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()