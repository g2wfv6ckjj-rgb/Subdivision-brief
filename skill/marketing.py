"""Digital Marketing Strategies section — social copy, reel scripts and a newsletter
draft, generated from the live metric dictionary for one subdivision.

EVERYTHING HERE IS GENERATED, NEVER TEMPLATED PROSE WITH A NUMBER DROPPED IN.
That distinction is the whole point of the module. A fixed caption like "homes are
flying off the shelf in {sub}!" stays grammatical while becoming false the moment a
subdivision behaves differently, and marketing copy is the artifact most likely to
be published without anyone re-reading the underlying report. So every claim below
is chosen by branching on the metrics: core.monthly_standouts() ranks what actually
moved month over month, and the hooks/CTAs are selected from the direction of that
movement rather than assumed.

THREE CONSTRAINTS THAT MUST NOT BE RELAXED
------------------------------------------
1. FAIR HOUSING. This is public-facing copy, which makes it the highest-risk
   surface in the whole report. Nothing here may characterize a neighborhood or
   the people in it, name or imply a protected class, reference schools, or use
   audience-targeting language ("perfect for young families", "safe", "up and
   coming", "great neighborhood"). Copy stays on price, timing, inventory and
   process facts only. SCHOOL CONTENT IS EXCLUDED DELIBERATELY even though the
   report carries a schools section -- school quality is a well-established
   steering vector and has no place in social copy.
2. SMALL SAMPLES. A month-specific claim published to the public needs enough
   closings behind it to survive being quoted back. MIN_MONTH_CLOSINGS gates
   month-over-month claims; below it the copy falls back to whole-year figures
   and says so, rather than announcing a 50% swing that is two houses.
3. NO COMPENSATION OR STEERING LANGUAGE. Copy never discusses commission or
   cooperative compensation (antitrust), never promises a result, and never
   implies pre-qualification. Rate figures are attributed and dated.

SEO / AI-SEARCH NOTES
---------------------
Copy is written to be retrievable by both classic search and answer engines:
the subdivision name, city and state appear together in the first line; the copy
answers a specific question a person would actually type or ask aloud; concrete
numerals and dates are used rather than vague adjectives, because extractive
models quote figures; and each piece carries a self-contained factual claim that
survives being lifted out of context. Hashtags are place-based, never
audience-based.
"""
import html as HT
from core import (M, Mshort, dur, monthly_standouts, cash_point, moi_label)

# A month-specific public claim needs at least this many closings behind it.
# At subdivision scale a month often holds one or two sales, where a "+50% month"
# is one house. Below the threshold the copy uses whole-year figures instead.
MIN_MONTH_CLOSINGS = 5

BANNED = [  # never emit these; kept visible so the rule is auditable
    'family', 'families', 'safe', 'safest', 'good schools', 'great schools',
    'up and coming', 'exclusive', 'prestigious', 'desirable neighborhood',
]


def _dirword(key, pct):
    """Plain direction language for a metric, correct for metrics where down is
    the favourable direction (days on market, months of supply)."""
    up = pct > 0
    if key == 'med_dom':
        return 'took longer to sell' if up else 'sold faster'
    if key == 'msi':
        return 'has more supply' if up else 'has less supply'
    if key == 'med_close':
        return 'rose' if up else 'eased'
    return 'increased' if up else 'decreased'


def _standout_line(s):
    """One neutral factual sentence about a month-over-month move."""
    return (f'{s["label"].capitalize()} {_dirword(s["key"], s["pct"])} '
            f'{abs(s["pct"]):.0f}% from {s["prev_m"]} to {s["cur_m"]}, '
            f'{s["prev"]} to {s["cur"]}.')


def _month_ok(mo_build, m):
    """Whether month-specific claims are publishable. Requires both a computable
    month-over-month series and enough closings in the latest month."""
    if not mo_build:
        return False, 0
    import monthly as MO
    closed = mo_build['series_ext']['closed'][MO.ALL]
    last = 0
    for v in reversed(closed):
        if v == v:
            last = int(v)
            break
    return last >= MIN_MONTH_CLOSINGS, last


