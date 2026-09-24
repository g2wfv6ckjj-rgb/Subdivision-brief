import sys, pandas as pd, numpy as np, html as HT, pathlib, math
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from core import *
import charts as C
from reports import CSS, cover, bands, methodology, REPORT_NOUN
from core import FIN, piti, fin_metrics, compare_row, set_county, check_rate, BriefError
from local import PROFILES, scorecard
import monthly as MO
import marketing as MK


FIN_SEC = """
<div class="sec pb"><span class="num">{nfin}</span><h2>Financing &amp; monthly payment</h2></div>
<p>Every buyer who closed here in the last year used {finmix}. What follows estimates the full monthly payment &mdash; principal, interest, taxes and insurance &mdash; using the actual tax bills recorded on these homes.</p>
<div class="cards">
<div class="card"><div class="k">Median annual property tax</div><div class="v">{taxm}</div><span class="d">{taxlo} to {taxhi} across sales</span></div>
<div class="card"><div class="k">Effective tax rate</div><div class="v">{taxrate}%</div><span class="d">Of the purchase price</span></div>
<div class="card"><div class="k">Median HOA dues</div><div class="v">{hoam}</div><span class="d">{hoanote}</span></div>
</div>
<div class="take"><span class="tag">Worth knowing</span><p>{hoaline}</p></div>
<h3>Monthly payment on the median {medp} purchase</h3>
{pititbl}
<p class="cap">Principal and interest at {rate}% on a 30-year fixed ({ratesrc}). Taxes use the median annual bill recorded on sales in this subdivision. Insurance and mortgage insurance are estimates &mdash; confirm both with your lender and insurance agent.</p>
<h3>What each home for sale would cost per month</h3>
{actpiti}
<p class="cap">Each estimate uses that specific home&rsquo;s recorded annual tax bill. Same rate and insurance assumptions as above.</p>
{cashblk}
<h3>Loan types and down payment options</h3>
{loantbl}
<div class="take"><span class="tag">The conforming line</span><p>The 2026 conforming loan limit in {county} is <strong>{limit}</strong>. {jumboline}</p></div>
"""

CMP_FULL = """
<div class="sec pb"><span class="num">{ncmp}</span><h2>Comparing subdivisions</h2></div>
<p>{sub} is the primary neighborhood; the others are shown on identical definitions so they can be weighed on the same terms.</p>
{tbl}
<p class="cap">Every column is built from that subdivision&rsquo;s own 365-day MLS export using the same calculations. Small sale counts mean these are directional comparisons, not precise rankings.</p>
"""


MOM_METRICS = [
    ('med_close', 'Median closed price',   'line', dict(money=True),  'Median price of the homes that closed in each month.'),
    ('med_dom',   'Median days on market', 'line', dict(unit=' days'),'Median days from listing to accepted offer, by month of closing.'),
    ('new',       'New listings',          'bar',  dict(),            'Homes newly listed in each month.'),
    ('total',     'Total listings',        'bar',  dict(),            'Homes available at any point in the month &mdash; those carried in from earlier months plus the new ones.'),
    ('pending',   'Went under contract',   'bar',  dict(),            'Homes that accepted an offer in each month.'),
    ('closed',    'Closed sales',          'bar',  dict(),            'Sales that completed in each month.'),
    ('msi',       'Months of supply',      'line', dict(dec=1),       'Active listings at month end against the trailing three-month sales pace.'),
]

def _chip(dd, head, money=False, dec=0):
    """One (heading, big, sub-lines, negative) tuple for the in-chart change panel."""
    if dd is None:
        return (head, '&mdash;', ['not computable'], False)
    txt, note = MO.fmt_delta(dd)
    # Both ends of the change panel share one precision so "$883K -> $1.1M" cannot
    # render one side at a different scale from the other.
    fm = mshort_series([dd['prev'], dd['cur']]) if money else (lambda v: f'{v:,.{dec}f}')
    neg = dd['pct'] is not None and dd['pct'] < 0
    sub = [f'{fm(dd["prev"])} &rarr; {fm(dd["cur"])}']
    if note:
        sub.append(note)
    if not dd['adjacent']:
        sub.append(f'{dd["prev_m"][:3]}&ndash;{dd["cur_m"][:3]}, skips empty month')
    return (head, txt, sub, neg)

def mom_block(d, num):
    """Month-over-month section. Series are reconstructed from the export's own event
    dates; see monthly.py for the two structural limits, both disclosed below."""
    b = MO.build(d)
    if not b: return ''
    yoy_ok = MO.yoy_available(d)
    body = ''
    for key, title, style, opts, cap in MOM_METRICS:
        ser = b['series'][key]
        keys = b['keys'] if b['multi'] else [MO.ALL]
        money = opts.get('money', False); dec = opts.get('dec', 0)
        # Deltas are computed on the extended span so year-over-year has a
        # prior-year month to reach back to; only the last 12 months are charted.
        ve = b['series_ext'][key][MO.ALL]
        mm = MO.mom(ve, b['months_ext'])
        yy = MO.yoy(ve, b['months_ext']) if yoy_ok else None
        chips = [_chip(mm, 'MONTH OVER MONTH', money, dec)]
        if yoy_ok:
            chips.append(_chip(yy, 'YEAR OVER YEAR', money, dec))
        if style == 'line':
            # Lines keep the combined series: an overall median is a real figure in
            # its own right, not the sum of the per-type ones.
            chart = C.mom_line(b['labels'], ser, keys, money=money, dec=dec, chips=chips)
        else:
            # Counts stack, and the combined series is dropped because it is exactly
            # the sum of the segments and would be drawn twice.
            bk = b['types'] if b['multi'] else [MO.ALL]
            chart = C.mom_bars(b['labels'], ser, bk, dec=dec, stacked=b['multi'], chips=chips)
        body += (f'<h3>{title}</h3>\n'
                 f'<div class="chart">{chart}</div>\n<p class="cap">{cap}</p>\n')
    span = f"{b['full'][0]} through {b['full'][-1]}"
    note = ('<div class="take"><span class="tag">How to read this section</span><p>'
            f'These twelve months run {span}. The current partial month is excluded, because a '
            'half-finished month reads as a collapse in every count. '
            'Monthly medians rest on very few sales at subdivision scale, so single-month moves in price '
            'and days on market should be read as noise unless the direction holds across several months. '
            'Listing counts and months of supply are reconstructed from listing, contract and closing '
            'dates, so the earliest month or two understates inventory: homes that left the market just '
            'before this window opened are not in the file.</p></div>')
    return (f'<div class="sec pb"><span class="num">{num}</span><h2>Month over month</h2></div>\n'
            f'<p>Each of the seven measures below is plotted across the twelve complete months in this '
            f'export, with the change into the most recent month shown beside it.</p>\n{note}\n{body}')

