"""Copy/paste email HTML — a short, client-safe version of the brief that an agent
can paste into Mailchimp, Constant Contact, Follow Up Boss, kvCORE or a plain
Gmail compose window.

WHY THIS IS NOT JUST THE REPORT WITH NARROWER MARGINS
-----------------------------------------------------
Email clients are not browsers and this file must assume the worst one:

  * Gmail strips <style> blocks and <head> entirely. Every rule must be an inline
    style="" attribute on the element itself.
  * Outlook desktop renders through Microsoft Word. No flexbox, no grid, no
    position, unreliable padding on divs. Layout is nested <table> or it does not
    hold together.
  * SVG does not render in Gmail, Outlook or Yahoo. EVERY CHART IN THE BRIEF IS
    THEREFORE IMPOSSIBLE HERE -- dumbbell, month-over-month lines, MOI scale. Not
    degraded, absent.
  * Base64 PNG substitutes do not rescue that: Gmail clips a message past ~102KB
    (hiding everything below the cut behind a "View entire message" link) and most
    clients block remote images by default, so a chart-led email arrives as a
    column of grey boxes.

So this output deliberately carries no charts. The one visual is a proportional
bar built from nested table cells with bgcolor, which renders in Outlook 2016
because it is table markup rather than CSS. Everything else is type and numbers.
The email's job is to be useful in ten seconds and earn the reply that sends the
actual PDF -- not to reproduce a twenty-page report nobody reads in an inbox.

COPY PROVENANCE
---------------
Body copy comes from marketing.newsletter(), the same generator that feeds the
Digital Marketing Strategies section. There is no second set of prose to keep
honest, so the minimum-sample gate (rule 19) and the Fair Housing constraints
apply here automatically and cannot drift out of sync with the report.

CAN-SPAM
--------
Commercial email needs a physical mailing address and a working unsubscribe.
Those belong to the SENDING SERVICE, which injects its own -- a hardcoded
unsubscribe link would be a dead link, which is worse than none. So this file
emits {{MERGE_TAG}} placeholders and a visible checklist telling the agent what
their platform must supply. Broker identification is a placeholder for the same
reason: it varies per agent, and a wrong license number on public advertising is
a Real Estate Commission problem.
"""
import html as HT
import re

import marketing as MK
from core import M, Mshort

# 600px is the long-standing safe width: it fits Outlook's reading pane without
# horizontal scroll and scales down on mobile.
W = 600
INK = '#10203A'; PINE = '#1F4B87'; SAND = '#B0895C'
MUTE = '#56657A'; RULE = '#CBD4DE'; WASH = '#F4F7FB'
# Web-safe stack only. Custom fonts fail in Outlook and fall back unpredictably.
FONT = "Georgia,'Times New Roman',serif"
SANS = "Arial,Helvetica,sans-serif"


def _strip(s):
    """Entities used by the print reports do not all survive a paste into a
    plain-text editor, and some services re-encode them. Normalize to characters
    that are safe in both HTML and text."""
    return (s.replace('&mdash;', '\u2014').replace('&rsquo;', '\u2019')
             .replace('&middot;', '\u00b7').replace('&amp;', '&'))


def _text(s):
    """HTML fragment -> plain text, for the text/plain twin."""
    s = _strip(s)
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return HT.unescape(s).strip()


def _metric_cell(label, value, note):
    return (
        f'<td width="25%" valign="top" style="padding:0 8px 14px 0;">'
        f'<div style="font-family:{SANS};font-size:10px;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{MUTE};padding-bottom:3px;">{label}</div>'
        f'<div style="font-family:{SANS};font-size:22px;font-weight:bold;color:{INK};'
        f'line-height:1.1;">{value}</div>'
        f'<div style="font-family:{SANS};font-size:11px;color:{MUTE};padding-top:2px;">{note}</div>'
        f'</td>')


def _bar(m):
    """The one 'chart' that survives every client: a proportional bar drawn as two
    table cells with bgcolor. No CSS, no image, no SVG -- renders in Outlook's Word
    engine and in text-only previews as a labeled number."""
    n = m['n_cl']
    if not n: return ''
    at = m['at_or_above']; under = m['under_orig']
    pa = max(2, round(at / n * 100))
    pu = max(2, 100 - pa)
    # A segment under ~22% cannot hold its label legibly, so drop the in-bar text
    # there and let the caption below carry it. The bar still shows the proportion.
    la = f'{at} at or above' if pa >= 22 else ''
    lu = f'{under} below' if pu >= 22 else ''
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;margin:0 0 6px;"><tr>'
        f'<td width="{pa}%" bgcolor="{PINE}" height="26" '
        f'style="font-family:{SANS};font-size:11px;color:#ffffff;text-align:center;'
        f'line-height:26px;">{la}</td>'
        f'<td width="{pu}%" bgcolor="{SAND}" height="26" '
        f'style="font-family:{SANS};font-size:11px;color:#ffffff;text-align:center;'
        f'line-height:26px;">{lu}</td>'
        f'</tr></table>'
        f'<div style="font-family:{SANS};font-size:11px;color:{MUTE};padding-bottom:16px;">'
        f'{at} of {n} sales closed at or above the original asking price &nbsp;&#183;&nbsp; '
        f'{under} closed below it</div>')


