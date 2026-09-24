"""Canonical dial names, geographies and the gauge renderer.

ONE SOURCE OF TRUTH for what the five indexes are called. Both subdivision-brief
and market-brief-salesrep import from here, and the carousel, the PDF brief and
any marketing artifact read the same names. Renaming a dial is a one-line change
in DIALS, not a grep across two skills.

NAMING HISTORY -- read before renaming anything again
-----------------------------------------------------
`balance` was shipped on the PDF as "Market Balance", then this carousel briefly
called it "Supply Pressure" (never shipped -- caught before print: the
arithmetic is 100*(1 - MOI/9), so a HIGH score means supply is SCARCE, and
"Supply Pressure 79" reads as heavy pressure from abundant supply, the exact
inverse), then "Inventory Tightness" as a distinct carousel-only name. It is
now "Market Balance" again everywhere, by explicit decision: the PDF and the
carousel had drifted into naming the same score two different things with
nothing telling a reader they were the same metric (see SKILL.md rule 58).
`chance` had the identical problem -- "Sale Odds" on the carousel, "Chance of
Selling" on the PDF -- resolved the same way, to "Chance of Selling"
everywhere. The internal keys (`balance`, `chance`) never change regardless of
label, so no stored output or downstream helper breaks.

`power` went to "Price Leverage" briefly, then back to "Pricing Power" --
the PDF's original name -- on a second look. All three subdivision-scoped
dials now match the PDF's own long-established names (Chance of Selling,
Pricing Power, Market Balance); the carousel and postcard were the side that
moved in every case. Which artifact's name wins is a per-score editorial
call, not a fixed rule, but in practice the PDF's names have won all three
times now that all three have actually been decided.

`rent_yield` is Rent to Price. Not "Rent Return", not "Cash Flow", not "Income
Potential": the arithmetic is GROSS annual rent over home value, with no taxes,
insurance, HOA, vacancy or management deducted. Any name implying money in pocket
promises a net figure the formula does not compute.

SCOPE IS NOT DECORATION
-----------------------
Every dial carries the geography it was computed at, and it prints on the face.
Three of the five are subdivision-scoped from the MLS export; two are area-level
and come from ZIP/county reference data. A ZIP-level number under a subdivision
heading is the failure this field exists to prevent.

DIRECTION
---------
Every dial is 0-100 and higher is better for the subdivision, with one caveat
worth stating in prose wherever it appears: "better" for Market Balance
means scarcer supply, which favours sellers and disadvantages buyers. The dial
does not take a side; the copy around it should say which side it helps.
"""
import math

# key -> (label, scope tag, plain-language question, source of the input)
DIALS = {
    'chance':  ('Chance of Selling',   'SUBDIVISION',  'Will a listing here actually sell?',   'mls'),
    'power':   ('Pricing Power',       'SUBDIVISION',  'Who holds the pricing power?',         'mls'),
    'balance': ('Market Balance',      'SUBDIVISION',  'How tight is the standing inventory?', 'mls'),
    'rent':    ('Rent to Price',       'ZIP',          'What does the rent side support?',     'zillow'),
    'growth':  ('Growth Outlook',      'ZIP / COUNTY', 'What does the long run look like?',    'area'),
}
ORDER = ['chance', 'power', 'balance', 'rent', 'growth']

INK = '#10203A'
PINE = '#1F4B87'
TRACK = '#E7EFF8'
ACCENT = '#E0A800'
SOFT = '#56657A'


def label(key):
    return DIALS[key][0]


def scope(key, area=None):
    """The geography tag for a dial face. Area-level dials take their real
    resolved geography when one is supplied, so a Jefferson County figure says
    Jefferson County rather than a generic 'ZIP / COUNTY'."""
    tag = DIALS[key][1]
    if area and key in ('rent', 'growth'):
        got = area.get(f'{key}_scope')
        if got:
            return got.upper()
    return tag


