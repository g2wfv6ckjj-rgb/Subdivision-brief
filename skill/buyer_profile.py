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
        archetype = 'Move-up buyer (space + schools)'
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
        archetype = 'Space-seeking buyer'
        reasons.append(f"{beds} bedrooms" + (f", {prop['sqft']:,} sq ft" if prop.get('sqft') else '')
                       + " -- generous space, though no school within 2 miles rated 7 or higher "
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


# ===========================================================================
# Full Ideal Buyer Profile table -- the deterministic counterpart of the
# research-driven table in the ideal-buyer-analysis skill. Same rows; every
# row is assembled from named numbers by fixed rules. Where that skill used
# live web research (Redfin search origins, job-market news, "CONFIRMED"
# sector claims), this uses the closest government dataset instead and says so.
#
# FAIR HOUSING: this table is agent-facing planning context. None of it is
# fed into ad copy (listing_marketing.py describes the property only), and
# the persona line deliberately names no age, family or household type.
# ===========================================================================

_INDUSTRY_SHORT = {
    'Educational services, and health care and social assistance': 'education and health care',
    'Professional, scientific, and management, and administrative and waste management services':
        'professional, scientific and management services',
    'Finance and insurance, and real estate and rental and leasing': 'finance, insurance and real estate',
    'Arts, entertainment, and recreation, and accommodation and food services':
        'arts, recreation, hospitality and food service',
    'Transportation and warehousing, and utilities': 'transportation, warehousing and utilities',
    'Other services, except public administration': 'other services',
    'Agriculture, forestry, fishing and hunting, and mining': 'agriculture and mining',
}


def _short_industry(name):
    return _INDUSTRY_SHORT.get(name, name[:1].lower() + name[1:])


def _money(v):
    return f'${v:,.0f}' if v is not None else 'n/a'


def _k(v):
    return f'${v / 1000:,.0f}K' if v is not None else 'n/a'


def payment(prop, fin):
    """PITI at 20% down using the app's maintained 30-yr rate (core.FIN), the
    property's ACTUAL most recent tax bill, the app's insurance assumption and
    the real HOA fee. Returns None without a list price."""
    price = prop.get('list_price')
    if not price:
        return None
    loan, r, n = price * 0.8, fin['rate'] / 12, 360
    pi = loan * r / (1 - (1 + r) ** -n)
    tax = (prop.get('annual_tax') or 0) / 12
    ins = price * fin['ins_rate'] / 12
    hoa = prop.get('hoa_fee') or 0
    total = pi + tax + ins + hoa
    return {'pi': round(pi), 'tax': round(tax), 'ins': round(ins), 'hoa': round(hoa),
            'total': round(total), 'rate': fin['rate'], 'rate_src': fin.get('rate_src'),
            'tax_actual': bool(prop.get('annual_tax')),
            'income_lo': round(total * 12 / 0.28, -3), 'income_hi': round(total * 12 / 0.22, -3)}


def _median(vals):
    vals = sorted(v for v in vals if v)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _kw(text, *words):
    t = (text or '').lower()
    return any(w in t for w in words)


def build_profile(prop, comps=None, area=None, demo=None, careers=None, origins=None, fin=None):
    """Returns {'persona', 'persona_line', 'rows': [(label, html_text)], 'sources': [...]}.
    Rows whose inputs are all missing are omitted, never filled with a guess."""
    import html as H
    comps = comps or []
    demo = demo or {}
    pay = payment(prop, fin) if fin else None
    desc = prop.get('description') or ''
    rows, sources = [], []
    scope = demo.get('scope', 'this ZIP')

    # Compare like with like: same property type when at least 3 such listings
    # came back, otherwise all nearby listings (and say which, below).
    same = [c for c in comps if c.get('property_type') and
            c.get('property_type') == prop.get('property_type')]
    pool = same if len(same) >= 3 else comps
    pool_label = (f'nearby {_type_noun(prop.get("property_type"))} listings' if pool is same
                  else 'nearby listings')
    comp_lot = _median([c.get('lot_sqft') for c in pool])
    comp_psf = _median([c['list_price'] / c['sqft'] for c in pool
                        if c.get('list_price') and c.get('sqft')])
    psf = (prop['list_price'] / prop['sqft']) if prop.get('list_price') and prop.get('sqft') else None
    mhv = demo.get('median_home_value')
    price = prop.get('list_price')

    # --- Current household status (decided first: the persona uses it) -----
    status = None
    if demo.get('owner_pct') is not None and mhv and price:
        above = round((price - mhv) / mhv * 100)
        if demo['owner_pct'] >= 60 and above > 5:
            status = 'Move-Up'
            txt = (f'Most likely a <b>current owner moving up</b>: {demo["owner_pct"]:.0f}% of homes in '
                   f'{scope} are owner-occupied, and at {_money(price)} this home is {above}% above the '
                   f'area\'s median owner-reported value ({_money(mhv)}), consistent with a buyer bringing '
                   f'equity from a lower-priced home.')
        else:
            status = 'First-Time'
            txt = (f'Plausibly a <b>first-time buyer or a renter converting to ownership</b>: at '
                   f'{_money(price)} this home is priced near the area\'s median owner-reported value '
                   f'({_money(mhv)}), and {100 - demo["owner_pct"]:.0f}% of local homes are renter-occupied.')
        if demo.get('median_gross_rent') and pay:
            txt += (f' Secondary: a local renter at the median gross rent of '
                    f'{_money(demo["median_gross_rent"])}/mo would take on '
                    f'{_money(pay["total"] - demo["median_gross_rent"])}/mo more at this price.')
        txt += ' (ACS home values are owner-reported and lag current prices.)'
        status_row = ('Current household status', txt)
    else:
        status_row = None

    # --- Age range -----------------------------------------------------------
    bands = demo.get('owner_age_bands') or []
    if bands:
        top2 = sorted(bands, key=lambda b: b[1], reverse=True)[:2]
        labels = [t[0] for t in top2]
        los = [int(lb.split('-')[0].rstrip('+')) for lb in labels]
        his = [int(lb.split('-')[1]) if '-' in lb else 99 for lb in labels]
        rng = f'~{min(los)}-{max(his)}' if max(his) < 99 else f'~{min(los)}+'
        txt = (f'<b>{rng}</b> (primary householder). Owners in {scope} are most often householders aged '
               + ' and '.join(f'{b} ({p:.0f}% of owner households)' for b, p in top2) + '.')
        rows.append(('Age range', txt))

    # --- Household composition (internal only) ------------------------------
    comp_bits = []
    if demo.get('family_hh_pct') is not None:
        comp_bits.append(f'{demo["family_hh_pct"]:.0f}% of households in {scope} are family households')
    if demo.get('avg_household_size'):
        comp_bits.append(f'average household size is {demo["avg_household_size"]:.2f}')
    if demo.get('median_family_income'):
        comp_bits.append(f'median family income is {_money(demo["median_family_income"])}')
    if comp_bits:
        txt = '; '.join(comp_bits) + '.'
        if prop.get('beds') and demo.get('avg_household_size'):
            extra = prop['beds'] - demo['avg_household_size']
            if extra >= 1:
                txt += (f' With {prop["beds"]} bedrooms, the home has more bedrooms than the typical '
                        f'household has people, leaving room for an office or guests.')
        rows.append(('Household composition<br><span style="font-weight:400">(internal profiling only '
                     '&mdash; not an ad-targeting criterion)</span>', txt))

    # --- Income band -------------------------------------------------------
    if pay:
        txt = (f'<b>~{_k(pay["income_lo"])}-{_k(pay["income_hi"])} combined gross.</b> At {_money(price)} '
               f'with 20% down at {pay["rate"] * 100:.2f}% ({H.escape(pay["rate_src"] or "")}), estimated '
               f'PITI &asymp; {_money(pay["total"])}/mo (P&amp;I {_money(pay["pi"])} + '
               f'{"actual" if pay["tax_actual"] else "no"} property tax {_money(pay["tax"])} + est. '
               f'insurance {_money(pay["ins"])} + HOA {_money(pay["hoa"])}). The band is where that payment '
               f'is 22-28% of gross income; confirm with a lender.')
        inc = [(a, v) for a, v in (demo.get('income_by_age') or []) if a != 'under 25']
        if inc:
            txt += (f' For comparison, {scope} median household income by householder age: '
                    + ', '.join(f'{a} {_k(v)}' for a, v in inc) + '.')
        rows.append(('Income band', txt))

    # --- Career types ------------------------------------------------------
    if careers:
        bits = []
        ind = careers.get('industry') or []
        if ind:
            bits.append('Top industries for employed residents of ' + careers['scope'] + ': '
                        + ', '.join(f'{_short_industry(n)} ({p:.1f}%)' for n, p in ind[:3]) + '.')
        occ = careers.get('occupation') or []
        if occ:
            n, p = occ[0]
            bits.append(f'{p:.1f}% work in {n[:1].lower() + n[1:]}.')
        if bits:
            rows.append(('Career types', ' '.join(bits)))

    if status_row:
        rows.append(status_row)

    # --- Core motivations / pain points -------------------------------------
    mot, tags = [], []
    if prop.get('lot_sqft') and comp_lot and prop['lot_sqft'] >= comp_lot * 1.2:
        mot.append(f'wants a <b>{prop["lot_sqft"] / 43560:.2f}-acre lot</b>, '
                   f'{round((prop["lot_sqft"] / comp_lot - 1) * 100)}% larger than the median of ' + pool_label)
        tags.append('a larger-than-typical lot')
    if psf and comp_psf and psf <= comp_psf * 0.9:
        mot.append(f'wants to buy below local per-foot pricing: <b>{_money(psf)}/sq ft</b> vs a '
                   f'{_money(comp_psf)} median for ' + pool_label)
        tags.append('below-market per-foot pricing')
    if _kw(desc, 'unfinished', 'rough-in', 'rough in'):
        mot.append('wants to <b>build equity through improvements</b> (the listing notes unfinished space '
                   'or rough-in plumbing)')
        tags.append('room to add value')
    if prop.get('hoa_fee') == 0:
        mot.append('no HOA')
        tags.append('no HOA')
    good = [s for s in (prop.get('schools') or []) if (s.get('rating') or 0) >= 7
            and (s.get('distance_mi') or 99) <= 2]
    if good:
        top = max(good, key=lambda x: x['rating'])
        mot.append(f'school access: {H.escape(top["name"])} rates {top["rating"]}/10, {top["distance_mi"]} mi away')
        tags.append('strong nearby schools')
    if _kw(desc, 'park', 'lake', 'trail', 'open space'):
        mot.append('proximity to the parks, lake or trails the listing highlights')
        tags.append('park, lake and trail access')
    if mot:
        rows.append(('Core motivations / pain points',
                     ' '.join(f'({i}) {m};' for i, m in enumerate(mot[:6], 1)).rstrip(';') + '.'))

    # --- Where they are moving from -----------------------------------------
    if origins:
        o = origins['origins']
        txt = (f'Top origins for people moving into {H.escape(origins["county"])}: '
               + ', '.join(f'{H.escape(x["place"].replace(" County, CO", "").replace(", CO", ""))} '
                           f'({x["people"]:,})' for x in o) + '.')
        if origins.get('top_share_pct') and origins.get('total_people'):
            txt += (f' Together that is {origins["top_share_pct"]}% of the {origins["total_people"]:,} '
                    f'people who moved into the county')
            txt += (f'; {origins["instate_pct"]}% came from elsewhere in Colorado.'
                    if origins.get('instate_pct') else '.')
        txt += f' (IRS SOI, {origins["as_of"]} tax years; county level, since no source publishes this by ZIP.)'
        rows.append(('Where they are moving from', txt))

    # --- Lifestyle & interests ---------------------------------------------
    life = []
    if _kw(desc, 'park', 'lake', 'trail'):
        life.append('outdoor recreation (the listing notes nearby park, lake or trails)')
    if _kw(desc, 'rec center', 'sports field', 'recreation center'):
        life.append('community recreation (nearby rec center or sports fields)')
    if _kw(desc, 'landscap', 'garden', 'yard', 'deck', 'patio'):
        life.append('outdoor living and gardening (yard, landscaping or deck)')
    if _kw(desc, 'stained glass', 'built-in', 'vintage', 'character', 'original'):
        life.append('values character features over new-build uniformity')
    if _kw(desc, 'office'):
        life.append('working from home (the listing notes an office)')
    if _kw(desc, 'fireplace'):
        life.append('cozy entertaining (fireplace)')
    if life:
        life[0] = life[0][:1].upper() + life[0][1:]
        rows.append(('Lifestyle &amp; interests', '; '.join(life) + '. Drawn from what the listing itself '
                     'highlights, not from demographic inference.'))

    # --- Data-driven rationale --------------------------------------------
    why = []
    if origins and len(origins['origins']) >= 2:
        o = origins['origins']
        agis = [x['avg_agi'] for x in o[:2] if x.get('avg_agi')]
        why.append(f'IRS data shows {H.escape(origins["county"])}\'s largest inflows come from '
                   f'{H.escape(o[0]["place"])} and {H.escape(o[1]["place"])}'
                   + (f', whose movers average {_k(min(agis))}-{_k(max(agis))} income per household' if agis else ''))
    inc = dict(demo.get('income_by_age') or [])
    if pay and inc:
        best = max(((a, v) for a, v in inc.items() if a != 'under 25'), key=lambda x: x[1], default=None)
        if best:
            why.append(f'the ACS shows {scope} householders aged {best[0]} earn a median {_k(best[1])} '
                       f'against the {_k(pay["income_lo"])}+ this home needs')
    if psf and comp_psf:
        rel = 'below' if psf < comp_psf else 'above'
        why.append(f'at {_money(psf)}/sq ft versus a {_money(comp_psf)} median for {pool_label}, it is priced '
                   f'{rel} local per-foot value')
    if why:
        rows.append(('Data-driven rationale', '; '.join(why)[:1].upper() + '; '.join(why)[1:] + '.'))

    # --- Persona -----------------------------------------------------------
    if _kw(desc, 'unfinished', 'rough-in', 'rough in'):
        adj = 'Equity-Building'
    elif prop.get('lot_sqft') and comp_lot and prop['lot_sqft'] >= comp_lot * 1.2:
        adj = 'Large-Lot'
    elif psf and comp_psf and psf <= comp_psf * 0.9:
        adj = 'Value-Seeking'
    else:
        adj = 'Ready-to-Buy'
    place = (origins or {}).get('county', '').replace(' County', '') or (prop.get('city') or '')
    persona = f'The {adj} {place} {status or "Home"} Buyer'.replace('  ', ' ')
    line_bits = []
    if pay:
        line_bits.append(f'a household with roughly {_k(pay["income_lo"])}-{_k(pay["income_hi"])} of combined income')
    if origins and origins['origins']:
        line_bits.append(f'most likely relocating from {H.escape(origins["origins"][0]["place"])} or nearby counties')
    if tags:
        line_bits.append('drawn by ' + tags[0] + (f' and {tags[1]}' if len(tags) > 1 else ''))
    persona_line = (', '.join(line_bits) + '.') if line_bits else ''
    persona_line = persona_line[:1].upper() + persona_line[1:]

    return {'persona': persona, 'persona_line': persona_line, 'rows': rows, 'payment': pay}


def re_strip(t):
    """Drop inline tags and the leading verb from a motivation for the persona line."""
    import re
    t = re.sub(r'<[^>]+>', '', t)
    return re.sub(r'^(wants to |wants a |wants )', '', t)
