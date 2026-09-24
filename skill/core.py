"""Subdivision Brief — builds Seller and Buyer reports from one MLS 365-day
subdivision activity export. Data source: a single CSV. No external market file."""
import pandas as pd, numpy as np, math, html, json, warnings
warnings.filterwarnings('ignore')

INK='#10203A'; PINE='#1F4B87'; SAGE='#6FA0D0'; BRONZE='#B0895C'; BRZT='#8A6A45'
DEEP='#7E6140'; SAND='#E0D5BC'; LINE='#CBD4DE'; SOFT='#56657A'; MIST='#E7EFF8'
F='DejaVu Sans Mono'; FP='Poppins,Liberation Sans,sans-serif'
def M(v): return '${:,.0f}'.format(v)

# ---------------------------------------------------------------- abbreviated money
# ONE formatter for every abbreviated dollar figure in the reports -- chart axes,
# point labels, change panels, price-band labels. Never hardcode a $...K string
# anywhere else, or a million-dollar subdivision renders "$1,100K" instead of the
# "$1.1M" that real estate actually uses.
#
# Precision is derived from the DATA rather than fixed, because one setting cannot
# serve both a $400K subdivision and a $4M one. mdec() picks the fewest decimals
# that keep every label within 0.5% of its true value, so a $1,261,000 median reads
# $1.26M (not the 3%-wrong $1.3M) while a clean $2,500,000 step reads $2.5M. Passing
# one dec for a whole series keeps the labels the same width, which is what makes an
# axis look balanced -- individually-stripped precision does not.
MSHORT_TOL = 0.005          # max relative rounding error allowed on an abbreviated label
MSHORT_MAXDEC = 2

def mdec(values, tol=MSHORT_TOL):
    """Fewest decimals in 0..2 that render every value >= $1M within `tol`.
    Values under $1M print as whole $K and never constrain the choice."""
    vals = [abs(float(v)) for v in values
            if v is not None and v == v and abs(float(v)) >= 1e6]
    if not vals: return 0
    for dec in range(MSHORT_MAXDEC + 1):
        q = 10 ** 6 / (10 ** dec)
        if all(abs(round(v / q) * q - v) <= v * tol for v in vals):
            return dec
    return MSHORT_MAXDEC

def Mshort(v, dec=None):
    """Abbreviated dollars. Millions get M, everything below gets K, and trailing
    zeros are stripped so a round value reads $1M rather than $1.00M."""
    if v is None or v != v: return '\u2014'
    v = float(v)
    sign = '\u2212' if v < 0 else ''
    a = abs(v)
    if a >= 1e6:
        d = MSHORT_MAXDEC if dec is None else dec
        s = f'{a/1e6:.{d}f}'
        if '.' in s: s = s.rstrip('0').rstrip('.')
        return f'{sign}${s}M'
    if a >= 1000:
        return f'{sign}${a/1000:,.0f}K'
    return f'{sign}${a:,.0f}'

def mshort_series(values):
    """Formatter closed over one series' precision, so every label in a chart is
    rendered at the same scale. Use this for axes and point labels."""
    d = mdec(values)
    return lambda v: Mshort(v, d)

# ---------------------------------------------------------------- load
def load(path):
    d=pd.read_csv(path)
    d['addr']=(d['Street Number'].astype(str)+' '+d.get('Street Dir Prefix',pd.Series(['']*len(d))).fillna('')
               +' '+d['Street Name'].fillna('')+' '+d.get('Street Suffix',pd.Series(['']*len(d))).fillna(''))
    d['addr']=d['addr'].str.replace(r'\s+',' ',regex=True).str.strip()
    for c in ['Listing Contract Date','Purchase Contract Date','Close Date']:
        if c in d: d[c]=pd.to_datetime(d[c],errors='coerce')
    d=_sanitize(d)
    n0=len(d)
    d=d.drop_duplicates(subset=['addr','Listing Contract Date','Original List Price'],keep='first').copy()
    d.attrs['dupes_removed']=n0-len(d)
    d['conc']=d.get('Concessions Amount',0)
    d['conc']=pd.to_numeric(d['conc'],errors='coerce').fillna(0)
    d['red']=d['Original List Price']>d['List Price']
    d['cut']=d['Original List Price']-d['List Price']
    d['ptc']=(d['Close Date']-d['Purchase Contract Date']).dt.days
    d['ttl']=(d['Close Date']-d['Listing Contract Date']).dt.days
    d['nchg']=np.where(~d['red'],0,np.where(d['Previous List Price']==d['Original List Price'],1,2))
    return d


def _sanitize(d):
    """Remove rows with values that cannot be real before they can distort a
    median, a percentage, or a score -- a single bad row has outsized leverage
    on a subdivision-size sample. This only removes what is provably impossible,
    never what is merely unusual:
      - a list or close price that is zero or negative
      - a closing recorded before the listing even started, or before the
        purchase contract that supposedly preceded it (both a sign of a
        data-entry date swap, not a real transaction)
      - negative days on market

    A merely large or small value (a $50 HOA, a 400-day listing, a $50,000
    starter home in a $1M subdivision) is left alone -- those can be real, and
    excluding them would be the skill inventing precision it doesn't have in
    the other direction. This is a floor, not an editorial judgment about what
    counts as an outlier.

    Removed rows are counted and a few addresses kept (attrs['sanity_examples'])
    so the methodology section can disclose exactly what was dropped and why,
    the same way duplicate removal is already disclosed -- silently dropping
    rows without saying so would be its own integrity problem.
    """
    n = len(d)
    bad = pd.Series(False, index=d.index)
    for col in ('List Price', 'Original List Price', 'Close Price'):
        if col in d:
            bad = bad | pd.to_numeric(d[col], errors='coerce').le(0).fillna(False)
    if 'Days In MLS' in d:
        bad = bad | pd.to_numeric(d['Days In MLS'], errors='coerce').lt(0).fillna(False)
    if 'Close Date' in d and 'Listing Contract Date' in d:
        bad = bad | (d['Close Date'] < d['Listing Contract Date']).fillna(False)
    if 'Close Date' in d and 'Purchase Contract Date' in d:
        bad = bad | (d['Close Date'] < d['Purchase Contract Date']).fillna(False)
    if not bad.any():
        d.attrs['sanity_removed'] = 0
        d.attrs['sanity_examples'] = []
        return d
    examples = d.loc[bad, 'addr'].head(5).tolist() if 'addr' in d else []
    out = d.loc[~bad].copy()
    out.attrs['sanity_removed'] = int(bad.sum())
    out.attrs['sanity_examples'] = examples
    return out


