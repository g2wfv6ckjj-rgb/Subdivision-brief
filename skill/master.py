"""Combined Seller + Buyer Master Brief.

One document, one visual system. Reuses core/monthly/marketing/local for every figure
so nothing is retyped; the new work here is the layout and the three disclosed scores.
"""
import sys, os, math, tempfile, asyncio
import pandas as pd, numpy as np
import core
from core import *
import charts as C
import monthly as MO
import marketing as MK
import local as L
import reports as R
import showings as SH
import talking as TP
import optimal as OP

MIST = '#E7EFF8'

# ============================================================== new components
def dial(score, verdict, w=156):
    cx, cy, r = 100, 96, 66
    ang = math.radians(180 - 180*score/100)
    ex, ey = cx + r*math.cos(ang), cy - r*math.sin(ang)
    col = PINE if score >= 67 else (SAGE if score >= 34 else BRONZE)
    ticks = ''
    for t in (33, 67):
        ta = math.radians(180 - 180*t/100)
        x1, y1 = cx + (r-11)*math.cos(ta), cy - (r-11)*math.sin(ta)
        x2, y2 = cx + (r+11)*math.cos(ta), cy - (r+11)*math.sin(ta)
        ticks += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#fff" stroke-width="2.4"/>'
    return f'''<svg viewBox="0 0 200 150" width="{w}" style="display:block">
<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" stroke="{MIST}" stroke-width="19" stroke-linecap="round"/>
<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {ex:.1f} {ey:.1f}" fill="none" stroke="{col}" stroke-width="19" stroke-linecap="round"/>
{ticks}
<text x="{cx}" y="{cy-6}" text-anchor="middle" font-family="Poppins,sans-serif" font-size="38" font-weight="700" fill="{INK}">{score}</text>
<text x="{cx}" y="{cy+12}" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="9" fill="{SOFT}">OUT OF 100</text>
<text x="{cx}" y="{cy+36}" text-anchor="middle" font-family="Poppins,sans-serif" font-size="13" font-weight="600" fill="{col}">{verdict}</text>
</svg>'''

def moi_ribbon(moi, w=560):
    hi = max(9.0, moi*1.25)
    px = lambda v: 18 + (w-36)*min(v, hi)/hi
    return f'''<svg viewBox="0 0 {w} 66" width="100%" style="display:block">
<rect x="18" y="18" width="{px(3)-18:.1f}" height="15" fill="{PINE}"/>
<rect x="{px(3):.1f}" y="18" width="{px(6)-px(3):.1f}" height="15" fill="{SAGE}"/>
<rect x="{px(6):.1f}" y="18" width="{w-18-px(6):.1f}" height="15" fill="{BRONZE}"/>
<polygon points="{px(moi):.1f},14 {px(moi)-6:.1f},4 {px(moi)+6:.1f},4" fill="{INK}"/>
<line x1="{px(moi):.1f}" y1="4" x2="{px(moi):.1f}" y2="35" stroke="{INK}" stroke-width="2.4"/>
<text x="{px(1.5):.1f}" y="46" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="8" fill="{SOFT}">SELLER&#8217;S &lt;3</text>
<text x="{(px(3)+px(6))/2:.1f}" y="46" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="8" fill="{SOFT}">BALANCED 3&#8211;6</text>
<text x="{(px(6)+w-18)/2:.1f}" y="46" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="8" fill="{SOFT}">BUYER&#8217;S &gt;6</text>
<text x="{w-18}" y="62" text-anchor="end" font-family="Poppins,sans-serif" font-size="11.5" font-weight="700" fill="{INK}">{moi:.1f} months of supply</text>
</svg>'''

def funnel(rows, w=560):
    top = rows[0][1]; h = 40; gap = 7
    out = [f'<svg viewBox="0 0 {w} {len(rows)*(h+gap)+8}" width="100%" style="display:block">']
    cols = [PINE, '#3C6BA5', SAGE, BRONZE]
    for i, (lab, n, note) in enumerate(rows):
        bw = (w-200)*n/top; y = i*(h+gap)
        out.append(f'<rect x="160" y="{y}" width="{bw:.1f}" height="{h}" rx="3" fill="{cols[i%4]}"/>')
        out.append(f'<text x="154" y="{y+18}" text-anchor="end" font-family="Poppins,sans-serif" font-size="10.5" font-weight="600" fill="{INK}">{lab}</text>')
        out.append(f'<text x="154" y="{y+31}" text-anchor="end" font-family="DejaVu Sans Mono,monospace" font-size="7.4" fill="{SOFT}">{note}</text>')
        out.append(f'<text x="{160+bw+9:.1f}" y="{y+26}" font-family="Poppins,sans-serif" font-size="17" font-weight="700" fill="{INK}">{n}</text>')
    return ''.join(out)+'</svg>'

def bandbars(rows, w=560):
    lo = min(r[2] for r in rows)-1.8; hi = max(max(r[2] for r in rows), 100.0)+1.4
    px = lambda v: 210 + (w-260)*(v-lo)/(hi-lo)
    h = 46
    out = [f'<svg viewBox="0 0 {w} {len(rows)*h+32}" width="100%" style="display:block">']
    x100 = px(100)
    out.append(f'<line x1="{x100:.1f}" y1="10" x2="{x100:.1f}" y2="{len(rows)*h+2}" stroke="{INK}" stroke-width="1.2" stroke-dasharray="3 3"/>')
    out.append(f'<text x="{x100:.1f}" y="{len(rows)*h+20}" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">100% OF ORIGINAL ASK</text>')
    for i, (band, n, pct, dtc) in enumerate(rows):
        y = 16+i*h
        col = PINE if pct >= 100 else BRONZE
        x = px(pct); a, b = (x100, x) if pct < 100 else (x, x100)
        out.append(f'<rect x="{min(a,b):.1f}" y="{y}" width="{abs(b-a):.1f}" height="16" fill="{col}" opacity=".9"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y+8}" r="6" fill="{col}"/>')
        out.append(f'<text x="0" y="{y+9}" font-family="Poppins,sans-serif" font-size="10.5" font-weight="600" fill="{INK}">{band}</text>')
        out.append(f'<text x="0" y="{y+22}" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">{n} SALES &#183; {dtc:.0f} DAYS TO OFFER</text>')
        lx, anch = (x+13, 'start') if pct >= 100 else (x-13, 'end')
        out.append(f'<text x="{lx:.1f}" y="{y+12}" text-anchor="{anch}" font-family="Poppins,sans-serif" font-size="11.5" font-weight="700" fill="{col}">{pct:.1f}%</text>')
    return ''.join(out)+'</svg>'

def price_speed_line(rows, w=580):
    """Median days-to-contract by price band, as a connected line -- replaces
    the per-sale dot strip in the Speed section. Solid bronze line per spec;
    each point also carries its band's own count, since a 5-way split on a
    subdivision-size file puts real but uneven samples behind each point."""
    vals = [r['median'] for r in rows]
    hi = max(vals) * 1.35 if vals else 1
    L, Rr, T, B, H = 46, 46, 34, 58, 250
    px = lambda i: L + (w - L - Rr) * i / max(len(rows) - 1, 1)
    py = lambda v: T + (H - T - B) * (1 - v / hi)
    pts = ' '.join(f'{px(i):.1f},{py(v):.1f}' for i, v in enumerate(vals))
    out = [f'<svg viewBox="0 0 {w} {H}" width="100%" style="display:block">']
    for gv in np.linspace(0, hi, 4)[1:3]:
        y = py(gv)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-Rr}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{L-8}" y="{y+3:.1f}" text-anchor="end" font-family="DejaVu Sans Mono,monospace" font-size="7.6" fill="{SOFT}">{gv:.0f}d</text>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="{BRONZE}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (r, v) in enumerate(zip(rows, vals)):
        x, y = px(i), py(v)
        anchor = 'start' if i == 0 else ('end' if i == len(rows) - 1 else 'middle')
        lx = x + (10 if i == 0 else (-10 if i == len(rows) - 1 else 0))
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{BRONZE}" stroke="#fff" stroke-width="2"/>')
        out.append(f'<text x="{lx:.1f}" y="{y-12:.1f}" text-anchor="{anchor}" font-family="Poppins,sans-serif" font-size="12.5" font-weight="700" fill="{BRZT}">{v:.0f}d</text>')
        out.append(f'<text x="{x:.1f}" y="{H-B+20:.1f}" text-anchor="{anchor}" font-family="Poppins,sans-serif" font-size="9.5" font-weight="600" fill="{INK}">{r["band"]}</text>')
        out.append(f'<text x="{x:.1f}" y="{H-B+33:.1f}" text-anchor="{anchor}" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">{int(r["count"])} sales</text>')
    out.append(f'<text x="{L}" y="{H-10:.1f}" font-family="DejaVu Sans Mono,monospace" font-size="7.4" fill="{SOFT}">PRICE BAND, LOW TO HIGH &#8594;</text>')
    return ''.join(out) + '</svg>'


def dotstrip(vals, median, unit='DAYS TO OFFER', w=560):
    vals = sorted(vals); hi = max(vals)
    step = 15 if hi <= 90 else (30 if hi <= 200 else 60)
    px = lambda v: 30 + (w-60)*v/hi
    rows = {}; out = [f'<svg viewBox="0 0 {w} 142" width="100%" style="display:block">']
    for v in vals:
        k = round(px(v)/9); rows[k] = rows.get(k, 0)+1
        y = 92 - (rows[k]-1)*9.2
        out.append(f'<circle cx="{px(v):.1f}" cy="{y:.1f}" r="4" fill="{PINE if v<=median else SAGE}"/>')
    out.append(f'<line x1="30" y1="99" x2="{w-30}" y2="99" stroke="{LINE}" stroke-width="1.2"/>')
    t = 0
    while t <= hi:
        out.append(f'<line x1="{px(t):.1f}" y1="99" x2="{px(t):.1f}" y2="104" stroke="{LINE}" stroke-width="1.2"/>')
        out.append(f'<text x="{px(t):.1f}" y="115" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="7.6" fill="{SOFT}">{t}</text>')
        t += step
    out.append(f'<line x1="{px(median):.1f}" y1="14" x2="{px(median):.1f}" y2="99" stroke="{BRZT}" stroke-width="2"/>')
    out.append(f'<text x="{px(median)+7:.1f}" y="22" font-family="Poppins,sans-serif" font-size="10" font-weight="700" fill="{BRZT}">MEDIAN {median:.0f}</text>')
    out.append(f'<text x="{w-30}" y="135" text-anchor="end" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">{unit} &#8594;</text>')
    return ''.join(out)+'</svg>'

