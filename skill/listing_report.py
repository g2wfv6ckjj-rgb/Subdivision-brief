"""Listing Report / Ideal Buyer Profile / Marketing Blueprint.

A single-property companion to the subdivision Master Brief -- same visual
system (reports.CSS, dials.py's gauges), completely different data source
and input shape: one street address instead of an MLS export, RealtyAPI
instead of the bundled reference pack for the property-specific numbers.

Deterministic end to end -- no Claude/LLM call anywhere in this module or
anything it imports. See SKILL.md rule 73 for the full account of what
RealtyAPI provides, what still comes from the existing Colorado reference
pack (co_data.py, unchanged), and what was deliberately left out (live
multi-source migration research, which has no deterministic substitute).

NOT YET VISUALLY VERIFIED. Every function that produces a string (buyer
profile, marketing creatives, this module's own section builders) is tested
against real fixture data -- see _selftest.py. The actual PDF layout has not
been screenshotted, because the local browser needed to render one is still
unavailable in this sandbox as of this writing. Treat the first real
generation on the live site as the actual visual check.
"""
import html as HT

import buyer_profile
import census_api
import co_data
import dials as DL
import listing_api
import listing_marketing
import reports as R
from core import Mshort


def _N(start=0):
    i = [start]
    def nxt():
        i[0] += 1
        return f'{i[0]:02d}'
    return nxt


def sec(n, t, pb=False):
    return f'<div class="sec{" pb" if pb else ""}"><span class="num">{n}</span><h2>{t}</h2></div>'


def _money(v, cents=False):
    if v is None:
        return 'n/a'
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def cover(prop):
    addr = HT.escape(prop.get('address_line') or 'Property')
    city = HT.escape(f"{prop.get('city') or ''}, {prop.get('state') or ''}".strip(', '))
    return f'''<div class="cover"><div class="badge">LISTING REPORT</div>
<div class="kick">Property Analysis &#183; Ideal Buyer Profile &#183; Marketing Blueprint</div>
<h1>{addr}</h1><p class="loc">{city}</p>
<div class="rng">SOURCED FROM REALTYAPI (UNOFFICIAL) &#183; NOT AN MLS EXPORT</div>{R.skyline()}</div>'''


def _property_section(prop, nn):
    photo = ''
    if prop.get('photo_url'):
        photo = (f'<img src="{HT.escape(prop["photo_url"])}" alt="" '
                f'style="width:100%;max-height:280pt;object-fit:cover;'
                f'border-radius:6pt;margin-bottom:10pt">')

    facts = []
    if prop.get('beds') is not None:
        facts.append(('BEDS', str(prop['beds'])))
    if prop.get('baths') is not None:
        facts.append(('BATHS', str(prop['baths'])))
    if prop.get('sqft'):
        facts.append(('SQ FT', f"{prop['sqft']:,}"))
    if prop.get('year_built'):
        facts.append(('YEAR BUILT', str(prop['year_built'])))
    if prop.get('lot_sqft'):
        facts.append(('LOT SIZE', f"{prop['lot_sqft']:,} sq ft"))
    if prop.get('hoa_fee') is not None:
        facts.append(('HOA/MO', _money(prop['hoa_fee']) if prop['hoa_fee'] else 'None'))
    cards = ''.join(f'<div class="card"><div class="k">{k}</div>'
                    f'<div class="v" style="font-size:15pt">{HT.escape(v)}</div></div>'
                    for k, v in facts)

    psf_suffix = f' &middot; {_money(prop["price_per_sqft"])}/sq ft' if prop.get('price_per_sqft') else ''
    price_line = (f'<div class="narr"><div class="lead">{_money(prop.get("list_price"))}'
                 f'{psf_suffix}</div></div>')

    desc = prop.get('description') or ''
    if len(desc) > 600:
        desc = desc[:600].rsplit(' ', 1)[0] + '...'

    mls_note = (f'<p class="cap">Listed via {HT.escape(prop["mls_name"])}.</p>'
               if prop.get('mls_name') else '')

    return (sec(nn(), 'The Property') + photo + price_line
           + f'<div class="cards">{cards}</div>'
           + (f'<p>{HT.escape(desc)}</p>' if desc else '')
           + mls_note)