def metrics(d):
    cl=d[d['Mls Status']=='Closed']; act=d[d['Mls Status']=='Active']
    exp=d[~d['Mls Status'].isin(['Closed','Active'])]
    m={}
    m['n_all']=len(d); m['n_cl']=len(cl); m['n_act']=len(act); m['n_exp']=len(exp)
    # n_exp is the 'not closed, not active' bucket and includes listings that are
    # under contract. Anything describing a listing as having FAILED must use
    # n_fail, which counts only genuinely terminated listings.
    _st=d['Mls Status'].astype(str).str.strip().str.lower()
    m['n_fail']=int(_st.isin(['expired','withdrawn','canceled','cancelled']).sum())
    m['n_pend']=int(_st.isin(['pending','active under contract','under contract']).sum())
    m['dupes']=d.attrs.get('dupes_removed',0)
    m['sanity_removed']=d.attrs.get('sanity_removed',0)
    m['sanity_examples']=d.attrs.get('sanity_examples',[])
    m['vol']=cl['Close Price'].sum(); m['med']=cl['Close Price'].median()
    m['hi']=cl['Close Price'].max(); m['lo']=cl['Close Price'].min()
    m['s2l']=(cl['Close Price']/cl['List Price']*100).mean()
    m['cpo']=(cl['Close Price']/cl['Original List Price']*100).mean()
    m['psf_med']=cl['PSF Finished'].median(); m['psf_avg']=cl['PSF Finished'].mean()
    m['dtc_med']=cl['Days In MLS'].median(); m['dtc_avg']=cl['Days In MLS'].mean()
    m['ptc_med']=cl['ptc'].median(); m['ptc_min']=cl['ptc'].min(); m['ptc_max']=cl['ptc'].max()
    m['at_or_above']=int((cl['Close Price']>=cl['Original List Price']).sum())
    # ORIGINAL list price is the reporting benchmark everywhere in these reports.
    # A home that cut its price and then sold at the reduced number is a below-asking
    # sale, not a full-price one; measuring against the final list price hides exactly
    # the reduction the seller took. The _list variants are retained only so the two
    # benchmarks can be reconciled in the methodology, and are never displayed.
    m['above_orig']=int((cl['Close Price']>cl['Original List Price']).sum())
    m['at_orig']=int((cl['Close Price']==cl['Original List Price']).sum())
    m['under_orig']=int((cl['Close Price']<cl['Original List Price']).sum())
    m['above_list']=int((cl['Close Price']>cl['List Price']).sum())
    m['at_list']=int((cl['Close Price']==cl['List Price']).sum())
    m['under_list']=int((cl['Close Price']<cl['List Price']).sum())
    m['no_change']=int((~cl['red']).sum()); m['changed']=int(cl['red'].sum())
    m['conc_n']=int((cl['conc']>0).sum()); m['conc_med']=cl[cl['conc']>0]['conc'].median() if (cl['conc']>0).any() else 0
    m['conc_avg']=cl['conc'].mean(); m['conc_tot']=cl['conc'].sum()
    m['ttl_nored']=cl[~cl['red']]['ttl'].median(); m['ttl_red']=cl[cl['red']]['ttl'].median()
    m['moi']=m['n_act']/(m['n_cl']/12) if m['n_cl'] else float('nan')
    m['act_med_list']=act['List Price'].median() if len(act) else float('nan')
    m['fin']=cl['Buyer Financing'].value_counts().to_dict() if 'Buyer Financing' in cl else {}
    m['fast']=int((cl['Days In MLS']<=7).sum()); m['fast14']=int((cl['Days In MLS']<=14).sum())
    # discount / leverage
    m['disc_orig']=((cl['Original List Price']-cl['Close Price'])/cl['Original List Price']*100).mean()
    m['disc_list']=((cl['List Price']-cl['Close Price'])/cl['List Price']*100).mean()
    u=cl[cl['Close Price']<cl['List Price']]
    m['disc_dollars']=(u['List Price']-u['Close Price']).mean() if len(u) else 0
    lev=[]
    b=pd.cut(cl['Days In MLS'],[-1,14,60,10**6],labels=['0–14 days','15–60 days','60+ days'])
    for lab,g in cl.groupby(b,observed=True):
        lev.append((lab,len(g),(g['Close Price']/g['Original List Price']*100).mean(),g['conc'].mean()))
    m['lev']=lev
    # How fast a RIGHT-PRICED home goes under contract. The proxy for right-priced
    # is "never took a price cut" -- a home priced correctly does not need to reduce.
    # Measured to the accepted-offer date (Purchase Contract Date), pooled across the
    # whole year, because the timing is a single aggregate figure; the week- and
    # month-level version is not supportable at subdivision sample sizes (see
    # SKILL.md note on listing-timing analysis).
    pc=pd.to_datetime(d.get('Purchase Contract Date'),errors='coerce')
    ld=pd.to_datetime(d.get('Listing Contract Date'),errors='coerce')
    dtc=(pc-ld).dt.days
    pend=pc.notna() & (dtc>=0)
    nocut=d['Original List Price']<=d['List Price']
    wp=dtc[pend & nocut]; cutd=dtc[pend & ~nocut]
    m['rp_n']=int(len(wp))
    m['rp_med']=float(wp.median()) if len(wp) else float('nan')
    m['rp_w1']=int((wp<=7).sum()); m['rp_w2']=int((wp<=14).sum())
    m['rp_cut_n']=int(len(cutd))
    m['rp_cut_med']=float(cutd.median()) if len(cutd) else float('nan')
    m['rp_all_med']=float(dtc[pend].median()) if int(pend.sum()) else float('nan')
    # ---- cash vs financed -------------------------------------------------
    # Buyer Financing is a free-text MLS field; 'Cash' is matched as a whole word
    # so 'Cash Out Refinance' or a blank never counts as a cash purchase. Rows with
    # no recorded financing are excluded from BOTH sides rather than assumed
    # financed, and n_fin_known is reported so the denominator is honest.
    if 'Buyer Financing' in cl:
        bf=cl['Buyer Financing'].astype(str).str.strip()
        known=bf.notna() & (bf!='') & (bf.str.lower()!='nan')
        iscash=known & bf.str.fullmatch(r'(?i)\s*cash\s*')
        isfin=known & ~iscash
    else:
        known=iscash=isfin=pd.Series(False,index=cl.index)
    m['n_fin_known']=int(known.sum()); m['n_cash']=int(iscash.sum()); m['n_fin']=int(isfin.sum())
    m['cash_pct']=(m['n_cash']/m['n_fin_known']*100) if m['n_fin_known'] else float('nan')
    g=lambda sel,col: float(cl[sel][col].median()) if int(sel.sum()) else float('nan')
    m['cash_ptc']=g(iscash,'ptc');  m['fin_ptc']=g(isfin,'ptc')
    m['cash_dtc']=g(iscash,'Days In MLS'); m['fin_dtc']=g(isfin,'Days In MLS')
    m['cash_med']=g(iscash,'Close Price'); m['fin_med']=g(isfin,'Close Price')
    m['cash_cpo']=float((cl[iscash]['Close Price']/cl[iscash]['Original List Price']*100).mean()) if m['n_cash'] else float('nan')
    m['fin_cpo']=float((cl[isfin]['Close Price']/cl[isfin]['Original List Price']*100).mean()) if m['n_fin'] else float('nan')
    return m,cl,act,exp