def _hook(m, sub, audience):
    """Opening hook, chosen from the market's actual posture rather than assumed."""
    moi = m['moi']
    if audience == 'seller':
        if m['at_or_above'] / m['n_cl'] >= 0.55:
            return f'Most sellers in {sub} got their original asking price or better last year.'
        return f'Most homes in {sub} sold for less than their first asking price last year.'
    # State what months of supply actually measures -- how long current inventory
    # would take to clear at the recent sales pace. It is a stock-versus-pace
    # figure, so it cannot support a claim about listing flow, and comparing this
    # subdivision to "the area" would require outside data this report never uses.
    if moi < 3:
        return (f'There is under three months of inventory in {sub} right now &mdash; '
                f'{m["n_act"]} homes for sale against the recent pace of sales.')
    if moi > 6:
        return (f'{sub} is carrying more than six months of inventory &mdash; '
                f'{m["n_act"]} homes for sale against the recent pace of sales.')
    return (f'{sub} is sitting at {moi:.1f} months of supply, in the range normally '
            f'called balanced.')


# ---------------------------------------------------------------- social posts
def social_posts(m, sub, city, standouts, month_ok, audience):
    """Two social captions per audience. Post 1 leads on the biggest real monthly
    move (or a whole-year figure when the month is too thin); post 2 leads on a
    process fact that is true regardless of market direction."""
    place = f'{sub} in {_place(city)}'
    out = []

    if month_ok and standouts:
        s = standouts[0]
        body = _standout_line(s)
        p1 = dict(
            label='Post 1 &mdash; the number that moved',
            hook=f'The biggest change in {sub} last month was not the one people expected.',
            body=(f'{body} That is one month of data in a subdivision this size, so it is a '
                  f'signal to watch rather than a trend to bet on &mdash; but it is the number '
                  f'worth knowing before you price or offer.'),
            cta=(f'Want the full {sub} market breakdown, including what every home actually '
                 f'sold for? Comment BRIEF and I will send it over.'),
            tags=f'#{_tag(sub)} #{_tag(_place(city).split(",")[0])} #RealEstateMarketUpdate',
        )
    else:
        p1 = dict(
            label='Post 1 &mdash; the year in one number',
            hook=_hook(m, sub, audience),
            body=(f'Across the last 12 months, {m["n_cl"]} homes closed in {place} at a median of '
                  f'{M(m["med"])}, a median of {m["dtc_med"]:.0f} days from listing to accepted offer. '
                  f'Sellers kept an average of {m["cpo"]:.1f}% of their original asking price. '
                  f'Monthly figures here rest on very few sales, so these whole-year numbers are the '
                  f'reliable ones.'),
            cta=((f'Curious what your home would do in this market? Send me a message and I will '
                  f'run your address against these numbers.') if audience == 'seller' else
                 (f'Thinking about buying in {sub}? Message me and I will send the current listings '
                  f'with each home&rsquo;s days on market and price history.')),
            tags=(f'#{_tag(sub)} #{_tag(_place(city).split(",")[0])} '
                  f'#{"HomeValues" if audience == "seller" else "HousingMarketUpdate"}'),
        )
    out.append(p1)

    if audience == 'seller':
        p2 = dict(
            label='Post 2 &mdash; the pricing lesson',
            hook=f'The first asking price in {sub} decides how long you wait.',
            body=(f'Homes here that never reduced went from listing to closing in a median of '
                  f'{m["ttl_nored"]:.0f} days. Homes that took a price adjustment took '
                  f'{m["ttl_red"]:.0f} days &mdash; {dur(abs(m["ttl_red"] - m["ttl_nored"]))} longer. '
                  f'Both sold. The difference was time, and the carrying costs that come with it.'),
            cta=(f'Thinking about selling in {sub}? Message me for the pricing analysis on your '
                 f'specific floor plan.'),
            tags=f'#{_tag(sub)} #{_tag(_place(city).split(",")[0])} #HomeSellingTips',
        )
    else:
        p2 = dict(
            label='Post 2 &mdash; where the leverage is',
            hook=f'Not every home in {sub} is negotiable. Here is how to tell which ones are.',
            body=(f'Of the {m["n_cl"]} sales in the last year, {m["under_orig"]} closed below the '
                  f'original asking price, and {m["conc_n"]} buyers had the seller contribute toward '
                  f'closing costs or a rate buy-down &mdash; a median of {M(m["conc_med"])} where one '
                  f'was paid. Days on market is the single best predictor of which listing will move.'),
            cta=(f'Buying in {sub}? Message me and I will send the current list with each home&rsquo;s '
                 f'days on market and price history.'),
            tags=f'#{_tag(sub)} #{_tag(_place(city).split(",")[0])} #HomeBuyingTips',
        )
    out.append(p2)
    return out


