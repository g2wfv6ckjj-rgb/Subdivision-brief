import pandas as pd, numpy as np, math, html
from core import INK,PINE,SAGE,BRONZE,BRZT,DEEP,SAND,LINE,SOFT,MIST,F,FP,M,Mshort,mdec,mshort_series,moi_label,moi_tier

def waffle(m):
    S,G,PER=44,7,11; cells=[PINE]*m['n_cl']+[SAGE]*m['n_act']+[SAND]*m['n_exp']
    rows=math.ceil(len(cells)/PER); W=PER*(S+G); H=rows*(S+G)+56
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Every listing by outcome">'
    for i,c in enumerate(cells):
        x=(i%PER)*(S+G); y=(i//PER)*(S+G)
        s+=f'<rect x="{x}" y="{y}" width="{S}" height="{S}" rx="4" fill="{c}"/>'
        s+=f'<path d="M {x+11} {y+24} L {x+22} {y+14} L {x+33} {y+24} L {x+33} {y+33} L {x+11} {y+33} Z" fill="#fff" opacity=".55"/>'
    ly=rows*(S+G)+26
    for i,(n,c,lab) in enumerate([(m['n_cl'],PINE,'SOLD'),(m['n_act'],SAGE,'FOR SALE NOW'),(m['n_exp'],SAND,'NOT SOLD OR PENDING')]):
        x=i*195
        s+=f'<rect x="{x}" y="{ly-13}" width="15" height="15" rx="3" fill="{c}"/>'
        s+=f'<text x="{x+22}" y="{ly}" font-size="15" font-weight="700" fill="{INK}" font-family="{FP}">{n}</text>'
        s+=f'<text x="{x+22}" y="{ly+15}" font-size="9" fill="{SOFT}" letter-spacing="1" font-family="{F}">{lab}</text>'
    return s+'</svg>'

def gauge(m):
    W,H,CX,CY,R=760,286,380,196,150; MAXM=9.0
    frac=min(m['moi']/MAXM,1.0)
    def pt(f,r):
        a=math.pi*(1-f); return CX+r*math.cos(a), CY-r*math.sin(a)
    def arc(f0,f1,r,wd,col):
        x0,y0=pt(f0,r); x1,y1=pt(f1,r); lg=1 if (f1-f0)>0.5 else 0
        return f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 {lg} 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linecap="round"/>'
    lab=moi_label(m['moi'])
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Months of supply">'
    s+=arc(0,1,R,30,'#E4EAF2')+arc(0,frac,R,30,PINE)
    x,y=pt(frac,R)
    s+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#fff" stroke="{PINE}" stroke-width="4"/>'
    s+=f'<text x="{CX}" y="{CY-52}" font-size="44" font-weight="700" fill="{INK}" text-anchor="middle" font-family="{FP}">{m["moi"]:.1f}</text>'
    s+=f'<text x="{CX}" y="{CY-30}" font-size="13" fill="{SOFT}" text-anchor="middle" font-family="{FP}">months of supply</text>'
    for bp in (3.0,6.0):
        fb=bp/MAXM; xa,ya=pt(fb,R-17); xb,yb=pt(fb,R+17)
        s+=f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" stroke="#fff" stroke-width="2.5"/>'
        xl,yl=pt(fb,R+30)
        s+=f'<text x="{xl:.1f}" y="{yl:.1f}" font-size="8" fill="{SOFT}" text-anchor="middle" font-family="{F}">{bp:.0f}</text>'
    s+=f'<text x="{CX-R-6}" y="{CY+22}" font-size="10" fill="{SOFT}" text-anchor="middle" letter-spacing="1.5" font-family="{F}">SELLER\u2019S</text>'
    s+=f'<text x="{CX+R+6}" y="{CY+22}" font-size="10" fill="{SOFT}" text-anchor="middle" letter-spacing="1.5" font-family="{F}">BUYER\u2019S</text>'
    s+=f'<text x="{CX}" y="{CY+40}" font-size="17" font-weight="700" fill="{PINE}" text-anchor="middle" font-family="{FP}">{lab}</text>'
    s+=f'<text x="{CX}" y="{CY+58}" font-size="10.5" fill="{SOFT}" text-anchor="middle" font-family="{FP}">{m["n_act"]} homes for sale &#183; {m["n_cl"]} sold in the last 12 months</text>'
    s+=f'<text x="{CX}" y="{CY+76}" font-size="9" fill="{SOFT}" text-anchor="middle" font-family="{F}">TICKS MARK THE STANDARD 3 AND 6 MONTH BREAKPOINTS</text>'
    return s+'</svg>'

def money_step(span, target=6):
    """A round 1/2/2.5/5/10 x 10^n step that divides `span` into about `target`
    gridlines. Keeps any price range legible without a per-report setting."""
    if span <= 0: return 1
    raw = span / target
    p = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= p * mult: return p * mult
    return p * 10

def dumbbell(cl):
    cl=cl.copy(); cl['diff']=cl['Close Price']-cl['Original List Price']
    ab=cl[cl['diff']>=0].sort_values('Close Price',ascending=False)
    be=cl[cl['diff']<0].sort_values('Close Price',ascending=False)
    lo=math.floor(min(cl['Original List Price'].min(),cl['Close Price'].min())/25000)*25000-15000
    hi=math.ceil(max(cl['Original List Price'].max(),cl['Close Price'].max())/25000)*25000+15000
    W,ROW,LB,RB=760,25,146,150; H=len(cl)*ROW+96
    def X(v): return LB+(v-lo)/(hi-lo)*(W-LB-RB)
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Asking price versus sale price">'
    s+=f'<defs><marker id="ar" markerWidth="7" markerHeight="7" refX="5.6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{BRONZE}"/></marker></defs>'
    # Gridline spacing is derived from the price span, never fixed. A fixed $50K step
    # drew 54 labels into 760px on a $760K-$3.4M subdivision -- an unreadable smear
    # along the axis. money_step() targets ~6 gridlines at any scale, so a $400K
    # neighborhood and a $4M one both come out legible with no per-report edit.
    step=money_step(hi-lo)
    ticks=[]
    g=math.ceil(lo/step)*step
    while g<=hi:
        ticks.append(g); g+=step
    fmt=mshort_series(ticks)
    for g in ticks:
        s+=f'<line x1="{X(g):.1f}" y1="34" x2="{X(g):.1f}" y2="{H-40}" stroke="{LINE}" stroke-width=".7"/>'
        s+=f'<text x="{X(g):.1f}" y="{H-26}" font-size="9" fill="{SOFT}" text-anchor="middle" font-family="{F}">{fmt(g)}</text>'
    y=44
    for grp,ttl,col,tcol in [(ab,f'GOT THE FULL ASKING PRICE OR MORE  \u2014  {len(ab)} HOMES',PINE,PINE),
                             (be,f'SOLD FOR LESS THAN THE FIRST ASKING PRICE  \u2014  {len(be)} HOMES',BRONZE,BRZT)]:
        s+=f'<rect x="0" y="{y-15:.0f}" width="{W}" height="17" fill="{MIST}"/>'
        s+=f'<text x="4" y="{y-3:.0f}" font-size="9.4" font-weight="700" fill="{tcol}" letter-spacing=".7" font-family="{F}">{ttl}</text>'
        y+=13
        for _,r in grp.iterrows():
            o,c=r['Original List Price'],r['Close Price']; dd=c-o
            s+=f'<text x="0" y="{y+4:.1f}" font-size="9" fill="{INK}" font-family="{F}">{html.escape(str(r["addr"])[:21])}</text>'
            if abs(X(c)-X(o))>4:
                mk=' marker-end="url(#ar)"' if dd<0 else ''
                s+=f'<line x1="{X(o):.1f}" y1="{y:.1f}" x2="{X(c):.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="2.2" opacity=".5"{mk}/>'
            s+=f'<circle cx="{X(o):.1f}" cy="{y:.1f}" r="3.6" fill="#fff" stroke="{SOFT}" stroke-width="1.5"/>'
            s+=f'<circle cx="{X(c):.1f}" cy="{y:.1f}" r="4.6" fill="{col}"/>'
            lab=M(c)+('' if dd==0 else ('  +'+M(dd)[1:] if dd>0 else '  \u2212'+M(-dd)[1:]))
            s+=f'<text x="{W-RB+14}" y="{y+4:.1f}" font-size="9.2" font-weight="700" fill="{tcol}" font-family="{F}">{lab}</text>'
            y+=ROW
        y+=12
    s+=f'<circle cx="{LB+6}" cy="14" r="3.6" fill="#fff" stroke="{SOFT}" stroke-width="1.5"/><text x="{LB+16}" y="17.5" font-size="9" fill="{SOFT}" font-family="{F}">First asking price</text>'
    s+=f'<circle cx="{LB+186}" cy="14" r="4.6" fill="{PINE}"/><text x="{LB+196}" y="17.5" font-size="9" fill="{SOFT}" font-family="{F}">What it sold for</text>'
    return s+'</svg>'

def speed(cl):
    labs=['Within 1 week','1 to 2 weeks','2 weeks to 1 month','1 to 2 months','Longer than 2 months']
    v=pd.cut(cl['Days In MLS'],[-1,7,14,30,60,10**6],labels=labs).value_counts().reindex(labs).values
    W,RH=760,40; H=len(labs)*RH+26; LBL=210; BARW=W-LBL-150
    mx=max(v.max(),1)
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="How quickly homes went under contract">'
    for i,l in enumerate(labs):
        y=6+i*RH; bw=v[i]/mx*BARW
        col=[PINE,PINE,SAGE,BRONZE,DEEP][i]
        s+=f'<text x="0" y="{y+18:.0f}" font-size="10.6" fill="{INK}" font-family="{FP}">{l}</text>'
        s+=f'<rect x="{LBL}" y="{y:.0f}" width="{max(bw,2):.1f}" height="24" rx="3" fill="{col}"/>'
        pct=v[i]/v.sum()*100
        s+=f'<text x="{LBL+max(bw,2)+10:.1f}" y="{y+17:.0f}" font-size="12.5" font-weight="700" fill="{col}" font-family="{FP}">{v[i]} home{"s" if v[i]!=1 else ""}</text>'
        s+=f'<text x="{LBL+max(bw,2)+80:.1f}" y="{y+17:.0f}" font-size="9.4" fill="{SOFT}" font-family="{F}">{pct:.0f}%</text>'
    return s+'</svg>'

def strip(vals,lo,hi,band=None,med=None,unit='',label='',dot=SAGE,W=760,H=120):
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{label}">'
    def X(v): return 45+(v-lo)/(hi-lo)*(W-110)
    if band:
        s+=f'<rect x="{X(band[0]):.1f}" y="24" width="{X(band[1])-X(band[0]):.1f}" height="46" rx="4" fill="{MIST}" stroke="{SAGE}" stroke-width="1.2"/>'
        s+=f'<text x="{(X(band[0])+X(band[1]))/2:.1f}" y="18" font-size="10" font-weight="700" fill="{PINE}" text-anchor="middle" font-family="{F}">{band[2]}</text>'
    for v in vals: s+=f'<circle cx="{X(v):.1f}" cy="47" r="5" fill="{dot}" opacity=".85"/>'
    if med is not None:
        s+=f'<line x1="{X(med):.1f}" y1="20" x2="{X(med):.1f}" y2="74" stroke="{BRONZE}" stroke-width="2"/>'
        s+=f'<text x="{X(med):.1f}" y="88" font-size="11" font-weight="700" fill="{BRZT}" text-anchor="middle" font-family="{FP}">Typical: {med:,.0f}{unit}</text>'
    n=6; 
    for i in range(n+1):
        t=lo+(hi-lo)*i/n
        s+=f'<text x="{X(t):.1f}" y="{H-14}" font-size="9" fill="{SOFT}" text-anchor="middle" font-family="{F}">{t:,.0f}</text>'
    s+=f'<text x="{W-40}" y="{H-2}" font-size="8.6" fill="{SOFT}" text-anchor="end" letter-spacing="1.2" font-family="{F}">{label.upper()}</text>'
    return s+'</svg>'

def timelines(cl):
    red=cl[cl['red']].sort_values('ttl'); ref=cl[~cl['red']]['ttl'].median()
    rows=[(r['addr'],int(r['Days In MLS']),int(r['ptc']),int(r['cut'])) for _,r in red.iterrows()]
    mx=max([r[1]+r[2] for r in rows]+[ref])*1.12
    W,RH,LB=760,32,150; H=(len(rows)+1)*RH+52
    def X(v): return LB+v/mx*(W-LB-190)
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Listing to closing timeline">'
    step=50 if mx>140 else 20
    g=0
    while g<=mx:
        s+=f'<line x1="{X(g):.1f}" y1="12" x2="{X(g):.1f}" y2="{H-34}" stroke="{LINE}" stroke-width=".7"/>'
        s+=f'<text x="{X(g):.1f}" y="{H-20}" font-size="9" fill="{SOFT}" text-anchor="middle" font-family="{F}">{g}</text>'
        g+=step
    s+=f'<text x="0" y="22" font-size="9.6" fill="{INK}" font-family="{F}">Typical, no change</text>'
    s+=f'<rect x="{X(0):.1f}" y="14" width="{X(ref)-X(0):.1f}" height="18" rx="2.5" fill="{SAGE}"/>'
    s+=f'<text x="{X(ref)+9:.1f}" y="27" font-size="11" font-weight="700" fill="{PINE}" font-family="{FP}">{ref:.0f} days</text>'
    for i,(nm,dtc,ptc,cut) in enumerate(rows):
        y=14+(i+1)*RH
        s+=f'<text x="0" y="{y+13:.1f}" font-size="9.6" fill="{INK}" font-family="{F}">{html.escape(str(nm)[:20])}</text>'
        s+=f'<rect x="{X(0):.1f}" y="{y:.1f}" width="{max(X(dtc)-X(0),2):.1f}" height="18" rx="2.5" fill="{BRONZE}"/>'
        s+=f'<rect x="{X(dtc):.1f}" y="{y:.1f}" width="{max(X(ptc)-X(0),2):.1f}" height="18" rx="2.5" fill="{PINE}"/>'
        t=dtc+ptc
        s+=f'<text x="{X(t)+9:.1f}" y="{y+13:.1f}" font-size="11" font-weight="700" fill="{INK}" font-family="{FP}">{t} days</text>'
        s+=f'<text x="{X(t)+62:.1f}" y="{y+13:.1f}" font-size="9" fill="{SOFT}" font-family="{F}">cut {M(cut)}</text>'
    s+=f'<rect x="{LB}" y="{H-13}" width="13" height="13" rx="2" fill="{BRONZE}"/><text x="{LB+19}" y="{H-3}" font-size="9.4" fill="{INK}" font-family="{F}">Waiting for an offer</text>'
    s+=f'<rect x="{LB+215}" y="{H-13}" width="13" height="13" rx="2" fill="{PINE}"/><text x="{LB+234}" y="{H-3}" font-size="9.4" fill="{INK}" font-family="{F}">Under contract, heading to closing</text>'
    return s+'</svg>'

def cols(vals,labels,unit,cols_=None,fmt='{:.0f}',W=760,H=210,base=138):
    mx=max(vals)*1.18 if max(vals) else 1
    GW=(W-60)/len(vals); s=f'<svg viewBox="0 0 {W} {H}" width="100%">'
    for i,v in enumerate(vals):
        bx=50+i*GW+GW*0.17; bw=GW*0.66; bh=v/mx*base
        c=cols_[i] if cols_ else PINE
        s+=f'<rect x="{bx:.1f}" y="{base+14-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{c}"/>'
        s+=f'<text x="{bx+bw/2:.1f}" y="{base+8-bh:.1f}" font-size="15" font-weight="700" fill="{c}" text-anchor="middle" font-family="{FP}">{fmt.format(v)}</text>'
        s+=f'<text x="{bx+bw/2:.1f}" y="{base+34:.0f}" font-size="10.4" fill="{INK}" text-anchor="middle" font-family="{FP}">{labels[i]}</text>'
    s+=f'<line x1="46" y1="{base+14}" x2="{W-14}" y2="{base+14}" stroke="{INK}" stroke-width="1.2"/>'
    s+=f'<text x="{W/2:.0f}" y="{H-6}" font-size="9.6" fill="{SOFT}" text-anchor="middle" letter-spacing="1.4" font-family="{F}">{unit}</text>'
    return s+'</svg>'

def leverage(m):
    W,H,RH=760,190,50
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Buyer leverage by time on market">'
    s+=f'<text x="0" y="12" font-size="9" fill="{SOFT}" letter-spacing="1.5" font-family="{F}">WHAT BUYERS PAID, AS A SHARE OF THE FIRST ASKING PRICE</text>'
    base=100.0; mn=min(x[2] for x in m['lev'])-1.5
    for i,(lab,n,cpo,conc) in enumerate(m['lev']):
        y=26+i*RH
        w=(cpo-mn)/(base-mn)*(W-420)
        col=[PINE,SAGE,BRONZE][i]
        s+=f'<text x="0" y="{y+19:.0f}" font-size="10.8" fill="{INK}" font-family="{FP}">On the market {lab}</text>'
        s+=f'<text x="0" y="{y+32:.0f}" font-size="9" fill="{SOFT}" font-family="{F}">{n} sale{"s" if n!=1 else ""}</text>'
        s+=f'<rect x="200" y="{y:.0f}" width="{max(w,3):.1f}" height="28" rx="3" fill="{col}"/>'
        s+=f'<text x="{200+max(w,3)+10:.1f}" y="{y+20:.0f}" font-size="15" font-weight="700" fill="{col}" font-family="{FP}">{cpo:.1f}%</text>'
        s+=f'<text x="{200+max(w,3)+72:.1f}" y="{y+20:.0f}" font-size="9.4" fill="{SOFT}" font-family="{F}">avg credit {M(conc)}</text>'
    return s+'</svg>'

def mixbars(pairs,title,W=760,H=None):
    H=H or (len(pairs)*34+40)
    mx=max(v for _,v,_ in pairs) or 1
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{title}">'
    s+=f'<text x="0" y="12" font-size="9" fill="{SOFT}" letter-spacing="1.5" font-family="{F}">{title.upper()}</text>'
    for i,(lab,v,sub) in enumerate(pairs):
        y=26+i*34; w=v/mx*(W-330)
        s+=f'<text x="0" y="{y+16:.0f}" font-size="10.6" fill="{INK}" font-family="{FP}">{lab}</text>'
        s+=f'<rect x="200" y="{y:.0f}" width="{max(w,3):.1f}" height="22" rx="3" fill="{PINE}"/>'
        s+=f'<text x="{200+max(w,3)+9:.1f}" y="{y+16:.0f}" font-size="12" font-weight="700" fill="{PINE}" font-family="{FP}">{v}</text>'
        if sub: s+=f'<text x="{200+max(w,3)+40:.1f}" y="{y+16:.0f}" font-size="9.2" fill="{SOFT}" font-family="{F}">{sub}</text>'
    return s+'</svg>'


# --------------------------------------------------------------- month-over-month
# One line and one bar renderer, both multi-series so a mixed-property-type export
# colours automatically. Palette is the shared one; nothing is styled per report.
TYPE_COLORS = [PINE, BRONZE, SAGE, DEEP, BRZT, INK]

def _nice(hi):
    if hi <= 0: return 1, 1
    import math as _m
    step = 10 ** _m.floor(_m.log10(hi))
    for mult in (1, 2, 2.5, 5, 10):
        if hi / (step * mult) <= 4: return step * mult, _m.ceil(hi / (step * mult)) * step * mult
    return step * 10, _m.ceil(hi / (step * 10)) * step * 10

def _axes(W, H, L, R, T, B, hi, labels, money=False, dec=0):
    step, top = _nice(hi)
    s, n = '', len(labels)
    y = lambda v: H - B - (v / top) * (H - T - B)
    # Precision comes from the gridline values themselves, so every label on one
    # axis is rendered at the same scale -- that uniformity is what reads as balanced.
    gridvals = []
    g = 0.0
    while g <= top + 1e-9:
        gridvals.append(g); g += step
    mfmt = mshort_series(gridvals)
    g = 0.0
    while g <= top + 1e-9:
        yy = y(g)
        s += f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="{LINE}" stroke-width=".5"/>'
        lab = mfmt(g) if money else (f'{g:,.{dec}f}')
        s += f'<text x="{L-6}" y="{yy+3:.1f}" font-size="8" fill="{SOFT}" text-anchor="end" font-family="{F}">{lab}</text>'
        g += step
    bw = (W - L - R) / n
    for i, lb in enumerate(labels):
        s += f'<text x="{L+bw*(i+.5):.1f}" y="{H-B+13}" font-size="8" fill="{SOFT}" text-anchor="middle" font-family="{F}">{lb}</text>'
    return s, y, top, bw

def _legend(W, H, keys, colors):
    if len(keys) <= 1: return ''
    s, x = '', 0
    for k, c in zip(keys, colors):
        s += f'<rect x="{x}" y="{H-11}" width="9" height="9" rx="2" fill="{c}"/>'
        s += f'<text x="{x+13}" y="{H-3}" font-size="8" fill="{SOFT}" font-family="{F}">{html.escape(k)}</text>'
        x += 16 + len(k) * 4.9
    return s

def _pt_label(x, yy, txt, above=True):
    """Small value label pinned to a data point, nudged clear of the marker."""
    dy = -7 if above else 12
    anchor = 'middle'
    return (f'<text x="{x:.1f}" y="{yy+dy:.1f}" font-size="7.5" fill="{SOFT}" '
            f'text-anchor="{anchor}" font-family="{F}">{txt}</text>')


def _delta_chip(chips, X, W, H):
    """Compact change panel drawn inside the SVG, to the right of the plot, so the
    metric occupies one row instead of a stacked card block plus a chart. `chips`
    is a list of (heading, big, sub, negative) tuples -- one for MoM, optionally a
    second for YoY."""
    s = f'<line x1="{X-14}" y1="18" x2="{X-14}" y2="{H-24}" stroke="{LINE}" stroke-width=".5"/>'
    n = len(chips)
    slot = (H - 30) / n
    for i, (head, big, sub, neg) in enumerate(chips):
        y0 = 20 + i * slot
        col = BRZT if neg else PINE
        s += (f'<text x="{X}" y="{y0+9:.1f}" font-size="7" fill="{SOFT}" letter-spacing=".08em" '
              f'font-family="{F}">{head}</text>')
        s += (f'<text x="{X}" y="{y0+30:.1f}" font-size="19" font-weight="700" fill="{col}" '
              f'font-family="{FP}">{big}</text>')
        yy = y0 + 44
        for ln in sub:
            s += (f'<text x="{X}" y="{yy:.1f}" font-size="7" fill="{SOFT}" font-family="{F}">{ln}</text>')
            yy += 10
    return s


def mom_line(months, series, keys, money=False, dec=0, unit='', chips=None):
    """Line chart, one line per property type, with a value label at each point and
    an optional in-SVG change panel on the right. Gaps where a month had no data."""
    W, H, T, B = 760, 210, 16, 40
    L = 52
    R = 168 if chips else 12
    PW = W - R  # right edge of the plot area
    vals = [v for k in keys for v in series[k] if v == v]
    if not vals: return ''
    hi = max(vals) * 1.18
    ax, y, top, bw = _axes(PW, H, L, 0, T, B, hi, months, money, dec)
    s = f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Month over month">' + ax
    single = len(keys) == 1
    _mf = mshort_series(vals)
    def fmt(v):
        if money: return _mf(v)
        return f'{v:,.{dec}f}'
    for ki, k in enumerate(keys):
        c = TYPE_COLORS[ki % len(TYPE_COLORS)]
        pts, run = [], []
        for i, v in enumerate(series[k]):
            if v != v:
                if len(run) > 1: pts.append(run)
                run = []
            else:
                run.append((L + bw * (i + .5), y(v)))
        if len(run) > 1: pts.append(run)
        for seg in pts:
            s += ('<polyline fill="none" stroke="' + c + '" stroke-width="2.4" stroke-linejoin="round" points="'
                  + ' '.join(f'{x:.1f},{yy:.1f}' for x, yy in seg) + '"/>')
        for i, v in enumerate(series[k]):
            if v != v: continue
            cx, cy = L + bw * (i + .5), y(v)
            s += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" fill="#fff" stroke="{c}" stroke-width="2"/>'
            # Only label points on a single-series chart; on a multi-line chart the
            # labels would collide, so the axis and markers carry it instead.
            if single:
                s += _pt_label(cx, cy, fmt(v), above=True)
    s += _legend(PW, H, keys, TYPE_COLORS)
    if chips:
        s += _delta_chip(chips, PW + 20, W, H)
    return s + '</svg>'

def mom_bars(months, series, keys, dec=0, stacked=False, chips=None):
    """Bars per month with an optional in-SVG change panel on the right. With one
    series, a plain labelled bar. With several property types the bars stack, so the
    full column height still reads as the month's total and the segments show the
    mix -- a grouped chart plus a separate total series would draw the same number
    twice."""
    W, H, T, B = 760, 210, 16, 40
    L = 52
    R = 168 if chips else 12
    PW = W - R
    if stacked and len(keys) > 1:
        tot = [sum((series[k][i] if series[k][i] == series[k][i] else 0) for k in keys)
               for i in range(len(months))]
        vals = tot
    else:
        vals = [v for k in keys for v in series[k] if v == v]
    if not vals or max(vals) <= 0: return ''
    hi = max(vals) * 1.15
    ax, y, top, bw = _axes(PW, H, L, 0, T, B, hi, months, False, dec)
    s = f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Month over month">' + ax
    if stacked and len(keys) > 1:
        pad = bw * .22; w = bw - 2 * pad
        for i in range(len(months)):
            base = 0.0
            for ki, k in enumerate(keys):
                v = series[k][i]
                if v != v or v <= 0: continue
                y0, y1 = y(base + v), y(base)
                s += (f'<rect x="{L+bw*i+pad:.1f}" y="{y0:.1f}" width="{w:.1f}" '
                      f'height="{max(y1-y0,1):.1f}" fill="{TYPE_COLORS[ki%len(TYPE_COLORS)]}"/>')
                base += v
            if base > 0:
                s += (f'<text x="{L+bw*i+pad+w/2:.1f}" y="{y(base)-4:.1f}" font-size="8" fill="{SOFT}" '
                      f'text-anchor="middle" font-family="{F}">{base:,.{dec}f}</text>')
    else:
        n = max(1, len(keys)); pad = bw * .18; w = (bw - 2 * pad) / n
        for ki, k in enumerate(keys):
            c = TYPE_COLORS[ki % len(TYPE_COLORS)]
            for i, v in enumerate(series[k]):
                if v != v: continue
                x = L + bw * i + pad + ki * w
                hgt = (H - B) - y(v)
                if hgt < .5 and v == 0: continue
                s += f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{w-1.5:.1f}" height="{max(hgt,1):.1f}" rx="2" fill="{c}"/>'
                if n == 1:
                    s += (f'<text x="{x+(w-1.5)/2:.1f}" y="{y(v)-4:.1f}" font-size="8" fill="{SOFT}" '
                          f'text-anchor="middle" font-family="{F}">{v:,.{dec}f}</text>')
    s += _legend(PW, H, keys, TYPE_COLORS)
    if chips:
        s += _delta_chip(chips, PW + 20, W, H)
    return s + '</svg>'