def money_dotstrip(vals, median, w=560):
    vals = sorted(vals); hi = max(vals)
    fmt = mshort_series([0, hi])
    step = C.money_step(hi)
    px = lambda v: 30 + (w-60)*v/hi
    rows = {}; out = [f'<svg viewBox="0 0 {w} 142" width="100%" style="display:block">']
    for v in vals:
        k = round(px(v)/9); rows[k] = rows.get(k, 0)+1
        y = 92 - (rows[k]-1)*9.2
        out.append(f'<circle cx="{px(v):.1f}" cy="{y:.1f}" r="4" fill="{PINE if v<=median else SAGE}"/>')
    out.append(f'<line x1="30" y1="99" x2="{w-30}" y2="99" stroke="{LINE}" stroke-width="1.2"/>')
    t = 0
    while t <= hi:
        out.append(f'<line x1="{px(t):.1f}" y1="99" x2="{px(t):.1f}" y2="104" stroke="{LINE}" stroke-width="1.2"/>')
        out.append(f'<text x="{px(t):.1f}" y="115" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="7.6" fill="{SOFT}">{fmt(t)}</text>')
        t += step
    out.append(f'<line x1="{px(median):.1f}" y1="14" x2="{px(median):.1f}" y2="99" stroke="{BRZT}" stroke-width="2"/>')
    out.append(f'<text x="{px(median)+7:.1f}" y="22" font-family="Poppins,sans-serif" font-size="10" font-weight="700" fill="{BRZT}">MEDIAN {M(median)}</text>')
    out.append(f'<text x="{w-30}" y="135" text-anchor="end" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">SELLER CREDIT PAID &#8594;</text>')
    return ''.join(out)+'</svg>'

def spark(vals, label, big, delta, neg=False, w=172):
    v = [x for x in vals if x is not None]
    lo, hi = min(v), max(v); rng = (hi-lo) or 1
    n = len(vals)
    px = lambda i: 8 + (w-16)*i/(n-1)
    pts, seg = [], []
    for i, x in enumerate(vals):
        if x is None:
            if seg: pts.append(seg); seg = []
            continue
        seg.append(f'{px(i):.1f},{62-30*(x-lo)/rng:.1f}')
    if seg: pts.append(seg)
    last_i = max(i for i, x in enumerate(vals) if x is not None)
    lastx, lasty = px(last_i), 62-30*(vals[last_i]-lo)/rng
    poly = ''.join(f'<polyline points="{" ".join(s)}" fill="none" stroke="{PINE}" stroke-width="2.1" stroke-linejoin="round"/>' for s in pts)
    area = f'<polygon points="8,66 {" ".join(pts[0])} {pts[0][-1].split(",")[0]},66" fill="{MIST}"/>' if pts else ''
    dc = BRZT if neg else PINE
    return f'''<svg viewBox="0 0 {w} 100" width="100%" style="display:block">
{area}{poly}
<circle cx="{lastx:.1f}" cy="{lasty:.1f}" r="3.6" fill="{PINE}"/>
<text x="8" y="80" font-family="DejaVu Sans Mono,monospace" font-size="6.6" letter-spacing="1" fill="{SOFT}">{label}</text>
<text x="8" y="96" font-family="Poppins,sans-serif" font-size="15" font-weight="700" fill="{INK}">{big}</text>
<text x="{w-8}" y="96" text-anchor="end" font-family="Poppins,sans-serif" font-size="9.5" font-weight="700" fill="{dc}">{delta}</text>
</svg>'''

def mixbar(rows, w=560):
    x = 0; out = [f'<svg viewBox="0 0 {w} 72" width="100%" style="display:block">']
    for lab, pct, col in rows:
        bw = w*pct/100
        out.append(f'<rect x="{x:.1f}" y="0" width="{bw:.1f}" height="30" fill="{col}"/>')
        if bw > 40:
            out.append(f'<text x="{x+bw/2:.1f}" y="20" text-anchor="middle" font-family="Poppins,sans-serif" font-size="11" font-weight="700" fill="#fff">{pct:.0f}%</text>')
        x += bw
    step = w/max(len(rows), 1)
    for i, (lab, pct, col) in enumerate(rows):
        lx = i*step
        out.append(f'<rect x="{lx:.1f}" y="44" width="9" height="9" fill="{col}"/>')
        out.append(f'<text x="{lx+13:.1f}" y="52" font-family="DejaVu Sans Mono,monospace" font-size="7.2" fill="{SOFT}">{lab.upper()} {pct:.0f}%</text>')
    return ''.join(out)+'</svg>'

def dualspark(a, b, labels, w=560):
    """Showings per listing (bars) against median showings to pending (line)."""
    H = 150; L, Rr, T, B = 34, 34, 14, 34
    n = len(labels)
    bw = (w-L-Rr)/n
    ah = max(a); bh = max(b)
    out = [f'<svg viewBox="0 0 {w} {H}" width="100%" style="display:block">']
    for i, v in enumerate(a):
        h = (H-T-B)*v/ah
        out.append(f'<rect x="{L+i*bw+bw*.18:.1f}" y="{H-B-h:.1f}" width="{bw*.64:.1f}" height="{h:.1f}" fill="{MIST}"/>')
        out.append(f'<text x="{L+i*bw+bw/2:.1f}" y="{H-B-h-3:.1f}" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="6.4" fill="{SOFT}">{v:.1f}</text>')
    pts = ' '.join(f'{L+i*bw+bw/2:.1f},{H-B-(H-T-B)*v/bh:.1f}' for i, v in enumerate(b))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{BRONZE}" stroke-width="2.2"/>')
    for i, v in enumerate(b):
        cy = H-B-(H-T-B)*v/bh
        out.append(f'<circle cx="{L+i*bw+bw/2:.1f}" cy="{cy:.1f}" r="2.8" fill="{BRONZE}"/>')
        out.append(f'<text x="{L+i*bw+bw/2:.1f}" y="{cy+11:.1f}" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="6.4" font-weight="700" fill="{BRZT}">{v:g}</text>')
    out.append(f'<line x1="{L}" y1="{H-B}" x2="{w-Rr}" y2="{H-B}" stroke="{LINE}" stroke-width="1.2"/>')
    for i, l in enumerate(labels):
        out.append(f'<text x="{L+i*bw+bw/2:.1f}" y="{H-B+12:.1f}" text-anchor="middle" font-family="DejaVu Sans Mono,monospace" font-size="6.6" fill="{SOFT}">{l}</text>')
    out.append(f'<rect x="{L}" y="{H-14}" width="9" height="9" fill="{MIST}"/><text x="{L+13}" y="{H-6}" font-family="DejaVu Sans Mono,monospace" font-size="7" fill="{SOFT}">SHOWINGS PER LISTING</text>')
    out.append(f'<rect x="{L+180}" y="{H-14}" width="9" height="9" fill="{BRONZE}"/><text x="{L+193}" y="{H-6}" font-family="DejaVu Sans Mono,monospace" font-size="7" fill="{SOFT}">MEDIAN SHOWINGS TO PENDING</text>')
    return ''.join(out)+'</svg>'

def timeline_bars(cl, m, n=12, w=560):
    """The n longest runs among adjusted listings, against the no-change median.
    Capped deliberately: the full 39-row version is a wall of addresses."""
    red = cl[cl['red']].dropna(subset=['ttl']).nlargest(n, 'ttl')
    rows = [('Median, no reduction', m['ttl_nored'] - (m['ptc_med'] or 0), m['ptc_med'], None)]
    for _, r in red.iterrows():
        rows.append((r['addr'][:26], r['Days In MLS'], r['ptc'], r['cut']))
    hi = max(a+b for _, a, b, _ in rows)
    L, Rr, rh, gap = 150, 96, 15, 5.5
    H = len(rows)*(rh+gap) + 26
    px = lambda v: L + (w-L-Rr)*v/hi
    out = [f'<svg viewBox="0 0 {w} {H}" width="100%" style="display:block">']
    for i, (lab, a, b, cut) in enumerate(rows):
        y = i*(rh+gap)
        first = i == 0
        ca, cb = (SAGE, PINE) if first else (BRONZE, PINE)
        out.append(f'<rect x="{L}" y="{y}" width="{px(a)-L:.1f}" height="{rh}" fill="{ca}"/>')
        out.append(f'<rect x="{px(a):.1f}" y="{y}" width="{px(a+b)-px(a):.1f}" height="{rh}" fill="{cb}"/>')
        out.append(f'<text x="{L-7}" y="{y+11}" text-anchor="end" font-family="{"Poppins,sans-serif" if first else "DejaVu Sans Mono,monospace"}" font-size="{8.2 if first else 7.4}" font-weight="{700 if first else 400}" fill="{INK if first else SOFT}">{lab}</text>')
        t = f'{a+b:.0f} days' + ('' if cut is None or cut != cut else f'  \u2013{Mshort(cut)}')
        out.append(f'<text x="{px(a+b)+6:.1f}" y="{y+11}" font-family="Poppins,sans-serif" font-size="8" font-weight="700" fill="{INK}">{t}</text>')
    yb = len(rows)*(rh+gap)+4
    out.append(f'<rect x="{L}" y="{yb}" width="9" height="9" fill="{BRONZE}"/><text x="{L+13}" y="{yb+8}" font-family="DejaVu Sans Mono,monospace" font-size="7" fill="{SOFT}">WAITING FOR AN OFFER</text>')
    out.append(f'<rect x="{L+170}" y="{yb}" width="9" height="9" fill="{PINE}"/><text x="{L+183}" y="{yb+8}" font-family="DejaVu Sans Mono,monospace" font-size="7" fill="{SOFT}">ESCROW</text>')
    return ''.join(out)+'</svg>'


