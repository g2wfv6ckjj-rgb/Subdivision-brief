"""Investor Score -- rent yield, appreciation, and population/employment
growth, blended into one disclosed 0-100 score.

WHY THIS EXISTS SEPARATELY FROM PRICING POWER OR CHANCE OF SELLING
--------------------------------------------------------------------
Every other score in this report is computed entirely from the MLS export.
This one cannot be: rent, long-run appreciation, and population/employment
growth are not in a subdivision activity file at any geography. This module
pulls from public, free, no-key sources instead, the same architectural
pattern as enrich.py (schools) and demographics.py (Census) -- best-effort,
cached, gated at the fetch layer, and never blocking a build.

GEOGRAPHY IS BLENDED OUT OF NECESSITY, AND THAT IS DISCLOSED EVERY TIME
--------------------------------------------------------------------------
Rent and home value are ZIP-level (Zillow ZORI / ZHVI). Appreciation trend is
also ZIP-level when available, city-level otherwise. Population growth is
city-level (Census Population Estimates Program). Employment growth is
metro-level (BLS nonfarm payrolls) and OPTIONAL -- there is no bundled
ZIP-to-metro crosswalk in this module, so a caller supplies metro employment
growth directly (a single YoY percentage plus a label) when they have it.
Without it, the growth sub-score falls back to population alone, disclosed as
such rather than silently averaging in a placeholder.

Every rendered section states which geography each number actually describes.
Papering over "ZIP" vs "city" vs "metro" behind one tidy label would be a
false-precision problem of exactly the kind this skill exists to avoid.

WHAT IS AND ISN'T VERIFIED
-----------------------------
The ZORI/ZHVI fetch functions below talk to Zillow's public data downloads.
This sandbox's network allowlist does not include zillow.com, so -- the same
disclosed limitation as enrich.py's NCES/Places calls and demographics.py's
Census calls -- the live path is untested end-to-end here. `manual_profile()`
exists for exactly this situation: construct a profile from figures a person
already sourced and verified by hand (with citations), rather than blocking on
an unverified live call. Anything built with `manual_profile()` should say so
in the byline, and the values behind it should be checked against the primary
source (Zillow Research's own files, not a secondary aggregator) before this
goes in front of a client.

ANCHORS ARE THIS SKILL'S OWN CONVENTION
------------------------------------------
2%-8% gross yield, -5%-10% for appreciation and for growth: reasonable
starting guesses, printed on every render exactly like Pricing Power's 90%-
105% anchors, and just as much a target for a second opinion before this is
treated as authoritative.
"""
import json
import os
import time
import urllib.error
import urllib.request

UA = 'subdivision-brief/2.8 (real estate market report generator)'
ZORI_URL = 'https://files.zillowstatic.com/research/public_csv/zori/Zip_zori_uc_sfrcondomfr_sm_sa_month.csv'
ZHVI_URL = 'https://files.zillowstatic.com/research/public_csv/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv'
CACHE_TTL = 30 * 24 * 3600   # 30 days; these series update monthly at most


class InvestorError(Exception):
    pass


def scale(v, lo, hi):
    """Map a raw rate onto 0-100, clamped. Same helper shape as optimal.py and
    callout_cards.py so every scored module in this skill reads the same way."""
    if v is None or v != v:
        return None
    if hi == lo:
        return 0.0
    return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))


class _Cache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _p(self, key):
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in key)
        return os.path.join(self.root, f'{safe}.json')

    def get(self, key, ttl=CACHE_TTL):
        p = self._p(key)
        if not os.path.exists(p) or time.time() - os.path.getmtime(p) > ttl:
            return None
        try:
            with open(p) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def put(self, key, value):
        try:
            with open(self._p(key), 'w') as f:
                json.dump(value, f)
        except OSError:
            pass