def _p(txt, size=15):
    return (f'<p style="font-family:{FONT};font-size:{size}px;line-height:1.55;color:{INK};'
            f'margin:0 0 14px;">{txt}</p>')


def build_email(m, sub, city, mo_build):
    """Returns dict(html=..., text=..., subject=..., alt_subject=..., preheader=...).

    Copy is generated by marketing.newsletter(), so the sample gate and Fair
    Housing constraints carry over untouched."""
    month_ok, _ = MK._month_ok(mo_build, m)
    standouts = MK.monthly_standouts(mo_build, top=3)
    nl = MK.newsletter(m, sub, city, standouts, month_ok)
    place = MK._place(city)

    metrics_row = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;"><tr>'
        + _metric_cell('Homes sold', f'{m["n_cl"]}', 'last 12 months')
        + _metric_cell('Median price', Mshort(m['med']), 'closed sales')
        + _metric_cell('Days to offer', f'{m["dtc_med"]:.0f}', 'median')
        + _metric_cell('Supply', f'{m["moi"]:.1f} mo', 'at recent pace')
        + '</tr></table>')

    body = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background-color:{WASH};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="{W}" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:{W}px;max-width:100%;background-color:#ffffff;">
<tr><td style="padding:28px 32px 0;">
<div style="font-family:{SANS};font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:{SAND};padding-bottom:6px;">Market update</div>
<h1 style="font-family:{SANS};font-size:25px;line-height:1.2;color:{INK};margin:0 0 4px;font-weight:bold;">{sub}</h1>
<div style="font-family:{SANS};font-size:13px;color:{MUTE};padding-bottom:18px;">{place} &#183; last 12 months of activity</div>
<hr style="border:0;border-top:1px solid {RULE};margin:0 0 20px;">
</td></tr>
<tr><td style="padding:0 32px;">
{metrics_row}
{_bar(m)}
{_p(_strip(nl['opener']) + ' ' + _strip(nl['frame']))}
{_p(_strip(nl['seller']))}
{_p(_strip(nl['buyer']))}
</td></tr>
<tr><td style="padding:4px 32px 24px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background-color:{WASH};">
<tr><td style="padding:16px 18px;border-left:3px solid {SAND};">
{_p(_strip(nl['cta']), 15)[:-4].replace('margin:0 0 14px;', 'margin:0;')}</p>
</td></tr></table>
</td></tr>
<tr><td style="padding:0 32px 28px;">
<hr style="border:0;border-top:1px solid {RULE};margin:0 0 14px;">
<div style="font-family:{SANS};font-size:11px;line-height:1.6;color:{MUTE};">
{{{{BROKERAGE_NAME}}}} &#183; {{{{AGENT_NAME}}}}, {{{{LICENSE_NUMBER}}}}<br>
{{{{COMPANY_ADDRESS}}}}<br>
Equal Housing Opportunity. Figures are drawn from a 365-day MLS export of {sub} covering closed, active and expired listings, and reflect the market as of the date this was sent. Information deemed reliable but not guaranteed. This is not an offer to buy or sell, and is not intended to solicit property already listed with another brokerage.<br><br>
<a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:{MUTE};">Unsubscribe</a> &#183; <a href="{{{{PREFERENCES_URL}}}}" style="color:{MUTE};">Update preferences</a>
</div>
</td></tr>
</table>
</td></tr></table>'''

    preheader = _text(nl['preheader'])
    html = f'''<!-- {sub} market update -- paste into your email service's HTML/source view.
     All styles are inline; there is no <head> to lose. Replace every {{{{MERGE_TAG}}}}
     or map it to your platform's own field. -->
<div style="display:none;font-size:1px;color:#ffffff;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{HT.escape(preheader)}</div>
{body}'''

    text = f'''{_text(nl['subject'])}

{sub.upper()} — {place}
Last 12 months of activity

Homes sold: {m['n_cl']}
Median price: {M(m['med'])}
Median days to offer: {m['dtc_med']:.0f}
Months of supply: {m['moi']:.1f}
{m['at_or_above']} of {m['n_cl']} sales closed at or above the original asking price; {m['under_orig']} closed below it.

{_text(nl['opener'])} {_text(nl['frame'])}

{_text(nl['seller'])}