# ==================================================================== styling
EXTRA = r'''
.cover{background:#fff;color:var(--ink);padding:14pt 26pt 12pt;margin:-.02in -.02in 8pt;
  border-top:4pt solid var(--bronze);border-bottom:2.4pt solid var(--pine)}
.cover h1{font-size:32pt;margin:5pt 0 3pt;color:var(--ink)}
.cover .loc{font-size:11.5pt;margin:0 0 4pt;color:var(--pine)}
.cover .kick{color:var(--soft)}
.cover .rng{color:var(--soft)}
.cover .badge{border-color:var(--bronze);color:var(--gold)}
.cover svg{height:15px !important;margin-top:4pt !important;opacity:.5}
.cover svg g{stroke:var(--sage) !important}
.sec{margin:12pt 0 8pt}
.take p{font-size:9.6pt}
.take{padding:8pt 12pt;margin:8pt 0}
.dials{display:flex;gap:8pt;margin:7pt 0 4pt;break-inside:avoid}
.dialbox{flex:1;border:1px solid var(--line);border-radius:6pt;padding:9pt 8pt 7pt;text-align:center}
.dialbox .k{font-size:7pt;letter-spacing:.13em;text-transform:uppercase;color:var(--soft);font-family:"DejaVu Sans Mono",monospace}
.dialbox .d{font-size:7.9pt;color:#26384F;margin-top:4pt;line-height:1.38;font-family:"Lora",Georgia,serif;text-align:left}
.dialbox svg{margin:0 auto}
.tiles{display:flex;flex-wrap:wrap;gap:7pt;margin:8pt 0;break-inside:avoid}
.tile{flex:1 1 30%;min-width:150pt;border:1px solid var(--line);border-radius:5pt;padding:8pt 11pt}
.tile .k{font-size:6.8pt;letter-spacing:.12em;text-transform:uppercase;color:var(--soft);font-family:"DejaVu Sans Mono",monospace}
.tile .v{font-size:19.5pt;font-weight:700;line-height:1.05;margin:3pt 0 2pt;font-family:"Poppins",sans-serif}
.tile .d{font-size:7.8pt;color:var(--soft);font-family:"DejaVu Sans Mono",monospace}
.tile .up{color:var(--pine);font-weight:700}.tile .dn{color:var(--gold);font-weight:700}
.grid7{display:flex;flex-wrap:wrap;gap:6pt;align-items:stretch}
.g7{flex:0 0 calc(33.333% - 4pt);border:1px solid var(--line);border-radius:5pt;padding:6pt 4pt 4pt;display:flex;align-items:flex-end}
.lane{display:flex;gap:11pt;margin:9pt 0;break-inside:avoid}
.lane>div{flex:1}
.sell{border-top:3pt solid var(--pine);padding-top:8pt}
.buy{border-top:3pt solid var(--bronze);padding-top:8pt}
.lanek{font-family:"DejaVu Sans Mono",monospace;font-size:6.8pt;letter-spacing:.18em;font-weight:700;margin-bottom:5pt}
.sell .lanek{color:var(--pine)}.buy .lanek{color:var(--gold)}
.lane li{font-size:9.2pt}
.formula{background:var(--card);border-radius:5pt;padding:9pt 12pt;margin:8pt 0;
font-family:"DejaVu Sans Mono",monospace;font-size:7.6pt;line-height:1.62;color:#26384F;break-inside:avoid}
.formula b{color:var(--pine)}
'''

def _N(start=0):
    i = [start]
    def nxt():
        i[0] += 1
        return f'{i[0]:02d}'
    return nxt


def sec(n, t, pb=False):
    return f'<div class="sec{" pb" if pb else ""}"><span class="num">{n}</span><h2>{t}</h2></div>'

def cover(sub, city, span):
    return f'''<div class="cover"><div class="badge">MASTER BRIEF</div>
<div class="kick">Subdivision Market Report &#183; Seller &amp; Buyer</div><h1>{sub}</h1>
<p class="loc">{city}</p><div class="rng">{span}</div>{R.skyline()}</div>'''

def appendix_cover(sub, city, span):
    """Lighter cover for the companion Appendix -- agent talking points and
    marketing copy, not the market analysis itself (rule 69). References the
    Brief by name rather than repeating its own market-dashboard framing,
    since this document has no dashboard of its own."""
    return f'''<div class="cover"><div class="badge">MASTER BRIEF &mdash; APPENDIX</div>
<div class="kick">Talking Points &amp; Marketing Copy &#183; Companion to the Master Brief</div><h1>{sub}</h1>
<p class="loc">{city}</p><div class="rng">{span}</div>{R.skyline()}</div>'''

def tbl(rows, head):
    h = ''.join(f'<th>{c}</th>' for c in head)
    b = ''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'

# =============================================================== best conditions
_MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_TYPE_PLURAL = {
    'Single Family Residence': 'single family homes', 'Condominium': 'condos',
    'Townhouse': 'townhomes', 'Duplex': 'duplexes', 'Triplex': 'triplexes',
    'Manufactured Home': 'manufactured homes',
}


def _plural(t):
    return _TYPE_PLURAL.get(t, t.lower() + 's' if not t.lower().endswith('s') else t.lower())


def property_type_line(cl):
    col = None
    for c in ('Property Sub Type', 'Property Type', 'Structure Type'):
        if c in cl and cl[c].notna().any():
            col = c
            break
    if col is None:
        return 'Property type is not recorded in this export.'
    vc = cl[col].fillna('Unspecified').value_counts()
    if len(vc) == 1:
        return f'All {int(vc.iloc[0])} closed sales below are {_plural(vc.index[0])}.'
    parts = ', '.join(f'{_plural(t)} ({n})' for t, n in vc.items())
    return (f'This dataset spans more than one property type &mdash; {parts}. '
            f'Figures below blend every type together unless a table breaks them out separately.')


def best_conditions_block(prof):
    out = ['<h3>Best listing conditions, from this dataset&rsquo;s own history</h3>',
           '<p>What combination of conditions correlated with the fastest path to a signed contract '
           'here &mdash; and at what point a stalled, correctly-conditioned listing has historically '
           'been worth a real conversation about price or terms.</p>']

    upd = prof.get('updated')
    if upd:
        for row in upd:
            c = row['cells']
            label = '' if row['type'] == 'All' or len(upd) == 1 else f' &mdash; {row["type"]}'
            out.append(f'<h4 style="margin:10pt 0 4pt;font-size:9.4pt;color:var(--pine)">'
                       f'Priced right &#215; updated condition{label}</h4>')
            out.append(tbl([
                ('Priced right, updated', c['priced_right_updated']['n'],
                 f"{c['priced_right_updated']['median']:.0f} days" if c['priced_right_updated']['median'] is not None else '&mdash;'),
                ('Priced right, not updated', c['priced_right_not_updated']['n'],
                 f"{c['priced_right_not_updated']['median']:.0f} days" if c['priced_right_not_updated']['median'] is not None else '&mdash;'),
                ('Reduced, updated', c['reduced_updated']['n'],
                 f"{c['reduced_updated']['median']:.0f} days" if c['reduced_updated']['median'] is not None else '&mdash;'),
                ('Reduced, not updated', c['reduced_not_updated']['n'],
                 f"{c['reduced_not_updated']['median']:.0f} days" if c['reduced_not_updated']['median'] is not None else '&mdash;'),
            ], ['Condition', 'Sales', 'Median days to offer']))
            if row.get('reduced_rate_updated') is not None and row.get('reduced_rate_not_updated') is not None:
                ru, rn = row['reduced_rate_updated'] * 100, row['reduced_rate_not_updated'] * 100
                if abs(ru - rn) >= 8:
                    higher = 'updated' if ru > rn else 'not-updated'
                    out.append(f'<p class="cap">In this dataset, {higher} listings needed a price reduction '
                              f'more often &mdash; {ru:.0f}% of updated listings reduced at least once, against '
                              f'{rn:.0f}% of listings without recorded updates. Being updated did not, by '
                              f'itself, protect against needing a reduction here.</p>')
                else:
                    out.append('<p class="cap">Reduction rates were similar whether or not a listing was '
                              'recorded as updated &mdash; condition was not the deciding factor here.</p>')
    else:
        out.append('<p class="cap">Property Condition is not populated widely enough in this export to '
                  'split by updated status.</p>')

    wk = prof.get('weekday')
    if wk:
        if wk['headline']:
            h = wk['headline']
            out.append(f'<p><strong>Day of week listed:</strong> weekday listings here took a median of '
                      f'{h["weekday_median"]:.0f} days to an offer ({h["weekday_n"]} listings); weekend '
                      f'listings took {h["weekend_median"]:.0f} ({h["weekend_n"]}).</p>')
        else:
            n_we = sum(r['n'] for r in wk['table'] if r['day'] in ('Saturday', 'Sunday'))
            out.append(f'<p class="cap"><strong>Day of week listed:</strong> only {n_we} listings in this '
                      f'export started on a weekend, too few to compare against weekday listings with any '
                      f'confidence. The day-by-day counts are below for transparency, not as a recommendation.</p>')
        out.append(tbl([(r['day'], r['n'], f"{r['median']:.0f} days") for r in wk['table']],
                       ['Day listed', 'Sales', 'Median days to offer']))

    mo = prof.get('month')
    if mo:
        out.append('<p class="cap"><strong>Month listed:</strong> directional only &mdash; a 12-month, '
                  'single-dataset file puts a handful of listings behind most months. Thin months are '
                  'marked rather than hidden.</p>')
        out.append(tbl([(r['month'], r['n'], f"{r['median']:.0f} days" + (' *' if r['thin'] else ''))
                       for r in mo], ['Month listed', 'Sales', 'Median days to offer']))
        if any(r['thin'] for r in mo):
            out.append('<p class="cap">* Fewer than 6 listings started that month in this export.</p>')

    dec = prof.get('decision')
    if dec:
        out.append(f'''<div class="formula"><b>WHEN DOES WAITING BECOME A PRICING PROBLEM?</b>
Among the {dec['n']} listings here that never reduced their price, half had an accepted offer by day
{dec['p50']:.0f}, three-quarters by day {dec['p75']:.0f}, and nine in ten by day {dec['p90']:.0f}.
A correctly-conditioned listing &mdash; updated where that matters here, priced at or near this
market&rsquo;s own median, on market past roughly {dec['p90']:.0f} days &mdash; has, in this dataset&rsquo;s
own history, gone past where almost every comparable home found a buyer. That is the point to have a real
conversation about price or concessions, not a guess about when to have it.<br><br>
Concessions were about as common either way here &mdash; {dec['conc_rate_priced_right']*100:.0f}% of
priced-right sales included one, against {dec['conc_rate_reduced']*100:.0f}% of reduced sales &mdash; so a
concession is not, by itself, a substitute for a price correction in this market; the two levers do
different jobs.</div>''')

    out.append('<p class="cap">Not computed here: whether an open house was held, and when. No MLS export '
              'field records that, the same way showing activity needs a separate ShowingTime export. If an '
              'open-house log is ever supplied, that becomes a fifth input here.</p>')
    return ''.join(out)


