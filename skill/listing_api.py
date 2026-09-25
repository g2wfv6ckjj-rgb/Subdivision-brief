"""RealtyAPI integration -- property details for the Listing Report /
Ideal Buyer Profile feature. Deterministic, no Claude/LLM calls here or
anywhere downstream of this module -- see SKILL.md rule 73.

RealtyAPI is an unofficial scraper-based aggregator (their own description),
not a licensed MLS/RESO feed -- worth knowing since this becomes an
official FNT-branded tool, not a side project.

Auth: the x-realtyapi-key header, read from the REALTYAPI_KEY environment
variable -- never hardcoded, never logged, never passed as a function
argument from request-handling code (so it can't end up in a traceback).
"""
import os

import requests

BASE = 'https://realtor.realtyapi.io'
TIMEOUT = 20


class ListingAPIError(Exception):
    """Raised for any RealtyAPI failure -- bad address, rate limit, no key
    configured, network error. Callers catch this specifically and show a
    friendly message, the same pattern master.py's BriefError uses for the
    subdivision pipeline's own deliberate stops."""


def _key():
    k = os.environ.get('REALTYAPI_KEY')
    if not k:
        raise ListingAPIError('REALTYAPI_KEY is not set in the environment.')
    return k


def get_property(address, _raw=None):
    """Full details for one property by street address.

    Returns a plain dict with only the fields this skill actually uses --
    NOT the raw API response -- so every downstream module depends on one
    stable shape regardless of what RealtyAPI renames or adds upstream.
    Every field is None when it doesn't resolve, never a KeyError; nothing
    here assumes a field is present just because it showed up in one real
    example response.

    _raw: internal-use only, a pre-fetched response dict -- lets tests (and
    the fixture in fixtures/) exercise the parsing logic without a network
    call or a real API key. Real callers never pass this.
    """
    if _raw is not None:
        payload = _raw
    else:
        try:
            r = requests.get(f'{BASE}/details/byaddress', timeout=TIMEOUT,
                             headers={'x-realtyapi-key': _key()},
                             params={'address': address})
        except requests.RequestException as exc:
            raise ListingAPIError(f'Could not reach RealtyAPI: {exc}') from exc
        if r.status_code == 404:
            raise ListingAPIError(f'No property found for "{address}". Check the address and try again.')
        if r.status_code == 429:
            raise ListingAPIError('RealtyAPI rate limit hit. Wait a moment and try again.')
        if not r.ok:
            raise ListingAPIError(f'RealtyAPI returned {r.status_code}: {r.text[:200]}')
        payload = r.json()

    d = payload.get('detail')
    if not d:
        raise ListingAPIError(f'No property found for "{address}".')

    det = d.get('details') or {}
    addr = d.get('address') or {}
    mort = (d.get('mortgage') or {}).get('estimate') or {}
    est = d.get('estimates') or {}
    flood = (d.get('local') or {}).get('flood') or {}

    avm_values = [v.get('estimate') for v in (est.get('current_values') or []) if v.get('estimate')]
    avm_best = next((v['estimate'] for v in (est.get('current_values') or [])
                     if v.get('isbest_homevalue')), None)

    # Forecast: first source's own start/end point, not an average across
    # sources -- the sources disagree with each other by a wide margin (see
    # rule 73), and blending their forecasts would manufacture a false
    # precision none of them actually offers on its own.
    forecast = None
    fvals = est.get('forecast_values') or []
    if fvals and fvals[0].get('estimates'):
        pts = fvals[0]['estimates']
        if len(pts) >= 2 and pts[0].get('estimate') and pts[-1].get('estimate'):
            start, end = pts[0]['estimate'], pts[-1]['estimate']
            forecast = {
                'source': (fvals[0].get('source') or {}).get('name'),
                'start': start, 'end': end,
                'start_date': pts[0].get('date'), 'end_date': pts[-1].get('date'),
                'pct_change': round((end - start) / start * 100, 1) if start else None,
            }

    schools = [{'name': s.get('name'), 'rating': s.get('rating'),
               'distance_mi': s.get('distance_in_miles'),
               'levels': s.get('education_levels') or []}
              for s in (d.get('schools') or []) if s.get('name')]

    return {
        'address_line': addr.get('line'),
        'city': addr.get('city'),
        'state': addr.get('state_code'),
        'zip': addr.get('postal_code'),
        'county_fips': d.get('county_fips'),
        'neighborhood': (d.get('neighborhoods') or [None])[0],
        'status': d.get('status'),
        'list_price': d.get('list_price'),
        'price_per_sqft': d.get('price_per_sqft'),
        'last_sold_price': d.get('last_sold_price'),
        'last_sold_date': d.get('last_sold_date'),
        'beds': det.get('beds'),
        'baths': det.get('baths'),
        'sqft': det.get('sqft'),
        'lot_sqft': det.get('lot_sqft'),
        'year_built': det.get('year_built'),
        'property_type': det.get('type'),
        'description': det.get('text'),
        'hoa_fee': d.get('hoa_fee'),
        'mls_name': (d.get('mls') or {}).get('name'),
        'photo_url': (d.get('photos') or [{}])[0].get('href'),
        'photo_count': d.get('photo_count'),
        'schools': schools,
        # AVM: three independent valuation sources, not one number -- see
        # rule 73 on why the range is reported, not just avm_best.
        'avm_values': avm_values,
        'avm_best': avm_best,
        'avm_low': min(avm_values) if avm_values else None,
        'avm_high': max(avm_values) if avm_values else None,
        'forecast': forecast,
        'mortgage_estimate': {
            'loan_amount': mort.get('loan_amount'),
            'monthly_payment': mort.get('monthly_payment'),
            'down_payment': mort.get('down_payment'),
            'rate': mort.get('rate'),
            'term': mort.get('term'),
        } if mort else None,
        # Actual annual property tax from the most recent tax_history year --
        # a real bill, not an estimate. None when the county record is absent.
        'annual_tax': next((t.get('tax') for t in (d.get('tax_history') or [])
                            if t.get('tax')), None),
        'flood_zone': flood.get('fema_zone'),
        'flood_score': flood.get('flood_factor_score'),
    }


