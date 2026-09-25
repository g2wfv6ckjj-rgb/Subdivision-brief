"""Print-ready EDDM direct-mail postcard, matching the carousel's visual system.

FORMAT -- verified against current USPS EDDM Retail rules (checked live, not
assumed): a mailpiece must exceed 6.125" in height OR 10.5"-11" in length to
qualify as a flat; under either threshold it gets rejected at the counter or
bumped to a First-Class letter rate. 9" x 6.25" landscape is the most commonly
cited practical minimum specifically because 6.25" clears the height floor by
only an eighth of an inch -- comfortably, not by accident. Do not shrink this.

  TRIM   9.00 x 6.25 in   -- the size after cutting; what the recipient holds
  BLEED  0.125 in / side  -- design extends this far past trim so a cutter
                             mis-register never shows white edge
  CANVAS 9.25 x 6.50 in   -- TRIM + BLEED on all sides; this is what gets sent
  SAFE   0.25 in inside trim -- no text or logo any closer to the cut line
  DPI    300              -- canvas renders at 2775 x 1950 px

SIDE A -- three selectable front designs (rule 68), same real numbers, same
brand system, different standout treatment:
  'A' -- two stats side by side (median price, days to offer). Balanced,
         no single dominant focal point. The original design.
  'B' -- one oversized hero number (median price), two much smaller
         supporting stats beneath it. Bets that one huge number stops a
         hand mid-mail-sort better than two medium ones do.
  'C' -- leads with the Chance of Selling dial instead of a plain number.
         Ties the postcard's hero visual to the same graphic language the
         brief and carousel already use.
render()'s default (side_a_variant='ALL') produces all three as complete,
self-contained packages -- an agent opens all three PDFs and picks one, no
assembly required on their end. No single default is set at the skill level;
which design an office uses is theirs to choose, run to run or permanently.

SIDE B splits 9" trim width into a 5.5" message panel (left: the dials,
three checkable stats, brand line, Equal Housing Opportunity mark -- fully
populated, identical across all three variants, ships as-is) and a 3.5"
mailing panel (right) that is DELIBERATELY BLANK. It used to carry a
return-address box, an EDDM indicia placeholder and "Local Postal Customer" /
"ECRWSS" boilerplate; removed, because this is one shared template used by
many offices with different addresses, different USPS permits, and possibly
different mailing methods (true EDDM saturation addressing isn't the only
option), and a bracketed placeholder risks being mistaken for real content if
an agent forgets to replace it before it goes to press. The panel is left for
whoever prints it to add their own. The bottom 2.125" of that panel is where
USPS reserves space for its own barcode/indicia machine-stamping and rejects
mail with anything printed there -- this module never puts a design element
in that strip, not even a guide line; the annotated Guides.pdf shows exactly
where it starts, in a separate, clearly-marked reference file, so whoever
fills in the panel isn't guessing where they can safely put their own return
address or indicia.

Dial names/geography/gauge all come from dials.py, so this card and the
carousel can never drift into using different numbers for the same
subdivision. All three subdivision-scoped names now match the PDF's own
(Chance of Selling, Pricing Power, Market Balance) -- see SKILL.md rule 58.
"""
import html as HT

import brand as BR
import dials as DL
from core import Mshort

DPI = 300
TRIM_W, TRIM_H = 9.0, 6.25
BLEED = 0.125
CW, CH = TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED       # canvas, inches
PXW, PXH = round(CW * DPI), round(CH * DPI)           # canvas, pixels
SAFE = 0.25                                            # inches inside TRIM

MSG_W = 5.5      # message panel width, trim inches
MAIL_W = TRIM_W - MSG_W                                # 3.5in mailing panel
BARCODE_CLEAR_IN = 2.125                                # bottom strip, MUST stay blank

INK = '#10203A'
PINE = '#1F4B87'
SOFT = '#56657A'
YEL = '#FFC629'
YEL_D = '#C99400'
LINE = '#D7DFE9'
PAPER = '#FFFFFF'
FONT_H = '"Poppins","Liberation Sans",sans-serif'
FONT_B = '"Lora",Georgia,serif'
FONT_M = '"DejaVu Sans Mono",monospace'

