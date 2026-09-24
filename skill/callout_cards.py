"""Standalone 1080x1080 social callout cards.

DIFFERENT ARTIFACT FROM THE CAROUSEL
------------------------------------
`carousel.py` produces six slides read in sequence, so broker identification and
Equal Housing Opportunity live once on the final slide. These cards are single
posts. Each one travels alone, gets screenshotted alone, and therefore carries
its own broker line and EHO mark. Never strip that footer to buy layout room.

WHICH CARDS RENDER IS DECIDED BY THE DATA
-----------------------------------------
Same pattern as `core._CO_TESTS`: every test below runs against the export and
returns a card only when it clears a notability threshold AND has enough
observations behind it to be worth publishing. A quiet subdivision produces two
cards; a distinctive one produces five. Nothing here is a fixed claim with a
number dropped into it -- each test states which direction it found and words
itself accordingly, so a subdivision behaving the opposite way prints the
opposite headline rather than a false one.

Whole-year figures only, for the same reason as rule 24: a card is the most
reshared thing the skill makes and has to stay true months later.

Public-copy constraints are identical to rule 19: price, timing, inventory and
process facts only. No school content, no characterization of the neighborhood
or who lives there, no audience-targeting language, place-based hashtags only.
"""
import html as HT
import pathlib
import tempfile

import pandas as pd

import brand as BR
from core import M, Mshort, dur
import carousel as CR

S = CR.S
INK, PINE, SAGE = CR.INK, CR.PINE, CR.SAGE
BRONZE, GOLD, SOFT = CR.BRONZE, CR.GOLD, CR.SOFT
CARD, LINE, MIST = CR.CARD, CR.LINE, CR.MIST

MIN_OBS = 8          # per side of any two-group comparison
MAX_CARDS = 5
FLOOR = 20           # notability below this is not worth a post


def _scale(value, quiet, loud):
    """Map a raw signal onto 0-100 so tests rank against each other fairly.

    Ranking on raw magnitudes was a bug: a ratio test producing 196 buried a share
    test producing 34 regardless of which was actually the more unusual fact about
    the neighborhood. Every test returns `rank` through this.
    """
    if value != value or loud == quiet:
        return 0.0
    return max(0.0, min(100.0, (value - quiet) / (loud - quiet) * 100))


# ------------------------------------------------------------------ the tests
def _t_sellthrough(d, m, cl):
    """Did reducing the price change the odds of selling at all, either way?"""
    st = d['Mls Status'].astype(str).str.strip().str.lower()
    fail = st.isin(['expired', 'withdrawn', 'canceled', 'cancelled'])
    closed = st == 'closed'
    nr = ~d['red']
    a_c, a_f = int((closed & nr).sum()), int((fail & nr).sum())
    b_c, b_f = int((closed & ~nr).sum()), int((fail & ~nr).sum())
    if a_c + a_f < MIN_OBS or b_c + b_f < MIN_OBS:
        return None
    a = 100 * a_c / (a_c + a_f)
    b = 100 * b_c / (b_c + b_f)
    if abs(a - b) < 12:
        return None
    hi, lo = (a, b) if a > b else (b, a)
    if a > b:
        head = 'Priced right, it sold'
        sup = (f'{a:.0f}% of the listings that never reduced went on to close. '
               f'Of the ones that did reduce, {b:.0f}% did.')
    else:
        head = 'A reduction moved these homes'
        sup = (f'{b:.0f}% of the listings that reduced went on to close, against '
               f'{a:.0f}% of the ones that never did.')
    return dict(key='sellthrough', eyebrow='Chance of selling',
                big=f'{hi:.0f}%', unit='vs ' + f'{lo:.0f}%',
                head=head, sup=sup, accent=PINE,
                foot='Sell-through is closings divided by closings plus expired, withdrawn '
                     'and canceled listings. Listings still active or under contract are '
                     'excluded from both sides, because their outcome is not yet known.',
                rank=_scale(abs(a - b), 12, 45))


