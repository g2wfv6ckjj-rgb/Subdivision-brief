"""Automated schools and amenities enrichment, run at intake.

WHAT THIS REPLACES
------------------
`local.PROFILES` is a hand-keyed dictionary. Every new subdivision meant a manual
research pass, so most self-serve uploads rendered the "not yet compiled" state.
This module derives the same profile shape from the export itself plus public
data, and `PROFILES` becomes an OVERRIDE rather than the only source: a hand-built
entry still wins, because a human who has checked the boundaries beats a name
match every time.

NO GEOCODING STEP IS NEEDED. The MLS export carries Latitude/Longitude on every
row, so the subdivision centroid is a median of columns already in the file.

SOURCES AND WHY THESE ONES
--------------------------
Schools:
  * NCES Common Core of Data, via the Urban Institute Education Data API
    (educationdata.urban.org). Federal, free, no key, ODC-By licensed. Gives the
    directory record: NCES id, grade span, enrollment, student-teacher ratio,
    address, coordinates.
  * Colorado Department of Education School Performance Framework. The official
    state accountability rating, published as flat files. This is a named,
    citable, publisher-native rating, which is what rule 8 requires.

  GreatSchools 1-10, Niche and U.S. News are NOT fetched here. The GreatSchools
  1-10 ratings and assigned-school data sit behind their Enterprise Data License,
  and the self-serve NearbySchools API exposes only three coarse bands. Niche and
  U.S. News have no license path at all and scraping them breaches their terms.
  Where a hand-built PROFILES entry carries those ratings they still render --
  this module simply does not invent them.

Amenities:
  * Google Places Nearby Search (New). POST only, and a field mask is required.

WHAT MAY BE CACHED (this is a terms problem, not a performance one)
------------------------------------------------------------------
Google Maps Platform terms allow storing place IDs indefinitely and Places
coordinates for up to 30 days. Display names, addresses, ratings and photos have
no caching exception -- they must be requested live for each render. So the cache
here deliberately stores ONLY ids and coordinates, and `_scrub_place()` enforces
that on write rather than trusting the caller. Warehousing amenity names to save
API spend would be a licence breach, and it is the obvious shortcut to reach for.

Google Maps attribution must appear wherever this data is displayed.

FAIR HOUSING: FILTER AT THE FETCH LAYER, NOT AT RENDER
------------------------------------------------------
CCD and CDE files carry race, free-and-reduced-lunch and English-learner counts
in the same rows as the achievement data. Those are a steering vector and they
must never enter the pipeline at all. `SCHOOL_FIELDS` is an allowlist and
`_scrub_school()` drops everything else on ingest, so a blocked field cannot
reach a report, a share page or a cache file even by mistake. Filtering at render
would leave the data sitting in the cache waiting for the next careless join.
"""
import json
import math
import os
import time
import urllib.error
import urllib.request

import pandas as pd

UA = 'subdivision-brief/2.3 (real estate market report generator)'
EDU_API = 'https://educationdata.urban.org/api/v1/schools/ccd/directory'
PLACES_URL = 'https://places.googleapis.com/v1/places:searchNearby'

# Google terms: place id indefinitely, coordinates 30 days, nothing else.
PLACE_CACHE_TTL = 29 * 24 * 3600
SCHOOL_CACHE_TTL = 180 * 24 * 3600

# ---- allowlists ------------------------------------------------------------
SCHOOL_FIELDS = (
    'ncessch', 'school_name', 'lea_name', 'street_mailing', 'city_mailing',
    'state_mailing', 'zip_mailing', 'latitude', 'longitude', 'lowest_grade_offered',
    'highest_grade_offered', 'school_level', 'enrollment', 'teachers_fte',
    'charter', 'magnet', 'year',
)
CACHEABLE_PLACE_FIELDS = ('id', 'location')

