"""Resolve an MLS export's ZIPs to the area-level reference values.

Nothing outside this module reads the pack CSVs. Callers get an AreaContext in
which every value arrives with the geography it was measured at and the date it
is as of -- never a bare float. A figure that cannot report its own provenance
is how a Littleton-city population ended up printed under a Jefferson County
subdivision.

GEOGRAPHY COMES FROM THE CROSSWALK, NEVER FROM THE CITY FIELD. ZIP 80128's MLS
city says Littleton; it is 91% Jefferson County and essentially none of it is
inside Littleton city limits. Around 84% of Jefferson County is unincorporated
but carries incorporated-city mailing addresses, so resolving geography by name
is wrong across a large share of Colorado and never announces itself. The HUD
crosswalk's own `city` column is postal too, and is not used here either.

MISSING IS NORMAL. Roughly seven Colorado ZIPs in ten have no ZORI rent series,
so Rent to Price is usually absent. A missing input is dropped and the mean's
denominator recomputed -- never zeroed, never filled with a state average.
"""
import csv
import json
import os

PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'assets', 'co_reference')

ANCHOR_YIELD = (2.0, 8.0)       # gross annual rent / value, percent

# Growth Outlook's three inputs do NOT share one anchor. They did originally
# (-5%/+10% for all three, the investor.py convention) and that was a real
# bug, not just a simplification: appreciation's real Colorado range (-13% to
# +14%) is wider than that shared anchor, while population (-2.6% to +3.4%)
# and employment (-2.0% to +2.8%) compress into roughly its middle third --
# so appreciation alone drove nearly all real movement in the score even at
# equal nominal weights. Each input gets its own anchor, sized to its own
# observed Colorado range, so equal weights actually mean equal influence.
# See SKILL.md rule 61.
ANCHOR_APPR = (-8.0, 12.0)     # ZHVI YoY appreciation, percent
ANCHOR_POP = (-2.0, 3.0)       # county population, annualized percent/yr
ANCHOR_EMP = (-3.0, 4.0)       # CBSA/statewide payrolls YoY, percent

# A dominant ZIP holding less than this share of listings means the subdivision
# genuinely straddles ZIPs and the report should say so.
DOMINANT_MIN = 0.70


class Value:
    """A number that knows where it came from."""

    def __init__(self, value, scope, as_of, source):
        self.value, self.scope, self.as_of, self.source = value, scope, as_of, source

    def __repr__(self):
        return f'Value({self.value!r}, {self.scope!r}, {self.as_of!r})'


class AreaContext:
    def __init__(self):
        self.zip = None
        self.zips = []
        self.spans_zips = False
        self.county = None
        self.values = {}     # key -> Value
        self.dropped = {}    # key -> reason
        self.notes = []

    def get(self, key):
        v = self.values.get(key)
        return v.value if v else None

    def scope(self, key):
        v = self.values.get(key)
        return v.scope if v else None

    def as_dict(self):
        """Shape the carousel and report layers consume."""
        d = {}
        for k, v in self.values.items():
            d[k] = v.value
            d[f'{k}_scope'] = v.scope
            d[f'{k}_as_of'] = v.as_of
        d['_dropped'] = dict(self.dropped)
        d['_spans_zips'] = self.spans_zips
        return d


def _scale(x, lo, hi):
    if x is None:
        return None
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))