def _t_speed(d, m, cl):
    """Days to an accepted offer, priced right versus reduced."""
    a, b = m['rp_med'], m['rp_cut_med']
    if m['rp_n'] < MIN_OBS or m['rp_cut_n'] < MIN_OBS:
        return None
    if a != a or b != b or a <= 0 or b <= 0:
        return None
    if max(a, b) / max(min(a, b), 1) < 2:
        return None
    faster = 'never reduced' if a < b else 'reduced'
    return dict(key='speed', eyebrow='How long it took',
                big=f'{min(a, b):.0f}', unit=f'days vs {max(a, b):.0f}',
                head='The first price is what buys speed',
                sup=(f'Homes that {faster} went under contract in a median of '
                     f'{min(a, b):.0f} days. The other group took {max(a, b):.0f}.'),
                accent=PINE,
                foot=f'Median days from listing to accepted offer. {m["rp_n"]} listings never '
                     f'reduced; {m["rp_cut_n"]} did. Both groups found buyers &mdash; the '
                     f'difference was time.',
                rank=_scale(max(a, b) / max(min(a, b), 1), 2, 12))


def _t_notsold(d, m, cl):
    """Coming to market is not the same as selling.

    Denominator is RESOLVED listings only -- closed plus failed. Actives and
    pendings have no outcome yet, and counting them below the line understates
    the failure rate while counting them above it would be plainly wrong.
    """
    resolved = m['n_cl'] + m['n_fail']
    share = 100 * m['n_fail'] / resolved if resolved else 0
    if resolved < 30 or share < 10:
        return None
    return dict(key='notsold', eyebrow='Not every listing sells',
                big=f'{m["n_fail"]}', unit=f'of {resolved} that resolved',
                head='They came off the market without selling',
                sup=(f'{share:.0f}% of the listings that reached an outcome in the last '
                     f'twelve months expired or were withdrawn rather than closing.'),
                accent=BRONZE,
                foot=f'Counted across every listing in the export that reached an outcome: '
                     f'{m["n_cl"]} closed and {m["n_fail"]} expired or withdrawn. The '
                     f'{m["n_act"]} still active and {m["n_pend"]} under contract are excluded, '
                     f'because their outcome is not yet known.',
                rank=_scale(share, 10, 32))


def _t_credits(d, m, cl):
    """Seller credits, in whichever direction they run."""
    if not m['n_cl']:
        return None
    share = 100 * m['conc_n'] / m['n_cl']
    if 12 < share < 35:
        return None
    if share >= 35:
        head = 'A credit is part of the deal here'
        sup = (f'{m["conc_n"]} of {m["n_cl"]} sales included money from the seller toward '
               f'the buyer&rsquo;s costs, a median of {M(m["conc_med"])} where one was paid.')
    else:
        head = 'Credits are the exception here'
        sup = (f'Only {m["conc_n"]} of {m["n_cl"]} sales included a credit from the seller.')
    return dict(key='credits', eyebrow='Seller credits',
                big=f'{m["conc_n"]}', unit=f'of {m["n_cl"]} sales',
                head=head, sup=sup, accent=BRONZE if share >= 35 else PINE,
                foot='A credit goes toward the buyer&rsquo;s closing costs or a rate buy-down. '
                     'It comes off the seller&rsquo;s proceeds, so it belongs in the net sheet '
                     'from the start.',
                rank=_scale(abs(share - 25), 10, 45))


def _t_relist(d, m, cl):
    """Addresses that came to market more than once inside the window."""
    if 'addr' not in d:
        return None
    vc = d['addr'].value_counts()
    rep = int((vc > 1).sum())
    if len(d) < 30 or rep < 5:
        return None
    return dict(key='relist', eyebrow='Second and third tries',
                big=f'{rep}', unit='addresses',
                head='Some homes came to market more than once',
                sup=(f'{rep} addresses in this export appear more than once inside the same '
                     f'twelve months.'),
                accent=BRONZE,
                foot='Counted on street address within the export window. A relisting resets '
                     'the days-on-market clock but not what buyers have already seen.',
                rank=_scale(100 * rep / len(d), 3, 22))


def _t_fast(d, m, cl):
    """How much of the market moves in the first week."""
    if not m['n_cl']:
        return None
    share = 100 * m['fast'] / m['n_cl']
    if m['n_cl'] < 20 or share < 30:
        return None
    return dict(key='fast', eyebrow='The first week matters',
                big=f'{m["fast"]}', unit=f'of {m["n_cl"]} sales',
                head='Under contract inside seven days',
                sup=(f'{share:.0f}% of the homes that sold had an accepted offer within a '
                     f'week of coming to market. The median was {m["dtc_med"]:.0f} days.'),
                accent=PINE,
                foot='Measured from the listing date to the accepted-offer date on closed '
                     'sales only.',
                rank=_scale(abs(share - 25), 5, 42))


TESTS = [_t_sellthrough, _t_speed, _t_notsold, _t_credits, _t_relist, _t_fast]