def _valuation_section(prop, nn):
    avm_low, avm_high, avm_best = prop.get('avm_low'), prop.get('avm_high'), prop.get('avm_best')
    if not avm_low:
        return sec(nn(), "What It's Worth") + '<p class="cap">No automated valuation available for this property.</p>'

    spread_pct = round((avm_high - avm_low) / avm_low * 100) if avm_low else None
    spread_note = ''
    if spread_pct and spread_pct >= 10:
        spread_note = (f'<div class="take"><span class="tag">Worth knowing</span>'
                       f'<p>The three valuation models RealtyAPI aggregates disagree by '
                       f'{spread_pct}% on this property ({_money(avm_low)} to {_money(avm_high)}) '
                       f'-- a real spread, not a rounding difference. Treat the range itself as '
                       f'the honest answer, not any single number inside it.</p></div>')

    forecast = prop.get('forecast')
    forecast_html = ''
    if forecast and forecast.get('pct_change') is not None:
        direction = 'up' if forecast['pct_change'] >= 0 else 'down'
        forecast_html = (f'<p><strong>{forecast["source"]}</strong> projects this property\'s value '
                         f'moving {direction} {abs(forecast["pct_change"])}% between '
                         f'{forecast["start_date"]} and {forecast["end_date"]} -- one model\'s forecast, '
                         f'not a guarantee, and not averaged with the others above.</p>')

    return (sec(nn(), "What It's Worth")
           + f'<div class="cards">'
           + f'<div class="card"><div class="k">Low estimate</div><div class="v">{_money(avm_low)}</div></div>'
           + (f'<div class="card"><div class="k">Best estimate</div><div class="v">{_money(avm_best)}</div></div>' if avm_best else '')
           + f'<div class="card"><div class="k">High estimate</div><div class="v">{_money(avm_high)}</div></div>'
           + '</div>' + spread_note + forecast_html)


def _comp_row(c):
    sqft_txt = f"{c['sqft']:,}" if c.get('sqft') else ''
    return (f'<tr><td>{HT.escape(c.get("address_line") or "")}</td>'
           f'<td>{_money(c.get("list_price"))}</td>'
           f'<td>{c.get("beds") or ""}bd/{c.get("baths") or ""}ba</td>'
           f'<td>{sqft_txt}</td>'
           f'<td>{HT.escape((c.get("property_type") or "").replace("_", " "))}</td></tr>')


def _comps_section(comps, nn):
    if not comps:
        return sec(nn(), 'Nearby Listings') + '<p class="cap">No comparable listings available.</p>'
    rows = ''.join(_comp_row(c) for c in comps)
    return (sec(nn(), 'Nearby Listings')
           + '<table><thead><tr><th>Address</th><th>Price</th><th>Beds/Baths</th>'
           '<th>Sq Ft</th><th>Type</th></tr></thead><tbody>' + rows + '</tbody></table>'
           + f'<p class="cap">{len(comps)} listings pulled near this property\'s ZIP code via RealtyAPI. '
           'These are the listings returned by that search at the time this report was generated, not '
           'necessarily filtered to recently sold comparables -- see this report\'s methodology note.</p>')


def _school_row(s):
    levels = '/'.join(s['levels']).upper() if s.get('levels') else 'SCHOOL'
    rating_txt = f"Rated {s['rating']}/10" if s.get('rating') else 'Not rated'
    dist_txt = f" &middot; {s['distance_mi']} mi away" if s.get('distance_mi') is not None else ''
    return (f'<div class="amen"><div class="acat">{levels}</div>'
           f'<div class="aname">{HT.escape(s["name"])}</div>'
           f'<div class="adet">{rating_txt}{dist_txt}</div></div>')


def _neighborhood_section(prop, area, nn):
    dials_html = ''
    if area:
        got = DL.present({}, area)
        if got:
            faces = ''.join(
                f'<div style="display:inline-block;text-align:center;margin:0 14pt 8pt 0;vertical-align:top">'
                f'{DL.gauge(v, size=110, stroke=11, verdict=DL.verdict(v))}'
                f'<div style="font-weight:700;font-size:9pt">{DL.label(k)}</div>'
                f'<div class="cap" style="margin:0">{DL.scope(k, area)}</div></div>'
                for k, v in got)
            dials_html = f'<div style="margin:8pt 0">{faces}</div>'

    schools = prop.get('schools') or []
    schools_html = ''
    if schools:
        items = ''.join(_school_row(s) for s in schools[:6])
        schools_html = f'<h3>Nearby Schools</h3>{items}'

    if not dials_html and not schools_html:
        return ''
    return sec(nn(), 'The Neighborhood') + dials_html + schools_html