def callout_block(d, m, cl, act, exp, audience, num):
    """Notable call-outs. Content is produced by core.callouts(), which branches on
    this export's own metrics, so the list changes from subdivision to subdivision
    and between the two audiences. Never hand-write items here."""
    items = callouts(d, m, cl, act, exp, audience)
    if not items: return ''
    body = ''.join(f'<div class="take"><span class="tag">{c["title"]}</span>'
                   f'<p>{c["text"]}</p></div>' for c in items)
    return (f'<div class="sec pb"><span class="num">{num}</span>'
            f'<h2>What stands out{" for buyers" if audience=="buyer" else " this year"}</h2></div>\n'
            f'<p>The points below are the ones this subdivision&rsquo;s own numbers surface as unusual. '
            f'They are recalculated for every export, so a different neighborhood &mdash; or this one next '
            f'year &mdash; will surface a different list.</p>\n{body}\n')

def outlier_block(cl, m):
    """High and low sale of the year, with the characteristics the export supports
    as explanations. Rendered at the end of the year-in-numbers section."""
    rows = outliers(cl, m)
    if not rows: return ''
    body = ''.join(f'<li>{r}</li>' for r in rows)
    return ('<h3>The outliers, and what explains them</h3>\n'
            f'<div class="talk"><ul>{body}</ul></div>\n'
            '<p class="cap">Explanations are limited to characteristics recorded in the MLS export &mdash; '
            'size, condition language in the listing remarks, lot, garage, basement, days on market and '
            'credits. Other factors not captured in the export may also be at work.</p>\n')

def schools_amenities(sub, d, audience, n1='10', n2='11', auto=None):
    """Nearby Schools + Nearby Amenities. School names come from the MLS export;
    ratings and amenities come from local.PROFILES."""
    prof=PROFILES.get(sub)

    def mlsnames(col):
        """Every school recorded on the column, with its listing count, most common
        first. A subdivision -- and especially a master area merging several MLS
        subdivision names -- routinely spans more than one attendance area. Taking
        unique()[0] and calling it 'every home' was factually wrong wherever that
        happened, which is most places."""
        if col not in d: return []
        v=d[col].dropna().astype(str).str.strip()
        v=v[(v!='') & (v.str.lower()!='other') & (v.str.lower()!='nan')]
        return list(v.value_counts().items())

    def phrase(col, suffix):
        got=mlsnames(col)
        if not got: return None
        tot=sum(n for _,n in got)
        if len(got)==1: return f'{got[0][0]} {suffix}'
        return ', '.join(f'{nm} {suffix} ({n} of {tot})' for nm,n in got)

    def mlsname(col):
        got=mlsnames(col)
        return got[0][0] if got else None

    el,mi,hi=phrase('Elementary School','Elementary'),phrase('Middle Or Junior School','Middle'),phrase('High School','High')
    dist=mlsname('Elementary School District')
    _multi=any(len(mlsnames(c))>1 for c in ('Elementary School','Middle Or Junior School','High School'))
    _lede=('Homes in this report are listed across more than one attendance area. '
           'Counts below are the listings recorded for each school in the export.'
           if _multi else 'Every home in this report is listed as assigned to')
    if not prof and auto:
        return _auto_block(auto, dist, _lede, el, mi, hi, n1, n2)
    if not prof:
        listed=' &#183; '.join(x for x in [el, mi, hi] if x)
        pend=('<div style="border:1.2pt dashed var(--line);border-radius:5pt;padding:14pt 16pt;margin:9pt 0">'
              '<p style="margin:0;font-size:9.6pt;color:var(--soft)">Ratings and nearby amenities have not been '
              'compiled for this subdivision yet. Add an entry keyed to the subdivision name in '
              '<code>local.PROFILES</code> to populate these two sections.</p></div>')
        return f'''<div class="sec pb"><span class="num">{n1}</span><h2>Nearby schools</h2></div>
<p>{_lede} {listed or 'schools not recorded in the export'}{f", within {dist}" if dist else ""}.</p>
<p class="cap">Assigned-school fields are entered by the listing agent and are not a boundary
verification. Confirm current enrollment with the district before relying on them.</p>
{pend}
<div class="sec"><span class="num">{n2}</span><h2>Nearby amenities</h2></div>
{pend}'''
    rows=''
    for sc in prof['schools']:
        rows+=(f'<tr><td>{sc["level"]}</td><td>{sc["name"]}</td><td>{sc["grades"]}</td>'
               f'<td class="g">{sc["gs"]}/10</td><td>{sc["niche"]}</td><td style="white-space:normal">{sc["usnews"]}</td></tr>')
    notes=''.join(f'<li><strong>{sc["name"]}</strong> &mdash; {sc["note"]}</li>' for sc in prof['schools'])
    amen=''
    for a in prof['amenities']:
        amen+=(f'<div class="amen"><div class="acat">{a["cat"]}</div>'
               f'<div class="aname">{a["name"]}</div>'
               f'<p class="adet">{a["detail"]}</p>'
               f'<p class="awhy">{a["why"]}</p></div>')
    lead = ('Buyers consistently ask about schools first. Here is what the assigned schools actually score, '
            'with each rating shown as its source publishes it.') if audience=='Buyer' else (
            'These are the schools recorded on the listings in this report, and how they are rated by the '
            'three sources buyers check most often.')
    return f'''<div class="sec pb"><span class="num">{n1}</span><h2>Nearby schools</h2></div>
<p>{lead} Listings here fall within <strong>{prof['district']}</strong>.</p>
<p class="cap">{_lede} {' &#183; '.join(x for x in [el, mi, hi] if x)}. Assigned-school fields are entered by
the listing agent and are not a boundary verification &mdash; confirm current enrollment with the district.</p>
<div class="chart">{scorecard(prof)}</div>
<p class="cap">Each rating is shown exactly as its publisher reports it. The three use different scales and weight
different things, so they are not combined into a single score &mdash; GreatSchools rates 1&ndash;10, Niche issues a
letter grade, and U.S. News publishes a state ranking and does not rank elementary schools at all.</p>
<table>
  <thead><tr><th>Level</th><th>School</th><th>Grades</th><th>GreatSchools</th><th>Niche</th><th>U.S. News</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<h3>Worth knowing</h3>
<ul>{notes}</ul>
<div class="take"><span class="tag">Reading these fairly</span><p>Ratings are one input among many and each publisher weights different things &mdash; test scores, growth, equity, reviews, college readiness. <strong>School assignments and boundaries change.</strong> Confirm current enrollment with {prof['district']} directly before relying on it, and visit the schools that matter to you.</p></div>

<div class="sec pb"><span class="num">{n2}</span><h2>Nearby amenities</h2></div>
<p>What sits within easy reach of the subdivision, drawn from city, state and operator sources.</p>
{amen}
<p class="cap">Locations and features verified against Colorado Parks &amp; Wildlife, the City of Thornton, and facility
operators, {prof['retrieved']}. Distances are approximate &mdash; confirm drive times for any property you are
seriously considering.</p>'''

