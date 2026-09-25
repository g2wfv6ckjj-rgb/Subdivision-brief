"""Social carousel — up to six 1080x1350 slides carrying the most useful
seller-side and buyer-side figures from the brief, in the report's own palette.

FORMAT
------
1080x1350 portrait, 4:5. It occupies the most vertical space a feed will give a
single image, so a thumb-scrolling reader sees more of it before scrolling past.
Instagram, LinkedIn and Facebook all take 4:5 natively without a re-crop.
Output is one PNG per slide plus a combined PDF, because LinkedIn's document
carousel takes a PDF while Instagram takes the images.

Unlike email_html.py, this renders through Chromium, so full CSS is available --
flexbox, web fonts, gradients. The constraint here is not the client, it is the
phone: a carousel is read at arm's length while scrolling, so each slide carries
ONE idea and one dominant number. Anything that needs a caption to decode belongs
in the PDF brief instead.

WHY THESE SLIDES
----------------
The brief's charts do not translate. The dumbbell is 25 rows of paired dots --
illegible on a phone and meaningless without its axis. The month-over-month lines
rest on samples too thin to headline (rule 19). So the carousel carries the
figures that are both robust at subdivision scale and decision-relevant to both
audiences:

  1 what's happening  the subdivision named, with the one-line verdict
  2 the dials         every index that resolved, plus three checkable medians
  3 seller: outcome   what sellers got against their first asking price
  4 seller: timing    the measured cost of a price cut, which is also the buyer's
                      signal for which listings have room
  5 buyer: leverage   under-ask count, seller credits, cash share
  6 CTA               one ask, plus broker identification

Slide 2 pairs derived indexes with raw medians deliberately. An index asks the
reader to trust a formula; a median sale price is checkable against any listing
they know. Putting checkable numbers beside derived ones is what makes the
derived ones credible.

The old "year in four numbers" slide is gone -- slide 2 absorbed it. Two slides
carrying median price and days to offer was repetition a reader notices.

Slide 2 renders however many dials resolved. Three is the common case, not a
degraded one: roughly seven Colorado ZIPs in ten have no rent series, so Rent to
Price is usually absent. A missing dial is omitted, never zeroed.

Slides 3-5 all branch on the data. A subdivision where most sellers got their
price produces different headlines and different colour emphasis from one where
most did not -- see _seller_outcome() and _buyer_leverage().

CONSTRAINTS (identical to marketing.py, and for the same reasons)
-----------------------------------------------------------------
This is public-facing copy, so: price, timing, inventory and process facts only.
No school content, no characterization of the neighborhood or who lives there, no
audience-targeting language.

Every figure on these slides is a WHOLE-YEAR figure. There is no month-over-month
content at all, which is deliberate rather than an omission: a carousel is the
most screenshot-and-reshared artifact the skill produces, so it should carry only
the numbers that hold up months later. That also means MIN_MONTH_CLOSINGS never
needs to fire here -- there is no month-specific claim to gate.

Broker identification and Equal Housing Opportunity render on the final slide as
merge-tag placeholders, since they vary per agent.
"""
import html as HT
import pathlib
import tempfile

import brand as BR
import dials as DL
import marketing as MK
from core import M, Mshort, dur

S = 1080   # slide width, px
H = 1350   # slide height, px -- 4:5 portrait

INK = '#10203A'; PINE = '#1F4B87'; SAGE = '#6FA0D0'
BRONZE = '#B0895C'; GOLD = '#8A6A45'; SAND = '#E0D5BC'
LINE = '#CBD4DE'; SOFT = '#56657A'; MIST = '#E7EFF8'; CARD = '#F2F5F9'
PAPER = '#FFFFFF'

FONT_H = '"Poppins","Liberation Sans",sans-serif'
FONT_B = '"Lora","Bitstream Charter",Georgia,serif'
FONT_M = '"DejaVu Sans Mono",monospace'


# ---------------------------------------------------------------- slide chrome
def _slide(inner, bg=PAPER, cls=''):
    return (f'<section class="sl {cls}" style="background:{bg};">{inner}</section>')


def _eyebrow(txt, color=BRONZE):
    """NOTE: the FONT_* constants contain double quotes (font names need them in
    CSS), so they must never be interpolated into an inline style="..." attribute
    -- the first inner quote closes the attribute and the whole rule is dropped
    silently. Anything needing a font goes in a CSS class instead. Only the colour,
    which is quote-free, is passed inline here."""
    return f'<div class="eyebrow" style="color:{color};">{txt}</div>'