_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}


def _verdict(m):
    moi, dtc = m['moi'], m['dtc_med']
    if moi < 2 and dtc <= 21:
        return 'Homes are moving fast and inventory is thin.'
    if moi < 3:
        return 'Supply is tight and well-priced homes are selling.'
    if moi < 5:
        return "A balanced market &mdash; price and condition decide the outcome."
    return 'Inventory has built up and buyers have choices.'


def _base_css():
    return f'''
*{{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{width:{PXW}px;height:{PXH}px;background:#8894A6;font-family:{FONT_H};}}
.canvas{{width:{PXW}px;height:{PXH}px;background:{PAPER};position:relative;overflow:hidden;}}
'''


def _in(v):
    """inches -> px at DPI, as a CSS length."""
    return f'{v * DPI:.1f}px'


def side_a_html(m, sub, place, area=None, scores=None, variant='A'):
    """Hook side. No mail markings. Full bleed.

    Three layouts, same brand system (INK/PINE/YEL, Poppins/Lora), same real
    numbers -- they differ only in which number is the standout and how much
    visual weight it gets. Pick one per rule 68; nothing here is provisional
    once chosen, so don't ship more than one variant to a print vendor.

    'A' -- two stats side by side (median price, days to offer). The
           original design: balanced, no single dominant focal point.
    'B' -- one oversized hero number (median price) with two much smaller
           supporting stats beneath it. Single-focal-point design; the bet is
           that one huge number stops a hand mid-mail-sort better than two
           medium ones do.
    'C' -- leads with the Chance of Selling dial instead of a plain number.
           Ties the postcard's hero visual to the same graphic language the
           brief and carousel already use, so a recipient who has seen either
           recognizes the score rather than meeting a new, unexplained number.
    """
    verdict = _verdict(m)
    if variant not in ('A', 'B', 'C'):
        raise ValueError(f"side_a_html variant must be 'A', 'B' or 'C', got {variant!r}")

    base_css = _base_css() + f'''
.pad{{position:absolute;left:{_in(BLEED + SAFE)};top:{_in(BLEED + SAFE)};
  width:{_in(TRIM_W - 2*SAFE)};height:{_in(TRIM_H - 2*SAFE)};
  display:flex;flex-direction:column;justify-content:center;}}
.canvas::before{{content:"";position:absolute;left:0;right:0;top:0;height:{_in(0.12)};background:{YEL};}}
.canvas::after{{content:"";position:absolute;left:0;right:0;bottom:0;height:{_in(0.12)};background:{INK};}}
.kick{{font-size:{_in(0.20)};font-weight:700;letter-spacing:.16em;color:{SOFT};text-transform:uppercase;}}
.loc{{font-family:{FONT_B};font-size:{_in(0.30)};color:{PINE};margin-top:{_in(0.06)};}}
.verdict{{font-family:{FONT_B};font-size:{_in(0.26)};color:{INK};max-width:{_in(6.3)};line-height:1.35;}}
.cta{{display:inline-block;background:{INK};color:#fff;font-weight:700;
  font-size:{_in(0.20)};padding:{_in(0.10)} {_in(0.26)};align-self:flex-start;}}
'''

    if variant == 'A':
        css = base_css + f'''
h1{{font-size:{_in(0.86)};font-weight:700;color:{INK};letter-spacing:-.01em;line-height:1.0;margin-top:{_in(0.08)};}}
.verdict{{margin-top:{_in(0.22)};}}
.herorow{{display:flex;gap:{_in(0.55)};margin-top:{_in(0.30)};align-items:flex-end;}}
.heroval{{font-size:{_in(0.95)};font-weight:700;color:{INK};line-height:1;letter-spacing:-.02em;}}
.herolab{{font-family:{FONT_M};font-size:{_in(0.145)};letter-spacing:.1em;color:{PINE};margin-top:{_in(0.06)};}}
.sub{{font-family:{FONT_M};font-size:{_in(0.145)};letter-spacing:.1em;color:{SOFT};margin-top:{_in(0.02)};}}
.cta{{margin-top:{_in(0.34)};}}
'''
        body = f'''
  <div class="kick">Market Update</div>
  <h1>{HT.escape(sub.upper())}</h1>
  <div class="loc">{HT.escape(place)}</div>
  <div class="verdict">{verdict}</div>
  <div class="herorow">
    <div class="hero"><div class="heroval">{Mshort(m['med'])}</div>
      <div class="herolab">MEDIAN SALE PRICE</div><div class="sub">{m['n_cl']} closed sales, 365 days</div></div>
    <div class="hero"><div class="heroval">{m['dtc_med']:.0f}</div>
      <div class="herolab">MEDIAN DAYS TO OFFER</div><div class="sub">list to under contract</div></div>
  </div>
  <div class="cta">WHAT'S YOUR HOME WORTH IN TODAY'S MARKET?</div>'''

    elif variant == 'B':
        css = base_css + f'''
h1{{font-size:{_in(0.60)};font-weight:700;color:{INK};letter-spacing:-.01em;line-height:1.0;margin-top:{_in(0.06)};}}
.verdict{{margin-top:{_in(0.12)};font-size:{_in(0.20)};max-width:{_in(7.5)};}}
.knockout{{margin-top:{_in(0.18)};}}
.koval{{font-size:{_in(1.55)};font-weight:700;color:{INK};line-height:0.92;letter-spacing:-.03em;}}
.kolab{{font-family:{FONT_M};font-size:{_in(0.16)};letter-spacing:.12em;color:{PINE};margin-top:{_in(0.06)};}}
.miniRow{{display:flex;gap:{_in(0.60)};margin-top:{_in(0.20)};}}
.mini{{}}
.minival{{font-size:{_in(0.34)};font-weight:700;color:{INK};line-height:1;}}
.minilab{{font-family:{FONT_M};font-size:{_in(0.105)};letter-spacing:.08em;color:{SOFT};margin-top:{_in(0.03)};}}
.cta{{margin-top:{_in(0.22)};}}
'''
        body = f'''
  <div class="kick">Market Update &mdash; {HT.escape(place)}</div>
  <h1>{HT.escape(sub.upper())}</h1>
  <div class="verdict">{verdict}</div>
  <div class="knockout">
    <div class="koval">{Mshort(m['med'])}</div>
    <div class="kolab">MEDIAN SALE PRICE &middot; {m['n_cl']} CLOSED SALES, 365 DAYS</div>
  </div>
  <div class="miniRow">
    <div class="mini"><div class="minival">{m['dtc_med']:.0f} days</div><div class="minilab">TO OFFER</div></div>
    <div class="mini"><div class="minival">{m['cpo']:.1f}%</div><div class="minilab">OF ORIGINAL ASK</div></div>
  </div>
  <div class="cta">WHAT'S YOUR HOME WORTH IN TODAY'S MARKET?</div>'''

    elif variant == 'C':
        chance = (scores or {}).get('chance')
        gauge_svg = DL.gauge(chance, size=520, stroke=34, font=FONT_H) if chance is not None else ''
        css = base_css + f'''
h1{{font-size:{_in(0.58)};font-weight:700;color:{INK};letter-spacing:-.01em;line-height:1.0;margin-top:{_in(0.04)};}}
.loc{{font-size:{_in(0.22)};}}
.dialrow{{display:flex;align-items:center;gap:{_in(0.35)};margin-top:{_in(0.16)};}}
.dialwrap{{flex:0 0 auto;}}
.diallabel{{font-size:{_in(0.30)};font-weight:700;color:{INK};margin-top:{_in(-0.10)};}}
.dialsub{{font-family:{FONT_M};font-size:{_in(0.11)};letter-spacing:.08em;color:{PINE};margin-top:{_in(0.02)};}}
.sidestats{{display:flex;flex-direction:column;gap:{_in(0.16)};}}
.sideval{{font-size:{_in(0.40)};font-weight:700;color:{INK};line-height:1;}}
.sidelab{{font-family:{FONT_M};font-size:{_in(0.10)};letter-spacing:.07em;color:{SOFT};margin-top:{_in(0.02)};}}
.verdict{{margin-top:{_in(0.16)};font-size:{_in(0.19)};max-width:{_in(6.5)};}}
.cta{{margin-top:{_in(0.20)};}}
'''
        body = f'''
  <div class="kick">Market Update</div>
  <h1>{HT.escape(sub.upper())}</h1>
  <div class="loc">{HT.escape(place)}</div>
  <div class="dialrow">
    <div class="dialwrap">{gauge_svg}
      <div class="diallabel">Chance of Selling</div>
      <div class="dialsub">0&ndash;100, HIGHER IS BETTER</div></div>
    <div class="sidestats">
      <div><div class="sideval">{Mshort(m['med'])}</div><div class="sidelab">MEDIAN SALE PRICE</div></div>
      <div><div class="sideval">{m['dtc_med']:.0f} days</div><div class="sidelab">MEDIAN DAYS TO OFFER</div></div>
    </div>
  </div>
  <div class="verdict">{verdict}</div>
  <div class="cta">WHAT'S YOUR HOME WORTH IN TODAY'S MARKET?</div>'''

    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="canvas"><div class="pad">{body}
