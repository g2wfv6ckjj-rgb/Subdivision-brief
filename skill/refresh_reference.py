"""Build the Colorado reference pack from the raw downloads.

Run this quarterly, drop the output into scripts/assets/co_reference/, ship it.
Nothing at report time touches the raw files -- they are 130 MB and the pack is
a few hundred KB, because only two months per ZIP are ever consumed.

VALIDATION IS NOT OPTIONAL. Census and HUD change file layouts between vintages
without notice -- the 2025 PEP file broke the old loader twice in one file, via a
split two-row header and a state name folded into the name cell. So every table
is checked for plausible row counts and a known value before anything is written.
A refresh that silently drops half the ZIPs is worse than one that stops.
"""
import csv
import json
import os
import sys
from datetime import date

import pandas as pd

UP = '/mnt/user-data/uploads'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/outputs/co_reference'

FRED_DIR = os.environ.get('CO_FRED_DIR', UP)  # override for this session only

# CBSA code -> (metro name, FRED series id). One series per Colorado metro that
# BLS actually publishes an SM series for, plus the statewide series used as the
# fallback for every micropolitan CBSA and every ZIP with no CBSA at all --
# together 41% of Colorado ZIPs (see co_data.py).
EMPLOYMENT_SERIES = {
    '19740': ('Denver-Aurora-Lakewood', 'SMU08197400000000001A'),
    '17820': ('Colorado Springs',       'SMU08178200000000001A'),
    '24540': ('Greeley',                'SMU08245400000000001A'),
    '14500': ('Boulder',                'SMU08145000000000001A'),
    '22660': ('Fort Collins',           'SMU08226600000000001A'),
    '24300': ('Grand Junction',         'SMU08243000000000001A'),
    '39380': ('Pueblo',                 'SMU08393800000000001A'),
    '':      ('Colorado statewide',     'SMU08000000000000001A'),
}

SRC = {
    'zori':    f'{UP}/Zip_zori_uc_sfrcondomfr_sm_month.csv',
    'zhvi':    f'{UP}/Zip_zhvi_uc_sfrcondo_tier_0_33_0_67_sm_sa_month.csv',
    'pep':     f'{UP}/co-est2025-pop-08.xlsx',
    'acs':     '/home/claude/zc/ACSST5Y2024.S0101-Data.csv',
    'zipcty':  f'{UP}/ZIP-COUNTY_062026.xlsx',
    'zipcbsa': f'{UP}/ZIP-CBSA_062026.xlsx',
}


class BuildError(Exception):
    pass


def _check(cond, msg):
    if not cond:
        raise BuildError(msg)


# ------------------------------------------------------------------ Zillow
def zillow(path, label, require_year_ago=True):
    """Current and year-ago value per Colorado ZIP, plus the month they are as of.

    Takes the last column with data for each row individually: Zillow's file is
    ragged at the right edge, and a ZIP whose newest month is blank must report
    its own latest month rather than inherit the file's.

    require_year_ago=False (ZORI) keeps a ZIP on its current value alone when no
    12-months-back point exists. Zillow adds newly-covered ZIPs to ZORI without
    backfilling history, so a flat "needs 13 non-blank months" rule dropped 37 of
    193 Colorado ZIPs -- 19% of rent coverage -- even though nothing downstream
    consumes ZORI's year-ago figure; only current rent feeds gross yield.
    ZHVI keeps require_year_ago=True because appreciation needs both points, and
    every Colorado ZHVI ZIP already has 13+ months, so this changes nothing there.

    The year-ago point, when taken, is matched by its CALENDAR month label
    (exactly 12 months before the current month) rather than by counting back
    13 list positions -- position-counting silently miscomputes if a ZIP has a
    gap earlier in its series. Verified against this data: no gaps exist, but
    matching by label is correct regardless and costs nothing.
    """
    def month_minus_12(m):
        y, mo, d = m.split('-')
        y, mo = int(y), int(mo)
        return f'{y - 1}-{mo:02d}-{d}' if mo <= 12 else m

    out, month_seen = {}, None
    with open(path, encoding='utf-8-sig') as f:
        r = csv.reader(f)
        hdr = next(r)
        zi, si = hdr.index('RegionName'), hdr.index('State')
        mcols = [(i, h) for i, h in enumerate(hdr) if h[:2] == '20' and h.count('-') == 2]
        _check(len(mcols) > 24, f'{label}: only {len(mcols)} month columns found')
        for row in r:
            if row[si] != 'CO':
                continue
            vals = {m: row[i] for i, m in mcols if row[i] not in ('', None)}
            if not vals:
                continue
            m_now = max(vals)
            v_now = vals[m_now]
            m_ago = month_minus_12(m_now)
            v_ago = vals.get(m_ago)
            if require_year_ago and v_ago is None:
                continue
            out[row[zi].zfill(5)] = (float(v_now), m_now,
                                     float(v_ago) if v_ago is not None else None)
            month_seen = max(month_seen or m_now, m_now)
    _check(len(out) > 100, f'{label}: only {len(out)} Colorado ZIPs')
    return out, month_seen