# ---------------------------------------------------------------- financing
# Market inputs an agent/lender should refresh. Everything else is computed
# from the uploaded MLS export.
#
# CONCURRENCY: FIN is a TEMPLATE, not run state. set_county() returns a per-run
# COPY rather than mutating this dict, because two jobs running at once in a
# worker process would otherwise stomp each other's conforming limit -- a Boulder
# report would silently render Adams County's number depending on which job
# happened to call set_county() last. Never write run-specific values back here.

class BriefError(Exception):
    """Base for every error this skill raises deliberately. A service wrapping the
    skill can catch this and return a 4xx with the message shown to the user,
    while anything else remains a genuine 5xx."""

class CountyLimitError(BriefError):
    """Export's county has no verified conforming loan limit on file."""

class RateStaleError(BriefError):
    """Mortgage rate input is older than the allowed window."""

# Freddie Mac publishes PMMS weekly on Thursdays. Anything older than this is
# stale enough that the payment tables would misstate a buyer's monthly cost.
# In a self-serve context nobody is editing this file between runs, so staleness
# must be detected rather than trusted to an operator's memory.
RATE_MAX_AGE_DAYS = 14

FIN = dict(
    rate=0.0695,          # 30-yr fixed. Freddie Mac PMMS, week of 2026-09-17
    rate_src='Freddie Mac PMMS, week of September 17, 2026',
    rate_date='2026-09-17',   # survey date, ISO. Drives the staleness check below.
    ins_rate=0.0035,      # annual homeowners premium as a share of price (assumption)
    pmi_rate=0.005,       # annual conventional MI under 20% down (assumption)
    conforming=None,      # set per-run by set_county() from the export. Never hardcode.
    county=None,
)

def rate_age_days(cfg=None, today=None):
    """Days since the mortgage rate input was surveyed. None if undated."""
    cfg = cfg or FIN
    ds = cfg.get('rate_date')
    if not ds: return None
    today = today or pd.Timestamp.today().normalize()
    return int((pd.Timestamp(today) - pd.Timestamp(ds)).days)

def check_rate(cfg=None, strict=False, today=None):
    """Returns (stale, age_days, message). Raises instead when strict=True, which
    is what a self-serve deployment should pass -- there is no operator there to
    read a warning."""
    cfg = cfg or FIN
    age = rate_age_days(cfg, today)
    if age is None:
        msg = 'Mortgage rate input carries no survey date; cannot verify freshness.'
        if strict: raise RateStaleError(msg)
        return True, None, msg
    if age > RATE_MAX_AGE_DAYS:
        msg = (f'Mortgage rate input is {age} days old (surveyed {cfg["rate_date"]}, '
               f'limit {RATE_MAX_AGE_DAYS} days). Refresh core.FIN rate/rate_src/rate_date '
               f'from the Freddie Mac PMMS before running.')
        if strict: raise RateStaleError(msg)
        return True, age, msg
    return False, age, ''

# 2026 one-unit conforming loan limits, FHFA "All Counties" file (CY2026, HERA-based).
# Only counties verified against the FHFA source are listed. Anything absent raises
# rather than silently falling back, because a wrong limit silently mislabels jumbo
# loans throughout the buyer brief's financing section.
CLL_2026_CO = {
    'BOULDER': 879750,
    'ADAMS': 862500, 'ARAPAHOE': 862500, 'BROOMFIELD': 862500, 'CLEAR CREEK': 862500,
    'DENVER': 862500, 'DOUGLAS': 862500, 'ELBERT': 862500, 'GILPIN': 862500,
    'JEFFERSON': 862500, 'PARK': 862500,
    'CHAFFEE': 832750, 'CHEYENNE': 832750, 'LARIMER': 832750, 'WELD': 832750,
    'EL PASO': 832750, 'MESA': 832750, 'PUEBLO': 832750,
}
CLL_BASELINE_2026 = 832750

def set_county(d, cfg=None):
    """Derive the conforming limit from the export's county. Refuses to guess.

    Returns a NEW config dict for this run. It does not mutate the module-level
    FIN, so concurrent jobs cannot overwrite each other's conforming limit.
    Callers must use the returned dict and pass it to piti()/pmt()."""
    cfg = dict(cfg or FIN)
    col = d.get('County Or Parish')
    names = sorted(set(str(x).strip() for x in col.dropna())) if col is not None else []
    if len(names) != 1:
        raise CountyLimitError(
            f'Expected exactly one county in the export, found {names or "none"}. '
            'This report prices jumbo vs. conforming from the county, so it cannot '
            'run on a mixed-county or county-less export.')
    name = names[0]
    key = name.upper().replace(' COUNTY', '').strip()
    if key not in CLL_2026_CO:
        raise CountyLimitError(
            f'No verified 2026 conforming loan limit on file for {name} County. '
            f'Look it up at fhfa.gov/data/conforming-loan-limit, add it to CLL_2026_CO, '
            f'and re-run. (National baseline is ${CLL_BASELINE_2026:,} but high-cost '
            f'counties differ and guessing mislabels jumbo loans.)')
    cfg['conforming'] = CLL_2026_CO[key]
    cfg['county'] = f'{name} County, Colorado'
    return cfg

def pmt(loan, rate=None, years=30, cfg=None):
    r=(rate or (cfg or FIN)['rate'])/12; n=years*12
    return loan*r/(1-(1+r)**-n) if r else loan/n

def piti(price, down, tax_annual, hoa_annual=0.0, cfg=None):
    cfg = cfg or FIN
    loan=price*(1-down)
    mi=loan*cfg['pmi_rate']/12 if down<0.20 else 0.0
    return dict(loan=loan, down_amt=price*down, pi=pmt(loan,cfg=cfg), tax=tax_annual/12,
                ins=price*cfg['ins_rate']/12, mi=mi, hoa=hoa_annual/12,
                total=pmt(loan,cfg=cfg)+tax_annual/12+price*cfg['ins_rate']/12+mi+hoa_annual/12,
                jumbo=loan>cfg['conforming'])

def fin_metrics(cl, act):
    tr=(cl['Tax Annual Amount']/cl['Close Price']).median()
    hoa=cl.get('Association Fee Total Annual', pd.Series([0]*len(cl))).fillna(0)
    return dict(tax_rate=tr, tax_med=cl['Tax Annual Amount'].median(),
                tax_lo=cl['Tax Annual Amount'].min(), tax_hi=cl['Tax Annual Amount'].max(),
                hoa_med=hoa.median(), hoa_any=int((hoa>0).sum()), hoa_n=int(hoa.notna().sum()),
                hoa_note=(lambda s: str(s.mode().iloc[0]) if len(s.mode()) else '')(cl.get('Association Fee Frequency', pd.Series(['']*len(cl))).dropna()))

