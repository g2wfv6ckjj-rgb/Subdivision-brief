"""Talking-point selection.

WHY THIS EXISTS
---------------
Rule 11 already forbids a fixed sentence with a number interpolated into it, and
`core.py` satisfies that: `offer_point`, `seller_price_point`, `adjust_point`,
`escrow_point`, `leverage_point` and `cash_point` all branch on the metrics.

But the *list* was still fixed. Every brief printed the same five seller topics
and the same five buyer topics in the same order, whether or not those were the
five things worth saying about that subdivision. A neighborhood where credits are
rare still got a credits bullet; one where a fifth of listings never sold did not
get a bullet about it, because there was no slot for one.

So the topics are selected the same way the call-outs are: every test below runs
against the export, returns nothing when its subject is unremarkable there, and
returns a ranked point when it is. A quiet subdivision produces four bullets per
side; a distinctive one produces six, on different subjects.

NOTABILITY IS NORMALIZED
------------------------
Each test returns `rank` on a common 0-100 scale, so a ratio-based test cannot
crowd out a share-based one just because ratios produce bigger raw numbers. Use
`_scale()` for anything new. Ranking on raw magnitudes is the bug this avoids.

Every text is either produced by a branching helper in `core.py` or is a plain
statement of counts drawn straight from the export. Nothing here characterizes
the market in a fixed sentence.
"""
import pandas as pd

from core import (M, Mshort, dur, offer_point, seller_price_point, adjust_point,
                  escrow_point, leverage_point, cash_point, rightpriced_point,
                  moi_label)

PER_SIDE = 6
FLOOR = 18          # below this a point is not worth a slot


def _scale(value, quiet, loud):
    """Map a raw signal onto 0-100. `quiet` scores 0, `loud` scores 100."""
    if value != value:
        return 0.0
    if loud == quiet:
        return 0.0
    x = (value - quiet) / (loud - quiet)
    return max(0.0, min(100.0, x * 100))


def _q(text):
    return text


# ================================================================ seller tests
def _s_price(d, m, cl, ctx):
    """What sellers got against the first number published."""
    n, at = m['n_cl'], m['at_or_above']
    if n < 8:
        return None
    return dict(key='price', aud='seller', text=seller_price_point(m),
                pin=True,
                rank=max(_scale(abs(m['cpo'] - 100), 0.4, 6.0),
                         _scale(abs(at / n * 100 - 50), 8, 45)))


def _s_twoweek(d, m, cl, ctx):
    if m['n_cl'] < 12:
        return None
    share = 100 * m['fast14'] / m['n_cl']
    return dict(key='twoweek', aud='seller',
                text=(f'{m["fast14"]} of {m["n_cl"]} went under contract within two weeks. '
                      f'If we are still sitting at day fourteen, the market is telling us '
                      f'something.'),
                rank=_scale(abs(share - 40), 6, 45))


def _s_adjust(d, m, cl, ctx):
    a, b = m['ttl_nored'], m['ttl_red']
    if m['no_change'] < 5 or m['changed'] < 5 or a != a or b != b or min(a, b) <= 0:
        return None
    return dict(key='adjust', aud='seller', text=adjust_point(m),
                rank=_scale(max(a, b) / min(a, b), 1.15, 3.5))


def _s_credits(d, m, cl, ctx):
    if not m['n_cl']:
        return None
    share = 100 * m['conc_n'] / m['n_cl']
    if share < 8:
        return dict(key='credits', aud='seller',
                    text=(f'Only {m["conc_n"]} of {m["n_cl"]} sales included a credit to the '
                          f'buyer. A credit is not the default here, so it is worth holding '
                          f'as a concession rather than opening with it.'),
                    rank=_scale(30 - share, 4, 30))
    return dict(key='credits', aud='seller',
                text=(f'{m["conc_n"]} of {m["n_cl"]} sales included a credit to the buyer, a '
                      f'median of {M(m["conc_med"])}. Let us build that into the net sheet now '
                      f'rather than negotiate it at day sixty.'),
                rank=_scale(share, 12, 65))