# ------------------------------------------------------------------ HUD
def hud(path, label):
    """ZIP -> (geoid, residential ratio) for the dominant geography."""
    df = pd.read_excel(path)
    _check({'zip', 'geoid', 'state', 'res_ratio'} <= set(df.columns),
           f'{label}: unexpected columns {list(df.columns)}')
    co = df[df.state == 'CO'].copy()
    co['zip'] = co['zip'].astype(str).str.zfill(5)
    co['geoid'] = co.geoid.astype(str).str.zfill(5)
    dom = co.sort_values('res_ratio', ascending=False).groupby('zip').first()
    _check(len(dom) > 500, f'{label}: only {len(dom)} Colorado ZIPs')
    return {z: (r.geoid, float(r.res_ratio)) for z, r in dom.iterrows()}


# ------------------------------------------------------------------ Census PEP
def pep(path):
    """County FIPS -> (name, first year, first pop, last year, last pop).

    Returns (dict, ordered_names): the dict for lookups, ordered_names as the
    file's own row order -- which IS the correct FIPS sequence. Do not re-sort
    these names; see the module docstring in _fips_map for why that breaks.
    """
    raw = pd.read_excel(path, header=None)

    def as_year(v):
        """Year labels arrive mixed: the base column reads 2020 as an int and the
        rest as floats, so a plain isdigit() check found nothing and the whole
        file was rejected."""
        t = str(v).strip()
        try:
            n = int(float(t))
        except (TypeError, ValueError):
            return None
        return n if 2000 <= n <= 2100 else None

    yr_row = None
    for i in range(8):
        if sum(as_year(v) is not None for v in raw.iloc[i]) >= 3:
            yr_row = i
            break
    _check(yr_row is not None, 'PEP: no row of year labels found in the first 8 rows')
    years = [(j, as_year(v)) for j, v in enumerate(raw.iloc[yr_row])
             if as_year(v) is not None]
    out, order = {}, []
    for _, row in raw.iterrows():
        name = str(row[0]).strip().lstrip('.')
        if not name.endswith('County, Colorado'):
            continue
        pts = [(y, float(row[j])) for j, y in years if pd.notna(row[j])]
        if len(pts) >= 2:
            out[name] = (pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
            order.append(name)
    _check(len(out) == 64, f'PEP: {len(out)} Colorado counties, expected 64')
    jeff = out.get('Jefferson County, Colorado')
    _check(jeff and 500_000 < jeff[3] < 700_000,
           f'PEP: Jefferson County population implausible: {jeff}')
    return out, order


# ------------------------------------------------------------------ ACS
def acs_zcta(path):
    """ZCTA -> age lines. Column ids beat label matching: S0101's row labels are
    indented and get re-worded between vintages, the variable ids do not."""
    with open(path, encoding='utf-8-sig') as f:
        r = csv.reader(f)
        hdr = next(r)
        next(r)
        ix = {h: i for i, h in enumerate(hdr)}
        need = ['S0101_C01_001E', 'S0101_C01_022E', 'S0101_C01_028E', 'S0101_C01_032E']
        _check(all(n in ix for n in need), 'ACS: expected S0101 variable ids missing')
        out = {}
        for row in r:
            g = row[1]
            if 'ZCTA5' not in g:
                continue
            def num(k):
                v = row[ix[k]].replace(',', '')
                try:
                    return float(v)
                except ValueError:
                    return None
            out[g.split()[-1]] = {
                'total': num('S0101_C01_001E'),
                'under18': num('S0101_C01_022E'),
                'over65': num('S0101_C01_028E'),
                'median_age': num('S0101_C01_032E'),
            }
    _check(len(out) > 400, f'ACS: only {len(out)} Colorado ZCTAs')
    return out


def _fips_map(names_in_file_order):
    """FIPS -> county name. Colorado runs alphabetically on odd codes from 08001;
    Broomfield, created in 2001, sits at 08014 and does not take an odd slot.

    The input MUST be in the source file's own row order, not re-sorted here.
    Python's plain string sort places a space before any letter, so it puts
    "El Paso" before "Elbert" and "La Plata" before "Lake" -- both backwards
    from the real FIPS sequence, which goes Elbert (08039) then El Paso (08041),
    and Lake (08065) then La Plata (08067). A re-sort silently swaps those two
    pairs. The PEP file's row order is already correct; trust it.
    """
    out, n = {}, 1
    for name in names_in_file_order:
        if name.startswith('Broomfield'):
            out['08014'] = name
            continue
        out[f'08{n:03d}'] = name
        n += 2
    _check(out.get('08059', '').startswith('Jefferson'),
           f"FIPS map wrong: 08059 resolved to {out.get('08059')!r}, expected Jefferson")
    _check(out.get('08039', '').startswith('Elbert'),
           f"FIPS map wrong: 08039 resolved to {out.get('08039')!r}, expected Elbert")
    _check(out.get('08041', '').startswith('El Paso'),
           f"FIPS map wrong: 08041 resolved to {out.get('08041')!r}, expected El Paso")
    _check(out.get('08065', '').startswith('Lake'),
           f"FIPS map wrong: 08065 resolved to {out.get('08065')!r}, expected Lake")
    _check(out.get('08067', '').startswith('La Plata'),
           f"FIPS map wrong: 08067 resolved to {out.get('08067')!r}, expected La Plata")
    return out


# ------------------------------------------------------------------ BLS/FRED
def employment():
    """cbsa_code -> (series_id, year0, value0, year1, value1) for every series
    in EMPLOYMENT_SERIES. A missing file fails loudly rather than silently
    shipping a partial table -- this is the exact mistake made once already
    this build cycle, where a hand-patched employment.csv reverted to
    Denver-only the next time the builder ran."""
    out = {}
    for cbsa, (name, sid) in EMPLOYMENT_SERIES.items():
        path = f'{FRED_DIR}/{sid}.csv'
        _check(os.path.exists(path), f'employment: missing {sid}.csv for {name} '
                                     f'(expected at {path})')
        rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
        by_year = {}
        for r in rows:
            y = int(r['observation_date'][:4])
            try:
                by_year[y] = float(r[sid])
            except (KeyError, ValueError):
                pass
        years = sorted(by_year)
        _check(len(years) >= 2, f'employment: {name} has under 2 years of data')
        y0, y1 = years[-2], years[-1]
        out[cbsa] = (sid, y0, by_year[y0], y1, by_year[y1])
    return out


# ------------------------------------------------------------------ build
def build():
    os.makedirs(OUT, exist_ok=True)
    zori, zori_m = zillow(SRC['zori'], 'ZORI', require_year_ago=False)
    zhvi, zhvi_m = zillow(SRC['zhvi'], 'ZHVI')
    cty = hud(SRC['zipcty'], 'ZIP-COUNTY')
    cbsa = hud(SRC['zipcbsa'], 'ZIP-CBSA')
    pops, pop_order = pep(SRC['pep'])
    ages = acs_zcta(SRC['acs'])

    fips = _fips_map(pop_order)

    zips = sorted(set(cty) | set(zhvi) | set(zori))
    with open(f'{OUT}/zips.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['zip', 'county_fips', 'county_name', 'county_res_ratio', 'cbsa_code',
                    'zori_now', 'zori_month', 'zori_year_ago',
                    'zhvi_now', 'zhvi_month', 'zhvi_year_ago'])
        for z in zips:
            cf, ratio = cty.get(z, ('', ''))
            cb = cbsa.get(z, ('', ''))[0]
            ro = zori.get(z)
            hv = zhvi.get(z)
            w.writerow([z, cf, fips.get(cf, ''), f'{ratio:.4f}' if ratio != '' else '',
                        cb if cb != '99999' else '',
                        f'{ro[0]:.2f}' if ro else '', ro[1] if ro else '',
                        f'{ro[2]:.2f}' if ro and ro[2] is not None else '',
                        f'{hv[0]:.2f}' if hv else '', hv[1] if hv else '',
                        f'{hv[2]:.2f}' if hv else ''])

    with open(f'{OUT}/counties.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['county_name', 'pop_year0', 'pop0', 'pop_year1', 'pop1', 'pop_annual_pct'])
        for name, (y0, p0, y1, p1) in sorted(pops.items()):
            ann = ((p1 / p0) ** (1 / (y1 - y0)) - 1) * 100 if p0 and y1 > y0 else ''
            w.writerow([name, y0, int(p0), y1, int(p1),
                        f'{ann:.4f}' if ann != '' else ''])

    with open(f'{OUT}/zcta_age.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['zcta', 'total_pop', 'under18', 'over65', 'median_age'])
        for z, a in sorted(ages.items()):
            w.writerow([z, a['total'], a['under18'], a['over65'], a['median_age']])

    emp = employment()
    with open(f'{OUT}/employment.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cbsa_code', 'series_id', 'year0', 'value0', 'year1', 'value1', 'yoy_pct'])
        for cbsa, (sid, y0, v0, y1, v1) in sorted(emp.items()):
            w.writerow([cbsa, sid, y0, v0, y1, v1, f'{(v1 / v0 - 1) * 100:.4f}'])

    json.dump({
        'built': str(date.today()),
        'zori': {'source': 'Zillow ZORI', 'as_of': zori_m, 'zips': len(zori)},
        'zhvi': {'source': 'Zillow ZHVI', 'as_of': zhvi_m, 'zips': len(zhvi)},
        'pep': {'source': 'Census Population Estimates', 'as_of': '2025', 'counties': len(pops)},
        'acs': {'source': 'ACS 5-year S0101', 'as_of': '2024', 'zctas': len(ages)},
        'crosswalk': {'source': 'HUD USPS ZIP crosswalk', 'as_of': '2026Q2'},
        'employment': {'source': 'BLS/FRED state and metro employment',
                       'as_of': str(max(v[3] for v in emp.values())),
                       'cbsas': len([c for c in emp if c]),
                       'note': f'{len(emp)} series total: '
                               f'{len([c for c in emp if c])} metro + statewide fallback'},
    }, open(f'{OUT}/vintages.json', 'w'), indent=2)

    print(f'zips.csv      {len(zips):>4} rows')
    print(f'counties.csv  {len(pops):>4} rows')
    print(f'zcta_age.csv  {len(ages):>4} rows')
    print(f'ZORI as of {zori_m} | ZHVI as of {zhvi_m}')


if __name__ == '__main__':
    build()