</div></div>
</body></html>'''


def side_b_html(m, sub, scores=None, area=None, agent=None):
    """Mailing side. Left: message panel (dials, stats, brand, EHO) -- fully
    populated, ships as-is. Right: mailing panel -- deliberately BLANK.

    agent: optional dict (name, phone, email, headshot_path, logo_path) --
    an Agent.brand_dict() from the web app. When set, a compact row (small
    headshot if provided, name, phone) renders above the existing FNT
    brand/site line -- added alongside it, not replacing it, since the FNT
    identity and EHO mark stay mandatory regardless of what an individual
    agent has personalized. None (default, or an agent who hasn't set
    anything up) renders exactly as before this existed. See rule 72.

    This used to carry a return-address box, an EDDM indicia placeholder, and
    "ECRWSS" / "Local Postal Customer" boilerplate. Removed: this is a shared
    template used across many offices and mailing methods, and a return
    address or indicia box baked in as a bracketed placeholder risks being
    mistaken for real content if an agent forgets to replace it, or simply
    doesn't match how a given office actually mails (some will use EDDM
    saturation addressing, some a real mail-merge list, some a different
    permit format entirely). None of that is this skill's call to make for
    every office it ships to. The panel is left blank for whoever prints it
    to add their own -- see the Guides.pdf for exactly where the USPS barcode
    clear zone sits, so that addition doesn't have to guess.
    """
    got = DL.present(scores, area)
    cols = 3 if len(got) != 4 else 2
    # Market Balance gets its directional verdict word here too, matching
    # the PDF dashboard -- see rule 70.
    def _vw(k, v):
        return DL.verdict(v, 'Seller-leaning', 'Balanced', 'Buyer-leaning') if k == 'balance' else None
    faces = ''.join(
        f'<div class="dl"><div class="dlg">{DL.gauge(v, size=190, stroke=19, font=FONT_H, verdict=_vw(k, v))}</div>'
        f'<div class="dln">{DL.label(k)}</div><div class="dls">{DL.scope(k, area)}</div></div>'
        for k, v in got)
    stats = [
        (Mshort(m['med']), 'MEDIAN SALE PRICE'),
        (f"{m['dtc_med']:.0f} days", 'DAYS TO OFFER'),
        (f"{m['cpo']:.1f}%", 'OF ORIGINAL ASK'),
    ]
    srow = ''.join(f'<div class="ds"><div class="dsv">{v}</div><div class="dsk">{k}</div></div>'
                   for v, k in stats)
    miss = ''
    if len(got) < 5:
        absent = [DL.label(k) for k in DL.ORDER if k not in dict(got)]
        miss = f'<div class="dmiss">Not scored for this area: {", ".join(absent)}</div>'

    css = _base_css() + f'''
