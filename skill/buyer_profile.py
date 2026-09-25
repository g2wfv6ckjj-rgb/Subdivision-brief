"""Ideal Buyer Profile: a deterministic classifier, not an AI-generated
persona. Every claim in the output traces to a specific number already in
`prop` (from listing_api.get_property()) or `comps` (from
listing_api.get_comps()) -- no invented psychographics, no inference this
module can't point back to a real figure. See SKILL.md rule 73.

This exists because the original Ideal Buyer Profile concept (from the
ideal-buyer-analysis skill) built its buyer narrative from live, multi-source
web research -- migration signals, search-origin data, social trends. None
of that is available here without an LLM call at runtime, which is exactly
what this whole web app is built to avoid. This is the honest, deterministic
substitute: real property characteristics mapped to real buyer archetypes
through named, fixed rules -- not a smaller version of the same thing, a
different and more modest claim.
"""


_TYPE_NOUNS = {'condos': 'condo', 'townhomes': 'townhome', 'single_family': 'single-family home',
              'multi_family': 'multi-family home', 'land': 'lot'}


def _type_noun(ptype):
    """RealtyAPI's raw category names ('condos', 'single_family') aren't
    prose-ready nouns -- this maps the ones seen in real responses to a
    natural singular noun. Falls back to a de-underscored version of
    whatever RealtyAPI actually sent for any type not in this table, rather
    than guessing at every possible category name in advance."""
    key = (ptype or '').lower()
    return _TYPE_NOUNS.get(key, key.replace('_', ' ') or 'property')


def _comps_median(comps, field):
    vals = [c[field] for c in (comps or []) if c.get(field) is not None]
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    vals = [c[field] for c in (comps or []) if c.get(field) is not None]
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def classify_buyer(prop, comps=None, area=None):
    """Returns {'archetype': str, 'reasons': [str,...], 'notes': [str,...]}.

    archetype -- one primary label, chosen by the first matching rule below.
    reasons -- why that archetype, each citing a real number from prop/comps.
    notes -- secondary, non-exclusive observations (e.g. rental appeal) that
    don't change the primary archetype but are worth an agent knowing.
    """
    beds = prop.get('beds')
    ptype = (prop.get('property_type') or '').lower()
    schools = prop.get('schools') or []
    good_schools = [s for s in schools if (s.get('rating') or 0) >= 7
                    and (s.get('distance_mi') or 99) <= 2]
    med_sqft = _comps_median(comps, 'sqft')
    med_price = _comps_median(comps, 'list_price')

    archetype, reasons = None, []

    if beds is not None and beds >= 4 and good_schools:
        archetype = 'Move-up family buyer'
        top = max(good_schools, key=lambda s: s['rating'])
        reasons.append(f"{beds} bedrooms" + (f", {prop['sqft']:,} sq ft" if prop.get('sqft') else '')
                       + " -- room to grow into, not just fit into.")
        reasons.append(f"{top['name']} rates {top['rating']}/10 and sits "
                       f"{top['distance_mi']} mile{'s' if top['distance_mi'] != 1 else ''} away -- "
                       f"school quality this close is a specific, checkable draw, not a general area claim.")
    elif beds is not None and beds <= 2 and ('condo' in ptype or 'townhome' in ptype or 'townhomes' in ptype):
        archetype = 'First-time buyer or downsizer'
        reasons.append(f"{beds} bedroom{'s' if beds != 1 else ''} in a "
                       f"{_type_noun(prop.get('property_type'))} -- "
                       f"a lower-maintenance entry point, not a family-scale purchase.")
        if prop.get('hoa_fee') is not None:
            reasons.append(f"HOA fee of ${prop['hoa_fee']:,}/mo -- a real monthly number worth "
                           f"stating plainly, not folding into the price alone.")
    elif beds is not None and beds >= 4:
        archetype = 'Family buyer'
        reasons.append(f"{beds} bedrooms" + (f", {prop['sqft']:,} sq ft" if prop.get('sqft') else '')
                       + " -- sized for a family, though no school within 2 miles rated 7 or higher "
                       "in this data, so schools aren't the specific draw here the way they would be "
                       "for a top-rated district.")
    else:
        archetype = 'General buyer'
        reasons.append("Bed count and property type here don't point clearly toward one buyer "
                       "type over another -- this fits a broad range of buyers rather than one "
                       "specific profile, which is itself worth saying plainly.")

    if med_sqft and prop.get('sqft'):
        diff_pct = round((prop['sqft'] - med_sqft) / med_sqft * 100)
        if abs(diff_pct) >= 15:
            direction = 'more' if diff_pct > 0 else 'less'
            reasons.append(f"{prop['sqft']:,} sq ft is {abs(diff_pct)}% {direction} than the "
                           f"{med_sqft:,.0f} sq ft median among the {len(comps)} nearby listings pulled "
                           f"for this report.")

    notes = []
    if area and area.get('rent') is not None and area['rent'] >= 60:
        notes.append(f"Rent to Price for this area scores {area['rent']}/100 -- "
                     f"worth a specific mention to any buyer weighing this as a rental, "
                     f"not just an owner-occupant purchase.")
    if med_price and prop.get('list_price'):
        diff_pct = round((prop['list_price'] - med_price) / med_price * 100)
        if abs(diff_pct) >= 15:
            direction = 'above' if diff_pct > 0 else 'below'
            notes.append(f"Listed {abs(diff_pct)}% {direction} the ${med_price:,.0f} median list "
                         f"price among nearby comparable listings pulled for this report.")

    return {'archetype': archetype, 'reasons': reasons, 'notes': notes}