def _num(sub, idx, total, dark=False):
    """Page marker plus the publisher's site, because a single slide gets
    screenshotted out of the set and has to carry the source with it."""
    c = '#7C8FA8' if dark else SOFT
    return (f'<div class="pg" style="color:{c};">{sub} &nbsp;&#183;&nbsp; '
            f'{idx} / {total} &nbsp;&#183;&nbsp; {BR.SITE}</div>')


# ---------------------------------------------------------------- data-driven headlines
def _seller_outcome(m):
    """Headline and emphasis branch on what actually happened. A subdivision where
    most sellers landed under their first price must not inherit 'sellers are
    winning here'."""
    n, at = m['n_cl'], m['at_or_above']
    share = at / n * 100 if n else 0
    # "Evenly" must mean evenly. A 45-55 band only -- an earlier 30% floor let a
    # 32/68 split print as "about evenly", which is the kind of claim an agent
    # gets challenged on in a listing appointment.
    if share >= 55:
        return ('Most sellers got their asking price', PINE,
                f'{at} of {n} homes sold at or above the first price published.')
    if share >= 45:
        return ('It split about evenly', PINE,
                f'{at} of {n} homes sold at or above the first price published; '
                f'{m["under_orig"]} landed below it.')
    return ('Most homes sold below the first ask', BRONZE,
            f'{m["under_orig"]} of {n} homes closed under the price they opened at.')


def _buyer_leverage(m):
    """Same treatment for the buyer side."""
    n = m['n_cl']
    share = m['under_orig'] / n * 100 if n else 0
    if share >= 55:
        return ('There is room to negotiate here',
                f'{m["under_orig"]} of {n} sales closed below the original asking price.')
    if share >= 30:
        return ('Some listings have room, some do not',
                f'{m["under_orig"]} of {n} sales closed below the original asking price '
                f'&mdash; and {m["at_or_above"]} did not.')
    return ('Most homes here go at or above ask',
            f'Only {m["under_orig"]} of {n} sales closed below the original asking price.')


# ---------------------------------------------------------------- slide bodies
_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}


def _words(n):
    return _WORDS.get(n, str(n))


def _verdict(m):
    """One line naming what the market is doing, chosen from the export rather
    than written in advance. Kept descriptive -- it characterizes the MARKET, not
    the neighborhood or who lives in it."""
    moi, dtc = m['moi'], m['dtc_med']
    if moi < 2 and dtc <= 21:
        return 'Homes are moving fast and inventory is thin.'
    if moi < 3:
        return 'Supply is tight and well-priced homes are selling.'
    if moi < 5:
        return 'A balanced market &mdash; price and condition decide the outcome.'
    return 'Inventory has built up and buyers have choices.'


def _s1_cover(m, sub, place):
    return _slide(
        f'''<div class="pad ctr">
<div class="badge">Market brief</div>
<div class="covkick">What&#8217;s happening in</div>
<h1 class="cov">{HT.escape(sub)}</h1>
<div class="covloc">{HT.escape(place)}</div>
<div class="covrng">365 days of activity &nbsp;&#183;&nbsp; {m['n_cl']} closed sales</div>
<div class="covline"></div>
<div class="covsub">{_verdict(m)}</div>
</div>''', bg=PAPER, cls='light-cov')