.msg{{position:absolute;left:{_in(BLEED)};top:{_in(BLEED)};width:{_in(MSG_W)};height:{_in(TRIM_H)};
  padding:{_in(SAFE)};display:flex;flex-direction:column;overflow:hidden;}}
.mail{{position:absolute;left:{_in(BLEED+MSG_W)};top:{_in(BLEED)};width:{_in(MAIL_W)};height:{_in(TRIM_H)};
  border-left:1px dashed {LINE};}}
.mhd{{font-size:{_in(0.155)};font-weight:700;letter-spacing:.12em;color:{INK};text-transform:uppercase;}}
.mname{{font-size:{_in(0.30)};font-weight:700;color:{INK};margin-top:{_in(0.02)};}}
.rule{{height:2px;background:{INK};margin:{_in(0.08)} 0 {_in(0.14)};}}
.dgrid{{display:grid;grid-template-columns:repeat({cols},1fr);gap:{_in(0.16)} {_in(0.12)};margin-top:{_in(0.08)};}}
.dl{{text-align:center;min-width:0;}}
.dlg{{display:flex;justify-content:center;height:{_in(0.86)};align-items:flex-start;}}
.dln{{font-size:{_in(0.155)};font-weight:700;color:{INK};line-height:1.15;margin-top:{_in(0.02)};
  overflow-wrap:break-word;}}