def compare_row(csv, label):
    """Metrics for one subdivision, for the side-by-side comparison section."""
    d=load(csv); m,cl,act,exp=metrics(d)
    return dict(label=label, n_cl=m['n_cl'], n_act=m['n_act'], med=m['med'],
                dtc=m['dtc_med'], moi=m['moi'], at_or_above=m['at_or_above'],
                pct_at=m['at_or_above']/m['n_cl']*100 if m['n_cl'] else 0,
                cpo=m['cpo'], psf=m['psf_med'], conc_med=m['conc_med'],
                conc_pct=m['conc_n']/m['n_cl']*100 if m['n_cl'] else 0,
                under=m['under_orig'], ptc=m['ptc_med'])

# ---------------------------------------------------------------------------
# Talking-point phrasing helpers.
# Talking points must follow the data, not a fixed market narrative. These
# return prose whose CLAIM changes with the numbers, so a buyer's-market
# subdivision does not inherit seller's-market advice (and vice versa).
# ---------------------------------------------------------------------------

def dur(days):
    """Plain-English duration that never overstates. 44 days -> 'about six weeks'."""
    if days is None or days != days: return 'an unknown amount of time'
    d = float(days)
    if d < 10.5:  return f'about {round(d)} days'
    if d < 45:    return f'about {round(d/7)} weeks'
    m_ = d/30.44
    return 'about a month' if m_ < 1.25 else f'about {round(m_*2)/2:g} months'.replace('.0','')

def offer_point(m):
    """Buyer: how aggressively to open. Driven by the share paying under asking."""
    n, u = m['n_cl'], m['under_orig']
    if not n: return ''
    p = u/n*100
    if p >= 60:
        return (f'{u} of the {n} sales here closed below the original asking price &mdash; {p:.0f}% of them. '
                f'Opening under ask is the norm in this subdivision, not an insult.')
    if p <= 35:
        return (f'Only {u} of {n} buyers paid less than the original asking price. '
                f'Leading with a low offer on a new listing is unlikely to land.')
    return (f'{u} of {n} sales closed below the original asking price and {n-u} at or above it. '
            f'It cuts both ways here, so the right opening number depends on the individual listing.')

def seller_price_point(m):
    """Seller: how the original ask actually performed."""
    n, a = m['n_cl'], m['at_or_above']
    if not n: return ''
    p = a/n*100
    if p >= 55:
        return (f'{a} of the {n} homes that sold here last year got their original asking price or better. '
                f'This is a neighborhood where getting the number right is rewarded quickly.')
    return (f'Only {a} of the {n} homes that sold here last year got their original asking price or better &mdash; '
            f'{n-a} had to settle for less. The opening number has to be defensible, because the market here '
            f'does not bail out an ambitious one.')

def adjust_point(m):
    """Seller: cost of needing a price adjustment, measured not assumed."""
    a, b = m['ttl_nored'], m['ttl_red']
    if a != a or b != b:
        return 'There were too few sales in one group to compare adjusted and unadjusted listings.'
    return (f'Priced right at launch, the median run from listing to closing here was {a:.0f} days. '
            f'After an adjustment, {b:.0f} &mdash; {dur(b-a)} longer. Both sold; one just took far more patience.')

def escrow_point(m):
    """Seller: escrow expectations, stated with the actual spread."""
    med, lo, hi = m['ptc_med'], m['ptc_min'], m['ptc_max']
    tight = (hi-lo) <= 21
    tail = ('That part is predictable.' if tight else
            f'That said, closings here ran anywhere from {lo:.0f} to {hi:.0f} days, so build some slack into your plans.')
    return f'Once we have an accepted offer, the median close here took {med:.0f} days &mdash; {dur(med)}. {tail}'

def rightpriced_point(m, audience='seller'):
    """How fast a right-priced home goes under contract, pooled across the year.
    Branches on the median and on the no-cut vs cut gap so it stays true for a
    subdivision where right pricing does NOT buy speed. Right-priced = never took
    a price cut; timing is to the accepted-offer date.

    Always ties back to the blended, all-sales median (m['dtc_med']) shown on the
    dashboard and in the Speed section. Reporting the priced-right subset's median
    without that anchor reads like a contradiction of the dashboard number rather
    than what it actually is -- the same underlying data, split into two groups.
    A reader should never have to infer that on their own."""
    n = m.get('rp_n', 0)
    # Below five right-priced sales the median is one or two houses; report nothing
    # rather than dress up noise. A multi-year export clears this easily.
    if n < 5 or m['rp_med'] != m['rp_med']:
        return ''
    med = m['rp_med']; w1 = m['rp_w1']
    overall = m.get('dtc_med')
    if overall == overall and overall > 0 and overall > med * 1.25:
        blend = (f'The typical listing here took a median of {overall:.0f} days to get an accepted offer '
                 f'&mdash; but that figure blends two very different groups. ')
    else:
        blend = 'Across the year, '
    lead = (f'{blend}The {n} homes priced right from the start &mdash; the ones that never had to cut '
            f'&mdash; went under contract in a median of just {med:.0f} days. {w1} of those {n} had an '
            f'accepted offer inside their first week.')
    gap = ''
    if m.get('rp_cut_n', 0) >= 3 and m['rp_cut_med'] == m['rp_cut_med']:
        cm = m['rp_cut_med']
        if cm >= med * 1.8:
            gap = (f' The homes that had to reduce took a median of {cm:.0f} days by contrast &mdash; '
                   f'more than {cm/med:.0f} times as long. In this subdivision the first asking price is '
                   f'what buys speed, not the reduction that follows.')
        elif cm > med:
            gap = (f' Homes that had to reduce took a median of {cm:.0f} days, longer but not dramatically so.')
    if audience == 'buyer':
        tail = (' On a fresh listing that is priced correctly, the window to act is measured in days, not weeks '
                '&mdash; the homes that sit are usually the ones that started too high.')
        return lead + gap + tail
    tail = (' The practical takeaway for pricing: a right number out of the gate is rewarded almost immediately here, '
            'while an ambitious one tends to cost weeks and end up reducing anyway.')
    return lead + gap + tail