def _s_escrow(d, m, cl, ctx):
    if m['n_cl'] < 8 or m['ptc_med'] != m['ptc_med']:
        return None
    spread = (m['ptc_max'] - m['ptc_min']) / max(m['ptc_med'], 1)
    return dict(key='escrow', aud='seller', text=escrow_point(m),
                rank=_scale(spread, 0.5, 2.6))


def _s_failed(d, m, cl, ctx):
    resolved = m['n_cl'] + m['n_fail']
    if resolved < 25:
        return None
    share = 100 * m['n_fail'] / resolved
    return dict(key='failed', aud='seller',
                text=(f'{m["n_fail"]} of the {resolved} listings that reached an outcome here '
                      f'came off the market without selling &mdash; {share:.0f}%. Coming to '
                      f'market and selling are two different things, and the gap between them '
                      f'is the opening price.'),
                rank=_scale(share, 6, 30))


def _s_relist(d, m, cl, ctx):
    rep = ctx.get('repeats', 0)
    if len(d) < 30 or rep < 4:
        return None
    return dict(key='relist', aud='seller',
                text=(f'{rep} addresses in this export came to market more than once inside '
                      f'twelve months. A relisting resets the days-on-market clock but not '
                      f'what buyers have already seen.'),
                rank=_scale(100 * rep / len(d), 3, 22))


def _s_supply(d, m, cl, ctx):
    if m['moi'] != m['moi'] or m['n_act'] < 3:
        return None
    return dict(key='supply', aud='seller',
                text=(f'There are {m["n_act"]} homes for sale against the recent pace of sales '
                      f'&mdash; {m["moi"]:.1f} months of supply, which the standard scale calls '
                      f'{moi_label(m["moi"]).lower()}. The median asking price among them is '
                      f'{M(m["act_med_list"])}, and that is the field a new listing joins.'),
                rank=_scale(abs(m['moi'] - 4.5), 0.6, 4.0))


def _s_cash(d, m, cl, ctx):
    pt = cash_point(m, 'seller')
    if not pt or m['n_fin_known'] < 12:
        return None
    return dict(key='cash', aud='seller', text=pt,
                rank=_scale(abs(m['cash_pct'] - 12), 4, 30))


# ================================================================= buyer tests
def _b_speed(d, m, cl, ctx):
    if m['n_cl'] < 12:
        return None
    share = 100 * m['fast'] / m['n_cl']
    return dict(key='speed', aud='buyer',
                text=(f'{m["fast"]} of the {m["n_cl"]} sales went under contract within a week '
                      f'of listing and {m["fast14"]} within two weeks; the median was '
                      f'{m["dtc_med"]:.0f} days. {m["n_fail"]} listings never sold at all.'),
                rank=_scale(abs(share - 25), 5, 40))


def _b_offer(d, m, cl, ctx):
    if m['n_cl'] < 8:
        return None
    return dict(key='offer', aud='buyer', text=offer_point(m), pin=True,
                rank=_scale(abs(100 * m['under_orig'] / m['n_cl'] - 50), 8, 45))


def _b_leverage(d, m, cl, ctx):
    pt = leverage_point(m)
    if not pt or m['n_cl'] < 10:
        return None
    return dict(key='leverage', aud='buyer', text=pt,
                rank=_scale(m['disc_orig'], 0.6, 7.0))


def _b_credits(d, m, cl, ctx):
    if not m['n_cl'] or m['conc_n'] < 3:
        return None
    share = 100 * m['conc_n'] / m['n_cl']
    return dict(key='credits', aud='buyer',
                text=(f'{m["conc_n"]} of {m["n_cl"]} sellers paid a credit, a median of '
                      f'{M(m["conc_med"])}. That is a term worth asking for here, and it can be '
                      f'worth more than the same money off the price.'),
                rank=_scale(share, 10, 62))


def _b_cash(d, m, cl, ctx):
    pt = cash_point(m, 'buyer')
    if not pt or m['n_fin_known'] < 12:
        return None
    return dict(key='cash', aud='buyer', text=pt,
                rank=_scale(abs(m['cash_pct'] - 12), 4, 30))