.dls{{font-family:{FONT_M};font-size:{_in(0.088)};letter-spacing:.08em;color:{SOFT};margin-top:{_in(0.02)};}}
.dmiss{{font-family:{FONT_M};font-size:{_in(0.078)};color:{SOFT};margin-top:{_in(0.06)};}}
.statrow{{display:flex;gap:{_in(0.30)};margin-top:{_in(0.20)};border-top:1px solid {LINE};
  padding-top:{_in(0.14)};}}
.ds{{}}
.dsv{{font-size:{_in(0.26)};font-weight:700;color:{INK};line-height:1;}}
.dsk{{font-family:{FONT_M};font-size:{_in(0.075)};letter-spacing:.07em;color:{PINE};margin-top:{_in(0.03)};}}
.footline{{margin-top:auto;border-top:1px solid {LINE};padding-top:{_in(0.08)};
  display:flex;justify-content:space-between;align-items:flex-end;}}
.brand{{font-size:{_in(0.155)};font-weight:700;color:{INK};}}
.site{{font-family:{FONT_M};font-size:{_in(0.10)};color:{PINE};}}
.eho{{font-size:{_in(0.088)};font-weight:700;letter-spacing:.06em;color:{INK};text-align:right;}}
.agentrow{{display:flex;align-items:center;gap:{_in(0.14)};margin-top:{_in(0.22)};}}
.agentphoto{{width:{_in(0.62)};height:{_in(0.62)};border-radius:50%;object-fit:cover;
  border:2px solid {PAPER};box-shadow:0 2px 8px rgba(16,32,58,.15);flex:0 0 auto;}}
.agentname{{font-size:{_in(0.155)};font-weight:700;color:{INK};line-height:1.2;}}
.agentcontact{{font-family:{FONT_M};font-size:{_in(0.085)};color:{PINE};margin-top:{_in(0.02)};}}
'''
    agent_html = ''
    if agent and (agent.get('name') or agent.get('phone') or agent.get('email')):
        photo = (f'<img class="agentphoto" src="file://{agent["headshot_path"]}" alt="">'
                if agent.get('headshot_path') else '')
        contact_bits = [x for x in (agent.get('phone'), agent.get('email')) if x]
        agent_html = (f'<div class="agentrow">{photo}<div>'
                     f'<div class="agentname">{HT.escape(agent.get("name") or "")}</div>'
                     + (f'<div class="agentcontact">{HT.escape(" &#183; ".join(contact_bits))}</div>'
                        if contact_bits else '')
                     + '</div></div>')
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="canvas">
  <div class="msg">
    <div class="mhd">THE MARKET IN {(_WORDS.get(len(got), str(len(got)))).upper()} NUMBERS</div>
    <div class="mname">{HT.escape(sub)}</div>
    <div class="rule"></div>
    <div class="dgrid">{faces}</div>
    {miss}
    <div class="statrow">{srow}</div>
    {agent_html}
    <div class="footline">
      <div><div class="brand">{BR.NAME}</div><div class="site">{BR.SITE}</div></div>
      <div class="eho">{BR.EHO.upper()}</div>
    </div>
  </div>
  <div class="mail"></div>
</div>
</body></html>'''