def _tag(s):
    return ''.join(ch for ch in s.title() if ch.isalnum())


def _place(city):
    """Cover-line city strings carry a ZIP after a middot ('Boulder, CO - 80305').
    That reads as noise inside a sentence, so prose uses the city and state only.
    The ZIP still earns its keep in the report cover and footer."""
    return city.split('\u00b7')[0].strip().rstrip(',').strip()


# ---------------------------------------------------------------- reel scripts
def reel_scripts(m, sub, city, standouts, month_ok, audience):
    """Two ~40-second talking-head scripts per audience, with on-screen text cues.
    Roughly 100-110 spoken words each at a normal delivery pace."""
    out = []
    if month_ok and standouts:
        lead = _standout_line(standouts[0])
        second = _standout_line(standouts[1]) if len(standouts) > 1 else ''
        caveat = ('One month in a subdivision this size is a small sample, so treat that as a '
                  'signal, not a trend.')
    else:
        lead = (f'{m["n_cl"]} homes closed in {sub} over the last twelve months at a median of '
                f'{M(m["med"])}.')
        second = (f'The median home went under contract in {m["dtc_med"]:.0f} days.')
        caveat = ('Monthly numbers here rest on only a couple of sales, so the twelve-month figures '
                  'are the ones I trust.')

    if audience == 'seller':
        out.append(dict(
            label='Reel 1 &mdash; what just happened in the numbers',
            hook=f'If you own in {sub}, this is the number I would want you to see.',
            script=[
                (f'HOOK (0&ndash;3s): "If you own a home in {sub}, this is the one number I would '
                 f'want you to see this month."'),
                (f'POINT (3&ndash;20s): "{lead} {second}"'),
                (f'CONTEXT (20&ndash;32s): "{caveat} Across the whole year, sellers here kept an '
                 f'average of {m["cpo"]:.1f}% of their original asking price, and '
                 f'{m["at_or_above"]} of {m["n_cl"]} got that first number or better."'),
                (f'CTA (32&ndash;40s): "I put all of it in a {sub} market brief &mdash; every sale, '
                 f'what it listed for, what it closed for. Comment BRIEF and I will send it."'),
            ],
            onscreen=[f'{sub.upper()} MARKET UPDATE',
                      Mshort(m['med']) + ' MEDIAN SALE',   # always the median sale price;
                      # standouts[0]['cur'] is whichever series moved most and is not a price.
                      f'{m["cpo"]:.1f}% OF ORIGINAL ASK',
                      'COMMENT "BRIEF"'],
        ))
        out.append(dict(
            label='Reel 2 &mdash; the cost of overpricing',
            hook='Overpricing does not cost you a buyer. It costs you months.',
            script=[
                ('HOOK (0&ndash;3s): "Overpricing your home does not cost you the buyer. '
                 'It costs you months."'),
                (f'POINT (3&ndash;18s): "In {sub}, homes that never cut their price went from listing '
                 f'to closing in a median of {m["ttl_nored"]:.0f} days. Homes that had to adjust took '
                 f'{m["ttl_red"]:.0f}."'),
                (f'CONTEXT (18&ndash;32s): "Both sold. Every adjusted listing here eventually found a '
                 f'buyer. The difference was '
                 f'{dur(abs(m["ttl_red"] - m["ttl_nored"]))} of carrying costs, showings, and living '
                 f'in a house you are trying to leave."'),
                (f'CTA (32&ndash;40s): "If you are thinking about listing in {sub} this year, message '
                 f'me and I will show you where your price lands against these {m["n_cl"]} sales."'),
            ],
            onscreen=['PRICED RIGHT: ' + f'{m["ttl_nored"]:.0f} DAYS',
                      'AFTER A CUT: ' + f'{m["ttl_red"]:.0f} DAYS',
                      'BOTH SOLD',
                      'DM FOR YOUR NUMBER'],
        ))
    else:
        out.append(dict(
            label='Reel 1 &mdash; what buyers are walking into',
            hook=f'Here is what buying in {sub} actually looks like right now.',
            script=[
                (f'HOOK (0&ndash;3s): "Here is what buying in {sub} actually looks like right now, '
                 f'in real numbers."'),
                (f'POINT (3&ndash;20s): "{lead} {second}"'),
                (f'CONTEXT (20&ndash;32s): "{caveat} There are {m["n_act"]} homes for sale today at a '
                 f'median asking price of {M(m["act_med_list"])}, which works out to about '
                 f'{m["moi"]:.1f} months of supply."'),
                (f'CTA (32&ndash;40s): "I track every listing in {sub} with its days on market and '
                 f'price history. Comment LIST and I will send you the current one."'),
            ],
            onscreen=[f'BUYING IN {sub.upper()}',
                      f'{m["n_act"]} HOMES FOR SALE',
                      f'{m["moi"]:.1f} MONTHS OF SUPPLY',
                      'COMMENT "LIST"'],
        ))
        out.append(dict(
            label='Reel 2 &mdash; how to spot the negotiable listing',
            hook='Days on market tells you more than the asking price does.',
            script=[
                ('HOOK (0&ndash;3s): "Days on market tells you more about a listing than the asking '
                 'price ever will."'),
                (f'POINT (3&ndash;18s): "In {sub}, {m["under_orig"]} of {m["n_cl"]} sales closed below '
                 f'the original asking price, and the average sale came in {m["disc_orig"]:.1f}% under '
                 f'that first number."'),
                (f'CONTEXT (18&ndash;32s): "{m["conc_n"]} of those buyers also got a seller credit '
                 f'toward closing costs or a rate buy-down &mdash; a median of {M(m["conc_med"])}. '
                 f'The listings that had been sitting were the ones where that happened."'),
                (f'CTA (32&ndash;40s): "Send me a message before you write an offer in {sub} and I '
                 f'will pull the price history on that specific home first."'),
            ],
            onscreen=[f'{m["under_orig"]} OF {m["n_cl"]} PAID UNDER ASK',
                      f'AVG {m["disc_orig"]:.1f}% BELOW FIRST PRICE',
                      f'MEDIAN CREDIT {Mshort(m["conc_med"])}',
                      'DM BEFORE YOU OFFER'],
        ))
    return out