def _people_section(prop, demo, origins, nn):
    """Who lives here (Census ACS, ZCTA) and where movers come from (IRS,
    county). Agent-facing context only -- never fed into ad copy (rule 74)."""
    if not demo and not origins:
        return ''
    html = sec(nn(), 'Who Lives Here')

    if demo:
        facts = []
        if demo.get('median_hh_income') is not None:
            facts.append(('MEDIAN HOUSEHOLD INCOME', _money(demo['median_hh_income'])))
        if demo.get('median_age') is not None:
            facts.append(('MEDIAN AGE', f"{demo['median_age']:.1f}"))
        if demo.get('avg_household_size') is not None:
            facts.append(('AVG HOUSEHOLD SIZE', f"{demo['avg_household_size']:.2f}"))
        if demo.get('owner_pct') is not None:
            facts.append(('OWNER-OCCUPIED', f"{demo['owner_pct']:.0f}%"))
        if demo.get('median_home_value') is not None:
            facts.append(('MEDIAN HOME VALUE (ACS)', _money(demo['median_home_value'])))
        if demo.get('population') is not None:
            facts.append(('POPULATION', f"{demo['population']:,}"))
        html += '<div class="cards">' + ''.join(
            f'<div class="card"><div class="k">{k}</div><div class="v" style="font-size:15pt">{v}</div></div>'
            for k, v in facts) + '</div>'

        pay = (prop.get('mortgage_estimate') or {}).get('monthly_payment')
        inc = demo.get('median_hh_income')
        if pay and inc:
            share = round(pay * 12 / inc * 100)
            html += (f'<div class="take"><span class="tag">Affordability</span><p>The estimated '
                     f'{_money(pay)}/mo payment is {share}% of this area\'s median household income '
                     f'({_money(inc)}/yr), above the common 30% guideline -- a buyer at that income would '
                     f'likely need a larger down payment or other assets than the estimate assumes.</p></div>'
                     if share > 30 else
                     f'<div class="take"><span class="tag">Affordability</span><p>The estimated '
                     f'{_money(pay)}/mo payment is {share}% of this area\'s median household income '
                     f'({_money(inc)}/yr).</p></div>')
        html += (f'<p class="cap">{HT.escape(demo["source"])}, {HT.escape(demo["as_of"])}, '
                 f'{HT.escape(demo["scope"])} (the Census Bureau\'s approximation of the ZIP). '
                 f'Estimates carry margins of error that can be wide for smaller areas.</p>')

    if origins:
        rows = ''.join(
            f'<tr><td>{HT.escape(o["place"])}</td><td>{o["people"]:,}</td>'
            f'<td>{o["households"]:,}</td><td>{_money(o["avg_agi"])}</td></tr>'
            for o in origins['origins'])
        html += (f'<h3>Where Movers Into {HT.escape(origins["county"])} Came From</h3>'
                 '<table><thead><tr><th>Moved from</th><th>People</th><th>Households</th>'
                 '<th>Avg income per household</th></tr></thead><tbody>' + rows + '</tbody></table>'
                 f'<p class="cap">{HT.escape(origins["source"])}, {HT.escape(origins["as_of"])} tax years. '
                 'County level -- no source publishes migration by ZIP code. Flows under 20 households '
                 'are suppressed by the IRS. Income is average adjusted gross income per return.</p>')
    return html


def _buyer_section(buyer, nn):
    reasons = ''.join(f'<li>{HT.escape(r)}</li>' for r in buyer['reasons'])
    notes = ''
    if buyer['notes']:
        notes = ('<h3>Also Worth Knowing</h3><ul>'
                + ''.join(f'<li>{HT.escape(n)}</li>' for n in buyer['notes']) + '</ul>')
    return (sec(nn(), 'Who Is The Ideal Buyer')
           + f'<div class="narr"><div class="lead">{HT.escape(buyer["archetype"])}</div>'
           f'<ul>{reasons}</ul></div>' + notes
           + '<p class="cap">Built from this property\'s own characteristics -- bed count, size relative '
           'to nearby listings, school ratings within a fixed radius -- not from any inferred psychographic '
           'or demographic data. For agent planning only -- advertising should describe the property, never the '
           'buyer. See this report\'s methodology note for exactly what this is and isn\'t.</p>')


def _marketing_section(creatives, nn):
    return (sec(nn(), 'Marketing Blueprint', pb=True)
           + f'<div class="mkt"><div class="mkl">Digital / Social</div>'
           f'<div class="mkb" style="white-space:pre-line">{HT.escape(creatives["digital"])}</div></div>'
           + f'<div class="mkt"><div class="mkl">Print</div>'
           f'<div class="mkb" style="white-space:pre-line">{HT.escape(creatives["print"])}</div></div>'
           + f'<div class="mkt"><div class="mkl">Email</div>'
           f'<div class="mkh">{HT.escape(creatives["email"]["subject"])}</div>'
           f'<div class="mkb" style="white-space:pre-line">{HT.escape(creatives["email"]["body"])}</div></div>')


