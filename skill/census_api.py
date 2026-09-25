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
}


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
    if out['population'] is not None:
        out['population'] = int(out['population'])
    for k in ('median_hh_income', 'median_home_value'):
        if out[k] is not None:
            out[k] = int(out[k])

    if all(v is None for v in out.values()):
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