# Present in the source files, deliberately never ingested. Named so the
# exclusion is a documented decision rather than an accident of which columns
# somebody happened to copy.
BLOCKED_FIELDS = (
    'race', 'sex', 'free_lunch', 'reduced_price_lunch', 'free_or_reduced_price_lunch',
    'lunch_program', 'direct_certification', 'english_language_learners', 'lep',
    'title_i_eligible', 'title_i_status', 'disability', 'idea', 'homeless',
    'migrant', 'foster_care', 'military_connected',
)

AMENITY_GROUPS = (
    ('Groceries', ('supermarket', 'grocery_store')),
    ('Parks and open space', ('park', 'hiking_area')),
    ('Coffee and dining', ('cafe', 'restaurant')),
    ('Fitness and recreation', ('gym', 'community_center')),
    ('Everyday errands', ('pharmacy', 'hardware_store')),
)


class EnrichError(Exception):
    """Enrichment failed. Never fatal -- the brief falls back to names only."""


# ---------------------------------------------------------------- geometry
def centroid(d):
    """Median lat/lon of the export. Median rather than mean so one mis-keyed
    coordinate cannot drag the search centre into the next county."""
    if 'Latitude' not in d or 'Longitude' not in d:
        raise EnrichError('Export carries no Latitude/Longitude columns.')
    lat = pd.to_numeric(d['Latitude'], errors='coerce').dropna()
    lon = pd.to_numeric(d['Longitude'], errors='coerce').dropna()
    if lat.empty or lon.empty:
        raise EnrichError('Latitude/Longitude columns are present but empty.')
    return float(lat.median()), float(lon.median())


def spread_m(d, lat0, lon0):
    """Radius in metres covering the listings, so the amenity search matches the
    footprint of the area rather than a fixed guess."""
    lat = pd.to_numeric(d['Latitude'], errors='coerce').dropna()
    lon = pd.to_numeric(d['Longitude'], errors='coerce').dropna()
    dy = (lat - lat0).abs().max() * 111_320
    dx = (lon - lon0).abs().max() * 111_320 * math.cos(math.radians(lat0))
    return float(max(1200.0, min(8000.0, math.hypot(dx, dy) + 1600)))


# ---------------------------------------------------------------- scrubbing
def _scrub_school(rec):
    """Allowlist. Anything not named in SCHOOL_FIELDS is dropped on ingest."""
    out = {k: rec.get(k) for k in SCHOOL_FIELDS if k in rec}
    leaked = [k for k in out if any(b in k.lower() for b in BLOCKED_FIELDS)]
    for k in leaked:                      # belt and braces if the allowlist is edited
        out.pop(k, None)
    return out


def _scrub_place(rec):
    """Only what the Google terms allow us to keep."""
    return {k: rec.get(k) for k in CACHEABLE_PLACE_FIELDS if k in rec}


# ---------------------------------------------------------------- cache
class Cache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _p(self, key):
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in key)
        return os.path.join(self.root, f'{safe}.json')

    def get(self, key, ttl):
        p = self._p(key)
        if not os.path.exists(p):
            return None
        if time.time() - os.path.getmtime(p) > ttl:
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


# ---------------------------------------------------------------- transport
def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post_json(url, body, headers, timeout=20):
    data = json.dumps(body).encode()
    h = {'Content-Type': 'application/json', 'User-Agent': UA}
    h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ---------------------------------------------------------------- schools
FIPS = {'CO': 8, 'CA': 6, 'TX': 48, 'FL': 12, 'AZ': 4, 'NM': 35, 'UT': 49,
        'WY': 56, 'NE': 31, 'KS': 20, 'OK': 40}


def _norm(s):
    s = str(s or '').lower()
    for w in (' elementary', ' middle', ' junior high', ' high school', ' school',
              ' academy', ' jr', ' sr', '.', ',', "'"):
        s = s.replace(w, ' ')
    return ' '.join(s.split())