def cash_point(m, audience='seller'):
    """How much of this subdivision trades on cash, and whether that actually buys
    the seller anything. Branches on the cash share AND on the measured escrow gap,
    because a subdivision where cash closes no faster must not inherit 'cash is
    quicker here'. Returns '' when the export records too little financing data."""
    n, k = m.get('n_fin_known', 0), m.get('n_cash', 0)
    if n < 8:
        return ''
    p = m['cash_pct']
    cp, fp = m.get('cash_ptc'), m.get('fin_ptc')
    # Escrow gap is only worth a claim with a few sales on each side.
    gap = None
    if m['n_cash'] >= 3 and m['n_fin'] >= 3 and cp == cp and fp == fp:
        gap = fp - cp
    if p >= 40:
        head = (f'Cash is a major force here &mdash; {k} of the {n} sales with recorded financing were '
                f'cash purchases, {p:.0f}% of them.')
    elif p >= 20:
        head = (f'{k} of the {n} sales with recorded financing closed on cash, {p:.0f}% of them &mdash; '
                f'a meaningful minority, though most buyers here still finance.')
    elif k == 0:
        head = (f'Every one of the {n} sales with recorded financing here used a loan. Cash purchases '
                f'are not a factor in this subdivision.')
    else:
        head = (f'Cash is uncommon here &mdash; just {k} of the {n} sales with recorded financing, '
                f'{p:.0f}%. Nearly every buyer arrives with a lender.')
    if gap is None or k == 0:
        tail = ''
    elif gap >= 5:
        tail = (f' Those cash sales closed in a median of {cp:.0f} days against {fp:.0f} for financed '
                f'buyers &mdash; {dur(gap)} faster.')
        tail += (' A cash offer is worth real time on the calendar here, which is worth weighing against '
                 'a higher financed number.') if audience == 'seller' else \
                (' If you are financing, expect the longer timeline and make the rest of your terms '
                 'competitive rather than trying to match a cash close.')
    elif gap <= -5:
        tail = (f' Cash did not close faster here, though &mdash; a median of {cp:.0f} days against '
                f'{fp:.0f} for financed buyers.')
        tail += (' Do not discount a financed offer on speed alone in this subdivision.') if audience == 'seller' else \
                (' Financing is not the timing disadvantage here that it is in many neighborhoods.')
    else:
        tail = (f' The two closed at almost the same pace &mdash; a median of {cp:.0f} days on cash '
                f'against {fp:.0f} financed.')
        tail += (' Speed is not the reason to prefer one over the other here.') if audience == 'seller' else \
                (' A financed offer is not at a timing disadvantage in this subdivision.')
    return head + tail

def leverage_point(m):
    """Buyer: where the negotiating room actually is. Branches on the discount off
    the ORIGINAL asking price and on how common credits are, because a subdivision
    that discounts heavily must not inherit 'sellers hold firm here'."""
    d, n, k = m['disc_orig'], m['n_cl'], m['conc_n']
    if not n: return ''
    cp = k/n*100
    credit = (f'{k} of {n} buyers had the seller contribute toward closing costs or a rate '
              f'buy-down, a median of {M(m["conc_med"])} where one was paid.')
    if d <= 2:
        head = (f'Sellers here hold firm on price &mdash; across all {n} sales the average discount off the '
                f'<em>original</em> asking price was just {d:.1f}%.')
        tail = ('<strong>The concession is where buyers won.</strong> ' + credit +
                ' Ask for the credit, not the discount.') if cp >= 40 else \
               (credit + ' Neither lever moves far in this subdivision, so the leverage is in '
                'choosing which listing to pursue rather than in how hard you push on a given one.')
    elif d >= 5:
        head = (f'There is real room on price here &mdash; across all {n} sales the average discount off the '
                f'<em>original</em> asking price was {d:.1f}%, and {m["under_orig"]} of {n} buyers paid less '
                f'than the first number published.')
        tail = ('<strong>Price is the primary lever, and credits come on top.</strong> ' + credit) if cp >= 40 else \
               ('<strong>Price is where this negotiation happens</strong>, not credits &mdash; ' + credit)
    else:
        head = (f'Discounts here are modest but real &mdash; the average sale came in {d:.1f}% under the '
                f'<em>original</em> asking price, with {m["under_orig"]} of {n} buyers paying less than the first ask.')
        tail = ('<strong>Both levers are live.</strong> ' + credit +
                ' Expect to trade between the two rather than win on either alone.') if cp >= 40 else \
               (credit + ' With credits uncommon, the discussion here tends to land on price.')
    return head + ' ' + tail

def buyer_lead(m, sub):
    """Buyer brief opening. The market characterization must follow the numbers."""
    n, u, a = m['n_cl'], m['under_orig'], m['at_or_above']
    p = u/n*100 if n else 0
    if p >= 60:
        lead = (f'{sub} gives buyers real negotiating room right now, and knowing where the leverage '
                f'sits is worth more than knowing the average price.')
        body = (f'{n} homes sold here in the last twelve months at a median price of {M(m["med"])}. '
                f'Most went under contract in about {m["dtc_med"]:.0f} days, but only {a} of {n} sellers got their '
                f'original asking price or better &mdash; {u} sales closed below the asking price.')
        close = ('The room to negotiate here is real, but it is not uniform. It is widest on the homes that have '
                 'been sitting, and it shows up in credits as often as in price. This report shows exactly where.')
    elif p <= 35:
        lead = (f'{sub} is a competitive place to buy, and knowing where the leverage sits is worth more '
                f'than knowing the average price.')
        body = (f'{n} homes sold here in the last twelve months at a median price of {M(m["med"])}. '
                f'Most went under contract in about {m["dtc_med"]:.0f} days, and {a} of {n} sellers got their '
                f'original asking price or better. Only {u} buyers paid less than the asking price.')
        close = ('That does not mean there is no room to negotiate. It means the room is in credits and in the homes '
                 'that have been sitting &mdash; not in across-the-board discounts. This report shows exactly where.')
    else:
        lead = (f'{sub} cuts both ways for buyers, and knowing where the leverage sits is worth more '
                f'than knowing the average price.')
        body = (f'{n} homes sold here in the last twelve months at a median price of {M(m["med"])}. '
                f'Most went under contract in about {m["dtc_med"]:.0f} days. {a} of {n} sellers got their original '
                f'asking price or better, while {u} sales closed below the asking price.')
        close = ('Which of those two outcomes you get depends heavily on the individual listing and how long it has '
                 'been available. This report shows exactly where the leverage sits.')
    return (f'<div class="narr"><p class="lead">{lead}</p>\n<p>{body}</p>\n<p>{close}</p></div>')

# ---------------------------------------------------------------------------
# Notable call-outs.
# Each test inspects the export and returns a call-out only when the metric is
# actually notable. Every test knows how to describe BOTH directions, so a
# subdivision behaving the opposite way gets a true sentence rather than a
# fixed story with a number dropped into it (see SKILL.md rule 11). Which
# call-outs appear, and how many, therefore changes with each export.
# `w` is a 0-1 notability weight used only for ranking.
# ---------------------------------------------------------------------------

def _co(title, text, w, aud='both'):
    return dict(title=title, text=text, w=w, aud=aud)

def _pct(a, b): return (a/b*100) if b else 0.0

def _co_hoa(d, m, cl, act, exp):
    col = d.get('Association YN')
    if col is None or col.dropna().empty: return None
    v = col.dropna().astype(str).str.lower()
    n = len(v); yes = int(v.isin(['true','y','yes','1']).sum())
    fee = pd.to_numeric(d.get('Association Fee Total Annual', pd.Series([np.nan]*len(d))), errors='coerce')
    if yes == 0:
        return _co('No HOA anywhere in the subdivision',
                   f'All {n} listings in this export are recorded with no homeowners association. '
                   f'That is verified on every record rather than inferred from listing remarks, '
                   f'and it is a real monthly-cost difference against neighborhoods that carry dues.', .92)
    if yes == n:
        med = fee[fee > 0].median()
        extra = f' The median recorded annual amount is {M(med)}.' if med == med else ''
        return _co('Every home here carries an HOA',
                   f'All {n} listings are recorded with a homeowners association.{extra} '
                   f'Dues belong in any payment comparison against a no-HOA neighborhood.', .72)
    return _co('HOA status is split within the subdivision',
               f'{yes} of {n} listings are recorded with a homeowners association and {n-yes} without. '
               f'Dues are not a subdivision-wide assumption here &mdash; they have to be checked per home.', .80)

