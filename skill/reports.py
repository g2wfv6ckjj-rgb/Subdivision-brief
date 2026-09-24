import pandas as pd, numpy as np, math, random, html as H
from core import *
import charts as C

CSS=r'''
@page{size:Letter;margin:.5in .5in .66in .5in}
:root{--ink:#10203A;--soft:#56657A;--line:#CBD4DE;--pine:#1F4B87;--sage:#6FA0D0;--gold:#8A6A45;--bronze:#B0895C;--sand:#E0D5BC;--card:#F2F5F9}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font-family:"Lora","Bitstream Charter",Georgia,serif;font-size:10pt;line-height:1.5;color:var(--ink)}
h1,h2,h3,h4,.v,.big{font-family:"Poppins","Liberation Sans",sans-serif}
.mono,.eyebrow,table,caption,.tag,.k,.lbl,footer,.pillt,.cap,.note{font-family:"DejaVu Sans Mono",monospace}
p{margin:0 0 7pt}
.cover{background:var(--ink);color:#EDF2F8;padding:30pt 26pt 24pt;margin:-0.02in -0.02in 14pt;text-align:center}
.cover .kick{font-size:8pt;letter-spacing:.24em;text-transform:uppercase;color:#93A6BF;font-family:"DejaVu Sans Mono",monospace}
.cover h1{font-size:36pt;line-height:1.02;margin:8pt 0 4pt;color:#fff;font-weight:700;letter-spacing:-.02em}
.cover .loc{font-size:12.5pt;color:#C2D0E2;margin:0 0 6pt}
.cover .rng{font-family:"DejaVu Sans Mono",monospace;font-size:8.6pt;letter-spacing:.14em;color:#93A6BF}
.badge{display:inline-block;border:1.4pt solid #C9A46B;color:#C9A46B;border-radius:20pt;padding:3pt 14pt;font-size:8.4pt;letter-spacing:.18em;font-family:"DejaVu Sans Mono",monospace;margin-bottom:6pt}
.narr{border:1px solid var(--line);border-radius:6pt;padding:16pt 18pt;margin-bottom:12pt}
.narr .lead{font-size:15.5pt;line-height:1.3;margin:0 0 9pt;font-family:"Poppins",sans-serif;font-weight:500;letter-spacing:-.01em}
.narr p{font-size:10.4pt;color:#26384F;margin:0 0 6pt}
.sec{display:flex;align-items:baseline;gap:9pt;border-bottom:1.4pt solid var(--ink);padding-bottom:5pt;margin:15pt 0 9pt;break-after:avoid}
.num{font-size:8pt;color:var(--gold);letter-spacing:.1em}
h2{font-size:13pt;margin:0;text-transform:uppercase;font-weight:700}
h3{font-size:8.8pt;letter-spacing:.08em;margin:12pt 0 5pt;text-transform:uppercase;color:var(--pine);font-weight:600;break-after:avoid}
.cards{display:flex;flex-wrap:wrap;gap:7pt;margin:9pt 0;break-inside:avoid}
.card{flex:1 1 30%;border:1px solid var(--line);border-radius:5pt;padding:10pt 11pt;min-width:150pt}
.card .k{font-size:7.2pt;letter-spacing:.1em;text-transform:uppercase;color:var(--soft)}
.card .v{font-size:20pt;font-weight:700;line-height:1.05;margin:5pt 0 3pt}
.card .d{font-size:8.2pt;font-family:"DejaVu Sans Mono",monospace;color:var(--soft)}
.chart{break-inside:avoid;margin:5pt 0 2pt}
.cap{font-size:7.6pt;color:var(--soft);line-height:1.5;margin:5pt 0 0}
table{border-collapse:collapse;width:100%;font-size:8pt;margin:7pt 0 2pt}
thead{display:table-header-group}
th{text-align:left;font-size:6.6pt;letter-spacing:.09em;text-transform:uppercase;color:var(--soft);border-bottom:1.2pt solid var(--ink);padding:0 6pt 4pt 0;vertical-align:bottom}
td{padding:5pt 6pt 5pt 0;border-bottom:.6pt solid var(--line);white-space:nowrap}
tbody tr:nth-child(even){background:#F6F8FC}
tbody tr{break-inside:avoid}
td.g{color:var(--pine);font-weight:700} td.o{color:var(--gold);font-weight:700}
tr.hi td{background:#F6F1E7;font-weight:700;border-top:1.2pt solid var(--gold);border-bottom:1.2pt solid var(--gold)}
.pillt{display:inline-block;border-radius:20pt;padding:2.5pt 10pt;font-size:7.6pt;font-weight:700;color:#fff;letter-spacing:.04em}
.p1{background:#1F4B87}.p2{background:#4E7FB5}.p3{background:#8FA8C6}.p4{background:#B0895C}
ul{margin:0 0 7pt;padding-left:13pt} li{margin-bottom:4pt}
.take{border-left:2.5pt solid var(--bronze);background:var(--card);padding:9pt 12pt;margin:10pt 0;break-inside:avoid;border-radius:0 4pt 4pt 0}
.tag{font-size:6.5pt;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);display:block;margin-bottom:4pt;font-weight:700}
.take p{margin:0;font-size:10pt}
.talk{background:var(--card);border-radius:5pt;padding:12pt 14pt;margin:9pt 0;break-inside:avoid}
.talk h4{font-size:9pt;margin:0 0 7pt;text-transform:uppercase;letter-spacing:.08em;color:var(--pine)}
.talk li{font-size:10pt;margin-bottom:7pt}
.note{font-size:7.6pt;color:var(--soft);border-top:1px solid var(--line);padding-top:7pt;margin-top:12pt;line-height:1.5}
.amen{border-left:2pt solid var(--sage);padding:2pt 0 2pt 11pt;margin:0 0 11pt;break-inside:avoid}
.acat{font-family:"DejaVu Sans Mono",monospace;font-size:6.6pt;letter-spacing:.16em;text-transform:uppercase;color:var(--sage);margin-bottom:2pt}
.aname{font-family:"Poppins",sans-serif;font-size:11.5pt;font-weight:600;color:var(--ink);margin-bottom:3pt}
.adet{font-size:9.6pt;margin:0 0 3pt;color:#26384F}
.awhy{font-family:"DejaVu Sans Mono",monospace;font-size:8pt;color:var(--gold);margin:0}
.mkt{border:1px solid var(--line);border-left:2.5pt solid var(--sage);border-radius:0 5pt 5pt 0;padding:11pt 13pt;margin:9pt 0;break-inside:avoid}
.mkl{font-family:"DejaVu Sans Mono",monospace;font-size:6.6pt;letter-spacing:.16em;text-transform:uppercase;color:var(--sage);margin-bottom:5pt;font-weight:700}
.mkh{font-family:"Poppins",sans-serif;font-size:11.4pt;font-weight:600;line-height:1.25;margin:0 0 5pt;color:var(--ink)}
.mkb{font-size:9.6pt;margin:0 0 5pt;color:#26384F}
.mkc{font-size:9.4pt;margin:5pt 0 0;color:var(--ink);border-top:.6pt solid var(--line);padding-top:5pt}
.mkr{margin:4pt 0 5pt;padding-left:13pt}
.mkr li{font-size:9.4pt;margin-bottom:4pt;color:#26384F}
.mkt-tags{font-family:"DejaVu Sans Mono",monospace;font-size:8pt;color:var(--gold);margin:5pt 0 0}
.pb{break-before:page}
strong{font-weight:400;background:linear-gradient(transparent 60%,rgba(176,137,92,.34) 60%)}
'''