def _s2_dials(m, sub, scores=None, area=None):
    """Every index that resolved, plus three medians a reader can check.

    Layout adapts to the count: five dials go 3-over-2, three go in one row. The
    three-dial case must not look broken, because it is the usual one.
    """
    got = DL.present(scores, area)
    faces = ''
    for k, v in got:
        # Market Balance gets its directional verdict word here too, matching
        # the PDF dashboard -- the carousel used to show a bare number with
        # no cue which side a high score favors. See rule 70.
        vw = DL.verdict(v, 'Seller-leaning', 'Balanced', 'Buyer-leaning') if k == 'balance' else None
        faces += (f'<div class="dl"><div class="dlg">{DL.gauge(v, size=236, stroke=22, font=FONT_H, verdict=vw)}</div>'
                  f'<div class="dln">{DL.label(k)}</div>'
                  f'<div class="dls">{DL.scope(k, area)}</div></div>')
    stats = [
        (Mshort(m['med']), 'MEDIAN SALE PRICE', f"{m['n_cl']} closed sales"),
        (f"{m['dtc_med']:.0f} days", 'MEDIAN DAYS TO OFFER', 'list to under contract'),
        (f"{m['cpo']:.1f}%", 'OF THE ORIGINAL ASK', 'median close, first price'),
    ]
    srow = ''.join(f'<div class="ds"><div class="dsv">{v}</div>'
                   f'<div class="dsk">{k}</div><div class="dsn">{n}</div></div>'
                   for v, k, n in stats)
    miss = ''
    if len(got) < 5:
        absent = [DL.label(k) for k in DL.ORDER if k not in dict(got)]
        miss = ('<div class="dmiss">Not available for this area: '
                + ', '.join(absent) + '</div>')
    return _slide(
        f'''<div class="pad">
{_eyebrow(f'The market in {_words(len(got))} numbers')}
<h2 class="hd tight">{HT.escape(sub)}, scored</h2>
<div class="dgrid">{faces}</div>
{miss}
<div class="dstats">{srow}</div>
<div class="ft ftd">Each index runs 0&ndash;100 and prints the geography it was measured at.
Higher market balance means scarcer supply &mdash; good for sellers, harder for buyers.</div>
{_num(sub, 2, 6)}
</div>''')


def _s3_seller(m, sub):
    head, accent, sup = _seller_outcome(m)
    n = m['n_cl']; at = m['at_or_above']; und = m['under_orig']
    pa = max(6, round(at / n * 100)) if n else 50
    return _slide(
        f'''<div class="pad">
{_eyebrow('If you are selling')}
<h2 class="hd" style="color:{accent};">{head}</h2>
<div class="lede">{sup}</div>
<div class="barwrap">
  <div class="bar">
    <div class="seg" style="width:{pa}%;background:{PINE};"></div>
    <div class="seg" style="width:{100-pa}%;background:{BRONZE};"></div>
  </div>
  <div class="barkey">
    <span><i style="background:{PINE};"></i>{at} at or above ask</span>
    <span><i style="background:{BRONZE};"></i>{und} below ask</span>
  </div>
</div>
<div class="statrow">
  <div class="st"><div class="stv">{m['cpo']:.1f}%</div>
    <div class="std">of the original asking price,<br>on average</div></div>
  <div class="st"><div class="stv">{m['dtc_med']:.0f}</div>
    <div class="std">days to an accepted offer,<br>median</div></div>
</div>
<div class="ft">Measured against the <strong>original</strong> asking price &mdash; the first
number published, before any reduction. Measuring against a reduced price would count a
cut-then-sold home as a full-price sale.</div>
{_num(sub, 3, 6)}
</div>''')


def _s4_timing(m, sub):
    a, b = m['ttl_nored'], m['ttl_red']
    mx = max(a, b) or 1
    return _slide(
        f'''<div class="pad">
{_eyebrow('What a price cut costs')}
<h2 class="hd">The first price sets the timeline</h2>
<div class="lede">Both groups sold. The difference was
<strong>{dur(abs(b - a))}</strong> of carrying the house.</div>
<div class="hbars">
  <div class="hb">
    <div class="hbl">Never reduced</div>
    <div class="hbt"><div class="hbf" style="width:{a/mx*100:.0f}%;background:{PINE};">
      <span>{a:.0f} days</span></div></div>
  </div>
  <div class="hb">
    <div class="hbl">Took a price cut</div>
    <div class="hbt"><div class="hbf" style="width:{b/mx*100:.0f}%;background:{BRONZE};">
      <span>{b:.0f} days</span></div></div>
  </div>
</div>
<div class="ft">Median days from listing to closing, {m['n_cl']} sales.
Buying? A seller who has already reduced once has shown what they are willing to do.</div>
{_num(sub, 4, 6)}
</div>''')