def _co_fallout(d, m, cl, act, exp):
    n_all, n_f = m['n_all'], m['n_fail']
    if not n_all: return None
    p = _pct(n_f, n_all)
    if n_f == 0:
        return _co('Every listing found a buyer',
                   f'Not one of the {n_all} listings in this export expired or was withdrawn. '
                   f'Homes that came to market here got sold.', .85)
    if p >= 15:
        return _co('About one in five listings did not sell',
                   f'{n_f} of the {n_all} listings in this export expired or were withdrawn &mdash; {p:.0f}%. '
                   f'Coming to market is not the same as selling in this subdivision, and the '
                   f'difference is usually the opening price.', .90)
    if p >= 8:
        return _co('A meaningful share of listings did not sell',
                   f'{n_f} of {n_all} listings expired or were withdrawn ({p:.0f}%). '
                   f'Most homes sold, but the opening price still decided which ones.', .60)
    return None

def _co_relist(d, m, cl, act, exp):
    if 'addr' not in d: return None
    g = d.groupby('addr').size()
    rep = g[g > 1]
    if rep.empty: return None
    worst_addr = rep.idxmax(); worst_n = int(rep.max())
    sub = d[d['addr'] == worst_addr].sort_values('Days In MLS')
    sold = sub[sub['Mls Status'] == 'Closed']
    if len(sold):
        r = sold.iloc[0]
        tail = (f'{worst_addr} appears {worst_n} times &mdash; it finally closed at '
                f'{M(r["Close Price"])} after {int(r["Days In MLS"])} days on its successful attempt, '
                f'having already spent '
                f'{int(sub[sub["Mls Status"]!="Closed"]["Days In MLS"].sum())} days on the market before that.')
    else:
        tail = (f'{worst_addr} appears {worst_n} times and has still not sold, across '
                f'{int(sub["Days In MLS"].sum())} cumulative days on the market.')
    return _co('Some homes came to market more than once this year',
               f'{len(rep)} address{"es" if len(rep)!=1 else ""} in this export '
               f'{"appear" if len(rep)!=1 else "appears"} more than once inside the same twelve months. '
               f'{tail} The cost of starting too high is measurable here, not theoretical.', .88)

def _co_conc(d, m, cl, act, exp):
    n, k = m['n_cl'], m['conc_n']
    if not n: return None
    p = _pct(k, n)
    if p >= 60:
        return _co('Seller credits are the norm, not the exception',
                   f'{k} of {n} sales included a credit to the buyer &mdash; {p:.0f}% of them &mdash; '
                   f'at a median of {M(m["conc_med"])} where one was paid. '
                   f'This belongs in a net sheet from day one on the sell side, and in the opening ask on the buy side.', .86)
    if p <= 20:
        return _co('Seller credits are rare here',
                   f'Only {k} of {n} sales included any credit to the buyer ({p:.0f}%). '
                   f'Unlike many neighborhoods, the negotiation here is happening on price rather than on credits.', .82)
    return _co('Credits appear on some sales but are not automatic',
               f'{k} of {n} sales included a buyer credit ({p:.0f}%), median {M(m["conc_med"])} where paid. '
               f'Worth asking for, but not something either side should assume.', .45)

def _co_discipline(d, m, cl, act, exp):
    n, a = m['n_cl'], m['at_or_above']
    if not n: return None
    p = _pct(a, n)
    if p >= 55:
        return _co('The first asking price usually held',
                   f'{a} of {n} sellers collected their original asking price or better, and sales averaged '
                   f'{m["cpo"]:.1f}% of the first price published. Accurate pricing is rewarded here quickly.', .70)
    if p <= 30:
        return _co('The first asking price rarely held',
                   f'Only {a} of {n} sellers collected their original asking price or better; sales averaged '
                   f'{m["cpo"]:.1f}% of the first price published. The opening number has to be defensible &mdash; '
                   f'this market does not grow into an ambitious one.', .88)
    return None

def _co_speed(d, m, cl, act, exp):
    n = m['n_cl']
    if not n: return None
    p = _pct(m['fast'], n)
    if p >= 40:
        return _co('Well-priced homes go under contract in days',
                   f'{m["fast"]} of {n} sales were under contract within a week of listing, and the median was '
                   f'{m["dtc_med"]:.0f} days. On a fresh listing, a weekend of hesitation is a real risk to a buyer.', .78)
    if m['dtc_med'] >= 45:
        return _co('This is a patient market',
                   f'The median home took {m["dtc_med"]:.0f} days to find a buyer &mdash; {dur(m["dtc_med"])}. '
                   f'Both sides should plan the listing runway and the search around that, not around a two-week cycle.', .84)
    return None

def _co_fin(d, m, cl, act, exp):
    f = m.get('fin') or {}
    tot = sum(f.values())
    if not tot: return None
    top, topn = max(f.items(), key=lambda kv: kv[1])
    p = _pct(topn, tot)
    cash = f.get('Cash', 0)
    if _pct(cash, tot) >= 25:
        return _co('Cash is a major share of buyers here',
                   f'{cash} of {tot} closings were cash purchases ({_pct(cash,tot):.0f}%). '
                   f'A financed offer is competing against buyers with no appraisal and no loan contingency.', .86, 'buyer')
    if p >= 75:
        missing = [k for k in ('VA', 'FHA') if not f.get(k)]
        miss = (f' No {" or ".join(missing)} financing was used at all, despite being an accepted term on most listings here.'
                if missing else '')
        return _co(f'Financing is overwhelmingly {top.lower()}',
                   f'{topn} of {tot} closings used {top.lower()} financing ({p:.0f}%).{miss} '
                   f'Useful context for how an offer will be read by a listing agent here.', .62, 'buyer')
    return None

def _co_shape(d, m, cl, act, exp):
    """Uniform vintage + bimodal size is a distinctive combination worth naming."""
    yb = pd.to_numeric(d.get('Year Built'), errors='coerce').dropna()
    la = pd.to_numeric(d.get('Living Area'), errors='coerce').dropna()
    b = pd.to_numeric(d.get('Bedrooms Total'), errors='coerce').dropna().astype(int)
    if len(yb) < 8 or len(b) < 8: return None
    span = int(yb.max() - yb.min())
    vc = b.value_counts()
    top2 = vc.iloc[:2]
    concentrated = len(vc) >= 2 and _pct(top2.sum(), len(b)) >= 55 and abs(int(top2.iloc[0]) - int(top2.iloc[1])) <= 2
    bits = []
    if span <= 15:
        bits.append(f'every home in this export was built between {int(yb.min())} and {int(yb.max())} &mdash; a {span}-year span')
    if concentrated:
        pair = sorted(int(x) for x in top2.index)
        szs = []
        for bd in pair:
            sel = la[b.reindex(la.index).eq(bd)] if len(la) else pd.Series(dtype=float)
            szs.append(f'{int(top2[bd])} with {bd} bedrooms' + (f' near {sel.median():,.0f} sq ft' if len(sel) else ''))
        bits.append('the inventory clusters into two distinct products &mdash; ' + ' and '.join(szs))
    if not bits: return None
    return _co('Uniform vintage, two distinct floor plans' if len(bits) == 2 else 'The housing stock is unusually uniform',
               ('; and '.join(bits).capitalize() +
                '. Buyers here are choosing between a small number of clearly different products rather than sliding along a size curve, '
                'and sellers are being compared against very close substitutes.'), .58, 'buyer')