def pick(d, m, cl, limit=MAX_CARDS, floor=FLOOR):
    """Every test that clears its threshold, most unusual fact first.

    Returns fewer than `limit` when fewer subjects clear the floor. A weak card is
    worse than no card: it is the one that gets challenged in the comments.
    """
    out = [c for c in (t(d, m, cl) for t in TESTS) if c and c['rank'] >= floor]
    out.sort(key=lambda c: -c['rank'])
    return out[:limit]


# ------------------------------------------------------------------- rendering
EXTRA_CSS = f'''
.cocap{{position:absolute;left:0;right:0;top:0;height:14px;background:{{ACCENT}};}}
.cohead{{font-family:{CR.FONT_H};font-size:62px;line-height:1.05;font-weight:700;
  letter-spacing:-.02em;margin:14px 0 24px;}}
.cobig{{font-family:{CR.FONT_H};font-size:210px;font-weight:700;line-height:.9;
  letter-spacing:-.045em;}}
.counit{{font-family:{CR.FONT_M};font-size:26px;letter-spacing:.1em;text-transform:uppercase;
  color:{SOFT};margin-top:16px;}}
.cosup{{font-family:{CR.FONT_B};font-size:34px;line-height:1.42;color:#26384F;margin-top:36px;}}
.cofoot{{font-family:{CR.FONT_M};font-size:18px;line-height:1.62;color:{SOFT};
  border-top:3px solid {LINE};padding-top:24px;margin-top:auto;}}
.cosign{{margin-top:22px;text-align:center;}}
.cobrok{{font-family:{CR.FONT_M};font-size:22px;letter-spacing:.06em;color:{CR.PINE};
  margin-top:14px;}}
.coeho{{font-family:{CR.FONT_M};font-size:17px;color:{SOFT};margin-top:6px;}}
'''


def card_html(c, sub, place):
    accent = c['accent']
    return CR._slide(
        f'''<div class="cocap" style="background:{accent};"></div>
<div class="pad">
{CR._eyebrow(c['eyebrow'], accent)}
<h2 class="cohead" style="color:{INK};">{c['head']}</h2>
<div class="cobig" style="color:{accent};">{c['big']}</div>
<div class="counit">{c['unit']}</div>
<div class="cosup">{c['sup']}</div>
<div class="cofoot">{HT.escape(sub)}, {HT.escape(place)} &nbsp;&#183;&nbsp; 365-day MLS export.
{c['foot']} Information deemed reliable but not guaranteed.
<div class="cosign">{BR.logo_img(52)}
<div class="cobrok">{' &nbsp;&#183;&nbsp; '.join(BR.signoff_lines())}</div>
<div class="coeho">{BR.EHO}</div></div>
</div>
</div>''')


def captions(cards, sub, city):
    """A ready-to-paste caption per card. Place-based hashtags only."""
    place = city.split(',')[0].strip()
    tag = ''.join(w for w in sub.title().split())
    out = []
    for c in cards:
        out.append(dict(
            key=c['key'],
            text=(f'{c["sup"]} That is from the last twelve months of sales in {sub}, '
                  f'{city}.\n\nComment BRIEF and I will send you the full breakdown '
                  f'&mdash; every sale, what it listed for, what it closed for, and how '
                  f'long it took.\n\n#{tag} #{place.replace(" ", "")} #RealEstateMarketUpdate'),
        ))
    return out


def render(d, m, cl, sub, city, outdir, limit=MAX_CARDS):
    from playwright.sync_api import sync_playwright
    cards = pick(d, m, cl, limit)
    if not cards:
        return [], []
    place = CR.MK._place(city)
    slug = sub.replace(' ', '_')
    written = []
    with tempfile.TemporaryDirectory(prefix='callouts-') as tmp:
        tdir = pathlib.Path(tmp)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={'width': S, 'height': S}, device_scale_factor=1)
            for i, c in enumerate(cards, 1):
                one = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                       f'{CR.CSS}{EXTRA_CSS} body{{background:#fff;}} .sl{{margin:0;}}'
                       f'</style></head><body>{card_html(c, sub, place)}</body></html>')
                fp = tdir / f'{i}.html'
                fp.write_text(one, encoding='utf-8')
                pg.goto(fp.resolve().as_uri(), wait_until='networkidle')
                out = f'{outdir}/{slug}_Callout_{i}_{c["key"]}.png'
                pg.locator('section.sl').screenshot(path=out)
                written.append(out)
            b.close()
    return written, captions(cards, sub, city)