def _annotated(canvas_html_body_css, trim_w, trim_h, bleed, safe, mail_w=None, barcode_clear=None):
    """Overlay bleed/trim/safe (and, on side B, the mailing-panel clear zone)
    as red guide lines. INTERNAL REFERENCE ONLY -- never part of the print file."""
    x0, y0 = bleed * DPI, bleed * DPI
    w, h = trim_w * DPI, trim_h * DPI
    sx, sy = safe * DPI, safe * DPI
    svg = (f'<svg width="{PXW}" height="{PXH}" style="position:absolute;left:0;top:0;'
           f'pointer-events:none;z-index:99">'
           f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="red" stroke-width="3"/>'
           f'<rect x="{x0+sx}" y="{y0+sy}" width="{w-2*sx}" height="{h-2*sy}" fill="none" '
           f'stroke="red" stroke-dasharray="10,8" stroke-width="2"/>')
    if mail_w is not None and barcode_clear is not None:
        mx = x0 + (trim_w - mail_w) * DPI
        cy = y0 + h - barcode_clear * DPI
        svg += (f'<line x1="{mx}" y1="{cy}" x2="{x0+w}" y2="{cy}" stroke="red" '
                f'stroke-width="3" stroke-dasharray="4,4"/>'
                f'<text x="{mx+10}" y="{cy-14}" fill="red" font-size="22" '
                f'font-family="monospace">USPS CLEAR ZONE — NOTHING BELOW THIS LINE</text>')
    svg += '</svg>'
    return canvas_html_body_css.replace('</body>', svg + '</body>')