def _auto_block(auto, dist, lede, el, mi, hi, n1, n2):
    """Render the profile enrich.py derived from public data.

    Deliberately NOT the same table as the hand-built path: there is no
    GreatSchools 1-10, Niche grade or U.S. News rank here, because those are not
    fetchable under their licences. Showing an empty column for them would imply
    a rating exists and is merely missing. Rule 8 still holds -- nothing is
    combined into a composite.
    """
    rows = ''
    for s in auto.get('schools', []):
        rating = s.get('cde_rating') or '&mdash;'
        rows += (f'<tr><td>{s["level"]}</td><td>{s.get("name") or s["mls_name"]}</td>'
                 f'<td>{s["listings"]}</td><td>{s.get("grades", "&mdash;")}</td>'
                 f'<td>{s.get("enrollment") or "&mdash;"}</td>'
                 f'<td>{s.get("ratio") or "&mdash;"}</td>'
                 f'<td style="white-space:normal">{rating}</td></tr>')
    unmatched = [s for s in auto.get('schools', []) if not s.get('matched')]
    src = auto.get('school_source', 'the MLS export')
    spf = auto.get('spf_source')
    miss = ('' if not unmatched else
            '<p class="cap">' + ', '.join(s['mls_name'] for s in unmatched) +
            ' could not be matched to a federal directory record from the name recorded in the '
            'export, so those rows carry the listing name only. An unmatched school is left '
            'blank rather than matched to the nearest similar name.</p>')

    amen = ''
    for a in auto.get('amenities', []):
        amen += (f'<div class="amen"><div class="acat">{a["cat"]}</div>'
                 f'<div class="aname">{a["name"]}</div>'
                 f'<p class="adet">{a["detail"]}</p>'
                 f'<p class="awhy">{a.get("kind", "")}</p></div>')
    if not amen:
        amen = ('<div style="border:1.2pt dashed var(--line);border-radius:5pt;padding:14pt 16pt;'
                'margin:9pt 0"><p style="margin:0;font-size:9.6pt;color:var(--soft)">Nearby '
                'amenities were not retrieved for this run. Supply a Google Places API key to '
                'populate this section.</p></div>')
        attrib = ''
    else:
        attrib = ('<p class="cap">Places data &copy; Google. Listed by straight-line distance '
                  'from the centre of the listings in this export, not by any measure of '
                  'quality or desirability.</p>')

    return f'''<div class="sec pb"><span class="num">{n1}</span><h2>Nearby schools</h2></div>
<p>{lede} {" &#183; ".join(x for x in [el, mi, hi] if x)}{f", within {dist}" if dist else ""}.</p>
<table><thead><tr><th>Level</th><th>School</th><th>Listings</th><th>Grades</th>
<th>Enrollment</th><th>Students per teacher</th><th>State framework rating</th></tr></thead>
<tbody>{rows}</tbody></table>
{miss}
<p class="cap">Directory figures from {src}.{f" State accountability rating from the {spf}." if spf else
" No state accountability rating was attached for this run."} Ratings are reported exactly as the
publisher states them and are never combined into a single score. GreatSchools, Niche and U.S. News
ratings are not shown here: they are not available under a licence this pipeline holds. Assigned-school
fields are entered by the listing agent and are not a boundary verification &mdash; confirm current
enrollment with the district.</p>
<div class="sec"><span class="num">{n2}</span><h2>Nearby amenities</h2></div>
{amen}
{attrib}'''


def cash_block(m, audience):
    """Cash vs financed purchases. Rendered inside the escrow section of the Seller
    brief and the financing section of the Buyer brief, because that is where the
    timing consequence lands for each audience. Text comes from core.cash_point(),
    which branches on the measured gap."""
    pt = cash_point(m, audience)
    if not pt: return ''
    n = m['n_fin_known']
    cpo = ('<div class="card"><div class="k">Avg % of original ask</div>'
           f'<div class="v">{m["cash_cpo"]:.1f}%</div>'
           f'<span class="d">Cash &#183; financed paid {m["fin_cpo"]:.1f}%</span></div>'
           ) if m['n_cash'] and m['n_fin'] else ''
    esc = ('<div class="card"><div class="k">Median offer to closing</div>'
           f'<div class="v">{m["cash_ptc"]:.0f} days</div>'
           f'<span class="d">Cash &#183; financed took {m["fin_ptc"]:.0f} days</span></div>'
           ) if m['n_cash'] >= 3 and m['n_fin'] >= 3 else ''
    return (f'<h3>Cash buyers vs. financed buyers</h3>\n<div class="cards">'
            f'<div class="card"><div class="k">Bought with cash</div>'
            f'<div class="v">{m["n_cash"]} of {n}</div>'
            f'<span class="d">{m["cash_pct"]:.0f}% of sales &#183; {m["n_fin"]} used a loan</span></div>'
            f'{esc}{cpo}</div>\n'
            f'<div class="take"><span class="tag">What the financing mix means</span><p>{pt}</p></div>\n'
            f'<p class="cap">Based on the {n} closed sales that recorded a buyer financing type. '
            f'Cash counts only listings recorded exactly as cash; every other recorded type is '
            f'treated as financed. With counts this small these are directional figures.</p>\n')

def _tbl(rows,head):
    th=''.join(f'<th>{h}</th>' for h in head)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>'