def _co_garage(d, m, cl, act, exp):
    g = pd.to_numeric(d.get('Garage Spaces'), errors='coerce').dropna()
    if len(g) < 8: return None
    mode = g.mode()
    if mode.empty: return None
    mv = int(mode.iloc[0]); p = _pct(int((g == mv).sum()), len(g))
    if p >= 90 and mv >= 1:
        return _co(f'A {mv}-car garage is standard, not a premium',
                   f'{int((g==mv).sum())} of {len(g)} listings have a {mv}-car garage. '
                   f'It is not a differentiator in this subdivision &mdash; pricing a home as though it were will not hold.', .50)
    if p >= 60 and mv == 0:
        return _co('Most homes here have no garage',
                   f'{int((g==0).sum())} of {len(g)} listings record no garage spaces. '
                   f'Where a garage does exist it is a genuine point of difference.', .68)
    return None

def _co_escrow(d, m, cl, act, exp):
    med, lo, hi = m['ptc_med'], m['ptc_min'], m['ptc_max']
    if med != med: return None
    if (hi - lo) <= 21:
        return _co('Escrow timing is predictable',
                   f'Every sale closed between {lo:.0f} and {hi:.0f} days after the offer was accepted, median {med:.0f}. '
                   f'That is a tight enough window to plan a move around.', .48)
    return _co('Escrow timing varies more than usual',
               f'Closings ran from {lo:.0f} to {hi:.0f} days after acceptance &mdash; median {med:.0f}, but a spread of '
               f'{hi-lo:.0f} days. Build slack into any move-out or rate-lock plan.', .60)

def _co_supply(d, m, cl, act, exp):
    moi = m['moi']
    if moi != moi: return None
    if moi < 2:
        return _co('Inventory is very thin',
                   f'At the current pace of sales, the {m["n_act"]} homes for sale represent about {moi:.1f} months of supply. '
                   f'Under two months is a sharply supply-constrained market.', .80)
    if moi > 6:
        return _co('Supply has built up',
                   f'The {m["n_act"]} homes for sale represent about {moi:.1f} months of supply at the current pace &mdash; '
                   f'past the six-month line generally taken to favor buyers.', .84)
    return None

def _co_psf(d, m, cl, act, exp):
    p = pd.to_numeric(cl.get('PSF Finished'), errors='coerce').dropna()
    if len(p) < 6: return None
    spread = _pct(p.max() - p.min(), p.median())
    if spread < 55: return None
    return _co('Price per square foot varies enormously',
               f'Closed sales ranged from ${p.min():,.0f} to ${p.max():,.0f} per finished square foot against a median of '
               f'${p.median():,.0f} &mdash; a spread of {spread:.0f}% of the median. In housing stock this uniform in age, '
               f'that gap is condition and size, not location. A per-square-foot comparison to a neighbor is '
               f'close to meaningless here without adjusting for both.', .74)

_CO_TESTS = [_co_hoa, _co_fallout, _co_relist, _co_conc, _co_discipline, _co_speed,
             _co_fin, _co_shape, _co_garage, _co_escrow, _co_supply, _co_psf]

def callouts(d, m, cl, act, exp, audience='both', limit=5):
    """Return the notable call-outs for THIS export, ranked, audience-filtered."""
    out = []
    for t in _CO_TESTS:
        try:
            r = t(d, m, cl, act, exp)
        except Exception:
            r = None
        if not r: continue
        if r['aud'] != 'both' and r['aud'] != audience: continue
        out.append(r)
    out.sort(key=lambda r: -r['w'])
    # Reserve up to two slots for call-outs written specifically for this audience.
    # Without this the generic tests, which tend to score higher, crowd them out and
    # the Seller and Buyer briefs end up printing an identical list.
    own = [r for r in out if r['aud'] == audience][:2]
    rest = [r for r in out if r not in own]
    keep = own + rest[:max(0, limit - len(own))]
    return sorted(keep, key=lambda r: -r['w'])

# ---------------------------------------------------------------------------
# Outlier sales.
# Names the highest and lowest closed sale each run and mines the export for
# the characteristics that plausibly explain them. Every clause is conditional
# on the data; nothing is asserted that the file does not support.
# ---------------------------------------------------------------------------

_COND_POS = ['remodel', 'renovat', 'fully updated', 'completely updated', 'newly updated',
             'beautifully updated', 'quartz', 'new roof', 'brand-new', 'brand new', 'luxury']
_COND_NEG = ['fixer', 'as-is', 'as is', 'needs love', 'needs work', 'tlc', 'handyman',
             'investor special', 'short sale', 'deferred maintenance', 'estate sale']

def _cond_flags(txt):
    t = str(txt or '').lower()
    return ([k for k in _COND_POS if k in t], [k for k in _COND_NEG if k in t])

def _outlier_reasons(r, cl, m):
    """Characteristics from the export that plausibly explain this sale's position."""
    bits = []
    la = pd.to_numeric(cl.get('Living Area'), errors='coerce')
    psf = pd.to_numeric(cl.get('PSF Finished'), errors='coerce')
    sz, med_sz = r.get('Living Area'), la.median()
    if sz == sz and med_sz == med_sz:
        if sz >= med_sz * 1.25: bits.append(f'at {int(sz):,} finished sq ft it is well above the {int(med_sz):,} sq ft median')
        elif sz <= med_sz * 0.75: bits.append(f'at {int(sz):,} finished sq ft it is well below the {int(med_sz):,} sq ft median')
        else: bits.append(f'its {int(sz):,} finished sq ft is close to the subdivision median')
    ps, med_ps = r.get('PSF Finished'), psf.median()
    if ps == ps and med_ps == med_ps:
        d_ = _pct(ps - med_ps, med_ps)
        if abs(d_) >= 10:
            bits.append(f'${ps:,.0f} per finished sq ft, {abs(d_):.0f}% {"above" if d_>0 else "below"} the ${med_ps:,.0f} median')
    bd = r.get('Bedrooms Total')
    if bd == bd: bits.append(f'{int(bd)} bedrooms')
    if str(r.get('Basement YN')).lower() in ('true', 'yes', '1'): bits.append('a finished basement adds space the median home here does not have')
    gs = pd.to_numeric(pd.Series([r.get('Garage Spaces')]), errors='coerce').iloc[0]
    allg = pd.to_numeric(cl.get('Garage Spaces'), errors='coerce')
    if gs == gs and len(allg.dropna()) and gs > allg.median(): bits.append(f'{int(gs)} garage spaces against a subdivision norm of {int(allg.median())}')
    lot, med_lot = pd.to_numeric(pd.Series([r.get('Lot Size Acres')]), errors='coerce').iloc[0], pd.to_numeric(cl.get('Lot Size Acres'), errors='coerce').median()
    if lot == lot and med_lot == med_lot and lot >= med_lot * 1.3: bits.append(f'a {lot:.2f}-acre lot against a {med_lot:.2f}-acre median')
    pos, neg = _cond_flags(r.get('Public Remarks'))
    if pos: bits.append('the listing describes updated or remodeled condition')
    if neg: bits.append('the listing describes a home needing work or sold on non-standard terms')
    return bits