def present(scores, area=None):
    """The dials that actually have a value, in canonical order.

    A dial with no value is OMITTED, never rendered as zero and never filled
    with a state average. Roughly seven Colorado ZIPs in ten have no ZORI rent
    series at all, so a missing Rent to Price is the common case, not an error
    -- the layout has to look deliberate with three dials as well as five.
    """
    out = []
    for k in ORDER:
        v = (scores or {}).get(k)
        if v is None and area:
            v = area.get(k)
        if v is not None:
            out.append((k, int(round(v))))
    return out


def verdict(v, hi='Strong', mid='Moderate', lo='Limited'):
    """Same 34/67 tiering as the PDF's own verdict() (master.py), duplicated
    here rather than imported so the carousel and postcard never need to pull
    in master.py's much heavier PDF-building dependencies just for this. Keep
    the thresholds in sync if either ever changes -- there is no single
    shared source for this specific piece of logic."""
    return hi if v >= 67 else (mid if v >= 34 else lo)


def gauge(value, size=200, stroke=20, font=None, verdict=None):
    """Half-circle gauge, 0-100, sweeping left to right.

    large-arc-flag is ALWAYS 0. Every segment of a 180-degree gauge is a minor
    arc; deriving the flag from the fraction (as the older chart helpers did)
    makes Chromium draw the major arc for any value above 50, and the fill wraps
    around underneath the dial. The full-width track is split at its midpoint
    because an arc whose endpoints are diametrically opposed is ambiguous.

    verdict: an optional word/short phrase rendered as a third line below the
    0-100 label -- e.g. "Seller-leaning" for Market Balance, matching the
    word the PDF dashboard already prints under that same dial (master.py's
    dial()). Added specifically because the carousel and postcard showed a
    bare number for Market Balance with no cue which side a high score
    favors, unlike the PDF; see SKILL.md rule 70. Passing verdict makes the
    gauge taller (0.84x size instead of 0.70x) to fit the extra line without
    clipping it -- verified by rendering at each call site's actual size, not
    assumed from the arithmetic alone.
    """
    font = font or '"Poppins","Liberation Sans",sans-serif'
    cx, cy, r = size / 2, size / 2 + 14, size / 2 - stroke / 2 - 2
    frac = max(0.0, min((value or 0) / 100.0, 1.0))

    def pt(f, rr):
        a = math.pi * (1 - f)
        return cx + rr * math.cos(a), cy - rr * math.sin(a)

    def arc(f0, f1, col, wd):
        segs = [(f0, f1)]
        if f1 - f0 > 0.499:
            mid = (f0 + f1) / 2
            segs = [(f0, mid), (mid, f1)]
        s = ''
        for a0, a1 in segs:
            x0, y0 = pt(a0, r)
            x1, y1 = pt(a1, r)
            s += (f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}" '
                  f'fill="none" stroke="{col}" stroke-width="{wd}" stroke-linecap="round"/>')
        return s

    h = size * (0.84 if verdict else 0.70)
    s = f'<svg viewBox="0 0 {size} {h:.0f}" width="{size}" height="{h:.0f}">'
    s += arc(0, 1, TRACK, stroke)
    if frac > 0.004:
        s += arc(0, frac, PINE, stroke)
    tx, ty = pt(frac, r)
    s += (f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{stroke / 2 + 3:.1f}" fill="#fff" '
          f'stroke="{ACCENT}" stroke-width="4"/>')
    s += (f'<text x="{cx}" y="{cy - 14}" font-size="{size * 0.25:.0f}" font-weight="700" '
          f'fill="{INK}" text-anchor="middle" font-family=\'{font}\'>{int(round(value))}</text>')
    s += (f'<text x="{cx}" y="{cy + 8}" font-size="{size * 0.065:.0f}" fill="{SOFT}" '
          f'letter-spacing="1.6" text-anchor="middle" font-family=\'{font}\'>0&#8211;100</text>')
    if verdict:
        s += (f'<text x="{cx}" y="{cy + 8 + size * 0.13:.0f}" font-size="{size * 0.078:.0f}" '
              f'font-weight="600" fill="{PINE}" text-anchor="middle" '
              f'font-family=\'{font}\'>{verdict}</text>')
    return s + '</svg>'