def seller_html(d,m,cl,act,exp,sub,city):
    gb=bands(cl); bl=list(gb.iloc[:,0].astype(str))
    pace=lambda x: 'Moves fast' if x<=20 else ('Steady' if x<=30 else ('Slower' if x<=50 else 'Takes patience'))
    pcls=lambda x: 'p1' if x<=20 else ('p2' if x<=30 else ('p3' if x<=50 else 'p4'))
    prow=''.join(f'<tr><td>{r.iloc[0]}</td><td>{int(r["n"])}</td><td>{int(r["dtc"])} days</td>'
        f'<td>{r["cpo"]:.1f}%</td><td>{int(round(r["red"]*100))}%</td>'
        f'<td><span class="pillt {pcls(r["dtc"])}">{pace(r["dtc"])}</span></td></tr>' for _,r in gb.iterrows())
    red=cl[cl['red']].sort_values('ttl')
    rrow=''.join(f'<tr><td>{r["addr"]}</td><td>{M(r["Original List Price"])}</td><td class="o">&minus;{M(r["cut"])}</td>'
        f'<td>{M(r["Close Price"])}</td><td>{int(r["Days In MLS"])}</td><td>{int(r["ptc"])}</td>'
        f'<td class="o">{int(r["ttl"])}</td></tr>' for _,r in red.iterrows())
    rrow+=f'<tr><td><em>Median, no adjustment</em></td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td>'\
          f'<td class="g">{cl[~cl["red"]]["Days In MLS"].median():.0f}</td><td>{cl[~cl["red"]]["ptc"].median():.0f}</td>'\
          f'<td class="g">{m["ttl_nored"]:.0f}</td></tr>'
    arow=''.join(f'<tr><td>{r["addr"]}</td><td>{int(r["Bedrooms Total"])}</td><td>{"Ranch" if str(r["Levels"]).startswith("One") else "Two-story"}</td>'
        f'<td>{int(r["Living Area"]):,}</td><td>{M(r["Original List Price"])}</td><td>{M(r["List Price"])}</td>'
        f'<td>{int(r["Days In MLS"])}</td></tr>' for _,r in act.sort_values('List Price',ascending=False).iterrows())
    erow=''.join(f'<tr><td>{r["addr"]}</td><td>{M(r["Original List Price"])} &rarr; {M(r["List Price"])}</td>'
        f'<td class="o">Did not sell, {int(r["Days In MLS"])} days</td><td>{int(r["Living Area"]):,} sq ft</td></tr>' for _,r in exp.iterrows())
    nchg=cl['nchg'].value_counts()
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{sub} Seller {REPORT_NOUN}</title><style>{CSS}</style></head><body>
{cover(sub,city,'SELLER')}
<div class="narr"><p class="lead">Over the last year {m['n_cl']} homes sold in {sub}, and the ones priced accurately on day one were rewarded quickly.</p>
<p>The median sale closed at {M(m['med'])} after about {m['dtc_med']:.0f} days on the market, and {m['at_or_above']} of {m['n_cl']} sellers collected their original asking price or better. Sellers kept an average of {m['cpo']:.1f}% of what they first asked.</p>
<p>Homes that started above the market took several months and a price adjustment to find a buyer. They still sold &mdash; the difference was time and net proceeds. This report shows exactly what that difference cost.</p></div>

<div class="sec"><span class="num">01</span><h2>Market conditions</h2></div>
<div class="chart">{C.gauge(m)}</div>
<p class="cap">Months of supply estimates how long it would take to sell every home currently listed at the recent pace of sales. The standard breakpoints are <strong>under 3 months a seller&rsquo;s market, 3&ndash;6 balanced or neutral, over 6 a buyer&rsquo;s market</strong>.</p>

<div class="sec pb"><span class="num">02</span><h2>The year in numbers</h2></div>
<div class="cards">
<div class="card"><div class="k">Homes sold</div><div class="v">{m['n_cl']}</div><span class="d">In the last 12 months</span></div>
<div class="card"><div class="k">Sales volume</div><div class="v">${m['vol']/1e6:.1f}M</div><span class="d">Combined</span></div>
<div class="card"><div class="k">Median sale price</div><div class="v">{M(m['med'])}</div><span class="d">{M(m['lo'])} to {M(m['hi'])}</span></div>
<div class="card"><div class="k">Sale to original list price</div><div class="v">{m['cpo']:.1f}%</div><span class="d">Average, against the first price published</span></div>
<div class="card"><div class="k">Median $ per sq ft</div><div class="v">${m['psf_med']:,.0f}</div><span class="d">Finished space</span></div>
<div class="card"><div class="k">Median days to an offer</div><div class="v">{m['dtc_med']:.0f}</div><span class="d">{m['fast']} sold in a week or less</span></div>
</div>
<div class="take"><span class="tag">What this means</span><p><strong>{m['at_or_above']} of {m['n_cl']} sellers got their first asking price or better</strong>, and {m['fast14']} of {m['n_cl']} were under contract inside two weeks. Accurate pricing is being met with fast, full-price offers.</p></div>

<h3>How each price range behaved</h3>
{_tbl(prow,['Price range','Homes sold','Median days to an offer','Average % of first asking price','Needed a price change','Pace'])}
<p class="cap">Bands are set at the thirds of this subdivision&rsquo;s own sale prices, so each group holds a similar number of homes.</p>

{outlier_block(cl,m)}

{mom_block(d,'03')}
<div class="sec pb"><span class="num">04</span><h2>Every listing in the last year</h2></div>
<div class="chart">{C.waffle(m)}</div>
<p class="cap">{m['n_cl']} sold &#183; {m['n_act']} currently for sale &#183; {m['n_exp']} neither sold nor remain openly for sale &mdash; of those, {m['n_fail']} expired or were withdrawn and {m['n_pend']} are under contract.</p>
{('<h3>The listings that did not sell</h3>'+_tbl(erow,['Address','Asking price journey','Result','Size'])) if len(exp) else ''}

<div class="sec pb"><span class="num">05</span><h2>What sellers asked &mdash; and what they got</h2></div>
<p>Each row is one home. The open circle is the price it was first listed at. The filled circle is what it sold for.</p>
<div class="chart">{C.dumbbell(cl)}</div>
<p class="cap">Every figure here is measured against the <em>original</em> asking price &mdash; the first number published, before any reduction. {m['above_orig']} homes sold above it, {m['at_orig']} at it and {m['under_orig']} below, averaging {m['cpo']:.1f}% of the first ask. Measuring against a reduced price instead would count a home that cut its price and then sold at the lower number as a full-price sale, which hides the reduction the seller actually took.</p>