# ---------------------------------------------------------------- newsletter
def newsletter(m, sub, city, standouts, month_ok):
    """One email covering both sides of the conversation. Subject lines are written
    as questions a person would actually search or ask an assistant, which is what
    both classic SEO and answer engines reward."""
    if month_ok and standouts:
        opener = ' '.join(_standout_line(s) for s in standouts[:2])
        frame = ('Those are one month of movement in a subdivision that averages about '
                 f'{m["n_cl"]/12:.1f} sales a month, so I read them as signals rather than trends. '
                 'The twelve-month figures below are the reliable ones.')
    else:
        opener = (f'There were too few closings last month to draw a month-over-month conclusion '
                  f'worth publishing, so here is the twelve-month picture instead.')
        frame = (f'At about {m["n_cl"]/12:.1f} sales a month, a single month in {sub} is one or two '
                 f'houses. The annual figures are the ones that hold up.')
    return dict(
        subject=f'What is happening with home prices in {sub}?',
        alt_subject=f'{sub} market update: {m["n_cl"]} sales, median {M(m["med"])}',
        preheader=(f'The last 12 months in {sub}, {_place(city)} &mdash; what sold, what it sold for, '
                   f'and how long it took.'),
        opener=opener,
        frame=frame,
        seller=(f'<strong>If you are thinking about selling.</strong> {m["at_or_above"]} of the '
                f'{m["n_cl"]} homes that sold here got their original asking price or better, and '
                f'sellers kept an average of {m["cpo"]:.1f}% of that first number. The homes that '
                f'never had to reduce went from listing to closing in a median of '
                f'{m["ttl_nored"]:.0f} days; the ones that adjusted took {m["ttl_red"]:.0f}. '
                f'The opening price is what controls that gap &mdash; not the market.'),
        buyer=(f'<strong>If you are thinking about buying.</strong> There are {m["n_act"]} homes for '
               f'sale in {sub} today at a median asking price of {M(m["act_med_list"])}, about '
               f'{m["moi"]:.1f} months of supply. {m["under_orig"]} of the {m["n_cl"]} sales last '
               f'year closed below the original asking price, and {m["conc_n"]} buyers received a '
               f'seller credit toward closing costs or a rate buy-down, a median of '
               f'{M(m["conc_med"])} where one was paid. A listing that has been sitting is where '
               f'that room tends to be.'),
        cta=(f'Reply to this email with your address and I will send you the full {sub} brief &mdash; '
             f'every sale from the last twelve months, what each home listed for, what it closed '
             f'for, and how long it took.'),
    )