def _outlier_sentence(r, cl, m, kind):
    dom = r.get('Days In MLS'); cp, lp, olp = r.get('Close Price'), r.get('List Price'), r.get('Original List Price')
    conc = r.get('conc', 0) or 0
    vs = ''
    if cp == cp and lp == lp:
        if cp > lp: vs = f'closed <strong>above</strong> its {M(lp)} asking price'
        elif cp < lp: vs = f'closed <strong>below</strong> its {M(lp)} asking price'
        else: vs = f'closed exactly at its {M(lp)} asking price'
    if olp == olp and lp == lp and olp > lp:
        vs += f', after coming down from a first ask of {M(olp)}'
    tim = f' in {int(dom)} day{"s" if int(dom)!=1 else ""} on the market' if dom == dom else ''
    cred = f' with a {M(conc)} credit to the buyer' if conc and conc > 0 else ' with no seller credit'
    why = _outlier_reasons(r, cl, m)
    whys = ('; '.join(why[:4]) + '.') if why else ''
    lead = 'Highest sale' if kind == 'high' else 'Lowest sale'
    return (f'<strong>{lead} &mdash; {r["addr"]}, {M(cp)}.</strong> It {vs}{tim}{cred}. '
            f'What the file shows about it: {whys}')

def outliers(cl, m):
    """The high and low closed sale, with data-supported explanation. May return
    a third note when price and price-per-sq-ft point in opposite directions."""
    if len(cl) < 4: return []
    hi = cl.loc[cl['Close Price'].idxmax()]; lo = cl.loc[cl['Close Price'].idxmin()]
    out = [_outlier_sentence(hi, cl, m, 'high'), _outlier_sentence(lo, cl, m, 'low')]
    psf = pd.to_numeric(cl.get('PSF Finished'), errors='coerce')
    if psf.notna().sum() >= 4:
        pmax = cl.loc[psf.idxmax()]; pmin = cl.loc[psf.idxmin()]
        if pmax['addr'] != hi['addr'] or pmin['addr'] != lo['addr']:
            out.append(
                f'<strong>Price and price per square foot do not agree.</strong> '
                f'The highest price per finished square foot belongs to {pmax["addr"]} at ${pmax["PSF Finished"]:,.0f}, '
                f'which sold for {M(pmax["Close Price"])} &mdash; while the lowest, {pmin["addr"]} at '
                f'${pmin["PSF Finished"]:,.0f}, sold for {M(pmin["Close Price"])}. '
                f'Square footage drives the total price; condition and size drive the rate. '
                f'Comparing a per-square-foot figure to a neighbor without adjusting for size will point the wrong way.')
    return out


# ---------------------------------------------------------------------------
# Market condition scale.
# The three-tier breakpoints are industry standard and follow DMAR's published
# convention: under 3 months of supply is a seller's market, 3-6 is balanced or
# neutral, over 6 is a buyer's market. (NAR places balance nearer 5-6 months;
# DMAR's 3/6 is used here because these reports are Colorado Front Range.)
# The finer gradations below are NOT an industry standard -- no association
# publishes official sub-tiers -- so they are a symmetric subdivision of the
# standard breakpoints, and the report says so wherever the label appears.
# ---------------------------------------------------------------------------
MOI_SCALE = [
    (1.5, 'Strong seller\u2019s market'),
    (3.0, 'Seller\u2019s market'),
    (4.5, 'Balanced, slight seller\u2019s edge'),
    (6.0, 'Balanced, slight buyer\u2019s edge'),
    (9.0, 'Buyer\u2019s market'),
    (float('inf'), 'Strong buyer\u2019s market'),
]

def moi_label(moi):
    """Descriptive market label for a months-of-supply figure."""
    if moi != moi: return 'Not enough data'
    for cap, lab in MOI_SCALE:
        if moi < cap: return lab
    return MOI_SCALE[-1][1]

def moi_tier(moi):
    """0-5 index into MOI_SCALE, for chart shading."""
    if moi != moi: return 2
    for i, (cap, _) in enumerate(MOI_SCALE):
        if moi < cap: return i
    return len(MOI_SCALE) - 1

# ---------------------------------------------------------------------------
# Monthly standouts, for the Digital Marketing Strategies section. Ranks the
# month-over-month series by size of the most recent move so the marketing
# copy always reflects whichever number actually moved this run, never a
# fixed "market is hot" assumption. Content strings built from this must stay
# on price/timing/inventory facts only -- see SKILL.md rule 9 and the Fair
# Housing note rendered alongside this section.
# ---------------------------------------------------------------------------
_MO_LABELS = {
    'med_close': 'the median closed price', 'med_dom': 'median days on market',
    'new': 'new listings', 'pending': 'homes going under contract',
    'closed': 'closed sales', 'msi': 'months of supply',
}
_MO_FMT = {
    'med_close': ('money', 0), 'med_dom': ('num', 0), 'new': ('num', 0),
    'pending': ('num', 0), 'closed': ('num', 0), 'msi': ('num', 1),
}

def monthly_standouts(mo_build, top=3):
    """List of dicts (key,label,pct,cur,prev,cur_m,prev_m,delta), biggest |pct|
    move first. Empty list if the export doesn't support month-over-month
    (see monthly.py) or nothing moved."""
    if not mo_build: return []
    import monthly as MO
    out = []
    for key, label in _MO_LABELS.items():
        ve = mo_build['series_ext'][key][MO.ALL]
        dd = MO.mom(ve, mo_build['months_ext'])
        if dd is None or dd['pct'] is None:
            continue
        kind, dec = _MO_FMT[key]
        fm = (lambda v: f'${v/1000:.0f}K' if v >= 1000 else f'${v:,.0f}') if kind == 'money' else (lambda v: f'{v:,.{dec}f}')
        out.append(dict(key=key, label=label, pct=dd['pct'], cur=fm(dd['cur']), prev=fm(dd['prev']),
                         cur_m=dd['cur_m'], prev_m=dd['prev_m'], delta=dd['delta']))
    out.sort(key=lambda x: abs(x['pct']), reverse=True)
    return out[:top]