<div class="sec pb"><span class="num">06</span><h2>How fast homes found a buyer</h2></div>
<div class="chart">{C.speed(cl)}</div>
<p class="cap">Time from the day a home hit the market to the day an offer was accepted.</p>
{('<div class=\"take\"><span class=\"tag\">What right pricing buys</span><p>'+rightpriced_point(m,'seller')+'</p></div>') if rightpriced_point(m,'seller') else ''}

<div class="sec"><span class="num">07</span><h2>Seller credits at closing</h2></div>
<div class="cards">
<div class="card"><div class="k">Sales including a credit</div><div class="v">{m['conc_n']} of {m['n_cl']}</div><span class="d">{m['conc_n']/m['n_cl']*100:.0f}% of sales</span></div>
<div class="card"><div class="k">Median credit where paid</div><div class="v">{M(m['conc_med'])}</div><span class="d">Median amount</span></div>
<div class="card"><div class="k">Total credits paid</div><div class="v">{M(m['conc_tot'])}</div><span class="d">Across all {m['n_cl']} sales</span></div>
</div>
<div class="chart">{C.strip(sorted(cl[cl['conc']>0]['conc'].tolist()),0,max(cl['conc'].max()*1.1,1000),med=m['conc_med'],label='seller credit paid, in dollars')}</div>
<p class="cap">A credit is money the seller puts toward the buyer&rsquo;s closing costs or mortgage rate buy-down. It comes off the seller&rsquo;s proceeds, so it belongs in the net sheet from day one.</p>

<div class="sec pb"><span class="num">08</span><h2>Once an offer is accepted</h2></div>
<div class="chart">{C.strip(sorted(cl['ptc'].dropna().astype(int).tolist()),max(0,m['ptc_min']-6),m['ptc_max']+6,band=(m['ptc_min'],46,f'{int((cl["ptc"]<=46).sum())} OF {m["n_cl"]} CLOSED IN THIS WINDOW'),med=m['ptc_med'],unit=' days',label='days from accepted offer to closing')}</div>
<p class="cap">Every sale closed between {m['ptc_min']:.0f} and {m['ptc_max']:.0f} days after the offer was accepted.</p>
<div class="take"><span class="tag">Planning note</span><p>{escrow_point(m)}</p></div>
{cash_block(m,'seller')}

<div class="sec pb"><span class="num">09</span><h2>What happens when the price is adjusted</h2></div>
<div class="cards">
<div class="card"><div class="k">Priced right at launch</div><div class="v">{m['ttl_nored']:.0f} days</div><span class="d">Listing to closing &#183; {m['no_change']} homes</span></div>
<div class="card"><div class="k">After a price adjustment</div><div class="v">{m['ttl_red']:.0f} days</div><span class="d">Listing to closing &#183; {m['changed']} homes</span></div>
<div class="card"><div class="k">Price never changed</div><div class="v">{int(nchg.get(0,0))}</div><span class="d">Changed once: {int(nchg.get(1,0))} &#183; twice or more: {int(nchg.get(2,0))}</span></div>
</div>
<div class="chart">{C.timelines(cl)}</div>
<p class="cap">Bronze is time spent waiting for an offer; navy is the escrow period afterward. The navy portion barely changes. All of the extra time comes from the search for a buyer &mdash; which is what the asking price controls.</p>
{_tbl(rrow,['Address','First asking price','Adjustment','Sold for','Days to offer','Offer to closing','Total days'])}
<div class="take"><span class="tag">The takeaway</span><p>A price adjustment works &mdash; every adjusted listing here found a buyer. <strong>The variable is timing.</strong> Adjust once and early and the runway stays short; adjust in steps and it stretches.</p></div>

<div class="sec pb"><span class="num">10</span><h2>What&rsquo;s on the market now</h2></div>
{_tbl(arow,['Address','Beds','Style','Finished sq ft','First asking price','Current price','Days on market'])}
<p class="cap">These are the homes a new listing would compete against today. Median asking price among them is {M(m['act_med_list'])}.</p>

{schools_amenities(sub,d,'Seller','11','12')}

