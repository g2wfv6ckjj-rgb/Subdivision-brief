"""Census ACS 5-year demographics for one ZIP, fetched live at report time.

Runs server-side with CENSUS_API_KEY from the environment. This sandbox's
proxy blocks api.census.gov (403), so the live call has NOT been exercised
here; the parser is tested against a synthetic payload built to the Census
API's documented response shape (a JSON array whose first row is the header).
The first real report on Render is the live test -- see rule 74.

Detailed tables (B-prefix), not subject tables: detailed tables publish at
the ZCTA level reliably, and each variable below is a single well-known
estimate, not a derived percentage.

ZCTA != ZIP. A ZCTA is the Census Bureau's area approximation of a ZIP; they
usually match, and the report labels the figure "ZCTA" to stay honest about it.
ACS 5-year estimates carry margins of error that can be wide for small ZCTAs.
"""
import os
from functools import lru_cache
from urllib.parse import quote

import requests

BASE = 'https://api.census.gov/data'
VINTAGES = ('2024', '2023')   # newest first; falls back if a vintage is missing
TIMEOUT = 20

VARS = {
    'B01003_001E': 'population',
    'B01002_001E': 'median_age',
    'B19013_001E': 'median_hh_income',
    'B25010_001E': 'avg_household_size',
    'B25077_001E': 'median_home_value',
    'B25003_001E': 'occupied_units',
    'B25003_002E': 'owner_occupied_units',
    'B25064_001E': 'median_gross_rent',
    'B19113_001E': 'median_family_income',
    'B11001_001E': 'households',
    'B11001_002E': 'family_households',
    # Median household income by age of householder (B19049)
    'B19049_002E': 'inc_age_u25',
    'B19049_003E': 'inc_age_25_44',
    'B19049_004E': 'inc_age_45_64',
    'B19049_005E': 'inc_age_65p',
    # Owner-occupied units by age of householder (B25007, owner rows)
    'B25007_003E': 'own_15_24', 'B25007_004E': 'own_25_34', 'B25007_005E': 'own_35_44',
    'B25007_006E': 'own_45_54', 'B25007_007E': 'own_55_59', 'B25007_008E': 'own_60_64',
    'B25007_009E': 'own_65_74', 'B25007_010E': 'own_75_84', 'B25007_011E': 'own_85p',
}

INCOME_BY_AGE = [('under 25', 'inc_age_u25'), ('25-44', 'inc_age_25_44'),
                 ('45-64', 'inc_age_45_64'), ('65+', 'inc_age_65p')]
OWNER_AGE_BANDS = [('15-24', 'own_15_24'), ('25-34', 'own_25_34'), ('35-44', 'own_35_44'),
                   ('45-54', 'own_45_54'), ('55-59', 'own_55_59'), ('60-64', 'own_60_64'),
                   ('65-74', 'own_65_74'), ('75-84', 'own_75_84'), ('85+', 'own_85p')]


class CensusAPIError(Exception):
    """Any Census-side failure. Callers omit the section rather than fail
    the whole report -- area demographics are context, not the core."""


def _key():
    k = os.environ.get('CENSUS_API_KEY')
    if not k:
        raise CensusAPIError('CENSUS_API_KEY is not set in the environment.')
    return k


def _to_num(s):
    """Census returns strings; suppressed or unavailable estimates come back
    as large negative sentinels (-666666666, -999999999, ...) or null. Those
    become None -- never zero, never a guess."""
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return None if v < 0 else v


def parse(payload, zcta, vintage):
    """Turn the Census API's [header, row] array into the dict the report uses."""
    if not isinstance(payload, list) or len(payload) < 2:
        raise CensusAPIError(f'No ACS data for ZCTA {zcta}.')
    header, row = payload[0], payload[1]
    raw = dict(zip(header, row))
    out = {name: _to_num(raw.get(var)) for var, name in VARS.items()}

    occ, own = out.pop('occupied_units'), out.pop('owner_occupied_units')
    out['owner_pct'] = round(own / occ * 100, 1) if occ and own is not None else None

    hh, fam = out.pop('households'), out.pop('family_households')
    out['family_hh_pct'] = round(fam / hh * 100, 1) if hh and fam is not None else None

    out['income_by_age'] = [(label, int(out[k])) for label, k in INCOME_BY_AGE
                            if out.get(k) is not None]
    bands = [(label, out[k]) for label, k in OWNER_AGE_BANDS if out.get(k) is not None]
    owners = sum(v for _, v in bands)
    out['owner_age_bands'] = ([(label, round(v / owners * 100, 1)) for label, v in bands]
                              if owners else [])
    for _, k in INCOME_BY_AGE + OWNER_AGE_BANDS:
        out.pop(k, None)
    for k in ('median_gross_rent', 'median_family_income'):
        if out.get(k) is not None:
            out[k] = int(out[k])
    if out['population'] is not None:
        out['population'] = int(out['population'])
    for k in ('median_hh_income', 'median_home_value'):
        if out[k] is not None:
            out[k] = int(out[k])

    if all(v in (None, []) for v in out.values()):
        raise CensusAPIError(f'Every ACS estimate is suppressed for ZCTA {zcta}.')
    out['scope'] = f'ZCTA {zcta}'
    out['as_of'] = f'ACS 5-year {vintage}'
    out['source'] = 'U.S. Census Bureau, American Community Survey'
    return out