# ===================================================================== scores
def investor_block(prof, num):
    """Renders an investor.py profile. Unlike every other score in this
    report, this one is NOT computed from the MLS export -- it blends public
    rent, appreciation and growth data at whichever geography each series
    actually publishes at, and says so throughout rather than implying a
    single tidy neighborhood-level number.
    """
    fmt_pct = lambda v: ('&mdash;' if v is None else f'{v:+.1f}%')
    fmt_money = lambda v: ('&mdash;' if v is None else f'${v:,.0f}')
    verdict = ('Favorable' if (prof['overall'] or 0) >= 67 else
              ('Mixed' if (prof['overall'] or 0) >= 34 else 'Weak'))
    live_note = ('Fetched live for this run.' if prof['live'] else
                'Built from figures sourced and verified by hand for this run, not a live fetch.')

    growth_geo = prof['pop_geo'] or 'geography not stated'
    _yrs = prof.get('pop_years', 4)
    if prof['emp_sub'] is not None:
        growth_detail = (f"Population {fmt_pct(prof['pop_growth_4yr'])} over {_yrs} years "
                        f"({fmt_pct(prof['pop_annualized'])}/yr, {growth_geo}). Metro employment "
                        f"{fmt_pct(prof['emp_yoy'])} year over year"
                        + (f", unemployment {prof['emp_unemployment']:.1f}%" if prof['emp_unemployment'] is not None else '')
                        + f" ({prof['emp_geo'] or 'metro'}).")
    else:
        growth_detail = (f"Population {fmt_pct(prof['pop_growth_4yr'])} over {_yrs} years "
                        f"({fmt_pct(prof['pop_annualized'])}/yr, {growth_geo}). No metro employment "
                        f"figure was supplied for this run &mdash; the growth sub-score is population only.")

    srcs = ''.join(f'<li>{s}</li>' for s in prof['sources']) or '<li>Sources not recorded for this run.</li>'

    return f'''<div class="sec pb"><span class="num">{num}</span><h2>Investor score</h2></div>
<p>ZIP {prof['zip5']}. Rent, appreciation and growth, blended into one score &mdash; built the way every
score in this report is built, with every input and every anchor shown. {live_note}</p>
<div class="dials">
<div class="dialbox" style="flex:0 0 40%">{dial(prof['overall'] or 0, verdict, 150)}
<div class="d">Equal-weight mean of the three sub-scores at right. Anchors are this skill&rsquo;s own
convention, not an industry standard &mdash; read the inputs, not just the headline.</div></div>
<div class="tiles" style="flex:1;margin:0">
<div class="tile"><div class="k">Rental yield</div><div class="v">{(prof['rent_sub'] or 0):.0f}</div>
<div class="d">Gross yield {prof['gross_yield']:.1f}% &mdash; {fmt_money(prof['rent_month'])}/mo on a
{fmt_money(prof['zhvi_current'])} home. Anchored 2%&nbsp;=&nbsp;0, 8%&nbsp;=&nbsp;100.</div></div>
<div class="tile"><div class="k">Appreciation</div><div class="v">{(prof['apprec_sub'] or 0):.0f}</div>
<div class="d">{fmt_pct(prof['apprec_yoy'])} year over year, {prof['apprec_geo'] or 'geography not stated'}.
Anchored &minus;5%&nbsp;=&nbsp;0, 10%&nbsp;=&nbsp;100.</div></div>
<div class="tile"><div class="k">Population &amp; employment</div><div class="v">{(prof['growth_sub'] or 0):.0f}</div>
<div class="d">{growth_detail}</div></div>
</div>
</div>
<div class="formula"><b>HOW THE SCORE IS BUILT.</b><br>
Rent: {fmt_money(prof['rent_month'])} &#215; 12 &#247; {fmt_money(prof['zhvi_current'])} =
{prof['gross_yield']:.2f}% gross yield &rarr; <b>{prof['rent_sub']:.0f}</b><br>
Appreciation: {fmt_pct(prof['apprec_yoy'])} YoY &rarr; <b>{prof['apprec_sub']:.0f}</b><br>
Growth: {prof['growth_note']} &rarr; <b>{prof['growth_sub']:.0f}</b><br>
Overall = mean of the three = <b>{prof['overall']}</b></div>
<p class="cap"><strong>Three different geographies are blended here</strong> because that is the smallest
geography each series actually publishes at: ZIP for rent and home value, {prof['apprec_geo'] or 'city'}
for appreciation, {growth_geo} for population, {prof['emp_geo'] or 'metro, when supplied'} for employment.
This is not a subdivision-level or even always a ZIP-level figure &mdash; treat it as area context, not a
precise reading on any one property or block.</p>
<p class="cap"><strong>Sources:</strong></p>
<ul style="margin:2pt 0 0 14pt;font-size:8pt;color:var(--soft)">{srcs}</ul>'''


def demographics_block(demo, num):
    """Renders a Census profile built by demographics.enrich(). Private-report
    only -- never called from carousel.py or callout_cards.py."""
    fmt = lambda v, suf='': (f'{v:,.0f}{suf}' if v is not None else '&mdash;')
    income = '&mdash;' if demo['median_income'] is None else '$' + fmt(demo['median_income'])
    return f'''<div class="sec pb"><span class="num">{num}</span><h2>Neighborhood snapshot</h2></div>
<p>Census figures for {demo['phrase']} ({demo['geo_name']}), the smallest Census geography available for
this area &mdash; subdivisions are not a Census geography, so these numbers describe a wider area than the
report itself.</p>
<div class="tiles">
<div class="tile"><div class="k">Median household income</div><div class="v">{income}</div><div class="d">American Community Survey, {demo['year']} 5-year estimate</div></div>
<div class="tile"><div class="k">Median age</div><div class="v">{fmt(demo['median_age'])}</div><div class="d">Years</div></div>
<div class="tile"><div class="k">Owner-occupied</div><div class="v">{fmt(demo['owner_pct'], '%')}</div><div class="d">Of occupied housing units</div></div>
</div>
<div class="tiles">
<div class="tile"><div class="k">Renter-occupied</div><div class="v">{fmt(demo['renter_pct'], '%')}</div><div class="d">Of occupied housing units</div></div>
<div class="tile"><div class="k">Bachelor&rsquo;s degree or higher</div><div class="v">{fmt(demo['bachelor_pct'], '%')}</div><div class="d">Population 25 and older</div></div>
</div>
<p class="cap">Source: U.S. Census Bureau American Community Survey, {demo['year']} 5-year estimates, for
{demo['geo_name']}. These four figures are neutral market context in common use on consumer real estate
sites and are reported here exactly as the Census Bureau publishes them &mdash; never combined into a score,
never used to characterize who does or should live in an area, and never included in social graphics or any
public-facing copy generated by this skill. Crime statistics are deliberately not included: no reliable
figure exists at this geography without approximation, and pairing crime data with a real estate report
carries a documented Fair Housing steering risk. Verify any figure that matters to a specific decision
directly with the Census Bureau at data.census.gov.</p>'''


def market_notes_block(m, cfg):
    """General market education, deliberately NOT computed from the MLS export.

    Three things worth an agent's attention right now, none of them specific to
    this subdivision: buyer-agency compensation rules, Colorado property tax
    trajectory, and Colorado homeowners insurance costs. Kept structurally
    separate from every other section in this report -- each of those sections
    exists because the export supports the number; these exist because the
    topic is live in the market regardless of what any single export shows.
    Every figure here is sourced and dated rather than computed, and the text
    says so plainly rather than blending into the report's own data.

    Renders for both audiences (agent and sales rep) -- unlike Investor Score,
    which is about one area, this is about the transaction process and macro
    cost environment, equally relevant to either conversation.
    """
    ins_shown = m['med'] * cfg['ins_rate']
    return f'''<h3>What&rsquo;s changed in the market that this export can&rsquo;t show</h3>
<p class="cap">The three notes below are general market and policy context, not figures computed from this
subdivision&rsquo;s data &mdash; sourced and dated as of mid-2026, worth verifying before repeating.</p>

<div class="formula"><b>BUYER REPRESENTATION IS A WRITTEN, NEGOTIATED AGREEMENT NOW.</b> Since August 2024,
agents working with buyers must sign a written buyer-agency agreement before touring a home, disclosing
compensation in writing up front. That figure is negotiated directly between buyer and agent rather than
published in the MLS, and a seller can still choose to offer a concession toward it, but nothing requires
one. National industry surveys through 2026 have found average total commission roughly unchanged from
before the settlement, not meaningfully lower &mdash; the real shift is that the number is now an explicit,
written conversation on every transaction. For a buyer asking why they need to sign something before a
showing, that written disclosure is the point of the rule, not paperwork to skip past.</div>

<div class="formula"><b>COLORADO PROPERTY TAX BILLS ARE RISING INDEPENDENT OF HOME VALUES.</b> HB24B-1001,
building on SB24-233, permanently reset residential assessment rates for the 2025 and 2026 tax years, and a
temporary $55,000 taxable-value exclusion that had softened bills in 2023&ndash;2024 expired for 2025. The
practical result: many Colorado homeowners are seeing higher tax bills in 2026 even where assessed value
hasn&rsquo;t moved. The Tax Annual Amount figures used elsewhere in this report reflect what the current
owner is paying today, not necessarily what a bill looks like after the next reassessment &mdash; worth
confirming with the county assessor before a buyer budgets against last year&rsquo;s number.</div>

<div class="formula"><b>HOMEOWNERS INSURANCE HAS BECOME A REAL DEAL-RISK CONVERSATION.</b> Statewide premiums
have roughly doubled since 2018, driven mostly by hail losses rather than wildfire across most of the
Front Range &mdash; Colorado&rsquo;s own Division of Insurance found hail accounts for roughly a quarter to
over half of a typical premium depending on county, with wildfire adding more only in specific high-risk
zones. Various 2026 industry estimates put the statewide average homeowners premium in a $4,000&ndash;$6,600
range annually, well above the flat {cfg['ins_rate']*100:.2f}%-of-price assumption used in the payment table
above ({M(ins_shown)} a year on this subdivision&rsquo;s median). Encourage a buyer to get an actual quote
early rather than at the closing table &mdash; in the highest-risk zones, availability itself can be the
real constraint, not just price.</div>

<p class="cap">Sources: National Association of Realtors settlement practice changes (effective August 17,
2024, in force through 2026); Colorado House Bill 24B-1001 and Senate Bill 24-233; Colorado Division of
Insurance hail/wildfire premium analysis (February 2026) and 2026 industry rate surveys. General context,
not a quote or a guarantee &mdash; verify current figures before using them with a client.</p>'''


def net_sheet_pointer():
    """A pointer to the standalone net-sheet tool, not a rebuild of it here.
    Placed at the close of the financing section because that is where a
    reader's next question is naturally 'and what would I actually walk away
    with' -- the seller-side mirror of the buyer PITI table above it."""
    return '''<div class="take"><span class="tag">For sellers asking what they&rsquo;d walk away with</span>
<p>This report doesn&rsquo;t include a net proceeds estimate &mdash; that&rsquo;s a different calculation,
done well already. Run a full seller net sheet, including title and closing costs for this transaction, at
<strong>FidelityAgent.com</strong>.</p></div>'''