{callout_block(d,m,cl,act,exp,'seller','13')}
<div class="sec pb"><span class="num">14</span><h2>Talking points</h2></div>
<div class="talk"><h4>On pricing</h4><ul>
<li>&ldquo;{seller_price_point(m)}&rdquo;</li>
<li>&ldquo;{m['fast14']} of {m['n_cl']} went under contract within two weeks. If we are still sitting at day fourteen, the market is telling us something.&rdquo;</li></ul></div>
<div class="talk"><h4>On price adjustments</h4><ul>
<li>&ldquo;{adjust_point(m)}&rdquo;</li></ul></div>
<div class="talk"><h4>On credits and net proceeds</h4><ul>
<li>&ldquo;{m['conc_n']} of {m['n_cl']} sales included a credit to the buyer, a median of {M(m['conc_med'])}. Let&rsquo;s build that into the net sheet now rather than negotiate it at day sixty.&rdquo;</li></ul></div>
<div class="talk"><h4>On timing</h4><ul>
<li>&ldquo;{escrow_point(m)}&rdquo;</li></ul></div>
{MK.section(d,m,sub,city,'seller','15',MO.build(d))}
{methodology(m,sub)}
</body></html>'''

def buyer_html(d,m,cl,act,exp,sub,city,compares=None,cfg=None):
    cfg = cfg or FIN
    ranch=lambda r: 'Ranch' if str(r).startswith('One') else 'Two-story'
    act=act.sort_values('List Price',ascending=False)
    # inventory mix
    mixbeds=[]
    for b in sorted(set(list(act['Bedrooms Total'].dropna().astype(int))+list(cl['Bedrooms Total'].dropna().astype(int)))):
        na=int((act['Bedrooms Total']==b).sum()); ns=int((cl['Bedrooms Total']==b).sum())
        mixbeds.append((f'{b} bedroom',na,f'{ns} sold in the last year'))
    mixstyle=[]
    for st in ['One','Two']:
        na=int(act['Levels'].astype(str).str.startswith(st).sum()); ns=int(cl['Levels'].astype(str).str.startswith(st).sum())
        mixstyle.append((ranch(st),na,f'{ns} sold in the last year'))
    lev=[]
    for _,r in act.iterrows():
        dom=int(r['Days In MLS']); cut=r['Original List Price']-r['List Price']
        if dom>=90: sc,lab='p1','Strong'
        elif dom>=45: sc,lab='p2','Moderate'
        elif dom>=15: sc,lab='p3','Limited'
        else: sc,lab='p4','Minimal'
        lev.append(f'<tr><td>{r["addr"]}</td><td>{M(r["List Price"])}</td><td>{dom}</td>'
                   f'<td>{"&minus;"+M(cut) if cut>0 else "None yet"}</td>'
                   f'<td><span class="pillt {sc}">{lab}</span></td></tr>')
    arow=''.join(f'<tr><td>{r["addr"]}</td><td>{int(r["Bedrooms Total"])}</td><td>{ranch(r["Levels"])}</td>'
        f'<td>{int(r["Living Area"]):,}</td><td>{int(r["Year Built"])}</td><td>{M(r["List Price"])}</td>'
        f'<td>${r["PSF Finished"]:,.0f}</td><td>{int(r["Days In MLS"])}</td></tr>' for _,r in act.iterrows())
    fin=', '.join(f'{k} ({v})' for k,v in m['fin'].items())
    fm=fin_metrics(cl,act); med=m['med']
    rows=''
    for dp in (0.05,0.10,0.20):
        q=piti(med,dp,fm['tax_med'],fm['hoa_med'],cfg=cfg)
        rows+=(f'<tr><td>{int(dp*100)}% down &mdash; {M(q["down_amt"])}</td><td>{M(q["loan"])}</td>'
               f'<td>{M(q["pi"])}</td><td>{M(q["tax"])}</td><td>{M(q["ins"])}</td>'
               f'<td>{M(q["mi"]) if q["mi"] else "&mdash;"}</td><td class="g">{M(q["total"])}</td></tr>')
    pititbl=_tbl(rows,['Down payment','Loan amount','Principal &amp; interest','Taxes','Insurance','Mortgage insurance','Estimated monthly'])
    arows=''
    for _,r in act.iterrows():
        q10=piti(r['List Price'],0.10,r['Tax Annual Amount'],fm['hoa_med'],cfg=cfg)
        q20=piti(r['List Price'],0.20,r['Tax Annual Amount'],fm['hoa_med'],cfg=cfg)
        arows+=(f'<tr><td>{r["addr"]}</td><td>{M(r["List Price"])}</td><td>{M(r["Tax Annual Amount"]/12)}</td>'
                f'<td>{M(q10["total"])}{" <em>jumbo</em>" if q10["jumbo"] else ""}</td>'
                f'<td class="g">{M(q20["total"])}</td></tr>')
    actpiti=_tbl(arows,['Address','Asking price','Monthly taxes','Monthly at 10% down','Monthly at 20% down'])
    ln=[('Conventional, 20% down','20%','No mortgage insurance. Lowest monthly payment and the strongest-looking offer.'),
        ('Conventional, 5&ndash;15% down','5%','Mortgage insurance applies until you reach 20% equity, then it drops off.'),
        ('FHA','3.5%','Lower credit thresholds; mortgage insurance generally stays for the life of the loan.'),
        ('VA','0%','No down payment and no mortgage insurance for eligible service members and veterans.'),
        ('Jumbo','20&ndash;30%','Required above the conforming limit. Tighter credit and reserve requirements.')]
    used=set(m['fin'].keys())
    loanrows=''.join(f'<tr><td>{a}</td><td>{b}</td><td style="white-space:normal">{c}</td>'
        f'<td>{"Used here" if a.split(",")[0] in used else "&mdash;"}</td></tr>' for a,b,c in ln)
    loantbl=_tbl(loanrows,['Loan type','Common minimum down','Notes','In this subdivision'])
    hi=act['List Price'].max() if len(act) else med
    j5=piti(hi,0.05,fm['tax_med'],cfg=cfg)
    jumboline=(f'At the top of current inventory ({M(hi)}), a 5% down loan of {M(j5["loan"])} would cross into jumbo territory, '
               f'while 10% down stays conforming. On most homes here, a modest increase in down payment keeps the loan &mdash; and the rate &mdash; conventional.')
    hoaline=(f'HOA dues are recorded as {fm["hoa_note"].lower()} on most sales here, and the median annual HOA figure is {M(fm["hoa_med"])}. '
             f'That is why the effective tax rate of {fm["tax_rate"]*100:.2f}% runs higher than a typical Colorado bill &mdash; the neighborhood services are funded through the tax bill rather than a separate HOA payment. Budget for the tax, not for dues.')
    # Month over month is section 03, so everything downstream shifts by one.
    nfin,nsch,namen='07','08','09'
    ncmp='10' if compares else None
    # Call-outs sit immediately before the talking points, so both trail the
    # optional comparison section and stay sequential whether or not it renders.
    nco=f"{(11 if compares else 10):02d}"
    ntalk=f"{(12 if compares else 11):02d}"
    nmkt=f"{(13 if compares else 12):02d}"
    FINSEC=FIN_SEC.format(nfin=nfin, finmix=fin.lower() if fin else 'conventional financing', taxm=M(fm['tax_med']),
        taxlo=M(fm['tax_lo']), taxhi=M(fm['tax_hi']), taxrate=f"{fm['tax_rate']*100:.2f}",
        hoam=M(fm['hoa_med']), hoanote=fm['hoa_note'], hoaline=hoaline, medp=M(med),
        pititbl=pititbl, actpiti=actpiti, loantbl=loantbl, cashblk=cash_block(m,'buyer'), rate=f"{cfg['rate']*100:.2f}",
        ratesrc=cfg['rate_src'], county=cfg['county'], limit=M(cfg['conforming']), jumboline=jumboline)
    CMPSEC=''
    if compares:
        heads=['Measure',f'{sub} <em>(primary)</em>']+[c['label'] for c in compares]
        allr=[dict(label=sub,med=m['med'],dtc=m['dtc_med'],moi=m['moi'],n_act=m['n_act'],
                   pct_at=m['at_or_above']/m['n_cl']*100,under=m['under_orig'],n_cl=m['n_cl'],
                   conc_med=m['conc_med'],psf=m['psf_med'],cpo=m['cpo'],ptc=m['ptc_med'])]+list(compares)
        defs=[('Median sale price',lambda c:M(c['med'])),('Median days to an offer',lambda c:f"{c['dtc']:.0f}"),
              ('Months of supply',lambda c:f"{c['moi']:.1f}"),('Homes for sale now',lambda c:str(c['n_act'])),
              ('Sold at or above first asking price',lambda c:f"{c['pct_at']:.0f}%"),
              ('Buyers who paid under original asking',lambda c:f"{c['under']} of {c['n_cl']}"),
              ('Average % of first asking price',lambda c:f"{c['cpo']:.1f}%"),
              ('Median seller credit received',lambda c:M(c['conc_med'])),
              ('Median $ per finished sq ft',lambda c:f"${c['psf']:,.0f}"),
              ('Median days, offer to closing',lambda c:f"{c['ptc']:.0f}")]
        body=''
        for lab,fnc in defs:
            body+=f'<tr><td>{lab}</td>'+''.join(f'<td{" class=\"g\"" if i==0 else ""}>{fnc(c)}</td>' for i,c in enumerate(allr))+'</tr>'
        th=''.join(f'<th>{h}</th>' for h in heads)
        CMPSEC=CMP_FULL.format(ncmp=ncmp,sub=sub,tbl=f'<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>')

    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{sub} Buyer {REPORT_NOUN}</title><style>{CSS}</style></head><body>
{cover(sub,city,'BUYER')}
{buyer_lead(m,sub)}

<div class="sec"><span class="num">01</span><h2>Market conditions</h2></div>
<div class="chart">{C.gauge(m)}</div>
<p class="cap">Months of supply estimates how long it would take to sell every home currently listed at the recent pace of sales. The standard breakpoints are <strong>under 3 months a seller&rsquo;s market, 3&ndash;6 balanced or neutral, over 6 a buyer&rsquo;s market</strong>.</p>

<div class="sec pb"><span class="num">02</span><h2>Inventory mix</h2></div>
<p>What is available today, set against what has actually been selling.</p>
<div class="cards">
<div class="card"><div class="k">Homes for sale</div><div class="v">{m['n_act']}</div><span class="d">Right now</span></div>
<div class="card"><div class="k">Median asking price</div><div class="v">{M(m['act_med_list'])}</div><span class="d">Among current listings</span></div>
<div class="card"><div class="k">Sold in 12 months</div><div class="v">{m['n_cl']}</div><span class="d">About {m['n_cl']/12:.1f} per month</span></div>
</div>
<h3>By bedroom count</h3>
<div class="chart">{C.mixbars(mixbeds,'Homes currently for sale')}</div>
<h3>By style</h3>
<div class="chart">{C.mixbars(mixstyle,'Homes currently for sale')}</div>
<p class="cap">Bars show current inventory; the note beside each bar shows how many of that type sold in the last year. Where sales are high and inventory is zero, expect competition.</p>
<h3>Everything for sale today</h3>
{_tbl(arow,['Address','Beds','Style','Finished sq ft','Built','Asking price','$ per sq ft','Days on market'])}

{mom_block(d,'03')}
<div class="sec pb"><span class="num">04</span><h2>Negotiation power</h2></div>
<div class="cards">
<div class="card"><div class="k">Paid less than original asking</div><div class="v">{m['under_orig']} of {m['n_cl']}</div><span class="d">{m['under_orig']/m['n_cl']*100:.0f}% of buyers</span></div>
<div class="card"><div class="k">Paid at or above original asking</div><div class="v">{m['at_orig']+m['above_orig']} of {m['n_cl']}</div><span class="d">{m['above_orig']} paid over the first ask</span></div>
<div class="card"><div class="k">Average discount off original asking</div><div class="v">{m['disc_orig']:.1f}%</div><span class="d">Averaged across all sales</span></div>
<div class="card"><div class="k">Buyers who received a credit</div><div class="v">{m['conc_n']} of {m['n_cl']}</div><span class="d">{m['conc_n']/m['n_cl']*100:.0f}% of sales</span></div>
<div class="card"><div class="k">Median credit received</div><div class="v">{M(m['conc_med'])}</div><span class="d">Toward closing costs or rate</span></div>
<div class="card"><div class="k">Total credits to buyers</div><div class="v">{M(m['conc_tot'])}</div><span class="d">Across all {m['n_cl']} sales</span></div>
</div>
<div class="take"><span class="tag">Where the leverage actually is</span><p>{leverage_point(m)}</p></div>

<h3>Leverage grows with time on market</h3>
<div class="chart">{C.leverage(m)}</div>
<p class="cap">Homes that sold quickly went for essentially their full original asking price. The longer a listing sat, the further below its first price it eventually traded &mdash; and that is the single most reliable predictor of room to negotiate.</p>

<h3>Leverage on each home for sale today</h3>
{_tbl(''.join(lev),['Address','Asking price','Days on market','Price change so far','Your negotiating position'])}
<p class="cap">Position is based on days on market and whether the seller has already adjusted &mdash; the two signals this data shows to be predictive. A listing past 90 days that has already cut once is the strongest position a buyer can be in here.</p>

<div class="sec pb"><span class="num">05</span><h2>How fast you need to move</h2></div>
<div class="chart">{C.speed(cl)}</div>
<p class="cap">{m['fast']} of {m['n_cl']} homes went under contract within a week of listing. On a well-priced new listing, waiting a weekend is a real risk.</p>
{('<div class=\"take\"><span class=\"tag\">What right pricing buys</span><p>'+rightpriced_point(m,'buyer')+'</p></div>') if rightpriced_point(m,'buyer') else ''}
<div class="chart">{C.dumbbell(cl)}</div>
<p class="cap">Each row is one sale. Open circle is the first asking price, filled circle is what the buyer actually paid. {m['above_orig']} of these sold above the original asking price.</p>

{outlier_block(cl,m)}

<div class="sec pb"><span class="num">06</span><h2>What to expect once your offer is accepted</h2></div>
<div class="chart">{C.strip(sorted(cl['ptc'].dropna().astype(int).tolist()),max(0,m['ptc_min']-6),m['ptc_max']+6,band=(m['ptc_min'],46,f'{int((cl["ptc"]<=46).sum())} OF {m["n_cl"]} CLOSED IN THIS WINDOW'),med=m['ptc_med'],unit=' days',label='days from accepted offer to closing')}</div>
<p class="cap">Every sale closed between {m['ptc_min']:.0f} and {m['ptc_max']:.0f} days after the offer was accepted. Financing used by buyers here: {fin}.</p>

{FINSEC}
{schools_amenities(sub,d,'Buyer',nsch,namen)}
{CMPSEC}
{callout_block(d,m,cl,act,exp,'buyer',nco)}
<div class="sec pb"><span class="num">{ntalk}</span><h2>Talking points</h2></div>
<div class="talk"><h4>On making an offer</h4><ul>
<li>&ldquo;On a fresh, well-priced listing here, {m['fast']} of {m['n_cl']} sales went under contract inside a week. If we like it, we should be prepared to write the same day.&rdquo;</li>
<li>&ldquo;{offer_point(m)}&rdquo;</li></ul></div>
<div class="talk"><h4>On asking for a credit</h4><ul>
<li>&ldquo;{m['conc_n']} of {m['n_cl']} buyers here got the seller to contribute at closing, a median of {M(m['conc_med'])}. That is the standard ask in this neighborhood, and it can be worth more to you than the same money off the price.&rdquo;</li></ul></div>
<div class="talk"><h4>On choosing which home to pursue</h4><ul>
<li>&ldquo;Time on market is the tell. Homes here that sold in two weeks went for full price. Homes that sat past two months traded a few points below their first ask, and the sellers were more willing on credits too.&rdquo;</li></ul></div>
{MK.section(d,m,sub,city,'buyer',nmkt,MO.build(d))}
{methodology(m,sub)}
</body></html>'''