def render(m, sub, city, outdir, scores=None, area=None, place=None, side_a_variant='ALL', agent=None):
    """Writes complete postcard packages: for each front variant, a matching
    {slug}_Postcard_{X}_SideA.png, _SideB.png, _Print.pdf (both sides, exact
    trim+bleed size, no guides -- the actual print-vendor file), and
    _Guides.pdf (bleed/safe/clear-zone lines overlaid, INTERNAL REFERENCE
    ONLY -- never send this one to a print vendor).

    side_a_variant: 'ALL' (default -- produces all three complete packages,
    'A', 'B' and 'C', so an agent can open all three and pick one without
    assembling anything themselves), or a single letter to render just that
    one variant (for scripted use once a preference is known). See
    side_a_html()'s docstring for what each variant is.

    Side B (the mailing side) is identical across all three variants -- same
    dials, same stats, same blank mailing panel -- so it's rendered once and
    reused rather than three times.
    """
    import pathlib
    import shutil
    import tempfile
    from playwright.sync_api import sync_playwright

    place = place or city
    slug = sub.replace(' ', '_')
    variants = ['A', 'B', 'C'] if side_a_variant == 'ALL' else [side_a_variant]
    b_html = side_b_html(m, sub, scores, area, agent)

    out = []
    with tempfile.TemporaryDirectory(prefix='postcard-') as tmp:
        tdir = pathlib.Path(tmp)
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={'width': PXW, 'height': PXH}, device_scale_factor=1)

            # Side B rendered once, reused for every variant package below.
            fb = tdir / 'b.html'; fb.write_text(b_html, encoding='utf-8')
            pg.goto(fb.resolve().as_uri(), wait_until='networkidle')
            pb_master = f'{tdir}/b_master.png'
            pg.locator('div.canvas').screenshot(path=pb_master)
            b_guided = _annotated(b_html, TRIM_W, TRIM_H, BLEED, SAFE,
                                  mail_w=MAIL_W, barcode_clear=BARCODE_CLEAR_IN)
            fbg = tdir / 'b_guide.html'; fbg.write_text(b_guided, encoding='utf-8')
            pg.goto(fbg.resolve().as_uri(), wait_until='networkidle')
            gb_master = f'{tdir}/gb_master.png'
            pg.locator('div.canvas').screenshot(path=gb_master)

            for v in variants:
                tag = f'{slug}_Postcard_{v}' if side_a_variant == 'ALL' else f'{slug}_Postcard'
                a_html = side_a_html(m, sub, place, area, scores, v)

                fa = tdir / f'a_{v}.html'; fa.write_text(a_html, encoding='utf-8')
                pg.goto(fa.resolve().as_uri(), wait_until='networkidle')
                pa = f'{outdir}/{tag}_SideA.png'
                pg.locator('div.canvas').screenshot(path=pa)
                out.append(pa)

                pb = f'{outdir}/{tag}_SideB.png'
                shutil.copy(pb_master, pb)
                out.append(pb)

                # print-ready PDF: both sides, exact canvas size in points, no guides
                print_pdf = f'{outdir}/{tag}_Print.pdf'
                combined = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                           f'@page{{size:{CW}in {CH}in;margin:0;}} body{{margin:0;}}'
                           f'img{{display:block;width:{CW}in;height:{CH}in;'
                           f'page-break-after:always;}}</style></head><body>'
                           f'<img src="file://{pa}"><img src="file://{pb}"></body></html>')
                fc = tdir / f'combined_{v}.html'; fc.write_text(combined, encoding='utf-8')
                pg.goto(fc.resolve().as_uri(), wait_until='networkidle')
                pg.pdf(path=print_pdf, width=f'{CW}in', height=f'{CH}in',
                      print_background=True, margin={'top': '0', 'bottom': '0',
                                                     'left': '0', 'right': '0'})
                out.append(print_pdf)

                # Annotated guide, internal reference only. Screenshot the
                # canvas (with the SVG overlay appended), same method as the
                # side PNGs above -- NEVER pg.pdf() directly on this
                # pixel-authored HTML. page.pdf() lays print pages out at
                # their declared physical size using Chromium's print engine,
                # which does not honour the viewport this page was opened
                # with; a canvas authored in raw CSS pixels at an assumed
                # 300-px-per-inch scale (2775x1950 for this 9.25x6.5in card)
                # gets relaid-out against a viewport sized from the physical
                # page instead, at a different effective scale, and every
                # absolutely-positioned element lands somewhere else
                # entirely. It's silent -- no error, just wrong -- and only
                # shows up as content that appears to overflow a panel that
                # is, in the actual screenshot output, correctly contained.
                # Screenshotting first and wrapping the bitmap in a simple
                # img-sized-in-inches page (the same pattern Print.pdf above
                # already uses) sidesteps the mismatch entirely, because
                # stretching one image to a declared physical box does not
                # depend on Chromium's print-layout viewport.
                a_guided = _annotated(a_html, TRIM_W, TRIM_H, BLEED, SAFE)
                fag = tdir / f'a_guide_{v}.html'; fag.write_text(a_guided, encoding='utf-8')
                ga_png = f'{tdir}/ga_{v}.png'
                pg.goto(fag.resolve().as_uri(), wait_until='networkidle')
                pg.locator('div.canvas').screenshot(path=ga_png)

                gp = f'{outdir}/{tag}_Guides.pdf'
                guide_combined = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                                 f'@page{{size:{CW}in {CH}in;margin:0;}} body{{margin:0;}}'
                                 f'img{{display:block;width:{CW}in;height:{CH}in;'
                                 f'page-break-after:always;}}</style></head><body>'
                                 f'<img src="file://{ga_png}"><img src="file://{gb_master}"></body></html>')
                fgc = tdir / f'guide_combined_{v}.html'; fgc.write_text(guide_combined, encoding='utf-8')
                pg.goto(fgc.resolve().as_uri(), wait_until='networkidle')
                pg.pdf(path=gp, width=f'{CW}in', height=f'{CH}in',
                      print_background=True, margin={'top': '0', 'bottom': '0',
                                                     'left': '0', 'right': '0'})
                out.append(gp)

            br.close()

    return out