def school_names(d):
    """Every school recorded on the export with its listing count, per level.

    A master area merging several MLS subdivision names routinely spans more than
    one attendance area, so this returns a list, never a single name.
    """
    out = {}
    for level, col in (('Elementary', 'Elementary School'),
                       ('Middle', 'Middle Or Junior School'),
                       ('High', 'High School')):
        if col not in d:
            continue
        v = d[col].dropna().astype(str).str.strip()
        v = v[(v != '') & (~v.str.lower().isin(['other', 'nan', 'none']))]
        if len(v):
            out[level] = list(v.value_counts().items())
    return out


def nces_directory(state, year, cache, lea_hint=None):
    """CCD school directory for one state-year, scrubbed to the allowlist."""
    fips = FIPS.get(str(state).upper())
    if not fips:
        raise EnrichError(f'No FIPS code on file for state {state!r}.')
    key = f'ccd-{fips}-{year}'
    hit = cache.get(key, SCHOOL_CACHE_TTL)
    if hit is not None:
        return hit
    rows, url = [], f'{EDU_API}/{year}/?fips={fips}'
    while url and len(rows) < 20000:
        page = _get_json(url)
        rows.extend(_scrub_school(r) for r in page.get('results', []))
        url = page.get('next')
    if not rows:
        raise EnrichError(f'CCD directory returned nothing for {state} {year}.')
    cache.put(key, rows)
    return rows


def match_schools(names, directory, district=None, lat=None, lon=None):
    """Match MLS school names against the CCD directory.

    MLS school fields are agent-entered short forms -- 'Normandy', 'Ken Caryl' --
    so matching is on a normalized name within the district where one is given,
    then by proximity to the centroid. Anything that does not match cleanly is
    returned unmatched rather than guessed at: a wrong school is worse than none.
    """
    idx = {}
    for r in directory:
        idx.setdefault(_norm(r.get('school_name')), []).append(r)
    out = []
    for level, listed in names.items():
        for nm, count in listed:
            cands = idx.get(_norm(nm), [])
            if district and len(cands) > 1:
                narrowed = [c for c in cands if _norm(district) in _norm(c.get('lea_name'))]
                cands = narrowed or cands
            if len(cands) > 1 and lat is not None:
                cands.sort(key=lambda c: (float(c.get('latitude') or 0) - lat) ** 2
                           + (float(c.get('longitude') or 0) - lon) ** 2)
            rec = dict(level=level, mls_name=nm, listings=int(count), matched=bool(cands))
            if cands:
                c = cands[0]
                rec.update(name=c.get('school_name'), ncessch=c.get('ncessch'),
                           district=c.get('lea_name'), enrollment=c.get('enrollment'),
                           grades=f"{c.get('lowest_grade_offered')}\u2013{c.get('highest_grade_offered')}",
                           lat=c.get('latitude'), lon=c.get('longitude'))
                t = c.get('teachers_fte')
                e = c.get('enrollment')
                if t and e and float(t) > 0:
                    rec['ratio'] = round(float(e) / float(t), 1)
            else:
                rec['name'] = nm
            out.append(rec)
    return out


def attach_cde(schools, spf_path):
    """Attach the Colorado School Performance Framework rating.

    CDE publishes the framework results as spreadsheets keyed on the CDE school
    code, not NCESSCH, and no crosswalk ships with either file. Matching is
    therefore on normalized school name within district, and a school that does
    not match is left without a rating rather than assigned a neighbour's.
    """
    if not spf_path or not os.path.exists(spf_path):
        return schools
    try:
        spf = pd.read_excel(spf_path)
    except Exception as exc:                       # noqa: BLE001 - never fatal
        raise EnrichError(f'Could not read the CDE framework file: {exc}') from exc
    cols = {c.lower(): c for c in spf.columns}
    ncol = next((cols[c] for c in cols if 'school name' in c), None)
    rcol = next((cols[c] for c in cols
                 if 'plan type' in c or 'framework' in c or 'rating' in c), None)
    if not ncol or not rcol:
        raise EnrichError('CDE file did not carry recognisable name/rating columns.')
    lookup = {_norm(r[ncol]): r[rcol] for _, r in spf.iterrows()}
    for s in schools:
        v = lookup.get(_norm(s.get('name')))
        if v is not None and v == v:
            s['cde_rating'] = str(v)
    return schools