def build(csv, sub, city, outdir='/mnt/user-data/outputs', compares=None,
          strict_rate=False, today=None, email=False, carousel=False):
    """Render both briefs. Returns (paths, metrics, warnings).

    email=True additionally writes {slug}_Email.html -- a short, client-safe
    version for pasting into an email service. Opt-in, because most runs are for
    a listing appointment and do not need it.

    carousel=True writes six 1080x1080 PNG slides plus a combined PDF for social
    posting. Also opt-in, and independent of email.

    Concurrency notes, both of which matter the moment this runs behind a queue:
      * The intermediate HTML goes to a PER-JOB temp directory, never next to this
        module. Two jobs on the same subdivision name would otherwise write and
        read the same file and race each other into the wrong PDF -- and the skill
        directory is read-only in some deployments anyway.
      * The financing config is a per-run COPY returned by set_county(), never the
        module-level FIN. Concurrent Boulder and Adams jobs would otherwise share
        one conforming limit and silently mislabel jumbo loans in whichever job
        called set_county() first.

    strict_rate=True turns a stale mortgage rate into a hard failure instead of a
    warning. Self-serve deployments should pass True: there is no operator there
    to read a warning, and a stale rate misstates every payment in the buyer brief.
    """
    from playwright.sync_api import sync_playwright
    import tempfile
    warnings_out = []
    stale, age, msg = check_rate(strict=strict_rate, today=today)
    if stale and msg:
        warnings_out.append(msg)
    d=load(csv); cfg=set_county(d); m,cl,act,exp=metrics(d)
    out=[]
    with tempfile.TemporaryDirectory(prefix='subbrief-') as tmp:
        tmpdir=pathlib.Path(tmp)
        for kind,fn in [('Seller',seller_html),('Buyer',buyer_html)]:
            html=(fn(d,m,cl,act,exp,sub,city,compares,cfg=cfg) if kind=='Buyer'
                  else fn(d,m,cl,act,exp,sub,city))
            slug=sub.replace(' ','_')
            hp=tmpdir/f'{slug}_{kind}.html'; hp.write_text(html)
            pdf=f'{outdir}/{slug}_{kind}_{REPORT_NOUN.replace(chr(32),chr(95))}.pdf'
            foot=f'''<div style="width:100%;font-family:'DejaVu Sans Mono',monospace;font-size:6.2pt;color:#56657A;padding:0 .5in;display:flex;justify-content:space-between;letter-spacing:.07em;"><span>{sub.upper()} &nbsp;{kind.upper()} {REPORT_NOUN.upper()} &nbsp;&#183;&nbsp; {city.upper()} &nbsp;&#183;&nbsp; 365 DAYS OF ACTIVITY</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'''
            with sync_playwright() as p:
                b=p.chromium.launch(); pg=b.new_page(); pg.goto(hp.resolve().as_uri(),wait_until='networkidle')
                pg.emulate_media(media='print')
                pg.pdf(path=pdf,format='Letter',print_background=True,
                       margin={'top':'.5in','bottom':'.66in','left':'.5in','right':'.5in'},
                       display_header_footer=True,header_template='<div></div>',footer_template=foot)
                b.close()
            out.append(pdf)
    if email:
        import email_html as EH
        slug=sub.replace(' ','_')
        pack=EH.build_email(m, sub, city, MO.build(d))
        ep=f'{outdir}/{slug}_Email.html'
        pathlib.Path(ep).write_text(EH.wrap_document(pack, sub), encoding='utf-8')
        out.append(ep)
    if carousel:
        import carousel as CA
        import co_data as CD
        import master as MS
        # Area dials resolve from the bundled Colorado pack via the export's own
        # ZIPs. Geography comes from the HUD crosswalk, never the city field.
        # If the pack is absent or the ZIP has no rent series -- the usual case
        # outside the Front Range -- those dials are simply omitted.
        try:
            ctx = CD.from_export(d)
            area = ctx.as_dict()
            if ctx.spans_zips:
                warnings_out.append(
                    f"Subdivision spans ZIPs {', '.join(ctx.zips)}; area dials use "
                    f"{ctx.zip} (largest share of listings), not an average.")
            for k, why in ctx.dropped.items():
                warnings_out.append(f'Area dial dropped ({k}): {why}')
        except Exception as e:                      # pack missing or malformed
            area = None
            warnings_out.append(f'Area dials unavailable: {e}')
        out.extend(CA.render(m, sub, city, outdir,
                             scores=MS.scores(d, m, cl), area=area))
    return out,m,warnings_out

if __name__=='__main__':
    # usage: build.py <csv> "<Subdivision>" "<City>" [--email] [--carousel] [extra.csv::"Label" ...]
    FLAGS={'--email','--carousel'}
    args=[a for a in sys.argv[4:] if a not in FLAGS]
    want_email='--email' in sys.argv
    want_car='--carousel' in sys.argv
    extra=[]
    for a in args:
        path,_,lab=a.partition('::')
        extra.append(compare_row(path, lab or pathlib.Path(path).stem))
    try:
        files,m,warns=build(sys.argv[1],sys.argv[2],sys.argv[3],compares=extra or None,
                            email=want_email, carousel=want_car)
    except BriefError as e:
        # Deliberate, actionable stop -- print the message, not a traceback.
        print(f'ERROR: {e}', file=sys.stderr); sys.exit(2)
    for w in warns:
        print(f'WARNING: {w}', file=sys.stderr)
    print('\n'.join(files))