def skyline():
    random.seed(7); s='<svg viewBox="0 0 620 46" width="100%" height="34" style="margin-top:14pt;opacity:.35" aria-hidden="true"><g fill="none" stroke="#8FA6C4" stroke-width="1.6">'
    x=6
    while x<610:
        w=random.choice([26,34,42]); h=random.choice([16,24,32,40])
        if random.random()<.3: s+=f'<path d="M{x} 44 L{x} {44-h+8} L{x+w/2} {44-h-4} L{x+w} {44-h+8} L{x+w} 44"/>'
        else: s+=f'<rect x="{x}" y="{44-h}" width="{w}" height="{h}"/>'
        x+=w+7
    return s+'</g></svg>'

REPORT_NOUN = 'Brief'   # cover badge / titles / filenames. Change once, applies everywhere.

def cover(sub,city,kind,noun=None):
    noun=(noun or REPORT_NOUN).upper()
    return f'''<div class="cover"><div class="badge">{kind.upper()} {noun}</div>
<div class="kick">Subdivision Market Report</div><h1>{sub}</h1>
<p class="loc">{city}</p><div class="rng">365 DAYS OF ACTIVITY &#183; PREPARED JULY 2026</div>{skyline()}</div>'''

def bands(cl):
    q=[cl['Close Price'].min()-1]+list(np.percentile(cl['Close Price'],[33,66]))+[cl['Close Price'].max()]
    q=sorted(set([round(x/5000)*5000 for x in q]))
    # Band edges share one precision, so a band never reads "$1105K-$1.5M".
    _bf=mshort_series(q)
    labs=[f'{_bf(q[i])}\u2013{_bf(q[i+1])}' for i in range(len(q)-1)]
    b=pd.cut(cl['Close Price'],q,labels=labs,include_lowest=True)
    g=cl.groupby(b,observed=True).agg(n=('Close Price','size'),dtc=('Days In MLS','median'),
        red=('red','mean'),conc=('conc','mean'),psf=('PSF Finished','median'))
    g['cpo']=cl.groupby(b,observed=True).apply(lambda x:(x['Close Price']/x['Original List Price']*100).mean())
    return g.reset_index().rename(columns={g.index.name or 'Close Price':'band'})

