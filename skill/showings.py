"""Showing activity, loaded from ShowingTime / InfoSparks exports.

WHY THIS IS A LOADER, NOT A FIXTURE
------------------------------------
An earlier version of this module hard-coded Columbine Knolls' own numbers as
module-level constants. That worked for one report and would have silently
kept reporting Columbine Knolls' showing activity on every subsequent
subdivision -- a serious, silent-failure-class bug. This module now reads the
two InfoSparks CSV exports directly, the way core.load() reads the MLS export.

INPUT FILES
-----------
Two CSVs from REcolorado / InfoSparks, named by the platform's own export
convention:
  * "Showings Per Listing-<area>-<date>.csv"
  * "Median Showings to Pending-<area>-<date>.csv"

Both share a header block (Metric / Time Calculation / Data from / Segments /
Filters) before the actual `Date,<area>,` data rows begin. load() skips that
block and reads to the trailing REcolorado/InfoSparks attribution line.

Neither the agent-facing nor the sales-rep skill requires these files. When
neither is supplied, `enabled` is False and the caller skips the Showing
Activity section entirely -- this is precisely the agent-version behavior
requested: no ShowingTime access, no section 4, no gap left behind.
"""
import re


def _parse_infosparks(path):
    """One InfoSparks CSV -> [(month_label, value), ...], oldest first."""
    raw = open(path, encoding='utf-8-sig').read().splitlines()
    start = next((i for i, l in enumerate(raw) if l.startswith('Date,')), None)
    if start is None:
        raise ValueError(f'{path}: no "Date," header row found -- not an InfoSparks export?')
    rows = []
    for line in raw[start + 1:]:
        line = line.strip()
        if not line or line.startswith('"*') or line.startswith('"All'):
            continue
        parts = [p.strip().strip('"') for p in line.split(',')]
        if len(parts) < 2 or not parts[1]:
            continue
        try:
            val = float(parts[1])
        except ValueError:
            continue
        m = re.match(r'([A-Za-z]+)\s+(\d{4})', parts[0])
        label = f'{m.group(1)[:3]} {m.group(2)}' if m else parts[0]
        rows.append((label, val))
    return rows


def load(spl_path=None, stp_path=None, src_note=None):
    """Load one or both InfoSparks exports. Either alone still produces a
    usable (if partial) profile; both None returns the disabled sentinel.

    Returns a dict: enabled, labels, spl (showings/listing), stp (showings to
    pending), src -- the exact attribution line to print in the report.
    """
    if not spl_path and not stp_path:
        return dict(enabled=False, labels=[], spl=[], stp=[], src=None)

    spl_rows = _parse_infosparks(spl_path) if spl_path else []
    stp_rows = _parse_infosparks(stp_path) if stp_path else []
    spl_map = dict(spl_rows)
    stp_map = dict(stp_rows)
    labels = list(dict.fromkeys([l for l, _ in spl_rows] + [l for l, _ in stp_rows]))

    src = src_note or 'REcolorado\u00ae / InfoSparks \u00a9 ShowingTime Plus, LLC \u2014 user-defined area'
    return dict(
        enabled=True, labels=labels,
        spl=[spl_map.get(l) for l in labels],
        stp=[stp_map.get(l) for l in labels],
        src=src,
    )


def window(prof, full_labels):
    """Align a loaded profile onto the report's 12-month axis (labels like
    'Aug 2025'). Returns (spl, stp) lists with None where a month is absent."""
    if not prof['enabled']:
        return [None] * len(full_labels), [None] * len(full_labels)
    ix = {l: i for i, l in enumerate(prof['labels'])}
    spl = [prof['spl'][ix[l]] if l in ix else None for l in full_labels]
    stp = [prof['stp'][ix[l]] if l in ix else None for l in full_labels]
    return spl, stp


def yoy_pairs(prof):
    """Months present in both a year and the year before it within the loaded
    file. Returns [(month, a_prev, b_prev, a_cur, b_cur)]. Needs the loaded
    export to span 13+ months, which is exactly why this exists separately
    from the MLS file's 12-month window -- InfoSparks exports commonly do."""
    if not prof['enabled']:
        return []
    ix = {l: i for i, l in enumerate(prof['labels'])}
    out = []
    for l in prof['labels']:
        try:
            mon, yr = l.split()
            yr = int(yr)
        except ValueError:
            continue
        prev = f'{mon} {yr - 1}'
        if prev in ix:
            i, j = ix[prev], ix[l]
            out.append((mon, prof['spl'][i], prof['stp'][i], prof['spl'][j], prof['stp'][j]))
    return out
