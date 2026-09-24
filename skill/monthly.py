"""Month-over-month series for the subdivision reports.

Everything here is reconstructed from event dates already in the MLS export --
Listing Contract Date, Purchase Contract Date, Close Date, Withdrawn Date and
Days In MLS. No outside file and no monthly snapshot feed is used.

Two limits are structural and are disclosed in the report rather than papered over:

1. YEAR-OVER-YEAR NEEDS 24 MONTHS. A 365-day export contains one observation of
   each calendar month, so June-this-year has no June-last-year to compare to.
   yoy() returns None in that case and the report prints why. Supply a 24-month
   export and it computes automatically.

2. EARLY MONTHS UNDERSTATE INVENTORY. A 365-day export only contains listings
   that were still in the system inside that window, so homes that left the
   market shortly before the window opened are missing from the reconstructed
   active count in the first month or two. Inventory and months-of-supply lines
   are therefore biased low at the left edge of the chart.
"""
import pandas as pd, numpy as np

TYPE_COL = 'Property Sub Type'      # falls back to Property Type, then a single bucket
ALL = 'All property types'


# ------------------------------------------------------------------ setup
def type_series(d):
    """Property-type label per row. Reports colour by this when a file is mixed."""
    for c in (TYPE_COL, 'Property Type', 'Structure Type'):
        if c in d and d[c].notna().any():
            s = d[c].fillna('Unspecified').astype(str).str.strip()
            if s.nunique() > 1:
                return s, sorted(s.unique())
            return s, [s.iloc[0]]
    s = pd.Series([ALL] * len(d), index=d.index)
    return s, [ALL]


def _exit_date(d):
    """When a listing left the active pool: under contract, closed, withdrawn, or
    -- for an expired listing with no recorded exit -- listing date + days in MLS."""
    pc = d.get('Purchase Contract Date')
    cd = d.get('Close Date')
    wd = pd.to_datetime(d.get('Withdrawn Date'), errors='coerce') if 'Withdrawn Date' in d else pd.Series(pd.NaT, index=d.index)
    out = pd.Series(pd.NaT, index=d.index, dtype='datetime64[ns]')
    for src in (pc, cd, wd):
        if src is not None:
            out = out.fillna(pd.to_datetime(src, errors='coerce'))
    st = d['Mls Status'].astype(str).str.strip().str.lower()
    gone = st.isin(['expired', 'withdrawn', 'canceled', 'cancelled'])
    dim = pd.to_numeric(d.get('Days In MLS'), errors='coerce')
    fallback = pd.to_datetime(d['Listing Contract Date'], errors='coerce') + pd.to_timedelta(dim.fillna(0), unit='D')
    out = out.where(~(gone & out.isna()), fallback)
    return out


def month_axis(d, n=12):
    """The n complete months ending with the last complete month in the export.
    The current partial month is excluded -- a half-finished month reads as a
    collapse in every count and would be the single most misleading thing here."""
    ev = []
    for c in ('Listing Contract Date', 'Purchase Contract Date', 'Close Date'):
        if c in d: ev.append(pd.to_datetime(d[c], errors='coerce'))
    allev = pd.concat(ev).dropna()
    if allev.empty: return []
    last_full = (allev.max().to_period('M')) - 1
    return list(pd.period_range(end=last_full, periods=n, freq='M'))


# ------------------------------------------------------------------ series
def _by(d, months, tser, types, datecol, agg):
    """agg(frame) -> value, computed per month and per property type, plus a
    combined 'All property types' series."""
    dt = pd.to_datetime(d[datecol], errors='coerce').dt.to_period('M')
    out = {}
    for t in ([ALL] + types if len(types) > 1 else [ALL]):
        sel = d if t == ALL else d[tser == t]
        sdt = dt.reindex(sel.index)
        out[t] = [agg(sel[sdt == mo]) for mo in months]
    return out


def _active_at(d, tser, types, when, inclusive_start=False):
    """Count of listings active on a given date, by property type."""
    ld = pd.to_datetime(d['Listing Contract Date'], errors='coerce')
    ex = _exit_date(d)
    live = (ld <= when) & (ex.isna() | (ex > when))
    out = {}
    for t in ([ALL] + types if len(types) > 1 else [ALL]):
        sel = live if t == ALL else (live & (tser == t))
        out[t] = int(sel.sum())
    return out


