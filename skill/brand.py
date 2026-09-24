"""Publisher identity for the social graphics.

WHY A MODULE AND NOT A CONSTANT IN EACH FILE
--------------------------------------------
The carousel, the callout cards and any future artifact all sign off the same
way. Keeping the site line, the logo and the mark in one place means changing
the publisher is one edit rather than a hunt through three renderers, which is
the same reason `REPORT_NOUN` lives in `reports.py`.

THE LOGO
--------
Drop a file at `LOGO_FILE` (SVG or PNG) and every graphic picks it up on the next
build; it is inlined as a data URI so the renderer never needs network access.
With no file present the graphics fall back to a navy wordmark drawn in the
report's own type, so a build never fails and never ships a broken-image box.

WHAT STAYS ON EVERY GRAPHIC
---------------------------
Equal Housing Opportunity renders regardless of who the publisher is. These are
public housing-market graphics; the mark belongs on them whether the publisher is
a brokerage, a title company or anyone else.

The former {{AGENT_NAME}} / {{BROKERAGE_NAME}} / {{LICENSE_NUMBER}} merge tags are
gone because the publisher here is not a licensed real estate brokerage and has no
licence number to state. If an individual agent ever republishes these under their
own name, brokerage identification and licence number have to come back under
Colorado Real Estate Commission advertising rules -- set `AGENT_LINE` for that
case rather than deleting the site line.
"""
import base64
import os

INK = '#10203A'
BRONZE = '#B0895C'
SOFT = '#56657A'

SITE = 'www.fntcolorado.com'
NAME = 'Fidelity National Title'       # wordmark fallback text only
AGENT_LINE = None                      # set when an agent republishes; see above
EHO = 'Equal Housing Opportunity'

LOGO_FILE = os.environ.get(
    'BRIEF_LOGO', os.path.join(os.path.dirname(__file__), 'assets', 'logo.svg'))

_MIME = {'.svg': 'image/svg+xml', '.png': 'image/png',
         '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def logo_available():
    return bool(LOGO_FILE) and os.path.exists(LOGO_FILE)


def logo_img(height_px, alt='logo'):
    """Inline <img> at the requested height, or a navy wordmark if no file."""
    if not logo_available():
        return wordmark(height_px)
    ext = os.path.splitext(LOGO_FILE)[1].lower()
    mime = _MIME.get(ext)
    if not mime:
        return wordmark(height_px)
    with open(LOGO_FILE, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return (f'<img src="data:{mime};base64,{b64}" alt="{alt}" '
            f'style="height:{height_px}px;width:auto;display:block;margin:0 auto;">')


def wordmark(height_px):
    """Navy fallback mark. Deliberately plain so it never passes for a real logo."""
    fs = max(13, int(height_px * 0.52))
    rule = max(2, int(height_px * 0.06))
    return (f'<div style="text-align:center;">'
            f'<div style="font-family:Poppins,sans-serif;font-weight:700;'
            f'letter-spacing:-.01em;font-size:{fs}px;color:{INK};line-height:1.1;">'
            f'{NAME}</div>'
            f'<div style="width:{int(height_px*1.6)}px;height:{rule}px;'
            f'background:{BRONZE};margin:{max(4, height_px//8)}px auto 0;"></div></div>')


def signoff_lines():
    """Text lines under the mark, in order. AGENT_LINE only when it is set."""
    return [x for x in (AGENT_LINE, SITE) if x]