def _s5_buyer(m, sub):
    head, sup = _buyer_leverage(m)
    cash = (f'<div class="st"><div class="stv">{m["cash_pct"]:.0f}%</div>'
            f'<div class="std">of buyers paid cash</div></div>') if m.get('n_fin_known', 0) >= 8 else ''
    return _slide(
        f'''<div class="pad">
{_eyebrow('If you are buying')}
<h2 class="hd">{head}</h2>
<div class="lede">{sup}</div>
<div class="statrow three">
  <div class="st"><div class="stv">{m['disc_orig']:.1f}%</div>
    <div class="std">below the first price,<br>average sale</div></div>
  <div class="st"><div class="stv">{m['conc_n']}</div>
    <div class="std">got a seller credit &mdash;<br>median {Mshort(m['conc_med'])}</div></div>
  {cash}
</div>
<div class="ft">Seller credits go toward closing costs or a rate buy-down. Days on market
is the best single signal of which listing has room.</div>
{_num(sub, 5, 6)}
</div>''')


def _s6_cta(m, sub, place, agent=None):
    """agent: optional dict (name, phone, email, headshot_path, logo_path).
    None -- or an agent who hasn't set any of it up yet -- keeps the
    original generic FNT-only sign-off exactly as it was. Every other case
    (photo but no logo, contact info but no photo, etc.) degrades gracefully
    rather than assuming all fields are present -- see rule 72."""
    if agent:
        photo = ''
        if agent.get('headshot_path'):
            photo = (f'<img class="agentphoto" src="file://{agent["headshot_path"]}" '
                     f'alt="{HT.escape(agent.get("name") or "")}">')
        contact_bits = [x for x in (agent.get('phone'), agent.get('email')) if x]
        sign_html = (
            (photo or '')
            + (f'<div class="agentname">{HT.escape(agent.get("name") or "")}</div>' if agent.get('name') else '')
            + (f'<div class="agentcontact">{HT.escape(" &#183; ".join(contact_bits))}</div>' if contact_bits else '')
            + f'<div class="agentfnt">{BR.NAME}</div>'
        )
    else:
        sign_html = f'{BR.logo_img(96)}<div class="broker">{"<br>".join(BR.signoff_lines())}</div>'

    return _slide(
        f'''<div class="pad ctr">
{_eyebrow('Want the full picture?', '#C9A46B')}
<h2 class="hd cta">Every sale in {HT.escape(sub)},<br>with the numbers behind it.</h2>
<div class="ctasub">Send me a message and I will send the full brief &mdash; what each home
listed for, what it closed for, and how long it took.</div>
<div class="ctaline"></div>
{sign_html}
<div class="eho">{BR.EHO} &nbsp;&#183;&nbsp; Figures from a 365-day MLS export
of {HT.escape(sub)}, {HT.escape(place)}. Information deemed reliable but not guaranteed.</div>
</div>''', bg=PAPER, cls='light-cov')