def methodology(m,src,extra=''):
    raw_n = m['n_all'] + m['dupes'] + m.get('sanity_removed', 0)
    sanity_n = m.get('sanity_removed', 0)
    sanity_clause = ''
    if sanity_n:
        ex = m.get('sanity_examples', [])
        ex_txt = (' (for example, ' + ', '.join(ex[:3]) + ')') if ex else ''
        sanity_clause = (f' Before duplicates were removed, {sanity_n} record{"s" if sanity_n != 1 else ""} '
                         f'{"were" if sanity_n != 1 else "was"} dropped for a value that cannot be real &mdash; '
                         f'a non-positive price or a closing date earlier than the listing or contract date it '
                         f'supposedly followed{ex_txt}. This is a floor for data-entry errors only; a merely '
                         f'unusual but possible figure is never removed.')
    else:
        sanity_clause = ' No records were dropped for a data-entry error of this kind in this export.'
    return f'''<p class="note">{extra}<strong>How price changes are counted.</strong> The export carries Original List Price, Previous List Price and List Price. A listing counts as changed when the original and current prices differ. Where Previous List Price equals Original List Price the current price is the result of exactly one change; where it differs, at least two changes occurred. Counts are a floor, not a full history &mdash; a change later reversed would not be visible. Price-change dates are available only for listings whose most recent recorded event was the price change.<br><br>
<strong>Source.</strong> {src} MLS subdivision activity export covering the last 365 days: {raw_n} records, reduced to {m['n_all']} after removing {m['dupes']} duplicate entr{'y' if m['dupes']==1 else 'ies'}.{sanity_clause} Of those, {m['n_cl']} closed, {m['n_act']} are active, {m['n_fail']} expired or were withdrawn and {m['n_pend']} are under contract. All figures in this report are drawn from that single file; no outside market data is used. Months of supply divides active listings by the recent monthly sales pace. With {m['n_cl']} closed sales, subdivision-level figures are directional rather than statistically precise. Every figure is labeled with the statistic it is &mdash; median or average &mdash; rather than described as &ldquo;typical.&rdquo; <strong>All comparisons of sale price to asking price use the ORIGINAL list price</strong>, the first number published, before any reduction. Measuring against a later reduced price would score a home that cut its price and then sold at the lower number as a full-price sale, concealing the reduction. Against the final list price these same sales would average {m['s2l']:.1f}% rather than {m['cpo']:.1f}%. Information deemed reliable but not guaranteed.</p>'''