def build(d, n=12):
    """All seven month-over-month series, keyed by metric then property type.

    Series are computed across n+12 months but only the last n are charted. The
    extra twelve months exist so a year-over-year comparison has a prior-year month
    to reach back to; they are never plotted. `months`/`series` are the chart
    window, `months_ext`/`series_ext` the full computed span.
    """
    months = month_axis(d, n + 12)
    if not months: return None
    tser, types = type_series(d)
    multi = len(types) > 1
    keys = ([ALL] + types) if multi else [ALL]

    cnt = lambda f: int(len(f))
    medp = lambda f: float(f['Close Price'].median()) if len(f) else float('nan')
    medd = lambda f: float(f['Days In MLS'].median()) if len(f) else float('nan')

    S = {}
    S['closed']      = _by(d, months, tser, types, 'Close Date', cnt)
    S['med_close']   = _by(d, months, tser, types, 'Close Date', medp)
    S['med_dom']     = _by(d, months, tser, types, 'Close Date', medd)
    S['new']         = _by(d, months, tser, types, 'Listing Contract Date', cnt)
    S['pending']     = _by(d, months, tser, types, 'Purchase Contract Date', cnt)

    # Total listings in a month = still active entering the month + newly listed in it.
    S['total'] = {k: [] for k in keys}
    S['msi']   = {k: [] for k in keys}
    for i, mo in enumerate(months):
        start = mo.to_timestamp(how='start') - pd.Timedelta(days=1)
        end = mo.to_timestamp(how='end')
        a0 = _active_at(d, tser, types, start)
        a1 = _active_at(d, tser, types, end)
        for k in keys:
            S['total'][k].append(a0[k] + S['new'][k][i])
            # Months of supply on a trailing three-month sales pace. A single
            # month's closings is far too small a denominator at subdivision scale.
            w = [S['closed'][k][j] for j in range(max(0, i - 2), i + 1)]
            pace = (sum(w) / len(w)) if w else 0
            S['msi'][k].append(a1[k] / pace if pace > 0 else float('nan'))

    win = months[-n:]
    Sw = {k: {t: v[-n:] for t, v in ser.items()} for k, ser in S.items()}
    return dict(months=win, series=Sw, months_ext=months, series_ext=S,
                types=types, keys=keys, multi=multi,
                labels=[m.strftime('%b') for m in win],
                full=[m.strftime('%b %Y') for m in win])


# ------------------------------------------------------------------ deltas
def _last_valid(v):
    for i in range(len(v) - 1, -1, -1):
        if v[i] == v[i] and not (isinstance(v[i], float) and np.isinf(v[i])):
            return i
    return None


def _delta(v, months, i, j):
    cur, prev = v[i], v[j]
    pct = ((cur - prev) / prev * 100) if prev else None
    return dict(pct=pct, cur=cur, prev=prev, delta=cur - prev,
                cur_m=months[i].strftime('%b %Y'), prev_m=months[j].strftime('%b %Y'),
                adjacent=(i - j == 1))


def mom(v, months):
    """Latest month carrying data vs the previous month carrying data. When a month
    in between has no sales the comparison skips it, so the returned labels name
    the months actually compared rather than implying they were adjacent."""
    i = _last_valid(v)
    if i is None or i == 0: return None
    j = i - 1
    while j >= 0 and v[j] != v[j]: j -= 1
    if j < 0: return None
    return _delta(v, months, i, j)


def yoy(v, months):
    """Latest month vs the same calendar month a year earlier. Returns None when the
    export does not span two years -- which a 365-day export never does."""
    i = _last_valid(v)
    if i is None: return None
    target = months[i] - 12
    if target not in months: return None
    j = months.index(target)
    if v[j] != v[j]: return None
    return _delta(v, months, i, j)


def coverage_months(d):
    """How many complete months this export actually covers.

    Uses the span of CLOSING dates as the proxy, because closings are spread
    through whatever window the export was pulled for, while listing dates reach
    back before it: a 365-day export still contains listings first published two
    years ago that happened to survive into the window. Counting those would
    overstate coverage, and any month before the true window start holds only the
    listings that survived it -- a survivorship-biased sample that must never be
    compared against a complete month.
    """
    cd = pd.to_datetime(d.get('Close Date'), errors='coerce').dropna()
    if cd.empty: return 0
    a, b = cd.min().to_period('M'), cd.max().to_period('M')
    return (b - a).n + 1


def yoy_available(d):
    """A year-over-year comparison needs the same calendar month twice, so the
    export has to cover more than 13 months. A 365-day export never does."""
    return coverage_months(d) > 13


def fmt_delta(dd, kind='count'):
    """Human-readable change. Falls back to an absolute when the base is zero,
    because a percentage change from zero is undefined, not infinite."""
    if dd is None: return None, ''
    if dd['pct'] is None:
        sign = '+' if dd['delta'] > 0 else ''
        return f"{sign}{dd['delta']:,.0f}", 'from zero'
    sign = '+' if dd['pct'] > 0 else ''
    return f"{sign}{dd['pct']:.0f}%", ''