# ---------------------------------------------------------------- amenities
def places_nearby(lat, lon, radius, types, api_key, limit=4):
    """Nearby Search (New): POST only, field mask required.

    The mask is kept to what we actually display, because billing follows the
    mask. Nothing here is written to the cache except id and location.
    """
    if not api_key:
        raise EnrichError('No Google Places API key supplied.')
    body = {'includedTypes': list(types), 'maxResultCount': limit,
            'locationRestriction': {'circle': {
                'center': {'latitude': lat, 'longitude': lon},
                'radius': float(radius)}},
            'rankPreference': 'DISTANCE'}
    mask = ('places.id,places.displayName,places.formattedAddress,'
            'places.primaryTypeDisplayName,places.location')
    res = _post_json(PLACES_URL, body,
                     {'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': mask})
    return res.get('places', [])


def amenities(lat, lon, radius, api_key, cache=None, limit=3):
    """One group per AMENITY_GROUPS entry. Cache holds ids and coordinates only."""
    out = []
    for label, types in AMENITY_GROUPS:
        try:
            found = places_nearby(lat, lon, radius, types, api_key, limit)
        except (urllib.error.URLError, EnrichError, ValueError):
            continue
        if cache is not None:
            cache.put(f'places-{label}-{round(lat,4)}-{round(lon,4)}',
                      [_scrub_place(p) for p in found])
        for p in found:
            out.append(dict(cat=label,
                            name=(p.get('displayName') or {}).get('text', ''),
                            detail=p.get('formattedAddress', ''),
                            kind=(p.get('primaryTypeDisplayName') or {}).get('text', ''),
                            place_id=p.get('id')))
    return out


# ---------------------------------------------------------------- entry point
def enrich(d, sub, cache_dir='/tmp/brief-cache', places_key=None,
           spf_path=None, ccd_year=2023, state='CO'):
    """Build a profile from public data. Returns (profile, warnings).

    Never raises. Every source is optional and every failure degrades to the
    section rendering with names only, because a market report must not fail to
    build because a school API was slow.
    """
    warn, prof = [], {'source': 'auto'}
    cache = Cache(cache_dir)
    names = school_names(d)
    prof['listed'] = names
    try:
        lat, lon = centroid(d)
        prof['centroid'] = (lat, lon)
        rad = spread_m(d, lat, lon)
    except EnrichError as exc:
        warn.append(str(exc))
        lat = lon = rad = None

    dist = None
    if 'Elementary School District' in d:
        v = d['Elementary School District'].dropna()
        dist = str(v.iloc[0]) if len(v) else None
    prof['district'] = dist

    try:
        directory = nces_directory(state, ccd_year, cache)
        prof['schools'] = match_schools(names, directory, dist, lat, lon)
        prof['school_source'] = (f'NCES Common Core of Data {ccd_year}, via the Urban '
                                 f'Institute Education Data Portal')
    except (EnrichError, urllib.error.URLError, ValueError) as exc:
        warn.append(f'School directory unavailable: {exc}')
        prof['schools'] = [dict(level=lv, mls_name=nm, name=nm, listings=int(c),
                                matched=False)
                           for lv, lst in names.items() for nm, c in lst]

    if spf_path:
        try:
            prof['schools'] = attach_cde(prof['schools'], spf_path)
            prof['spf_source'] = 'Colorado Department of Education School Performance Framework'
        except EnrichError as exc:
            warn.append(str(exc))

    if lat is not None and places_key:
        try:
            prof['amenities'] = amenities(lat, lon, rad, places_key, cache)
            prof['amenity_source'] = 'Google Places'
        except (EnrichError, urllib.error.URLError, ValueError) as exc:
            warn.append(f'Amenities unavailable: {exc}')
            prof['amenities'] = []
    else:
        if not places_key:
            warn.append('No Google Places API key supplied; amenities not fetched.')
        prof['amenities'] = []

    return prof, warn