# ---------------------------------------------------------------- document
CSS = f'''
*{{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{background:#8894A6;}}
.sl{{width:{S}px;height:{H}px;position:relative;overflow:hidden;display:block;}}
.pad{{position:absolute;inset:0;padding:84px 78px;display:flex;flex-direction:column;}}
.ctr{{align-items:center;justify-content:center;text-align:center;}}
.light-cov::before{{content:"";position:absolute;left:0;right:0;top:0;height:14px;
  background:{BRONZE};}}
.light-cov::after{{content:"";position:absolute;left:0;right:0;bottom:0;height:14px;
  background:{PINE};}}
.dark, .dark .hd{{color:#EDF2F8;}}
.pg{{position:absolute;left:78px;bottom:58px;font-family:{FONT_M};font-size:18px;
   letter-spacing:.16em;text-transform:uppercase;}}
.eyebrow{{font-family:{FONT_M};font-size:23px;letter-spacing:.2em;text-transform:uppercase;
   margin-bottom:8px;}}

.badge{{display:inline-block;border:3px solid {BRONZE};color:{GOLD};border-radius:60px;
  padding:10px 34px;font-family:{FONT_M};font-size:19px;letter-spacing:.2em;
  text-transform:uppercase;margin-bottom:44px;}}
h1.cov{{font-family:{FONT_H};font-size:104px;line-height:.98;font-weight:700;color:{INK};
  letter-spacing:-.025em;margin-bottom:18px;}}
.covloc{{font-family:{FONT_B};font-size:38px;color:{PINE};margin-bottom:14px;}}
.covrng{{font-family:{FONT_M};font-size:20px;letter-spacing:.16em;color:{SOFT};
  text-transform:uppercase;}}
.covkick{{font-family:{FONT_B};font-size:40px;color:{SOFT};margin-bottom:10px;}}
.covline{{width:110px;height:4px;background:{BRONZE};margin:46px auto;}}
.covsub{{font-family:{FONT_B};font-size:34px;line-height:1.4;color:#26384F;}}

h2.hd{{font-family:{FONT_H};font-size:66px;line-height:1.05;font-weight:700;color:{INK};
  letter-spacing:-.02em;margin:18px 0 26px;}}
h2.hd.tight{{margin-bottom:14px;}}

.dgrid{{display:flex;flex-wrap:wrap;justify-content:center;gap:30px 22px;
  margin:18px 0 6px;}}
.dl{{flex:0 0 282px;}}
.dl{{text-align:center;}}

.dlg{{display:flex;justify-content:center;height:200px;align-items:flex-start;}}
.dln{{font-family:{FONT_H};font-size:30px;font-weight:700;color:{INK};line-height:1.15;
  margin-top:4px;letter-spacing:-.01em;height:72px;display:flex;align-items:center;
  justify-content:center;}}
.dls{{font-family:{FONT_M};font-size:17px;letter-spacing:.14em;color:{SOFT};margin-top:10px;}}
.dmiss{{font-family:{FONT_M};font-size:17px;color:{SOFT};margin-top:16px;}}
.ft.ftd{{margin-top:36px;}}
.dstats{{display:flex;gap:26px;margin-top:auto;border-top:4px solid {LINE};padding-top:34px;}}
.ds{{flex:1;}}
.dsv{{font-family:{FONT_H};font-size:64px;font-weight:700;line-height:1;color:{INK};
  letter-spacing:-.03em;}}
.dsk{{font-family:{FONT_M};font-size:17px;letter-spacing:.12em;color:{PINE};margin-top:11px;}}
.dsn{{font-family:{FONT_M};font-size:18px;color:{SOFT};margin-top:7px;}}
.lede{{font-family:{FONT_B};font-size:34px;line-height:1.42;color:#26384F;margin-bottom:44px;}}
.ft{{font-family:{FONT_M};font-size:19px;line-height:1.6;color:{SOFT};margin-top:auto;
  padding-bottom:52px;}}

.quad{{display:flex;flex-wrap:wrap;gap:26px;margin-top:34px;}}
.qc{{flex:1 1 44%;background:{CARD};border-radius:14px;padding:38px 34px;}}
.qk{{font-family:{FONT_M};font-size:19px;letter-spacing:.12em;text-transform:uppercase;
  color:{SOFT};margin-bottom:14px;}}
.qv{{font-family:{FONT_H};font-size:82px;font-weight:700;line-height:1;color:{INK};
  letter-spacing:-.03em;}}
.qd{{font-family:{FONT_M};font-size:20px;color:{SOFT};margin-top:12px;}}

.barwrap{{margin-bottom:52px;}}
.bar{{display:flex;height:74px;border-radius:10px;overflow:hidden;}}
.seg{{height:100%;}}
.barkey{{display:flex;gap:44px;margin-top:22px;font-family:{FONT_M};font-size:22px;
  color:{SOFT};}}
.barkey i{{display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:11px;
  vertical-align:-2px;}}

.statrow{{display:flex;gap:30px;}}
.st{{flex:1;border-top:4px solid {LINE};padding-top:26px;}}
.stv{{font-family:{FONT_H};font-size:76px;font-weight:700;line-height:1;color:{PINE};
  letter-spacing:-.03em;}}
.std{{font-family:{FONT_M};font-size:20px;line-height:1.55;color:{SOFT};margin-top:14px;}}
.statrow.three .stv{{font-size:64px;}}

.hbars{{margin-bottom:20px;}}
.hb{{margin-bottom:40px;}}
.hbl{{font-family:{FONT_M};font-size:22px;letter-spacing:.1em;text-transform:uppercase;
  color:{SOFT};margin-bottom:14px;}}
.hbt{{background:{CARD};border-radius:10px;overflow:hidden;}}
.hbf{{height:88px;border-radius:10px;display:flex;align-items:center;justify-content:flex-end;
  padding-right:26px;}}
.hbf span{{font-family:{FONT_H};font-size:42px;font-weight:700;color:#fff;}}

h2.cta{{font-size:62px;color:{INK};margin:26px 0 30px;}}
.ctasub{{font-family:{FONT_B};font-size:32px;line-height:1.45;color:#26384F;max-width:780px;}}
.ctaline{{width:110px;height:4px;background:{BRONZE};margin:46px auto 40px;}}
.broker{{font-family:{FONT_M};font-size:27px;letter-spacing:.06em;line-height:1.5;
  color:{PINE};margin-top:22px;}}
.eho{{font-family:{FONT_M};font-size:17px;line-height:1.65;color:{SOFT};margin-top:26px;
  max-width:800px;}}
.agentphoto{{width:132px;height:132px;border-radius:50%;object-fit:cover;
  border:4px solid {PAPER};box-shadow:0 3px 14px rgba(16,32,58,.18);margin-bottom:18px;}}
.agentname{{font-family:{FONT_H};font-size:36px;font-weight:700;color:{INK};letter-spacing:-.01em;}}
.agentcontact{{font-family:{FONT_M};font-size:22px;color:{PINE};margin-top:8px;letter-spacing:.02em;}}
.agentfnt{{font-family:{FONT_M};font-size:16px;letter-spacing:.14em;text-transform:uppercase;
  color:{SOFT};margin-top:20px;}}
'''