def scores(d, m, cl):
    """Three scores, every input disclosed. Sub-metric anchors are ours, not an
    industry standard, and the report says so."""
    st = d['Mls Status'].astype(str).str.strip().str.lower()
    fail = st.isin(['expired', 'withdrawn', 'canceled', 'cancelled'])
    closed = st == 'closed'
    nr = ~d['red']
    s = {}
    s['all_cl'] = int(closed.sum()); s['all_fail'] = int(fail.sum())
    s['all_rate'] = 100*s['all_cl']/(s['all_cl']+s['all_fail'])
    s['nc_cl'] = int((closed & nr).sum()); s['nc_fail'] = int((fail & nr).sum())
    s['nc_rate'] = 100*s['nc_cl']/(s['nc_cl']+s['nc_fail'])
    s['cut_cl'] = int((closed & ~nr).sum()); s['cut_fail'] = int((fail & ~nr).sum())
    s['cut_rate'] = 100*s['cut_cl']/(s['cut_cl']+s['cut_fail'])
    s['chance'] = int(round(s['nc_rate']))

    clamp = lambda x: max(0.0, min(100.0, x))
    s['pp_cpo'] = clamp((m['cpo']-90)/15*100)
    s['pp_nocut'] = 100*m['no_change']/m['n_cl']
    s['pp_noconc'] = 100*(m['n_cl']-m['conc_n'])/m['n_cl']
    s['power'] = int(round((s['pp_cpo']+s['pp_nocut']+s['pp_noconc'])/3))

    s['balance'] = int(round(clamp(100*(1-m['moi']/9))))
    return s

def verdict(v, hi='Strong', mid='Moderate', lo='Limited'):
    return hi if v >= 67 else (mid if v >= 34 else lo)

def bal_word(moi):
    return moi_label(moi)