def _methodology(prop, comps, has_area, has_demo=False):
    mls_clause = f'This listing itself is carried on {HT.escape(prop["mls_name"])}' if prop.get('mls_name') else ''
    parts = [
        f'<strong>Source.</strong> Property details, valuation estimates, and nearby listings come from '
        f'RealtyAPI, an unofficial third-party aggregator of Realtor.com data -- not a licensed MLS/RESO '
        f'feed. {mls_clause} '
        f'per RealtyAPI\'s own data.',
        '<strong>Valuation.</strong> The value range shown blends three independent automated valuation '
        'models (Quantarium, Cotality/CoreLogic, Collateral Analytics) that can and do disagree by a wide '
        'margin on the same property -- the range is the honest figure, not any single point estimate '
        'inside it. Any forecast shown is one model\'s own projection, not averaged across sources and not '
        'a guarantee.',
        '<strong>Nearby listings.</strong> Pulled from RealtyAPI\'s search-by-ZIP endpoint at the time this '
        'report was generated. Whether these are filtered to recently-sold comparables specifically has not '
        'been independently confirmed against RealtyAPI\'s own documentation -- treat this table as nearby '
        'market context rather than a certified comparable-sales analysis until that\'s verified.',
    ]
    if has_area:
        parts.append('<strong>Area context</strong> (Rent to Price, Growth Outlook) comes from the same '
                     'bundled Colorado reference pack (Zillow, Census, BLS) used throughout this skill '
                     'family, resolved by this property\'s ZIP code -- not from RealtyAPI.')
    if has_demo:
        parts.append('<strong>Who lives here.</strong> Median income, age, household size, tenure and home '
                     'value come live from the Census Bureau\'s American Community Survey 5-year estimates '
                     'for the property\'s ZCTA. Movers\' origins come from IRS county-to-county migration '
                     'data and describe the county, not the ZIP.')
    parts.append('<strong>Ideal Buyer Profile.</strong> A deterministic classification built from this '
                 'property\'s own characteristics against fixed rules -- not AI-generated, not built from '
                 'demographic or migration data of any kind.')
    parts.append('Information deemed reliable but not guaranteed.')
    return f'<p class="note">{" ".join(parts)}</p>'


def build_html(prop, comps=None, area=None, demo=None, origins=None):
    """prop: from listing_api.get_property(). comps: from
    listing_api.get_comps(), optional. area: from co_data.resolve([zip]) or
    co_data.from_export(), optional -- Rent to Price / Growth Outlook for
    the property's ZIP, when available.
    """
    buyer = buyer_profile.classify_buyer(prop, comps=comps, area=area)
    creatives = listing_marketing.creatives(prop, buyer)
    nn = _N()

    body = (cover(prop)
           + _property_section(prop, nn)
           + _valuation_section(prop, nn)
           + _comps_section(comps, nn)
           + _neighborhood_section(prop, area, nn)
           + _people_section(prop, demo, origins, nn)
           + _buyer_section(buyer, nn)
           + _marketing_section(creatives, nn)
           + _methodology(prop, comps, bool(area), has_demo=bool(demo or origins)))

    return f'<!doctype html><html><head><meta charset="utf-8"><style>{R.CSS}</style></head><body>{body}</body></html>'


def build(address, outdir='/mnt/user-data/outputs'):
    """The single entry point a route calls: takes a plain street address,
    does every lookup itself (property details, comps, area context), and
    writes one PDF. Mirrors master.build()'s shape (a path in, a path out)
    even though everything about how it gets there is different -- one live
    API instead of an uploaded export, no tier/carousel/agent options yet.

    Raises listing_api.ListingAPIError for anything RealtyAPI-side (bad
    address, no key configured, rate limit) -- callers should catch that
    specifically and show a friendly message, the same pattern
    master.build() uses BriefError for.
    """
    import os
    import tempfile

    prop = listing_api.get_property(address)

    comps = []
    if prop.get('zip'):
        try:
            comps = listing_api.get_comps(prop['zip'])
        except listing_api.ListingAPIError:
            pass  # comps are a bonus section, not worth failing the whole report over

    area = None
    if prop.get('zip'):
        try:
            area = co_data.resolve([prop['zip']]).as_dict()
        except Exception:
            area = None  # same discipline as co_data's other callers: omit, never guess

    demo = None
    if prop.get('zip'):
        try:
            demo = census_api.get_demographics(prop['zip'])
        except census_api.CensusAPIError:
            demo = None  # context, not core -- omit the cards, keep the report
    origins = co_data.top_origins(prop['zip']) if prop.get('zip') else None

    html = build_html(prop, comps=comps, area=area, demo=demo, origins=origins)

    os.makedirs(outdir, exist_ok=True)
    slug = (prop.get('address_line') or 'Listing').replace(' ', '_').replace(',', '')
    out_path = os.path.join(outdir, f'{slug}_Listing_Report.pdf')

    with tempfile.TemporaryDirectory(prefix='listing_') as tmp:
        html_path = os.path.join(tmp, 'report.html')
        with open(html_path, 'w') as f:
            f.write(html)

        async def go():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                b = await p.chromium.launch()
                pg = await b.new_page()
                await pg.goto('file://' + html_path)
                await pg.pdf(path=out_path, format='Letter', print_background=True)
                await b.close()

        import asyncio
        asyncio.run(go())

    return out_path, prop, comps, area
