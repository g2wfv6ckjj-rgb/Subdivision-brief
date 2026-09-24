"""Neighborhood demographics from the Census Bureau's American Community
Survey, agent skill only.

WHY THESE FOUR FIELDS AND NO OTHERS
-------------------------------------
median household income, median age, renter vs. owner-occupied share, and
bachelor's-degree-or-higher share. These four are the demographic set already
in common, unremarkable use on consumer real-estate sites (Redfin, Realtor.com
neighborhood pages) as neutral market context, not characterization of who
should or should not live somewhere.

CRIME DATA IS DELIBERATELY NOT INCLUDED. This was asked for and is deliberately
left out, on purpose, not by oversight:

  1. No reliable, free, subdivision- or even ZIP-level crime API exists.
     FBI NIBRS/UCR data is published at the reporting-AGENCY level (often a
     whole city or county police department), so a subdivision figure would
     have to be approximated or invented -- exactly the kind of manufactured
     precision this skill's own principles prohibit elsewhere (rule: flag
     when sample sizes don't support an analysis rather than producing
     spurious output).
  2. Crime statistics carry well-documented reliability and reporting-bias
     problems, and pairing them with a real estate report creates a Fair
     Housing steering risk that the other three fields do not: a "safety"
     framing on a neighborhood report is one of the clearest paths to
     discriminatory steering under the Fair Housing Act and Colorado Real
     Estate Commission advertising rules, given how strongly crime reporting
     correlates with the racial composition of a neighborhood rather than
     with actual risk.
  3. Every other characterization rule already in this skill points the same
     direction: no composite school scores, no neighborhood characterization
     in public content, no audience-targeting language. Crime data is the
     same category of risk at a higher stakes level.

If crime data is added later, that has to be a deliberate, informed decision
made with the client's compliance counsel, not a default in this module.

WHERE THIS RENDERS
-------------------
The private PDF report only -- never the social carousel, callout cards, or
any public-facing copy. That boundary already exists for schools (rule 19)
and applies here for the same reason, at higher stakes.

GEOGRAPHY FALLBACK
-------------------
ACS 5-year estimates do not exist at the subdivision level -- subdivisions are
not a Census geography at all. The chain here is: ZCTA (ZIP code tabulation
area, the closest Census equivalent to a ZIP) -> place (city) -> county,
using whichever is the smallest geography the Census Geocoder can resolve the
export's centroid into. The report always states which geography the numbers
actually describe -- "this ZIP code," not "this neighborhood" -- because that
distinction matters and papering over it would be a false precision problem
of exactly the kind this module exists to avoid.

NETWORK. This sandbox's egress allowlist does not include api.census.gov or
geocoding.geo.census.gov, so the live fetch path is untested end-to-end here,
the same limitation already disclosed for enrich.py's NCES/Places calls. The
parsing and fallback logic are tested against fixtures.
"""
import json
import os
import time
import urllib.error
import urllib.request

GEOCODER_URL = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
ACS_URL = 'https://api.census.gov/data/{year}/acs/acs5'
UA = 'subdivision-brief/2.5 (real estate market report generator)'

# ACS table/variable ids for the four allowed fields, 5-year estimates.
VARS = {
    'median_income': 'B19013_001E',
    'median_age': 'B01002_001E',
    'owner_occ': 'B25003_002E', 'renter_occ': 'B25003_003E', 'tenure_total': 'B25003_001E',
    'bachelor_plus': 'B15003_022E,B15003_023E,B15003_024E,B15003_025E',  # sum these
    'edu_total': 'B15003_001E',
}
FIELD_LIST = ','.join(sorted(set(','.join(VARS.values()).split(','))))

GEO_ORDER = [
    ('zip code tabulation area', 'ZCTA', 'this ZIP code'),
    ('place', 'Incorporated Places', 'this city'),
    ('county', 'County', 'this county'),
]


class DemoError(Exception):
    pass


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def resolve_geography(lat, lon):
    """Smallest Census geography containing (lat, lon), trying ZCTA then
    place then county. Returns (level_label, geo_name, fips_params) or raises
    DemoError if the geocoder itself is unreachable."""
    url = (f'{GEOCODER_URL}?x={lon}&y={lat}&benchmark=Public_AR_Current'
           f'&vintage=Current_Current&format=json')
    try:
        res = _get_json(url)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise DemoError(f'Census geocoder unreachable: {exc}') from exc
    geos = res.get('result', {}).get('geographies', {})
    for key, level_label, phrase in GEO_ORDER:
        for gkey, glist in geos.items():
            if key in gkey.lower() and glist:
                g = glist[0]
                return level_label, g.get('NAME', ''), phrase, g
    raise DemoError('Geocoder returned no ZCTA, place or county for this centroid.')


def fetch_acs(level_label, geo_fields, year=2023, api_key=None):
    """One ACS 5-year pull for the resolved geography. geo_fields carries the
    FIPS codes the geocoder returned (state/county/place/zcta as available)."""
    if level_label == 'ZCTA':
        geo = f'zip code tabulation area:{geo_fields.get("ZCTA5", geo_fields.get("BASENAME", ""))}'
    elif level_label == 'Incorporated Places':
        geo = f'place:{geo_fields.get("PLACE", "")}&in=state:{geo_fields.get("STATE", "")}'
    else:
        geo = f'county:{geo_fields.get("COUNTY", "")}&in=state:{geo_fields.get("STATE", "")}'
    url = f'{ACS_URL.format(year=year)}?get={FIELD_LIST}&for={geo}'
    if api_key:
        url += f'&key={api_key}'
    try:
        rows = _get_json(url)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise DemoError(f'ACS request failed: {exc}') from exc
    if len(rows) < 2:
        raise DemoError('ACS returned no data row for this geography.')
    header, vals = rows[0], rows[1]
    raw = dict(zip(header, vals))
    return raw


def _num(raw, key, default=None):
    try:
        v = float(raw.get(key))
        return None if v < 0 else v
    except (TypeError, ValueError):
        return default


def summarize(raw):
    """Raw ACS cell values -> the four report fields, with graceful handling
    of Census's negative sentinel codes for suppressed/unavailable cells."""
    income = _num(raw, VARS['median_income'])
    age = _num(raw, VARS['median_age'])
    own, rent, tot = _num(raw, VARS['owner_occ']), _num(raw, VARS['renter_occ']), _num(raw, VARS['tenure_total'])
    owner_pct = 100 * own / tot if own is not None and tot else None
    renter_pct = 100 * rent / tot if rent is not None and tot else None
    bach_cols = VARS['bachelor_plus'].split(',')
    bach_sum = sum(v for v in (_num(raw, c) for c in bach_cols) if v is not None)
    edu_tot = _num(raw, VARS['edu_total'])
    bach_pct = 100 * bach_sum / edu_tot if edu_tot else None
    return dict(median_income=income, median_age=age, owner_pct=owner_pct,
               renter_pct=renter_pct, bachelor_pct=bach_pct)


def enrich(lat, lon, year=2023, api_key=None):
    """Best-effort, never raises past this point -- returns (profile_or_None,
    warnings). A market report must not fail to build because the Census API
    was slow or the geocoder timed out."""
    warn = []
    try:
        level_label, geo_name, phrase, geo_fields = resolve_geography(lat, lon)
    except DemoError as exc:
        return None, [str(exc)]
    try:
        raw = fetch_acs(level_label, geo_fields, year=year, api_key=api_key)
    except DemoError as exc:
        return None, [str(exc)]
    stats = summarize(raw)
    return dict(level=level_label, geo_name=geo_name, phrase=phrase, year=year, **stats), warn
