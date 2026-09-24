"""Best-conditions analysis for Chance of Selling.

WHAT THIS ANSWERS
------------------
Given this subdivision's own history, what combination of listing conditions
correlated with the fastest path to a signed contract, and at what point does
a correctly-conditioned listing sitting unsold stop being "patience" and start
being a pricing problem?

WHAT IT DOES NOT ANSWER, AND WHY
---------------------------------
Two inputs the person asking for this analysis wanted are not in a standard
MLS subdivision export, and this module says so rather than faking them:

  * OPEN HOUSES. No MLS export field records whether or when a listing held
    one. This needs a separate open-house log, the same way Showing Activity
    needs a separate ShowingTime export (see showings.py). If one is ever
    supplied, this is the natural place to wire it in.
  * WHEN a price change happened during a listing's life. The export has
    whether a listing was ever reduced and the total elapsed time, not a
    reduction timestamp. So this module can say how long PRICED-RIGHT listings
    typically took to get an offer, and use that as the benchmark for "this is
    the point where waiting stops paying off" -- it cannot say precisely which
    day a real reduction happened on.

EVERY SPLIT IS SAMPLE-GATED
----------------------------
Day-of-week and month-listed splits are exactly the case the skill's own
principle warns about: "flag when sample sizes don't support a given analysis
... rather than producing spurious output." A 365-day, single-subdivision
export puts single digits in some weekday and month buckets. Those numbers are
shown -- hiding them would be worse -- but always labeled directional, and the
module refuses to name a "best" day or month outright the way `moi_label` names
a market condition, because the sample does not support that kind of claim.

PROPERTY TYPE AND PRICE BAND
------------------------------
Every split here is computed once on the whole file and, when the export
contains more than one property type (the sales-rep ZIP/city/county version
routinely will), once per type. A subdivision-only, single-type export
collapses to the single-type case automatically -- there is no special-casing
needed at the call site.
"""
import numpy as np
import pandas as pd

MIN_CELL = 8      # a 2x2 cell below this is not shown as its own number
MIN_DOW = 15       # weekday-vs-weekend needs this many per side to headline
MIN_MONTH = 6      # a month bucket below this is folded into "too few to show"


def _type_col(cl):
    for c in ('Property Sub Type', 'Property Type', 'Structure Type'):
        if c in cl and cl[c].notna().any():
            s = cl[c].fillna('Unspecified').astype(str).str.strip()
            if s.nunique() > 1:
                return s
    return None


def updated_split(cl, by_type=True):
    """Priced-right x updated-condition grid, median days and count per cell.

    Returns a list of dicts, one per property type (or one row keyed 'All' if
    the file is single-type), each holding the four cells. A cell below
    MIN_CELL prints its raw count but is flagged thin rather than omitted --
    at this level omitting it would look like the data was hidden rather than
    just small.
    """
    if 'Property Condition' not in cl or cl['Property Condition'].notna().sum() < MIN_CELL * 2:
        return None
    cond = cl['Property Condition'].fillna('Not specified')
    upd = cond == 'Updated/Remodeled'
    pr = ~cl['red']
    tcol = _type_col(cl) if by_type else None
    groups = [('All', cl.index)] if tcol is None else [(t, cl.index[tcol == t]) for t in sorted(tcol.unique())]
    out = []
    for label, idx in groups:
        sub_pr, sub_upd = pr.reindex(idx), upd.reindex(idx)
        sub = cl.loc[idx]
        if len(idx) < MIN_CELL:
            continue
        cells = {}
        for prv, prl in ((True, 'priced_right'), (False, 'reduced')):
            for uv, ul in ((True, 'updated'), (False, 'not_updated')):
                sel = sub[(sub_pr == prv) & (sub_upd == uv)]
                n = len(sel)
                cells[f'{prl}_{ul}'] = dict(
                    n=n, median=float(sel['Days In MLS'].median()) if n else None, thin=n < MIN_CELL)
        upd_share_reduced = float(sub_upd[~sub_pr].mean()) if (~sub_pr).sum() else None
        notupd_share_reduced = float((~sub_upd[~sub_pr]).mean()) if False else None
        out.append(dict(type=label, n=len(idx), cells=cells,
                        reduced_rate_updated=float((~sub_pr[sub_upd]).mean()) if sub_upd.sum() else None,
                        reduced_rate_not_updated=float((~sub_pr[~sub_upd]).mean()) if (~sub_upd).sum() else None))
    return out or None