# ---------------------------------------------------------------- render
# -------------------------------------------------------- standalone HTML
def newsletter_html(m, sub, city, mo_build):
    """A self-contained .html file of just the newsletter draft -- the same
    content and copy already embedded in the Appendix PDF's 'Digital
    Marketing Strategies' section, but as its own downloadable file an agent
    can open directly in a browser or paste straight into an email tool,
    rather than extracting it from page 6 of a PDF. Inline styles throughout
    (not a <style> block) because many email clients strip <style> tags on
    paste -- this needs to survive that. No Playwright involved: this is
    plain HTML, not a PDF or PNG, so it's the cheapest of every download
    option here to generate.
    """
    month_ok, _last_n = _month_ok(mo_build, m)
    standouts = monthly_standouts(mo_build, top=3)
    nl = newsletter(m, sub, city, standouts, month_ok)
    place = _place(city)
    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{HT.escape(nl["subject"])}</title></head>
<body style="margin:0;padding:0;background:#FBF6EE;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FBF6EE;padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#FFFDF8;border:1px solid #E9DFCF;border-radius:8px;overflow:hidden;">
<tr><td style="background:#1B2740;padding:24px 32px;">
  <div style="color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:12px;letter-spacing:.1em;text-transform:uppercase;opacity:.75;">Email newsletter draft</div>
  <div style="color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:21px;font-weight:700;margin-top:6px;">{HT.escape(sub)}, {HT.escape(place)}</div>
</td></tr>
<tr><td style="padding:26px 32px 8px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F0E9DA;border:1px solid #E3D3AE;border-radius:6px;">
  <tr><td style="padding:14px 16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.6;color:#7A7061;">
    <strong style="color:#1B2740;">Subject:</strong> {HT.escape(nl["subject"])}<br>
    <strong style="color:#1B2740;">Alternate subject:</strong> {HT.escape(nl["alt_subject"])}<br>
    <strong style="color:#1B2740;">Preheader:</strong> {HT.escape(nl["preheader"])}
  </td></tr>
  </table>
</td></tr>
<tr><td style="padding:20px 32px;font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.65;color:#1B2740;">
  <p style="margin:0 0 18px;">{nl["opener"]} {nl["frame"]}</p>
  <p style="margin:0 0 18px;">{nl["seller"]}</p>
  <p style="margin:0 0 18px;">{nl["buyer"]}</p>
</td></tr>
<tr><td style="padding:4px 32px 28px;">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
  <tr><td align="center" style="background:#1B2740;border-radius:6px;padding:16px 20px;">
    <span style="color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;">{HT.escape(nl["cta"])}</span>
  </td></tr>
  </table>
</td></tr>
<tr><td style="padding:18px 32px;border-top:1px solid #E9DFCF;font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.6;color:#7A7061;">
  Figures drawn from a 365-day MLS export of {HT.escape(sub)}, {HT.escape(place)}. Re-run this report
  before reusing this draft in a later month &mdash; the figures above go stale. Add your brokerage
  name, license number and the Equal Housing Opportunity mark before sending, per Colorado Real Estate
  Commission advertising rules. Information deemed reliable but not guaranteed.
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''


def _post_html(p):
    return (f'<div class="mkt"><div class="mkl">{p["label"]}</div>'
            f'<p class="mkh">{p["hook"]}</p>'
            f'<p class="mkb">{p["body"]}</p>'
            f'<p class="mkc"><strong>CTA:</strong> {p["cta"]}</p>'
            f'<p class="mkt-tags">{p["tags"]}</p></div>')


def _reel_html(r):
    beats = ''.join(f'<li>{b}</li>' for b in r['script'])
    osd = ' &nbsp;&#8226;&nbsp; '.join(r['onscreen'])
    return (f'<div class="mkt"><div class="mkl">{r["label"]}</div>'
            f'<p class="mkh">{r["hook"]}</p>'
            f'<ul class="mkr">{beats}</ul>'
            f'<p class="mkt-tags"><strong>On-screen text:</strong> {osd}</p></div>')