def _load(name):
    path = os.path.join(PACK, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def _num(row, key):
    v = (row or {}).get(key, '')
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def vintages():
    path = os.path.join(PACK, 'vintages.json')
    if not os.path.exists(path):
        return {}
    return json.load(open(path))


def dominant(zips):
    """Pick the ZIP that carries the subdivision, plus whether it straddles.

    Accepts a list (one entry per listing) or a {zip: count} mapping. Values are
    never averaged across ZIPs -- an averaged rent describes no real place.
    """
    if not zips:
        return None, False
    if isinstance(zips, dict):
        counts = dict(zips)
    else:
        counts = {}
        for z in zips:
            z = str(z).strip()[:5].zfill(5)
            if z.isdigit():
                counts[z] = counts.get(z, 0) + 1
    if not counts:
        return None, False
    total = sum(counts.values())
    top = max(counts, key=counts.get)
    return top, (counts[top] / total) < DOMINANT_MIN


def resolve(zips):
    """Build the AreaContext for an export's ZIPs."""
    ctx = AreaContext()
    z, spans = dominant(zips)
    ctx.zip, ctx.spans_zips = z, spans
    if isinstance(zips, dict):
        ctx.zips = sorted(zips)
    else:
        ctx.zips = sorted({str(x).strip()[:5].zfill(5) for x in zips or []})
    if not z:
        ctx.dropped['rent'] = 'no ZIP found in the export'
        ctx.dropped['growth'] = 'no ZIP found in the export'
        return ctx

    rows = _load('zips.csv')
    if rows is None:
        ctx.dropped['rent'] = 'reference pack not installed'
        ctx.dropped['growth'] = 'reference pack not installed'
        return ctx
    row = next((r for r in rows if r['zip'] == z), None)
    if row is None:
        ctx.dropped['rent'] = f'ZIP {z} not in the Colorado pack'
        ctx.dropped['growth'] = f'ZIP {z} not in the Colorado pack'
        return ctx

    vt = vintages()
    ctx.county = row.get('county_name') or None

    # ---- Rent to Price: GROSS annual rent over value, nothing deducted -----
    rent, zhvi = _num(row, 'zori_now'), _num(row, 'zhvi_now')
    if rent and zhvi:
        gy = rent * 12 / zhvi * 100
        ctx.values['rent'] = Value(
            round(_scale(gy, *ANCHOR_YIELD)), f'ZIP {z}',
            row.get('zori_month') or vt.get('zori', {}).get('as_of'), 'Zillow ZORI/ZHVI')
        ctx.values['gross_yield'] = Value(round(gy, 2), f'ZIP {z}',
                                          row.get('zori_month'), 'Zillow ZORI/ZHVI')
    else:
        ctx.dropped['rent'] = (f'no Zillow rent series for ZIP {z} — about 70% of '
                               f'Colorado ZIPs have none')

    # ---- Growth Outlook: appreciation + population + employment ------------
    subs, parts = [], []
    now, ago = _num(row, 'zhvi_now'), _num(row, 'zhvi_year_ago')
    if now and ago:
        ap = (now / ago - 1) * 100
        subs.append(_scale(ap, *ANCHOR_APPR))
        parts.append(f'appreciation {ap:+.2f}% (ZIP {z})')
    else:
        ctx.notes.append('growth: home-value appreciation unavailable')

    pop_pct, pop_scope = None, None
    counties = _load('counties.csv') or []
    crow = next((r for r in counties if r['county_name'] == ctx.county), None)
    if crow:
        pop_pct = _num(crow, 'pop_annual_pct')
        pop_scope = ctx.county
    if pop_pct is not None:
        subs.append(_scale(pop_pct, *ANCHOR_POP))
        parts.append(f'population {pop_pct:+.2f}%/yr ({pop_scope})')
    else:
        ctx.notes.append('growth: county population unavailable')

    # Employment resolves per-CBSA where BLS publishes one -- seven Colorado
    # metros do. Everywhere else (micropolitan CBSAs and the 154 ZIPs with no
    # CBSA at all -- 41% of the state) falls back to the statewide series
    # rather than dropping the term, since a real statewide number is a better
    # growth input than silently losing a third of the index.
    emp = _load('employment.csv') or []
    cb = row.get('cbsa_code') or ''
    erow = next((r for r in emp if r['cbsa_code'] == cb), None) if cb else None
    used_fallback = False
    if erow is None:
        erow = next((r for r in emp if r['cbsa_code'] == ''), None)
        used_fallback = True
    if erow:
        ey = _num(erow, 'yoy_pct')
        subs.append(_scale(ey, *ANCHOR_EMP))
        label = 'Colorado statewide' if used_fallback else f'CBSA {cb}'
        parts.append(f'employment {ey:+.2f}% ({label})')
        if used_fallback:
            ctx.notes.append('growth: no metro-level employment series for this '
                             'area — used the statewide figure instead')
    else:
        ctx.notes.append('growth: no employment series available at all '
                         '— dropped, denominator recomputed')

    if subs:
        ctx.values['growth'] = Value(
            round(sum(subs) / len(subs)),
            (ctx.county or f'ZIP {z}').replace(', Colorado', ''),
            vt.get('pep', {}).get('as_of'), '; '.join(parts))
        if len(subs) < 3:
            ctx.dropped['growth_inputs'] = f'{len(subs)} of 3 inputs available'
    else:
        ctx.dropped['growth'] = 'no growth inputs available for this area'

    return ctx


def from_export(df, zip_col=None):
    """Convenience: pull the ZIPs straight off a loaded MLS export."""
    if zip_col is None:
        for c in ('Postal Code', 'Zip Code', 'ZipCode', 'Zip', 'PostalCode'):
            if c in getattr(df, 'columns', []):
                zip_col = c
                break
    if zip_col is None:
        return resolve([])
    vals = [str(v) for v in df[zip_col].dropna().tolist()]
    return resolve(vals)


def top_origins(zip_code, limit=5):
    """Where people moving INTO this ZIP's county came from -- IRS SOI
    county-to-county inflow, 2022-2023 tax years.

    COUNTY LEVEL ONLY. No government source publishes migration below the
    county; this is the county the ZIP mostly sits in (zips.csv's county_fips,
    the same HUD-crosswalk geography rule as everything else here), never a
    ZIP-to-ZIP flow. Callers must label it that way.

    Returns None -- never an empty or guessed list -- when the ZIP isn't in
    the pack, the migration file isn't installed, or the IRS suppressed every
    flow for this county (it drops any flow under 20 returns, which removes
    13 of Colorado's 64 counties entirely).

    'people' is the IRS exemption count (their own proxy for persons);
    'households' is the return count. avg_agi is aggregate AGI (reported by
    the IRS in thousands) divided by returns -- an average, not a median.
    """
    z = str(zip_code or '').strip()[:5].zfill(5)
    row = next((r for r in (_load('zips.csv') or []) if r['zip'] == z), None)
    if not row or not row.get('county_fips'):
        return None
    mig = _load('migration.csv')
    if mig is None:
        return None
    hits = [r for r in mig if r['county_fips'] == row['county_fips']]
    origins = []
    for r in hits:
        people, returns, agi = _num(r, 'exemptions'), _num(r, 'returns'), _num(r, 'agi')
        if not people or people < 0 or not returns or returns < 0:
            continue  # IRS uses -1 for a suppressed cell
        origins.append({
            'place': f"{r['origin_county']}, {r['origin_state']}",
            'people': int(people),
            'households': int(returns),
            'avg_agi': round(agi * 1000 / returns) if agi and agi > 0 else None,
        })
    if not origins:
        return None
    origins.sort(key=lambda o: o['people'], reverse=True)
    vt = vintages().get('irs_migration', {})
    total = _num(hits[0], 'total_people')
    instate = _num(hits[0], 'instate_people')
    top = origins[:limit]
    return {
        'county': (row.get('county_name') or '').replace(', Colorado', ''),
        'total_people': int(total) if total and total > 0 else None,
        'top_share_pct': (round(sum(o['people'] for o in top) / total * 100)
                          if total and total > 0 else None),
        'instate_pct': (round(instate / total * 100)
                        if total and total > 0 and instate and instate > 0 else None),
        'as_of': vt.get('as_of', '2022-2023'),
        'source': 'IRS SOI county-to-county migration',
        'origins': top,
    }