def weekday_split(cl):
    """Weekday vs weekend listed. Full 7-day table always included for
    transparency; the weekday/weekend headline only renders when both sides
    clear MIN_DOW, since a subdivision-scale file routinely does not."""
    if 'Listing Contract Date' not in cl:
        return None
    dow = pd.to_datetime(cl['Listing Contract Date'], errors='coerce').dt.day_name()
    wknd = dow.isin(['Saturday', 'Sunday'])
    n_wk, n_we = int((~wknd).sum()), int(wknd.sum())
    headline = None
    if n_wk >= MIN_DOW and n_we >= MIN_DOW:
        headline = dict(weekday_median=float(cl.loc[~wknd, 'Days In MLS'].median()), weekday_n=n_wk,
                        weekend_median=float(cl.loc[wknd, 'Days In MLS'].median()), weekend_n=n_we)
    order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    table = []
    for day in order:
        sel = cl.loc[dow == day, 'Days In MLS']
        if len(sel):
            table.append(dict(day=day, n=int(len(sel)), median=float(sel.median())))
    return dict(headline=headline, table=table, reliable=(n_wk >= MIN_DOW and n_we >= MIN_DOW))


def month_split(cl):
    """Median days-to-contract by the calendar month a listing hit the market.
    Always directional at subdivision scale -- this module never calls a
    'best month,' it only reports what happened, with the count beside it."""
    if 'Listing Contract Date' not in cl:
        return None
    mon = pd.to_datetime(cl['Listing Contract Date'], errors='coerce')
    key = mon.dt.strftime('%b')
    order = mon.dt.month
    tbl = pd.DataFrame({'m': key, 'o': order, 'd': cl['Days In MLS']}).dropna(subset=['m'])
    g = tbl.groupby(['m', 'o'])['d'].agg(['median', 'count']).reset_index().sort_values('o')
    rows = [dict(month=r['m'], n=int(r['count']), median=float(r['median']), thin=r['count'] < MIN_MONTH)
            for _, r in g.iterrows()]
    return rows or None


def decision_signal(cl, m):
    """The 'how long is too long' benchmark: percentile days-to-offer among
    listings that never reduced, i.e. the market's own record for a correctly
    priced home. Framed as a benchmark to weigh a stalled listing against, not
    a promise about any individual home."""
    pr = ~cl['red']
    vals = cl.loc[pr, 'Days In MLS'].dropna()
    if len(vals) < MIN_CELL:
        return None
    p50, p75, p90 = np.percentile(vals, [50, 75, 90])
    conc = cl['conc'] if 'conc' in cl else pd.Series(0, index=cl.index)
    conc_pr = float((conc[pr] > 0).mean()) if pr.sum() else None
    conc_red = float((conc[~pr] > 0).mean()) if (~pr).sum() else None
    return dict(n=len(vals), p50=float(p50), p75=float(p75), p90=float(p90),
               conc_rate_priced_right=conc_pr, conc_rate_reduced=conc_red)


def price_point_bands(cl, n=5):
    """Median days-to-contract by price quintile -- the data behind the Speed
    section's line chart. Finer than the tercile bands used for pricing-power
    tables (which need larger cells for a percent-of-ask average); a days-to-
    contract median tolerates a smaller cell, and the chart needs enough
    points to read as a line rather than three dots."""
    from core import mshort_series
    valid = cl.dropna(subset=['Close Price', 'Days In MLS'])
    if len(valid) < n * 4:
        n = max(3, len(valid) // 6) or 3
    q = sorted(set(round(x / 5000) * 5000 for x in
               [valid['Close Price'].min() - 1] +
               list(np.percentile(valid['Close Price'], np.linspace(0, 100, n + 1)[1:-1])) +
               [valid['Close Price'].max()]))
    if len(q) < 3:
        return None
    fmt = mshort_series(q)
    labs = [f'{fmt(q[i])}\u2013{fmt(q[i+1])}' for i in range(len(q) - 1)]
    b = pd.cut(valid['Close Price'], q, labels=labs, include_lowest=True)
    g = valid.groupby(b, observed=True)['Days In MLS'].agg(['median', 'count'])
    g = g.reset_index().rename(columns={g.index.name or 'Close Price': 'band'})
    return g.to_dict('records')


def build(cl, m):
    """Everything the report section needs, in one call. Any piece the data
    can't support comes back None and the caller skips it -- nothing here
    ever renders a placeholder in place of a real number."""
    return dict(
        updated=updated_split(cl),
        weekday=weekday_split(cl),
        month=month_split(cl),
        decision=decision_signal(cl, m),
        has_open_house_data=False,   # never true from a bare MLS export; see module docstring
    )