def _b_band(d, m, cl, ctx):
    """Where the room actually is, by price band. Reads the bands, never assumes
    the top band is the soft one."""
    bd = ctx.get('bands')
    if bd is None or len(bd) < 3 or m['n_cl'] < 18:
        return None
    lo = bd.loc[bd['cpo'].idxmin()]
    hi = bd.loc[bd['cpo'].idxmax()]
    gap = hi['cpo'] - lo['cpo']
    if gap < 1.2:
        return None
    return dict(key='band', aud='buyer',
                text=(f'The room is not spread evenly. Homes in the {lo["band"]} band closed at '
                      f'an average {lo["cpo"]:.1f}% of their original asking price across '
                      f'{int(lo["n"])} sales, against {hi["cpo"]:.1f}% in the {hi["band"]} band. '
                      f'Which band a home sits in matters more than the list price itself.'),
                rank=_scale(gap, 1.2, 7.0))


def _b_escrow(d, m, cl, ctx):
    if m['n_cl'] < 8 or m['ptc_med'] != m['ptc_med']:
        return None
    return dict(key='escrow', aud='buyer', text=escrow_point(m),
                rank=_scale((m['ptc_max'] - m['ptc_min']) / max(m['ptc_med'], 1), 0.5, 2.6))


def _b_supply(d, m, cl, ctx):
    if m['moi'] != m['moi'] or m['n_act'] < 3:
        return None
    return dict(key='supply', aud='buyer',
                text=(f'{m["n_act"]} homes are for sale right now, {m["moi"]:.1f} months of '
                      f'supply at the recent pace. Median asking price among them is '
                      f'{M(m["act_med_list"])}. That is the whole field to choose from today.'),
                rank=_scale(abs(m['moi'] - 4.5), 0.6, 4.0))


def _b_fresh(d, m, cl, ctx):
    pt = rightpriced_point(m, 'buyer')
    if not pt or m['rp_n'] < 8 or m['rp_cut_n'] < 8:
        return None
    a, b = m['rp_med'], m['rp_cut_med']
    if a != a or b != b or min(a, b) <= 0:
        return None
    return dict(key='fresh', aud='buyer',
                text=(f'A fresh listing and a stale one are different negotiations. Homes that '
                      f'never reduced went under contract in a median of {a:.0f} days; the ones '
                      f'that reduced took {b:.0f}. Days on market is the single best signal of '
                      f'which conversation you are in.'),
                rank=_scale(max(a, b) / min(a, b), 1.4, 8.0))


SELLER_TESTS = [_s_price, _s_twoweek, _s_adjust, _s_credits, _s_escrow,
                _s_failed, _s_relist, _s_supply, _s_cash]
BUYER_TESTS = [_b_speed, _b_offer, _b_leverage, _b_credits, _b_cash,
               _b_band, _b_escrow, _b_supply, _b_fresh]


def _context(d, m, cl, bands=None):
    ctx = {'bands': bands}
    ctx['repeats'] = int((d['addr'].value_counts() > 1).sum()) if 'addr' in d else 0
    return ctx


def pick(d, m, cl, bands=None, per_side=PER_SIDE, floor=FLOOR):
    """(seller_points, buyer_points), strongest signal first.

    Returns fewer than `per_side` when fewer subjects clear the floor. That is the
    intended behaviour: a thin bullet is worse than no bullet in a listing
    appointment, because it is the one the client will push on.

    Points carrying `pin` lead the list regardless of rank -- see the note in the
    loop below.
    """
    ctx = _context(d, m, cl, bands)
    out = {}
    for aud, tests in (('seller', SELLER_TESTS), ('buyer', BUYER_TESTS)):
        found = [p for p in (t(d, m, cl, ctx) for t in tests) if p]
        # Pinned subjects lead regardless of rank. What the seller gets against the
        # first asking price, and what buyers actually paid against it, are the
        # subject of the meeting -- a brief that drops them because the spread was
        # unremarkable has answered a question nobody asked.
        pinned = [p for p in found if p.get('pin')]
        rest = [p for p in found if not p.get('pin') and p['rank'] >= floor]
        rest.sort(key=lambda p: -p['rank'])
        out[aud] = pinned + rest[:max(0, per_side - len(pinned))]
    return out['seller'], out['buyer']