def _fetch_csv_row(url, zip5, timeout=25):
    """Stream a Zillow research CSV looking for one ZIP's row. These files run
    tens of MB, so this reads line by line rather than loading the whole file.
    Untested live in this sandbox -- see module docstring."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            header = r.readline().decode('utf-8', 'replace').strip().split(',')
            if 'RegionName' not in header:
                raise InvestorError('Unexpected CSV shape from Zillow research file.')
            zi = header.index('RegionName')
            for line in r:
                row = line.decode('utf-8', 'replace').strip().split(',')
                if len(row) > zi and row[zi] == str(zip5):
                    return dict(zip(header, row))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise InvestorError(f'Zillow research fetch failed: {exc}') from exc
    return None


def _latest_two(row, header_order):
    """Last two non-empty monthly columns in a Zillow wide-format row, oldest
    first, for a simple most-recent-vs-a-year-ago comparison."""
    vals = []
    for col in header_order:
        v = row.get(col, '')
        if v not in ('', None):
            try:
                vals.append((col, float(v)))
            except ValueError:
                continue
    return vals[-13:] if len(vals) >= 13 else vals  # ~12 months back for YoY


def fetch_zori(zip5, cache=None):
    key = f'zori-{zip5}'
    if cache:
        hit = cache.get(key)
        if hit is not None:
            return hit
    row = _fetch_csv_row(ZORI_URL, zip5)
    if row is None:
        raise InvestorError(f'ZIP {zip5} not found in the ZORI file (too small a rental market to publish).')
    months = [k for k in row if k[:2].isdigit() is False and '-' in k]
    series = _latest_two(row, sorted(months))
    if len(series) < 2:
        raise InvestorError(f'ZORI series for {zip5} too short to read.')
    result = dict(current=series[-1][1], month=series[-1][0], year_ago=series[0][1] if len(series) >= 12 else None)
    if cache:
        cache.put(key, result)
    return result


def fetch_zhvi(zip5, cache=None):
    key = f'zhvi-{zip5}'
    if cache:
        hit = cache.get(key)
        if hit is not None:
            return hit
    row = _fetch_csv_row(ZHVI_URL, zip5)
    if row is None:
        raise InvestorError(f'ZIP {zip5} not found in the ZHVI file.')
    months = [k for k in row if '-' in k]
    series = _latest_two(row, sorted(months))
    if len(series) < 2:
        raise InvestorError(f'ZHVI series for {zip5} too short to read.')
    result = dict(current=series[-1][1], month=series[-1][0],
                 year_ago=series[0][1] if len(series) >= 12 else None)
    if cache:
        cache.put(key, result)
    return result


def fetch_zori_local(path, zip5):
    """Same row-scan as fetch_zori(), pointed at a CSV the person downloaded
    themselves from zillow.com/research/data (Rentals > ZORI > Zip Code) and
    uploaded, rather than a URL this sandbox can't reach. This is the
    supported path today -- see module docstring."""
    return _read_local_series(path, zip5)


def fetch_zhvi_local(path, zip5):
    """Same as fetch_zori_local(), for a ZHVI export (Home Values > ZHVI, All
    Homes SFR/Condo, Smoothed & Seasonally Adjusted > Zip Code)."""
    return _read_local_series(path, zip5)


def _read_local_series(path, zip5):
    if not os.path.exists(path):
        raise InvestorError(f'{path} does not exist.')
    with open(path, encoding='utf-8-sig') as f:
        header = f.readline().strip().split(',')
        if 'RegionName' not in header:
            raise InvestorError(f'{path}: no RegionName column -- is this a Zillow research export?')
        zi = header.index('RegionName')
        months = sorted(c for c in header if '-' in c)
        for line in f:
            row = line.rstrip('\n').split(',')
            if len(row) > zi and row[zi].lstrip('0') == str(zip5).lstrip('0'):
                d = dict(zip(header, row))
                series = _latest_two(d, months)
                if len(series) < 2:
                    raise InvestorError(f'ZIP {zip5} found but its series is too short to read.')
                return dict(current=series[-1][1], month=series[-1][0],
                           year_ago=series[0][1] if len(series) >= 12 else None,
                           n_months=len(series))
    raise InvestorError(f'ZIP {zip5} not found in {os.path.basename(path)}.')


def fetch_population_local(path, city, state):
    """Read a Census PEP 'Incorporated Places' file (SUB-IP-EST20XX-POP,
    downloaded from census.gov/data/tables/time-series/demo/popest and
    uploaded) and return the named city's population for every year present.

    Column names in Census PEP files vary by vintage (POPESTIMATE2020 vs
    POPESTIMATE_2020, etc.) and the file ships as CSV or XLSX depending on
    which button was clicked -- this reads either, and matches columns by
    pattern (a 4-digit year found in the header) rather than an exact name,
    the same defensive-parsing approach as enrich.py's CDE column matching.
    Matching a city name is fuzzy on purpose: PEP rows are typically named
    like "Littleton city, Colorado", not just "Littleton" -- this strips
    the geography-type suffix and compares case-insensitively.
    """
    if not os.path.exists(path):
        raise InvestorError(f'{path} does not exist.')

    def _norm_city(s):
        s = str(s).lower().strip()
        # State-level PEP files put the whole label in one column -- "Littleton
        # city, Colorado" -- while the national file splits the state into
        # STNAME. Drop anything after the first comma so the suffix strip below
        # still sees a bare "littleton city" in both layouts.
        s = s.split(',')[0].strip()
        for suf in (' city', ' town', ' village', ' borough', ' municipality', ' cdp'):
            if s.endswith(suf):
                s = s[:-len(suf)]
        return s.strip()

    import re

    ext = os.path.splitext(path)[1].lower()
    if ext in ('.xlsx', '.xls'):
        try:
            import pandas as pd
        except ImportError as exc:
            raise InvestorError('Reading an .xlsx PEP file needs pandas; re-download as CSV instead.') from exc
        df = pd.read_excel(path)
        header = list(df.columns)
        rows_iter = (dict(zip(header, r)) for r in df.itertuples(index=False, name=None))
    else:
        import csv
        raw = open(path, 'rb').read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Census place names occasionally carry Latin-1 bytes (e.g.
            # "Ca\xf1on City") in an otherwise-UTF-8 file. Falling back
            # rather than crashing on one accented place name.
            text = raw.decode('latin-1')
        reader = csv.reader(text.splitlines())
        header = next(reader)
        rows_iter = [{header[i]: v for i, v in enumerate(row) if i < len(header)} for row in reader]

    # The state-level SUB-IP files (e.g. SUB-IP-EST2025-POP-08.xlsx) carry two
    # title rows, then a SPLIT header: "Geographic Area" and the estimates-base
    # label sit on one row while the year numbers sit on the next. Neither row
    # alone looks like a header, so the single-row match below found no NAME
    # column and no year columns and the file was rejected outright. Rebuild a
    # flat header from the first rows when that happens, before the normal match.
    if not any(re.search(r'20\d{2}', str(c)) for c in header):
        probe = rows_iter if isinstance(rows_iter, list) else list(rows_iter)
        flat, yr_row = None, None
        for i, row in enumerate(probe[:8]):
            vals = [str(v).strip() for v in row.values()]
            if sum(bool(re.fullmatch(r'20\d{2}', v)) for v in vals) >= 3:
                yr_row = i
                flat = ['NAME' if j == 0 else (f'POPESTIMATE{v}' if re.fullmatch(r'20\d{2}', v)
                        else f'col{j}') for j, v in enumerate(vals)]
                break
        if flat:
            keys = list(header)
            header = flat
            rows_iter = [{flat[j]: r.get(keys[j]) for j in range(min(len(flat), len(keys)))}
                         for r in probe[yr_row + 1:]]

    name_col = next((c for c in header if c.strip().upper() in ('NAME', 'CTYNAME')), None)
    state_col = next((c for c in header if c.strip().upper() in ('STNAME', 'STATE_NAME')), None)
    year_cols = {}
    for c in header:
        m = re.search(r'(20\d{2})', c)
        if m and ('POP' in c.upper() or 'EST' in c.upper()):
            year_cols[int(m.group(1))] = c
    if name_col is None or not year_cols:
        raise InvestorError(f'{os.path.basename(path)}: could not find a NAME column and '
                           f'year-labeled population columns -- is this the SUB-IP-EST POP file?')

    target = _norm_city(city)
    for row in rows_iter:
        if _norm_city(row.get(name_col, '')) != target:
            continue
        if state_col and state.lower() not in str(row.get(state_col, '')).lower():
            continue
        out = {}
        for yr, col in sorted(year_cols.items()):
            try:
                out[yr] = float(str(row[col]).replace(',', ''))
            except (ValueError, TypeError):
                continue
        if len(out) < 2:
            raise InvestorError(f'Found {city} but fewer than 2 years of population data.')
        return out
    raise InvestorError(f'"{city}, {state}" not found in {os.path.basename(path)}. '
                       f'PEP rows are usually named like "Littleton city, Colorado" -- '
                       f'check the exact spelling in the file if this keeps failing.')


def population_growth_from_local(path, city, state):
    """years -> (growth_4yr_pct, geo_label, first_year, last_year, first_pop, last_pop)."""
    series = fetch_population_local(path, city, state)
    years = sorted(series)
    first, last = years[0], years[-1]
    p0, p1 = series[first], series[last]
    growth = (p1 - p0) / p0 * 100 if p0 else None
    span = last - first
    geo = f'{city} city, {first}&ndash;{last} (U.S. Census Bureau Population Estimates Program, primary source)'
    return growth, geo, first, last, p0, p1


def enrich_from_local_files(zip5, zori_path, zhvi_path, pop_growth_4yr=None, pop_geo=None,
                            metro_emp_yoy=None, metro_emp_geo=None, metro_unemployment=None,
                            sources=None, pop_years=4):
    """The real, verifiable path once ZORI/ZHVI CSVs have been downloaded from
    Zillow directly and uploaded. Reads both LIVE from the person's own
    primary-source files -- no secondary aggregator, no network call this
    sandbox can't make. Returns (profile_or_None, warnings), same contract as
    enrich(): never raises past this point.
    """
    warn = []
    try:
        zori = fetch_zori_local(zori_path, zip5)
        rent_month = zori['current']
    except InvestorError as exc:
        return None, [str(exc)]

    zhvi_current = apprec_yoy = apprec_geo = None
    try:
        zhvi = fetch_zhvi_local(zhvi_path, zip5)
        zhvi_current = zhvi['current']
        if zhvi.get('year_ago') is not None:
            apprec_yoy = (zhvi_current - zhvi['year_ago']) / zhvi['year_ago'] * 100
            apprec_geo = f'ZIP {zip5}'
    except InvestorError as exc:
        warn.append(str(exc))

    if apprec_yoy is None:
        warn.append('ZIP-level appreciation unavailable from the uploaded ZHVI file for this ZIP '
                   '(fewer than 12 months of history in the export). Supply a city-level fallback '
                   'via apprec_yoy/apprec_geo if needed.')

    gross_yield = (rent_month * 12) / zhvi_current * 100 if zhvi_current else None
    src_list = list(sources or [])
    src_list.append(f'Rent: Zillow Observed Rent Index, ZIP {zip5}, {zori["month"]}, from a ZORI CSV '
                    f'downloaded directly from zillow.com/research/data and read locally -- primary source.')
    if zhvi_current is not None:
        src_list.append(f'Home value / appreciation: Zillow Home Value Index, ZIP {zip5}, {zhvi["month"]}, '
                        f'from a ZHVI CSV downloaded directly from zillow.com/research/data -- primary source.')

    prof = score(zip5=zip5, rent_month=rent_month, zhvi_current=zhvi_current, gross_yield=gross_yield,
                apprec_yoy=apprec_yoy, apprec_geo=apprec_geo,
                pop_growth_4yr=pop_growth_4yr, pop_geo=pop_geo, pop_years=pop_years,
                emp_yoy=metro_emp_yoy, emp_geo=metro_emp_geo, emp_unemployment=metro_unemployment,
                sources=src_list, live=True)
    return prof, warn


def manual_profile(zip5, geo_labels, rent_month, zhvi_current, apprec_yoy, apprec_geo,
                   pop_growth_4yr, pop_geo, emp_yoy=None, emp_geo=None, emp_unemployment=None,
                   sources=None, pop_years=4):
    """Build a profile from figures a person has already sourced and verified
    by hand, rather than blocking on a live fetch this sandbox can't test.
    `sources` is a list of citation strings printed verbatim in the report.

    pop_years: how many years the pop_growth_4yr figure actually spans -- the
    name is legacy from this module's first version, which only ever saw
    4-year PEP windows; a 5-year window (e.g. 2020-2025) needs pop_years=5 or
    the annualized rate below is wrong. Always pass the real span.

    Nothing here is invented -- every field is exactly what the caller passes
    in. This function's only job is the scoring arithmetic and the disclosed
    geography bookkeeping, identical to what the live-fetch path would do.
    """
    gross_yield = (rent_month * 12) / zhvi_current * 100 if zhvi_current else None
    return score(
        zip5=zip5, rent_month=rent_month, zhvi_current=zhvi_current, gross_yield=gross_yield,
        apprec_yoy=apprec_yoy, apprec_geo=apprec_geo, pop_growth_4yr=pop_growth_4yr, pop_geo=pop_geo,
        emp_yoy=emp_yoy, emp_geo=emp_geo, emp_unemployment=emp_unemployment,
        sources=sources or [], live=False, pop_years=pop_years,
    )


def score(zip5, rent_month, zhvi_current, gross_yield, apprec_yoy, apprec_geo,
         pop_growth_4yr, pop_geo, emp_yoy=None, emp_geo=None, emp_unemployment=None,
         sources=None, live=True, pop_years=4):
    """The scoring arithmetic, shared by the live-fetch path and
    manual_profile(). Anchors: rule -- see module docstring.

    pop_years: actual number of years pop_growth_4yr spans (see
    manual_profile() docstring) -- do not assume 4 for a PEP file that now
    covers 2020-2025 (5 years) or any other span.
    """
    pop_annualized = (((1 + pop_growth_4yr / 100) ** (1 / pop_years) - 1) * 100
                      if pop_growth_4yr is not None else None)

    rent_sub = scale(gross_yield, 2.0, 8.0)
    apprec_sub = scale(apprec_yoy, -5.0, 10.0)
    pop_sub = scale(pop_annualized, -5.0, 10.0)
    emp_sub = scale(emp_yoy, -5.0, 10.0) if emp_yoy is not None else None

    if emp_sub is not None:
        growth_sub = (pop_sub + emp_sub) / 2
        growth_note = 'population and employment growth, averaged'
    else:
        growth_sub = pop_sub
        growth_note = 'population growth only -- no metro employment figure was supplied for this run'

    parts = [p for p in (rent_sub, apprec_sub, growth_sub) if p is not None]
    overall = round(sum(parts) / len(parts)) if parts else None

    return dict(
        zip5=zip5, live=live, sources=sources or [],
        rent_month=rent_month, zhvi_current=zhvi_current, gross_yield=gross_yield, rent_sub=rent_sub,
        apprec_yoy=apprec_yoy, apprec_geo=apprec_geo, apprec_sub=apprec_sub,
        pop_growth_4yr=pop_growth_4yr, pop_years=pop_years, pop_annualized=pop_annualized,
        pop_geo=pop_geo, pop_sub=pop_sub,
        emp_yoy=emp_yoy, emp_geo=emp_geo, emp_unemployment=emp_unemployment, emp_sub=emp_sub,
        growth_sub=growth_sub, growth_note=growth_note, overall=overall,
    )


def enrich(zip5, apprec_geo_fallback='city', metro_emp_yoy=None, metro_emp_geo=None,
          metro_unemployment=None, cache_dir='/tmp/brief-cache', pop_growth_4yr=None,
          pop_geo=None, sources=None):
    """Best-effort live path: fetch ZORI and ZHVI for one ZIP, combine with a
    caller-supplied population figure (population growth has no bundled fetch
    here -- see demographics.py, which already resolves a Census geography for
    the same run and is the natural place to source this from) and an
    optional metro employment figure. Returns (profile_or_None, warnings).
    Never raises -- a market report must not fail to build over a rent index
    being slow or a ZIP too small to publish.
    """
    warn = []
    cache = _Cache(cache_dir)
    try:
        zori = fetch_zori(zip5, cache)
        rent_month = zori['current']
    except InvestorError as exc:
        return None, [str(exc)]

    try:
        zhvi = fetch_zhvi(zip5, cache)
        zhvi_current = zhvi['current']
        apprec_yoy = (None if zhvi.get('year_ago') is None else
                     (zhvi_current - zhvi['year_ago']) / zhvi['year_ago'] * 100)
        apprec_geo = 'ZIP ' + str(zip5) if zhvi.get('year_ago') is not None else None
    except InvestorError as exc:
        warn.append(str(exc))
        zhvi_current = apprec_yoy = apprec_geo = None

    if zhvi_current is None or apprec_yoy is None:
        warn.append('Appreciation could not be computed from the ZIP-level series; '
                    'supply a city-level fallback via pop_geo/apprec_geo_fallback if available.')

    gross_yield = (rent_month * 12) / zhvi_current * 100 if zhvi_current else None

    prof = score(zip5=zip5, rent_month=rent_month, zhvi_current=zhvi_current, gross_yield=gross_yield,
                apprec_yoy=apprec_yoy, apprec_geo=apprec_geo,
                pop_growth_4yr=pop_growth_4yr, pop_geo=pop_geo,
                emp_yoy=metro_emp_yoy, emp_geo=metro_emp_geo, emp_unemployment=metro_unemployment,
                sources=sources or [], live=True)
    return prof, warn