def slides(m, sub, city, scores=None, area=None, agent=None):
    """The slide fragments, in order.

    `scores` is master.scores() output; `area` carries the ZIP/county reference
    values and their resolved geographies. Both are optional -- with neither,
    slide 2 renders whatever the MLS export alone supports.
    """
    place = MK._place(city)
    m = dict(m); m['_sub'] = sub
    return [
        _s1_cover(m, sub, place),
        _s2_dials(m, sub, scores, area),
        _s3_seller(m, sub),
        _s4_timing(m, sub),
        _s5_buyer(m, sub),
        _s6_cta(m, sub, place, agent),
    ]


def document(m, sub, city, gap=True, scores=None, area=None, agent=None):
    """Full HTML holding every slide, for rendering or preview."""
    sl = slides(m, sub, city, scores, area, agent)
    sep = 'margin:0 auto 26px;' if gap else 'margin:0 auto;'
    body = ''.join(s.replace('style="background:', f'style="{sep}background:') for s in sl)
    page = '' if gap else ('body{background:#fff;} .sl{margin:0;} '
                           '@page{size:%dpx %dpx;margin:0;}' % (S, H))
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<title>{HT.escape(sub)} carousel</title><style>{CSS}{page}</style></head>'
            f'<body>{body}</body></html>')


def render(m, sub, city, outdir, pdf=True, scores=None, area=None, agent=None):
    """Write one PNG per slide, plus a combined PDF for LinkedIn document posts.
    Returns the list of paths written.

    agent: optional dict (name, phone, email, headshot_path, logo_path) --
    an Agent.brand_dict() from the web app. Renders on the closing CTA
    slide (_s6_cta) in place of the generic FNT-only sign-off. None
    (default) keeps the original generic branding untouched. See rule 72.
    """
    from playwright.sync_api import sync_playwright
    slug = sub.replace(' ', '_')
    frags = slides(m, sub, city, scores, area, agent)
    written = []
    with tempfile.TemporaryDirectory(prefix='carousel-') as tmp:
        tdir = pathlib.Path(tmp)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={'width': S, 'height': H}, device_scale_factor=1)
            for i, frag in enumerate(frags, 1):
                one = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                       f'<style>{CSS} body{{background:#fff;}} .sl{{margin:0;}}</style>'
                       f'</head><body>{frag}</body></html>')
                fp = tdir / f'{i}.html'; fp.write_text(one, encoding='utf-8')
                pg.goto(fp.resolve().as_uri(), wait_until='networkidle')
                out = f'{outdir}/{slug}_Carousel_{i}.png'
                pg.locator('section.sl').screenshot(path=out)
                written.append(out)
            if pdf:
                allp = tdir / 'all.html'
                allp.write_text(document(m, sub, city, gap=False, scores=scores,
                                         area=area, agent=agent), encoding='utf-8')
                pg.goto(allp.resolve().as_uri(), wait_until='networkidle')
                pg.emulate_media(media='print')
                pout = f'{outdir}/{slug}_Carousel.pdf'
                pg.pdf(path=pout, width=f'{S}px', height=f'{H}px',
                       print_background=True,
                       margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
                written.append(pout)
            b.close()
    return written