def section(d, m, sub, city, audience, num, mo_build):
    """The Digital Marketing Strategies section, appended to both briefs."""
    month_ok, last_n = _month_ok(mo_build, m)
    standouts = monthly_standouts(mo_build, top=3)
    posts = social_posts(m, sub, city, standouts, month_ok, audience)
    reels = reel_scripts(m, sub, city, standouts, month_ok, audience)
    nl = newsletter(m, sub, city, standouts, month_ok)

    gate = ('' if month_ok else
            f'<div class="take"><span class="tag">Why this copy uses annual figures</span><p>'
            f'The most recent complete month recorded {last_n} closing'
            f'{"" if last_n == 1 else "s"} in {sub}, below the {MIN_MONTH_CLOSINGS}-sale minimum '
            f'this skill requires before publishing a month-specific claim. A percentage swing '
            f'built on {last_n or "no"} sale{"" if last_n == 1 else "s"} is arithmetic, not a '
            f'market signal, and it will not survive being questioned. The copy below therefore '
            f'uses whole-year figures, which are the defensible ones at this sample size.</p></div>')

    stand = ''
    if month_ok and standouts:
        items = ''.join(f'<li>{_standout_line(s)}</li>' for s in standouts)
        stand = (f'<h3>What actually moved this month</h3><div class="talk"><ul>{items}</ul></div>'
                 f'<p class="cap">Ranked by size of the month-over-month move. The copy below is '
                 f'built from this list, so it changes every time the report is re-run.</p>')

    who = 'seller' if audience == 'seller' else 'buyer'
    body = f'''<div class="sec pb"><span class="num">{num}</span><h2>Digital marketing strategies</h2></div>
<p>Ready-to-use copy for the {who} conversation in {sub}, built from the same figures as the rest of
this report. Every number below traces to the uploaded export, so this content can be published as
written &mdash; but read the compliance note at the end of the section before you post.</p>
{gate}
{stand}
<h3>Social posts</h3>
{''.join(_post_html(p) for p in posts)}
<h3>Talking-head reel scripts</h3>
<p class="cap">Each script runs about 40 seconds at a normal speaking pace. The on-screen text
cues are listed in the order they should appear.</p>
{''.join(_reel_html(r) for r in reels)}
<h3>Email newsletter draft</h3>
<div class="mkt">
<div class="mkl">Covers both the buyer and seller conversation</div>
<p class="mkb"><strong>Subject:</strong> {nl['subject']}<br>
<strong>Alternate subject:</strong> {nl['alt_subject']}<br>
<strong>Preheader:</strong> {nl['preheader']}</p>
<p class="mkb">{nl['opener']} {nl['frame']}</p>
<p class="mkb">{nl['seller']}</p>
<p class="mkb">{nl['buyer']}</p>
<p class="mkc"><strong>CTA:</strong> {nl['cta']}</p>
</div>
<h3>How this copy is built to be found</h3>
<div class="talk"><ul>
<li>The subdivision name, city and state appear together in the opening line of every piece, which
is the association both search engines and answer engines index on.</li>
<li>Each piece answers a question a person would actually type or say aloud &mdash; what homes are
selling for, how long they take, whether there is room to negotiate.</li>
<li>Concrete numerals and named months are used instead of adjectives, because extractive and
generative search surfaces quote figures and skip vague description.</li>
<li>Every claim is self-contained, so it stays accurate when it is lifted out of context by a
summary or an assistant.</li>
<li>Hashtags are place-based only. Audience-based tags are a Fair Housing exposure, not a reach
strategy.</li>
</ul></div>
<div class="take"><span class="tag">Before you publish &mdash; compliance</span><p>This copy is written to
stay on price, timing, inventory and process facts. <strong>It deliberately contains no school
references, no description of the neighborhood or who lives there, and no audience-targeting
language</strong> &mdash; those are the established Fair Housing steering risks, and the schools
section of this report is for the client conversation, not for public copy. Add your brokerage name,
license and the Equal Housing Opportunity mark to every published item, per Colorado Real Estate
Commission advertising rules. Do not add compensation or commission claims. Figures are drawn from a
365-day MLS export and go stale &mdash; re-run this report before reusing this copy in a later
month, and state the data window when you post.</p></div>
<p class="cap">All copy is generated from this export&rsquo;s own metrics rather than written to a
template, so a subdivision moving the other direction produces different copy, different hooks and a
different set of monthly standouts.</p>
'''
    return body