{_text(nl['buyer'])}

{_text(nl['cta'])}

--
{{{{BROKERAGE_NAME}}}} · {{{{AGENT_NAME}}}}, {{{{LICENSE_NUMBER}}}}
{{{{COMPANY_ADDRESS}}}}
Equal Housing Opportunity. Figures are drawn from a 365-day MLS export of {sub} covering closed, active and expired listings, and reflect the market as of the date this was sent. Information deemed reliable but not guaranteed. This is not an offer to buy or sell, and is not intended to solicit property already listed with another brokerage.
Unsubscribe: {{{{UNSUBSCRIBE_URL}}}}
'''
    return dict(html=html, text=text, subject=_text(nl['subject']),
                alt_subject=_text(nl['alt_subject']), preheader=preheader)


def wrap_document(pack, sub):
    """The deliverable file. Opens with the subject lines and a merge-tag checklist,
    then a live preview, then the raw HTML in a <textarea> for one-click copy.

    The textarea matters: selecting rendered HTML in a browser and copying it gives
    you styled rich text, which most services then re-encode and mangle. Copying
    from a textarea yields the literal source, which is what the HTML/source view
    of every email platform actually wants."""
    esc = HT.escape(pack['html'])
    esct = HT.escape(pack['text'])
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{HT.escape(sub)} — email copy</title>
<style>
 body{{font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:#10203A;
      max-width:860px;margin:0 auto;padding:28px 20px 60px;background:#fff}}
 h2{{font-size:15px;letter-spacing:.1em;text-transform:uppercase;color:#1F4B87;
     margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid #CBD4DE}}
 .fld{{background:#F4F7FB;border-left:3px solid #B0895C;padding:10px 14px;margin:0 0 10px}}
 .fld b{{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#56657A}}
 textarea{{width:100%;height:290px;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;
   padding:12px;border:1px solid #CBD4DE;border-radius:4px;background:#FAFCFE;color:#10203A}}
 .note{{font-size:13px;color:#56657A;margin:8px 0 0}}
 ul{{font-size:14px;color:#26384F}} li{{margin-bottom:5px}}
 .prev{{border:1px solid #CBD4DE;border-radius:4px;overflow:hidden;margin-top:8px}}
 code{{background:#F4F7FB;padding:1px 5px;border-radius:3px;font-size:13px}}
 button{{font:13px/1 inherit;padding:8px 14px;border:1px solid #1F4B87;background:#1F4B87;
   color:#fff;border-radius:4px;cursor:pointer;margin-top:8px}}
</style></head><body>
<h1 style="font-size:22px;margin:0 0 4px;">{HT.escape(sub)} — email copy</h1>
<p class="note">Paste the HTML below into the <strong>source</strong> or <strong>code</strong> view of your
email service. Do not copy the preview — copy from the box, which gives you the literal markup.</p>

<h2>Subject lines</h2>
<div class="fld"><b>Subject</b>{HT.escape(pack['subject'])}</div>
<div class="fld"><b>Alternate subject</b>{HT.escape(pack['alt_subject'])}</div>
<div class="fld"><b>Preheader</b>{HT.escape(pack['preheader'])}</div>

<h2>Before you send</h2>
<ul>
<li>Replace every <code>{{{{MERGE_TAG}}}}</code>, or map it to your platform's equivalent field.</li>
<li><strong>CAN-SPAM:</strong> your sending service must supply a real physical mailing address and a
working unsubscribe link. They are left as placeholders here on purpose — a hardcoded unsubscribe
would be a dead link, which is worse than none.</li>
<li>Confirm brokerage name, agent name and license number are correct for the sender. Colorado Real
Estate Commission advertising rules apply to email.</li>
<li>Send yourself a test and open it in Gmail and Outlook before sending to a list.</li>
<li>These figures go stale. Re-run the brief and regenerate this email each month rather than
resending an old one.</li>
</ul>

<h2>HTML — copy this</h2>
<textarea id="h" readonly onclick="this.select()">{esc}</textarea>
<button onclick="var t=document.getElementById('h');t.select();document.execCommand('copy');this.textContent='Copied';">Copy HTML</button>

<h2>Plain-text version</h2>
<p class="note">Most services want a text alternative alongside the HTML, and having one helps
deliverability. Paste this into the plain-text tab.</p>
<textarea id="t" readonly onclick="this.select()" style="height:200px;">{esct}</textarea>
<button onclick="var t=document.getElementById('t');t.select();document.execCommand('copy');this.textContent='Copied';">Copy text</button>

<h2>Preview</h2>
<p class="note">Approximate. Outlook renders through Word and will differ slightly; the layout is
table-based so it holds, but always send yourself a test.</p>
<div class="prev">{pack['html']}</div>
</body></html>'''