def get_comps(zip_code, status=None, limit=10, _raw=None):
    """Listings near a ZIP code, for the comps section.

    Verified against a real /search/byzip response (a genuine sample, not
    guessed) -- confirmed field names: the results live under
    `searchResults` (not `listings`/`results`, both wrong earlier guesses),
    fields are flat on each item (beds/baths/sqft/list_price/property_type
    directly on the dict, not nested under a `details` key), photos are
    plain URL strings in `photos` (not `{href: ...}` objects the way the
    single-property endpoint returns them -- `primary_photo` is used
    instead, which sidesteps that shape difference entirely), and each
    result carries its own single `estimate` (AVM) figure.

    ONE THING STILL UNCONFIRMED: the sample this was verified against
    returned only status="for_sale" listings -- it was not filtered to
    sold comps, so the actual query parameter name for that filter is still
    a guess (`status=` below). If comps come back as active listings
    instead of recently-sold ones, that parameter name is the first thing
    to check against RealtyAPI's real docs or another sample. See rule 73.
    """
    try:
        params = {'zipCode': zip_code, 'limit': limit}
        if status:
            params['status'] = status
        r = requests.get(f'{BASE}/search/byzip', timeout=TIMEOUT,
                         headers={'x-realtyapi-key': _key()}, params=params) \
            if _raw is None else None
    except requests.RequestException as exc:
        raise ListingAPIError(f'Could not reach RealtyAPI: {exc}') from exc
    if _raw is None:
        if not r.ok:
            raise ListingAPIError(f'RealtyAPI returned {r.status_code}: {r.text[:200]}')
        payload = r.json()
    else:
        payload = _raw

    results = payload.get('searchResults') or []
    comps = []
    for item in results:
        addr = item.get('address') or {}
        comps.append({
            'address_line': addr.get('line'),
            'city': addr.get('city'), 'state': addr.get('state_code'), 'zip': addr.get('postal_code'),
            'county': item.get('county'),
            'status': item.get('status'),
            'list_price': item.get('list_price'),
            'last_sold_price': item.get('last_sold_price'),
            'last_sold_date': item.get('last_sold_date'),
            'estimate': item.get('estimate'),
            'beds': item.get('beds'), 'baths': item.get('baths'), 'sqft': item.get('sqft'),
            'lot_sqft': item.get('lot_sqft'),
            'property_type': item.get('property_type'),
            'list_date': item.get('list_date'),
            'price_reduced_amount': item.get('price_reduced_amount'),
            'photo_url': item.get('primary_photo'),
        })
    return comps