@lru_cache(maxsize=512)
def _fetch(zcta):
    key = _key()
    get = 'NAME,' + ','.join(VARS)
    geo = quote(f'zip code tabulation area:{zcta}')
    last_err = None
    for vintage in VINTAGES:
        url = f'{BASE}/{vintage}/acs/acs5?get={get}&for={geo}&key={quote(key)}'
        try:
            r = requests.get(url, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last_err = f'Could not reach the Census API: {exc}'
            continue
        if r.status_code == 204 or not r.text.strip():
            last_err = f'No ACS {vintage} data for ZCTA {zcta}.'
            continue
        if not r.ok:
            last_err = f'Census API returned {r.status_code} for {vintage}.'
            continue
        try:
            return vintage, r.json()
        except ValueError:
            # An invalid or unactivated key returns an HTML page, not JSON.
            last_err = 'Census API did not return JSON -- check the key is activated.'
    raise CensusAPIError(last_err or f'No ACS data for ZCTA {zcta}.')


def get_demographics(zip_code, _raw=None, _vintage='2024'):
    """_raw: a pre-fetched payload, for tests only. Real callers never pass it."""
    zcta = str(zip_code or '').strip()[:5].zfill(5)
    if _raw is not None:
        return parse(_raw, zcta, _vintage)
    vintage, payload = _fetch(zcta)
    return parse(payload, zcta, vintage)


# ---------------------------------------------------------------------------
# Occupation and industry mix (Data Profile DP03)
# ---------------------------------------------------------------------------
# DP03 variable NUMBERS have shifted between ACS releases, so they are never
# hard-coded. The group's own metadata (labels) is fetched once per vintage
# and variables are chosen by label -- a renumbering then changes which
# variable is read, never what the report calls it.

def pick_dp03(metadata):
    """From DP03 group metadata, return {var: (section, name)} for the
    top-level percent rows of the OCCUPATION and INDUSTRY sections."""
    picks = {}
    for var, meta in (metadata.get('variables') or {}).items():
        if not var.endswith('PE'):
            continue
        parts = [p.strip() for p in (meta.get('label') or '').split('!!')]
        if len(parts) != 4 or not parts[0].lower().startswith('percent'):
            continue
        section = parts[1].upper()
        if section in ('OCCUPATION', 'INDUSTRY'):
            picks[var] = (section.lower(), parts[3])
    return picks


def parse_careers(picks, payload, zcta, vintage):
    if not picks or not isinstance(payload, list) or len(payload) < 2:
        raise CensusAPIError(f'No occupation/industry data for ZCTA {zcta}.')
    raw = dict(zip(payload[0], payload[1]))
    out = {'occupation': [], 'industry': []}
    for var, (section, name) in picks.items():
        v = _to_num(raw.get(var))
        if v is not None:
            out[section].append((name, v))
    for k in out:
        out[k].sort(key=lambda x: x[1], reverse=True)
    if not out['occupation'] and not out['industry']:
        raise CensusAPIError(f'Occupation/industry estimates suppressed for ZCTA {zcta}.')
    out['scope'], out['as_of'] = f'ZCTA {zcta}', f'ACS 5-year {vintage} (DP03)'
    return out


@lru_cache(maxsize=4)
def _dp03_picks(vintage):
    r = requests.get(f'{BASE}/{vintage}/acs/acs5/profile/groups/DP03.json', timeout=TIMEOUT)
    if not r.ok:
        raise CensusAPIError(f'DP03 metadata unavailable for {vintage}.')
    return pick_dp03(r.json())


@lru_cache(maxsize=512)
def _fetch_careers(zcta):
    key = _key()
    last_err = None
    for vintage in VINTAGES:
        try:
            picks = _dp03_picks(vintage)
            if not picks:
                raise CensusAPIError('DP03 labels did not match the expected format.')
            geo = quote(f'zip code tabulation area:{zcta}')
            url = (f'{BASE}/{vintage}/acs/acs5/profile?get={",".join(picks)}'
                   f'&for={geo}&key={quote(key)}')
            r = requests.get(url, timeout=TIMEOUT)
            if r.ok and r.text.strip():
                return parse_careers(picks, r.json(), zcta, vintage)
            last_err = f'Census profile API returned {r.status_code} for {vintage}.'
        except (requests.RequestException, ValueError, CensusAPIError) as exc:
            last_err = str(exc)
    raise CensusAPIError(last_err or f'No DP03 data for ZCTA {zcta}.')


def get_careers(zip_code, _meta=None, _raw=None, _vintage='2024'):
    """Occupation groups and industries of employed residents, largest first.
    _meta/_raw: pre-fetched metadata and payload, for tests only."""
    zcta = str(zip_code or '').strip()[:5].zfill(5)
    if _raw is not None:
        return parse_careers(pick_dp03(_meta), _raw, zcta, _vintage)
    return _fetch_careers(zcta)