# ================================================================ report body
def report_html(d, m, cl, act, exp, sub, city, cfg, auto=None, audience='agent',
                 showings_prof=None, demo=None, investor=None, area=None):
    import build as B
    s = scores(d, m, cl)
    nn = _N()
    mo = MO.build(d)
    lab, full = mo['labels'], mo['full']
    ser = mo['series']['All property types'] if 'All property types' in mo['series'] else None
    S = {k: v['All property types'] for k, v in mo['series'].items()}
    show_on = audience == 'salesrep' and showings_prof and showings_prof.get('enabled')
    spl, stp = SH.window(showings_prof, full) if show_on else ([None] * len(full), [None] * len(full))
    bd = R.bands(cl)
    nchg = cl['nchg'].value_counts()
    span = (f"{cl['Close Date'].min():%b %-d, %Y}".upper() + ' &ndash; '
            + f"{cl['Close Date'].max():%b %-d, %Y}".upper()
            + ' &#183; 365 DAYS OF ACTIVITY')

    # ---- headline tiles
    d_dtc = MO.mom(S['med_dom'], mo['months']); d_med = MO.mom(S['med_close'], mo['months'])
    d_new = MO.mom(S['new'], mo['months']); d_msi = MO.mom(S['msi'], mo['months'])

    # ---- price-adjustment table
    rr = cl[cl['red']].nlargest(6, 'cut')
    rrow = [(r['addr'], M(r['Original List Price']), '&minus;'+M(r['cut']), M(r['Close Price']),
             f"{r['Days In MLS']:.0f} days", f"{r['ptc']:.0f} days", f"{r['ttl']:.0f} days")
            for _, r in rr.iterrows()]
    arow = [(r['addr'], f"{r['Bedrooms Total']:.0f}", str(r.get('Levels', '')),
             f"{r['Living Area']:,.0f}", M(r['Original List Price']), M(r['List Price']),
             f"{r['Days In MLS']:.0f}")
            for _, r in act.sort_values('List Price', ascending=False).iterrows()]

    fin_rows = []
    _fc = {'Conventional': PINE, 'Cash': BRONZE, 'FHA': SAGE, 'VA': '#8FA8C6'}
    tot = sum(m['fin'].values())
    for k, v in sorted(m['fin'].items(), key=lambda x: -x[1]):
        fin_rows.append((k, 100*v/tot, _fc.get(k.split(',')[0].strip(), '#B9C6D6')))

    yo = SH.yoy_pairs(showings_prof) if show_on else []
    yrow = [(mn, f'{a25:.1f}', f'{a26:.1f}', f'{a26-a25:+.1f}', f'{b25:.1f}', f'{b26:.1f}', f'{b26-b25:+.1f}')
            for mn, a25, b25, a26, b26 in yo]

    H = []
    H.append(f'<!doctype html><html><head><meta charset="utf-8"><style>{R.CSS}{EXTRA}</style></head><body>')
    H.append(cover(sub, city, span))

    # ------------------------------------------------------------ 01 dashboard
    H.append(sec(nn(), 'Market dashboard'))
    H.append('<div class="dials">')
    H.append(f'''<div class="dialbox"><div class="k">Chance of Selling</div>{dial(s['chance'], verdict(s['chance']))}
<div class="d">{s['nc_cl']} of the {s['nc_cl']+s['nc_fail']} listings that never reduced their price went on to close.
Listings that did reduce closed {s['cut_rate']:.0f}% of the time.</div></div>''')
    H.append(f'''<div class="dialbox"><div class="k">Market Balance</div>{dial(s['balance'], verdict(s['balance'], 'Seller-leaning', 'Balanced', 'Buyer-leaning'))}
<div class="d">{m['moi']:.1f} months of supply against the trailing sales pace. The 3 and 6 month breakpoints are
the standard convention; wording between them is descriptive.</div></div>''')
    # Rent to Price / Growth Outlook: area-level, from the bundled Colorado
    # reference pack (co_data.py), not this export. Each is OMITTED here --
    # never shown at 0 -- when it didn't resolve; roughly seven Colorado ZIPs
    # in ten have no Zillow rent series, so a two-dial dashboard is the
    # common case outside the Front Range, not a broken one. Unlike Pricing
    # Power (rule 44), these have no section of their own anywhere in this
    # document to fall back on, so the dashboard is their only appearance.
    if area and area.get('rent') is not None:
        gy = area.get('gross_yield')
        gy_txt = f'{gy:.1f}%' if gy is not None else 'n/a'
        H.append(f'''<div class="dialbox"><div class="k">Rent to Price</div>{dial(area['rent'], verdict(area['rent']))}
<div class="d">{gy_txt} gross annual rent against home value in {area.get('rent_scope', 'this area')}, before
taxes, insurance, HOA or vacancy.</div></div>''')
    if area and area.get('growth') is not None:
        H.append(f'''<div class="dialbox"><div class="k">Growth Outlook</div>{dial(area['growth'], verdict(area['growth']))}
<div class="d">Blends home-value appreciation, population growth and employment growth across
{area.get('growth_scope', 'this area')}, equally weighted.</div></div>''')
    H.append('</div>')

    H.append('<div class="tiles">')
    for k, v, dd, cls in [
        ('Median sale price', M(m['med']), _fd(d_med, 'money')+' month over month', 'up'),
        ('Median $/sq ft', M(m['psf_med']), f"average {M(m['psf_avg'])}", 'up'),
        ('Median days to offer', f"{m['dtc_med']:.0f}", _fd(d_dtc)+' month over month', 'up'),
        ('Sale to original ask', f"{m['cpo']:.1f}%", f"{m['at_or_above']} of {m['n_cl']} sold at or above", 'dn'),
        ('Closed sales', f"{m['n_cl']}", f"{m['n_fail']} expired or withdrawn", 'up'),
        ('Active listings', f"{m['n_act']}", f"{m['moi']:.1f} months of supply", 'up'),
    ]:
        H.append(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="d {cls}">{dd}</div></div>')
    H.append('</div>')

    H.append(f'<div class="chart">{moi_ribbon(m["moi"])}</div>')
    rp = rightpriced_point(m, 'seller')
    if rp:
        H.append(f'<div class="take"><span class="tag">Read this first</span><p>{rp}</p></div>')

    # --------------------------------------------------- 02 chance of selling
    H.append(sec(nn(), 'Chance of selling, if priced right', pb=True))
    fn = [("Entered the market", m['n_all'], "ALL LISTINGS IN THE EXPORT"),
          ("Closed", m['n_cl'], f"{100*m['n_cl']/m['n_all']:.0f}% OF ALL LISTINGS"),
          ("Expired or withdrawn", m['n_fail'], f"{100*m['n_fail']/m['n_all']:.0f}% OF ALL LISTINGS"),
          ("Under contract now", m['n_pend'], "PENDING AT EXPORT")]
    H.append(f'<div class="chart">{funnel(fn)}</div>')
    H.append(f'''<div class="formula"><b>HOW THE SCORE IS BUILT.</b> Sell-through = closed &#247; (closed + expired + withdrawn + canceled),
computed on this export only. The headline score uses the subset that never reduced its asking price &mdash; the
working proxy for &ldquo;priced right&rdquo; &mdash; because a home priced correctly does not need to reduce.<br>
&nbsp;&nbsp;Never reduced: {s['nc_cl']} closed, {s['nc_fail']} failed &rarr; <b>{s['nc_rate']:.1f}%</b><br>
&nbsp;&nbsp;Reduced at least once: {s['cut_cl']} closed, {s['cut_fail']} failed &rarr; <b>{s['cut_rate']:.1f}%</b><br>
&nbsp;&nbsp;All listings: {s['all_cl']} closed, {s['all_fail']} failed &rarr; <b>{s['all_rate']:.1f}%</b><br>
No outside data and no weighting. Listings still active or under contract are excluded from both sides,
because their outcome is not yet known.</div>''')
    H.append('<h3>Days to offer and price performance by band</h3>')
    H.append(tbl([(r['band'], f"{r['n']:.0f}", f"{r['dtc']:.0f}", f"{r['cpo']:.1f}%",
                   f"{100*r['red']:.0f}%", M(r['conc']), M(r['psf']))
                  for _, r in bd.iterrows()],
                 ['Price band', 'Sales', 'Median days to offer', 'Avg % of original ask',
                  'Share that reduced', 'Avg credit', 'Median $/sq ft']))
    H.append(f'<p class="cap">Bands are the thirds of this subdivision&rsquo;s own closed prices. '
             f'With {m["n_cl"]} sales each band rests on roughly {m["n_cl"]//3} records &mdash; directional, not statistically precise.</p>')
    H.append(f'<div class="take"><span class="tag">What moves the score</span><p>{adjust_point(m)}</p></div>')
    H.append(best_conditions_block(OP.build(cl, m)))

    # --------------------------------------------------------- 03 pricing power
    H.append(sec(nn(), 'Pricing Power', pb=True))
    H.append(f'<p class="cap" style="margin-top:-4pt">{property_type_line(cl)}</p>')
    H.append('<h3>Sale price against the original asking price</h3>')
    H.append(f'<div class="chart">{bandbars([(r["band"], int(r["n"]), r["cpo"], r["dtc"]) for _, r in bd.iterrows()])}</div>')
    H.append(f'''<div class="formula"><b>HOW THE SCORE IS BUILT.</b> An equal-weight blend of three measured figures.
The 0&#8211;100 anchors are this skill&rsquo;s own convention, not an industry standard, and are printed here so the
score can be checked.<br>
&nbsp;&nbsp;% of original ask, {m['cpo']:.1f}% &mdash; anchored 90%&nbsp;=&nbsp;0, 105%&nbsp;=&nbsp;100 &rarr; <b>{s['pp_cpo']:.0f}</b><br>
&nbsp;&nbsp;Share needing no price reduction, {m['no_change']} of {m['n_cl']} &rarr; <b>{s['pp_nocut']:.0f}</b><br>
&nbsp;&nbsp;Share closing with no seller credit, {m['n_cl']-m['conc_n']} of {m['n_cl']} &rarr; <b>{s['pp_noconc']:.0f}</b><br>
Mean of the three = <b>{s['power']}</b>. Read the three inputs, not just the headline.</div>''')
    H.append('<h3>What a price adjustment costs</h3>')
    H.append(tbl([('Never reduced', f"{m['no_change']}", f"{m['ttl_nored']:.0f} days", f"{m['rp_med']:.0f} days"),
                  ('Reduced at least once', f"{m['changed']}", f"{m['ttl_red']:.0f} days", f"{m['rp_cut_med']:.0f} days")],
                 ['', 'Sales', 'Median listing to closing', 'Median days to offer']))
    H.append('<h3>Buyer financing mix</h3>')
    H.append(f'<div class="chart">{mixbar(fin_rows)}</div>')
    H.append(f'<p class="cap">Recorded buyer financing across all {tot} closed sales. Mechanics only &mdash; '
             f'no rate here applies to any individual buyer.</p>')

    # ------------------------------------------------------------- 04 showings
    # Sales-rep skill only, and only when an InfoSparks export was actually
    # supplied for this run -- the agent skill never has ShowingTime access,
    # so this whole section (and its page) is simply absent there, not blank.
    if show_on:
        H.append(sec(nn(), 'Showing activity', pb=True))
        H.append(f'<div class="chart">{dualspark([x for x in spl if x is not None], [x for x in stp if x is not None], [l for l, x in zip(lab, spl) if x is not None])}</div>')
        H.append(f'<p class="cap">Bars: average showings per active listing. Line: median number of showings a listing '
                 f'took before going under contract. Source: {showings_prof["src"]}. This is a separate export from the '
                 f'subdivision activity file and covers a user-defined area, so counts will not tie exactly to the listing '
                 f'counts elsewhere in this report.</p>')
        if yrow:
            H.append('<h3>Year over year, the months present in both years</h3>')
            H.append(tbl(yrow, ['Month', 'Showings/listing, prior year', 'Current year', 'Change',
                                'Showings to pending, prior year', 'Current year', 'Change']))
            H.append('<p class="cap">The showings export runs 13+ months, so these months have a true prior-year '
                     'comparison. The subdivision activity file covers 365 days and does not.</p>')

    # ---------------------------------------------------------------- 05 speed
    H.append(sec(nn(), 'How fast homes found a buyer', pb=True))
    ppb = OP.price_point_bands(cl)
    if ppb:
        H.append(f'<div class="chart">{price_speed_line(ppb)}</div>')
        H.append('<p class="cap">Median days from listing to accepted offer, by price band from low to high. '
                 'Solid line connects each band\'s median; the count beneath each point is that band\'s sample '
                 'size. A band under roughly ten sales is directional rather than precise.</p>')
    else:
        H.append(f'<div class="chart">{dotstrip(cl["Days In MLS"].dropna().tolist(), m["dtc_med"])}</div>')
        H.append('<p class="cap">One dot per closed sale, from the day it hit the market to the day an offer was accepted.</p>')
    q1, q3 = np.percentile(cl['Days In MLS'], [25, 75])
    H.append('<div class="tiles">')
    for k, v, dd in [('Fastest quarter', f'&#8804; {q1:.0f} days', f"{int((cl['Days In MLS']<=q1).sum())} sales"),
                     ('Median', f"{m['dtc_med']:.0f} days", f"{m['n_cl']} sales"),
                     ('Slowest quarter', f'&#8805; {q3:.0f} days', f"{int((cl['Days In MLS']>=q3).sum())} sales")]:
        H.append(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="d">{dd}</div></div>')
    H.append('</div>')
    H.append(f'<div class="take"><span class="tag">What the spread means</span><p>{seller_price_point(m)}</p></div>')

    # ---------------------------------------------------------- 06 concessions
    H.append(sec(nn(), 'Seller credits at closing', pb=True))
    H.append('<div class="tiles">')
    H.append(f'<div class="tile"><div class="k">Sales including a credit</div><div class="v">{m["conc_n"]} of {m["n_cl"]}</div><div class="d">{100*m["conc_n"]/m["n_cl"]:.0f}% of sales</div></div>')
    H.append(f'<div class="tile"><div class="k">Median credit where paid</div><div class="v">{M(m["conc_med"])}</div><div class="d">Median amount</div></div>')
    H.append(f'<div class="tile"><div class="k">Total credits paid</div><div class="v">{M(m["conc_tot"])}</div><div class="d">Across all {m["n_cl"]} sales</div></div>')
    H.append('</div>')
    H.append(f'<div class="chart">{money_dotstrip(cl[cl["conc"]>0]["conc"].tolist(), m["conc_med"])}</div>')
    H.append('<p class="cap">A credit is money the seller puts toward the buyer&rsquo;s closing costs or rate '
             'buy-down. It comes off the seller&rsquo;s proceeds, so it belongs in the net sheet from day one.</p>')
    H.append(tbl([(r['band'], f"{r['n']:.0f}", M(r['conc'])) for _, r in bd.iterrows()],
                 ['Price band', 'Sales', 'Average credit']))

    # ---------------------------------------------------- 07 price adjustment
    H.append(sec(nn(), 'What happens when the price is adjusted', pb=True))
    H.append('<div class="tiles">')
    H.append(f'<div class="tile"><div class="k">Priced right at launch</div><div class="v">{m["ttl_nored"]:.0f} days</div><div class="d">Listing to closing &#183; {m["no_change"]} homes</div></div>')
    H.append(f'<div class="tile"><div class="k">After a price adjustment</div><div class="v">{m["ttl_red"]:.0f} days</div><div class="d">Listing to closing &#183; {m["changed"]} homes</div></div>')
    H.append(f'<div class="tile"><div class="k">Price never changed</div><div class="v">{int(nchg.get(0,0))}</div><div class="d">Once: {int(nchg.get(1,0))} &#183; twice or more: {int(nchg.get(2,0))}</div></div>')
    H.append('</div>')
    H.append(f'<div class="chart">{timeline_bars(cl, m)}</div>')
    H.append(f'<p class="cap">The {min(12, m["changed"])} longest runs among the {m["changed"]} listings that '
             f'reduced, against the median for the {m["no_change"]} that never did. Bronze is time spent waiting '
             f'for an offer; navy is escrow. The navy portion barely moves &mdash; nearly all of the extra time '
             f'comes from the search for a buyer, which is what the asking price controls.</p>')
    H.append('<h3>The six largest adjustments this year</h3>')
    H.append(tbl(rrow, ['Address', 'First asking price', 'Adjustment', 'Sold for',
                        'Days to offer', 'Offer to closing', 'Total days']))
    H.append('<p class="cap">Price-change counts are a floor. A change later reversed would not be visible in the export.</p>')

    # --------------------------------------------------------------- 08 escrow
    H.append(sec(nn(), 'Once an offer is accepted', pb=True))
    H.append(f'<div class="chart">{dotstrip(cl["ptc"].dropna().tolist(), m["ptc_med"], unit="DAYS FROM ACCEPTED OFFER TO CLOSING")}</div>')
    H.append(f'<p class="cap">Every sale closed between {m["ptc_min"]:.0f} and {m["ptc_max"]:.0f} days after the offer was accepted.</p>')
    H.append(f'<div class="take"><span class="tag">Planning note</span><p>{escrow_point(m)}</p></div>')
    H.append(B.cash_block(m, 'seller'))

    # ------------------------------------------------------- 09 twelve months
    H.append(sec(nn(), 'Twelve months at a glance', pb=True))
    n_series = 9 if show_on else 7
    H.append(f'<p>{n_series} series, one page. Each tile carries the trend, the latest value and the change into the '
             'most recent complete month.</p>')
    fm = mshort_series([x for x in S['med_close'] if x == x])
    tiles = [
        (S['med_close'], 'MEDIAN CLOSED PRICE', fm(_lastv(S['med_close'])), _fd(d_med,'money'), False),
        (S['med_dom'], 'MEDIAN DAYS ON MARKET', f"{_lastv(S['med_dom']):.0f}", _fd(d_dtc), False),
        (S['new'], 'NEW LISTINGS', f"{_lastv(S['new']):.0f}", _fd(d_new), False),
        (S['total'], 'TOTAL LISTINGS', f"{_lastv(S['total']):.0f}", _fd(MO.mom(S['total'], mo['months'])), False),
        (S['pending'], 'WENT UNDER CONTRACT', f"{_lastv(S['pending']):.0f}", _fd(MO.mom(S['pending'], mo['months'])), False),
        (S['closed'], 'CLOSED SALES', f"{_lastv(S['closed']):.0f}", _fd(MO.mom(S['closed'], mo['months'])), False),
        (S['msi'], 'MONTHS OF SUPPLY', f"{_lastv(S['msi']):.1f}", _fd(d_msi), False),
    ]
    if show_on:
        tiles += [
            (spl, 'SHOWINGS PER LISTING', f"{_lastv(spl):.1f}", _pctd(spl), False),
            (stp, 'SHOWINGS TO PENDING', f"{_lastv(stp):g}", _pctd(stp), False),
        ]
    H.append('<div class="grid7">')
    for vals, l, big, dl, neg in tiles:
        H.append(f'<div class="g7">{spark(vals, l, big, dl or "&#8212;", neg)}</div>')
    H.append('</div>')
    _pt_col = next((c for c in ('Property Sub Type', 'Property Type', 'Structure Type') if c in cl and cl[c].notna().any()), None)
    _pt_note = None
    if _pt_col:
        _vc = cl[_pt_col].fillna('Unspecified').value_counts()
        if len(_vc) > 1:
            _pt_note = ', '.join(f'{_plural(t)} ({n})' for t, n in _vc.items())
    H.append(f'<p class="cap">Months shown: {full[0]} through {full[-1]}. The current partial month is excluded &mdash; '
             'a half-finished month reads as a collapse in every count. Every series above combines every property '
             'type present in this export' + (f' &mdash; {_pt_note}' if _pt_note else '') + ', and the '
             'month-over-month percentages are computed on that same combined series, not on any single type. '
             'Year-over-year on the MLS series needs a 24-month export; a 365-day file holds one observation of each '
             'calendar month. The earliest month or two understates inventory, because listings that left the market '
             'just before the window opened are not in the file.</p>')

    # ---------------------------------------------------------- 10 competition
    H.append(sec(nn(), 'What&rsquo;s on the market now', pb=True))
    H.append(tbl(arow, ['Address', 'Beds', 'Style', 'Finished sq ft', 'First asking price',
                        'Current price', 'Days on market']))
    H.append(f'<p class="cap">These are the homes a new listing would compete against today. '
             f'Median asking price among them is {M(m["act_med_list"])}.</p>')
    H.append(f'<div class="take"><span class="tag">Negotiating room</span><p>{leverage_point(m)}</p></div>')

    # ----------------------------------------------------------- 11 buyer purchasing power
    H.append(sec(nn(), 'Buyer purchasing power', pb=True))
    H.append(B.fin_block(m, cl, act, cfg) if hasattr(B, 'fin_block') else _fin_table(m, cl, act, cfg))
    H.append(concessions_power_block(m, cl, cfg))
    H.append(market_notes_block(m, cfg))
    H.append(net_sheet_pointer())

    # ------------------------------------------------------- investor score
    # Both audiences, per direct instruction -- unlike schools/amenities and
    # demographics, which are audience-gated, this renders for agent and
    # sales-rep alike whenever a profile is supplied. Silently absent when
    # investor is None, same pattern as every other optional enrichment.
    if investor:
        H.append(investor_block(investor, nn()))

    # ------------------------------------------------------- 12/13 schools/amen/demographics
    # Paused on request (schools/amenities pulled from the agent report for now).
    # Left as an easy re-enable rather than deleted: uncomment the
    # schools_amenities line to bring it back. Demographics stays wired below
    # it, gated on `demo`, which is only populated when the caller explicitly
    # passes demo_opts to build() -- it does not render by default today
    # regardless of this pause, so nothing else needs to change to keep it
    # dormant alongside schools/amenities.
    if audience == 'agent':
        # H.append(B.schools_amenities(sub, d, 'Master', nn(), nn(), auto=auto))
        if demo:
            H.append(demographics_block(demo, nn()))

    # -------------------------------------------------------- what stands out
    H.append(B.callout_block(d, m, cl, act, exp, 'both', nn()))
    H.append(B.outlier_block(cl, m))

    # --------------------------------------------------- brief/appendix split
    # Everything above this point is the market analysis -- what a seller or
    # buyer would actually review together with the agent. Everything below
    # (talking points, marketing copy, reel scripts, the email draft) is
    # agent-facing prep material, not something to hand across the table and
    # read line by line. Split into two documents at exactly this boundary
    # (rule 69): the Brief ends here, the Appendix starts at Talking Points.
    # The methodology block is computed here (moved up from where it used to
    # sit, at the very end) and reused verbatim in both documents, so each
    # stands on its own if shared separately -- an appendix a colleague opens
    # without the Brief still discloses its own scope and sources.
    _subdiv_names = []
    if 'Subdivision Name' in d:
        _seen = set()
        for v in d['Subdivision Name'].dropna().astype(str).str.strip():
            key = v.lower()
            if key and key not in _seen:
                _seen.add(key)
                _subdiv_names.append(v)
    if len(_subdiv_names) > 1:
        _scope = (f'The export covers {len(_subdiv_names)} MLS subdivision names reported together as one '
                  f'market: {", ".join(_subdiv_names)}. ')
    elif _subdiv_names:
        _scope = f'The export covers the MLS subdivision name {_subdiv_names[0]}. '
    else:
        _scope = ''
    meth = R.methodology(m, sub, extra=(
        '<strong>Scope.</strong> This master brief merges the Seller and Buyer briefs into one document, '
        'split into a Brief (the market analysis) and a companion Appendix (talking points and marketing '
        'copy). '
        f'{_scope}'
        '<strong>Showing data</strong>, when present, comes from a separate REcolorado / InfoSparks export '
        'for a user-defined area and is labeled wherever it appears; it is not drawn from the subdivision '
        'activity file. '
        '<strong>The scores on page one</strong> are computed from this export using the arithmetic printed '
        'beside each one, with two exceptions: Rent to Price and Growth Outlook are area-level, resolved '
        'from a bundled Colorado reference pack (Zillow, Census and BLS data) via this export\'s own ZIP '
        'codes rather than computed from the export itself -- each states its own geography on the dial. '
        'None of the five are licensed from, or comparable to, any third-party market score. '
        '<strong>Investor Score</strong>, when present, is a separate legacy score built entirely from '
        'outside data rather than the MLS export &mdash; its own section states every source and geography. '
        '<strong>The market notes in Buyer Purchasing Power</strong> are general policy and cost context, '
        'sourced and dated where they appear, not computed from this export.'))
    # The boilerplate asserts a single-file report. This brief may carry several clearly
    # labeled companion sources, so the sentence enumerates whichever are actually present
    # in this run rather than naming just one and leaving the rest uncounted.
    exceptions = ['Rent to Price and Growth Outlook on page one, resolved from a bundled Colorado '
                  'reference pack rather than this export']
    if show_on:
        exceptions.append('the showing-activity section and its two tiles in the twelve-month grid, from a '
                          'separate REcolorado / InfoSparks export for a user-defined area')
    if investor:
        exceptions.append('the Investor Score section, built from Zillow, Census Bureau and Bureau of Labor '
                          'Statistics data rather than this export')
    exceptions.append('the general market notes in Buyer Purchasing Power, which are policy and cost context, '
                      'not figures computed from this file')
    if len(exceptions) == 1:
        exc_txt = exceptions[0]
    else:
        exc_txt = '; '.join(exceptions[:-1]) + '; and ' + exceptions[-1]
    meth = meth.replace(
        'All figures in this report are drawn from that single file; no outside market data is used.',
        f'Most figures in this report are drawn from that single file. The stated exceptions are: {exc_txt}. '
        f'No other outside market data is used.')
    H.append(meth)
    H.append('</body></html>')
    brief_split = len(H)

    # ------------------------------------------------------- 15 talking points
    sp, bp = TP.pick(d, m, cl, bd)
    H.append(sec(nn(), 'Talking points', pb=True))
    H.append('<div class="lane">')
    H.append('<div class="sell"><div class="lanek">IF YOU ARE SELLING</div><ul>'
             + ''.join(f'<li>&ldquo;{p["text"]}&rdquo;</li>' for p in sp) + '</ul></div>')
    H.append('<div class="buy"><div class="lanek">IF YOU ARE BUYING</div><ul>'
             + ''.join(f'<li>&ldquo;{p["text"]}&rdquo;</li>' for p in bp) + '</ul></div>')
    H.append('</div>')
    H.append(f'<p class="cap">Both the wording and the <em>choice of subjects</em> come from this '
             f'export. Every candidate topic is scored for how unusual it is here and only those '
             f'clearing the threshold are printed, so a different subdivision surfaces a different '
             f'list &mdash; this run selected {len(sp)} seller and {len(bp)} buyer points from '
             f'{len(TP.SELLER_TESTS)} and {len(TP.BUYER_TESTS)} candidates. What sellers got '
             f'against the original asking price, and what buyers paid against it, always appear: '
             f'they are the subject of the conversation whether or not the spread is unusual.</p>')

    # -------------------------------------------------------------- marketing
    H.append(MK.section(d, m, sub, city, 'seller', nn(), mo))
    H.append(_buyer_marketing(d, m, sub, city, mo))

    H.append(meth)
    H.append('</body></html>')

    brief_html = ''.join(x for x in H[:brief_split] if x)
    appendix_preamble = (f'<!doctype html><html><head><meta charset="utf-8">'
                        f'<style>{R.CSS}{EXTRA}</style></head><body>'
                        + appendix_cover(sub, city, span))
    appendix_html = appendix_preamble + ''.join(x for x in H[brief_split:] if x)
    return brief_html, appendix_html


def _fd(dd, kind='count'):
    """(text, note) -> a single string naming the two months actually compared."""
    if dd is None: return '&#8212;'
    txt, note = MO.fmt_delta(dd, kind)
    tail = f" vs {dd['prev_m'].split()[0]}" if not dd['adjacent'] else ''
    return f"{txt}{(' '+note) if note else ''}{tail}"


def _pctd(v):
    """Month-over-month change for a plain list, in the same voice as _fd."""
    vv = [x for x in v if x is not None and x == x]
    if len(vv) < 2: return '&#8212;'
    cur, prev = vv[-1], vv[-2]
    if not prev: return f'{cur-prev:+g}'
    return f'{(cur-prev)/prev*100:+.0f}%'


def _lastv(v):
    for x in reversed(v):
        if x is not None and x == x:
            return x
    return float('nan')


def concessions_power_block(m, cl, cfg):
    """What a concession is actually worth to a buyer's own payment.

    The points-to-rate conversion below is a widely cited industry rule of
    thumb (roughly one discount point per quarter-point of rate), not a
    lender quote -- it is labeled that way in the output, the same way the
    rest of this financing section labels its assumptions. An individual
    buyer's actual buy-down math depends on their lender's own pricing.
    """
    if not m['n_cl'] or m['conc_n'] == 0:
        return ('<h3>What a concession is worth</h3>'
                '<p class="cap">No sales in this export included a seller-paid concession, so there is '
                'nothing to illustrate here.</p>')
    share = 100 * m['conc_n'] / m['n_cl']
    price = m['med']
    down = 0.10
    loan = price * (1 - down)
    base = pmt(loan, cfg=cfg)
    pts = (m['conc_med'] / loan) * 100 if loan else 0
    rate_cut = pts * 0.0025
    reduced = pmt(loan, rate=max(cfg['rate'] - rate_cut, 0.01), cfg=cfg)
    delta = base - reduced
    return f'''<h3>What a concession is worth</h3>
<p>{m['conc_n']} of {m['n_cl']} buyers here received a concession &mdash; a {share:.0f}% chance for a buyer
shaped like the ones already in this dataset, all else equal. Where one was paid, the median was
{M(m['conc_med'])}.</p>
<div class="formula"><b>ILLUSTRATIVE ONLY.</b> On the median sale price of {M(price)} at {down*100:.0f}% down,
{M(m['conc_med'])} directed entirely to a permanent rate buy-down is roughly {pts:.2f} discount points on a
{M(loan)} loan. Using the common industry rule of thumb of about 0.25% of rate per point:<br>
&nbsp;&nbsp;At the current rate, {cfg['rate']*100:.2f}%: <b>{M(base)}</b> principal &amp; interest<br>
&nbsp;&nbsp;With the buy-down, about {(cfg['rate']-rate_cut)*100:.2f}%: <b>{M(reduced)}</b> principal &amp; interest<br>
&nbsp;&nbsp;Estimated monthly difference: <b>{M(delta)}</b><br>
This is a rule-of-thumb illustration, not a lender quote &mdash; the real conversion depends on the buyer&rsquo;s
own lender, loan program and the day&rsquo;s pricing. A concession can just as easily go toward closing costs
instead of a buy-down, which changes this math entirely; that allocation is the buyer&rsquo;s and lender&rsquo;s
call, not something this report can see.</div>'''


def _fin_table(m, cl, act, cfg):
    price = m['med']
    fm = fin_metrics(cl, act)
    rows = []
    for dn, lbl in [(0.03, '3% down'), (0.10, '10% down'), (0.20, '20% down')]:
        tax = fm['tax_med']
        p = piti(price, dn, tax, fm['hoa_med'], cfg=cfg)
        rows.append((lbl, M(price*dn), M(price*(1-dn)), M(p['pi']), M(p.get('mi', 0)), M(p['hoa']), M(p['total'])))
    jum = 'above' if price > cfg['conforming'] else 'below'
    hoa_line = ''
    if fm['hoa_n'] and fm['hoa_any']:
        hoa_line = (f' HOA dues are recorded on {fm["hoa_any"]} of {fm["hoa_n"]} sales here, billed '
                   f'{(fm["hoa_note"] or "at a frequency not specified").lower()}; the median annual figure, '
                   f'{M(fm["hoa_med"])}, is built into the payment above. A home without dues, or with dues '
                   f'above or below this median, will differ from this table.')
    return (f'<p>Illustrative only, on the median sale price of {M(price)} and the median annual tax of '
            f'{M(fm["tax_med"])} in this export. Rate: {cfg["rate"]*100:.2f}% '
            f'({cfg["rate_src"]}). No rate here is quoted for an individual buyer &mdash; that is a licensed '
            f'loan officer&rsquo;s job.</p>'
            + tbl(rows, ['Scenario', 'Down payment', 'Loan amount', 'Principal &amp; interest',
                         'Mortgage insurance', 'HOA', 'Est. monthly PITI'])
            + f'<p class="cap">The 2026 conforming loan limit for {cfg["county"]} is {M(cfg["conforming"])}. '
              f'The median sale price here sits {jum} that limit. Taxes come from the export; homeowners '
              f'insurance is estimated at {cfg["ins_rate"]*100:.2f}% of price a year and conventional mortgage '
              f'insurance at {cfg["pmi_rate"]*100:.2f}% of the loan a year. Both are assumptions, not quotes '
              f'&mdash; see the note below on why the insurance figure in particular is worth double-checking '
              f'with a current quote in this market.{hoa_line}</p>')


def _buyer_marketing(d, m, sub, city, mo):
    """Buyer-audience social copy, so the master brief carries both conversations."""
    month_ok, last_n = MK._month_ok(mo, m)
    st = monthly_standouts(mo, top=3)
    posts = MK.social_posts(m, sub, city, st, month_ok, 'buyer')
    reels = MK.reel_scripts(m, sub, city, st, month_ok, 'buyer')
    return ('<h3>Buyer-side social posts</h3>'
            + ''.join(MK._post_html(p) for p in posts)
            + '<h3>Buyer-side reel scripts</h3>'
            + ''.join(MK._reel_html(r) for r in reels))


# ==================================================================== driver
def build(csv, sub, city, outdir='/mnt/user-data/outputs', enrich_opts=None,
          audience='agent', showings_paths=None, demo_opts=None,
          investor_profile=None, investor_opts=None, carousel=False):
    """audience: 'agent' (default) or 'salesrep'.
      agent    -- no Showing Activity section; schools/amenities + Census
                  demographics included when enrich_opts/demo_opts supplied.
      salesrep -- Showing Activity included when showings_paths supplied;
                  schools/amenities and demographics are never rendered.

    showings_paths: (spl_csv_path, stp_csv_path) tuple, salesrep only. Either
    element may be None. Ignored entirely for the agent audience.

    demo_opts: dict passed to demographics.enrich(), e.g. {'api_key': ...}.
    Agent audience only; ignored for salesrep.

    investor_profile: a ready-built dict from investor.score() or
    investor.manual_profile() -- takes priority over investor_opts. Renders
    for BOTH audiences when supplied, unlike schools/demographics.

    investor_opts: dict passed to investor.enrich() when investor_profile is
    not supplied directly, e.g. {'metro_emp_yoy': 0.7, 'metro_emp_geo': ...,
    'pop_growth_4yr': -1.6, 'pop_geo': ...}. 'zip5' defaults to the export's
    own most common Postal Code if not given.

    carousel: writes the 1080x1350 social carousel (six PNGs + a combined
    PDF) alongside the Master Brief, sourced from the SAME scores() this
    function already computes for the page-one dashboard, plus Rent to
    Price / Growth Outlook resolved from the bundled Colorado reference pack
    (co_data.py) via the export's own ZIPs -- no separate upload. A dial that
    can't resolve (no rent series for the area, the common case outside the
    Front Range) is omitted from the carousel, never zeroed. This mirrors
    build.py's carousel wiring; master.py never had it until now -- see
    SKILL.md rule 59 and the note on rule 58's PDF/carousel naming mismatch,
    which applies here exactly as it does to build.py's path.
    """
    assert audience in ('agent', 'salesrep'), f'unknown audience {audience!r}'
    d = core.load(csv)
    m, cl, act, exp = core.metrics(d)
    cfg = core.set_county(d)
    stale, age, msg = core.check_rate(cfg, strict=True)

    auto = None
    if audience == 'agent' and enrich_opts is not None:
        # Enrichment is best-effort by design: a market report must never fail to
        # build because a school API was slow or a key was missing.
        import enrich as EN
        auto, ew = EN.enrich(d, sub, **enrich_opts)
        for w in ew:
            print(f'[enrich] {w}')

    demo = None
    if audience == 'agent' and demo_opts is not None:
        import enrich as EN
        import demographics as DM
        try:
            lat, lon = EN.centroid(d)
        except EN.EnrichError as exc:
            print(f'[demographics] could not compute centroid: {exc}')
            lat = lon = None
        if lat is not None:
            demo, dw = DM.enrich(lat, lon, **demo_opts)
            for w in dw:
                print(f'[demographics] {w}')

    investor = investor_profile
    if investor is None and investor_opts is not None:
        import investor as INV
        opts = dict(investor_opts)
        if 'zip5' not in opts and 'Postal Code' in d:
            modal = d['Postal Code'].dropna()
            if len(modal):
                opts['zip5'] = str(int(modal.mode().iloc[0]))
        if 'zip5' in opts:
            investor, iw = INV.enrich(**opts)
            for w in iw:
                print(f'[investor] {w}')
        else:
            print('[investor] no zip5 supplied and none found in the export; skipped.')

    showings_prof = None
    if audience == 'salesrep' and showings_paths is not None:
        spl_path, stp_path = showings_paths
        try:
            showings_prof = SH.load(spl_path, stp_path)
        except (OSError, ValueError) as exc:
            print(f'[showings] {exc}')
            showings_prof = None

    # Resolved once, early, so both the page-one dashboard and (if requested)
    # the carousel use the same numbers -- previously this only ran for the
    # carousel, after the PDF's own HTML was already built, so Rent to Price
    # and Growth Outlook never appeared anywhere in the PDF itself even
    # though the carousel had them. See SKILL.md rule 69.
    import co_data as CD
    area_warnings = []
    try:
        ctx = CD.from_export(d)
        area = ctx.as_dict()
        if ctx.spans_zips:
            area_warnings.append(
                f"Subdivision spans ZIPs {', '.join(ctx.zips)}; area dials use "
                f"{ctx.zip} (largest share of listings), not an average.")
        for k, why in ctx.dropped.items():
            area_warnings.append(f'Area dial dropped ({k}): {why}')
    except Exception as exc:                     # pack missing or malformed
        area = None
        area_warnings.append(f'Area dials unavailable: {exc}')
    for w in area_warnings:
        print(f'[area] {w}')

    brief_html, appendix_html = report_html(d, m, cl, act, exp, sub, city, cfg, auto=auto,
                       audience=audience, showings_prof=showings_prof, demo=demo,
                       investor=investor, area=area)
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='brief_')
    hp = os.path.join(tmp, 'brief.html')
    open(hp, 'w').write(brief_html)
    hp_appendix = os.path.join(tmp, 'appendix.html')
    open(hp_appendix, 'w').write(appendix_html)
    suffix = 'Sales_Brief' if audience == 'salesrep' else 'Master_Brief'
    out = os.path.join(outdir, f'{sub.replace(" ", "_")}_{suffix}.pdf')
    out_appendix = os.path.join(outdir, f'{sub.replace(" ", "_")}_{suffix}_Appendix.pdf')

    async def go():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page()
            await pg.goto('file://'+hp)
            await pg.pdf(path=out, format='Letter', print_background=True)
            await pg.goto('file://'+hp_appendix)
            await pg.pdf(path=out_appendix, format='Letter', print_background=True)
            await b.close()
    asyncio.run(go())

    paths = [out, out_appendix]
    if carousel:
        import carousel as CA
        paths.extend(CA.render(m, sub, city, outdir, scores=s_scores(d, m, cl), area=area))

    return paths, m, s_scores(d, m, cl)


def s_scores(d, m, cl):
    return scores(d, m, cl)


if __name__ == '__main__':
    aud = sys.argv[4] if len(sys.argv) > 4 else 'agent'
    p, m, s = build(sys.argv[1], sys.argv[2], sys.argv[3], audience=aud)
    print('wrote', p)
    print('scores', {k: s[k] for k in ('chance', 'power', 'balance')})
