"""Not part of the deployed app -- a one-off local check before shipping."""
import io
import os
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
shutil.rmtree(BASE / 'instance', ignore_errors=True)
(BASE / 'instance').mkdir()

os.environ['ADMIN_EMAIL'] = 'xiaohui@fntcolorado.com'
os.environ['ADMIN_PASSWORD'] = 'admin-test-pw'
os.environ['ADMIN_NAME'] = 'Xiaohui'
os.environ['SECRET_KEY'] = 'test-secret'

import app as appmod
from models import Agent, Report, db

client = appmod.app.test_client()

# 1. admin bootstrap + login
r = client.post('/login', data={'email': 'xiaohui@fntcolorado.com', 'password': 'admin-test-pw'})
assert r.status_code == 302, f'admin login failed: {r.status_code}'
print('1. admin login: OK')

# 2. admin creates an agent
with appmod.app.app_context():
    before = Agent.query.count()
r = client.post('/admin/agents', data={'email': 'agent1@example.com', 'name': 'Agent One', 'office': 'Denver'})
assert r.status_code == 302, f'create agent failed: {r.status_code}'
with appmod.app.app_context():
    agent = Agent.query.filter_by(email='agent1@example.com').first()
    assert agent is not None, 'agent not created'
    agent.set_password('agent-test-pw')  # known password for this test, bypassing the emailed one-time pw
    db.session.commit()
    agent_id = agent.id
print('2. admin creates agent: OK')
client.post('/logout')

# 3. agent logs in
r = client.post('/login', data={'email': 'agent1@example.com', 'password': 'agent-test-pw'})
assert r.status_code == 302, f'agent login failed: {r.status_code}'
r = client.get('/')
assert r.status_code == 200 and b'Launch Reports' in r.data
assert b'Subdivision Brief' in r.data and b'Listing Report' in r.data
r = client.get('/subdivision')
assert r.status_code == 200 and b'MLS export (.csv)' in r.data and b'data-working' in r.data
print('3. agent login + home hub + subdivision form: OK')

# 4. generate a real report from the Hilltop CSV, carousel + postcard both on
csv_path = '/mnt/user-data/uploads/Hilltop_last_365_days.csv'
with open(csv_path, 'rb') as fh:
    data = {
        'subdivision': 'Hilltop', 'city': 'Denver, CO',
        'carousel': 'on', 'postcard': 'on',
        'csv_file': (fh, 'Hilltop_last_365_days.csv'),
    }
    r = client.post('/generate', data=data, content_type='multipart/form-data')
assert r.status_code == 302, f'generate failed: {r.status_code} {r.data[:500]}'
report_url = r.headers['Location']
print(f'4. generate: OK -> {report_url}')

r = client.get(report_url)
assert r.status_code == 200, 'report detail page failed'
body = r.data.decode()
for expect in ['Master_Brief.pdf', 'Master_Brief_Appendix.pdf', 'Carousel_1.png',
              'Postcard_A_Print.pdf', 'Postcard_B_Print.pdf', 'Postcard_C_Print.pdf']:
    assert expect in body, f'missing expected file in report: {expect}'
print('5. all expected files present (brief, appendix, carousel, all 3 postcard variants): OK')

with appmod.app.app_context():
    rpt = Report.query.filter_by(agent_id=agent_id).first()
    fname = rpt.files.split('\n')[0]
    rid = rpt.id
r = client.get(f'/download/{rid}/{fname}')
assert r.status_code == 200 and len(r.data) > 1000, 'download failed or file too small'
print(f'6. download ({fname}, {len(r.data):,} bytes): OK')

# 7. a second agent cannot see the first agent's report
r = client.post('/admin/agents', data={'email': '', 'name': ''})  # noop, just to keep session admin-free below
client.post('/logout')
client.post('/login', data={'email': 'xiaohui@fntcolorado.com', 'password': 'admin-test-pw'})
client.post('/admin/agents', data={'email': 'agent2@example.com', 'name': 'Agent Two'})
with appmod.app.app_context():
    a2 = Agent.query.filter_by(email='agent2@example.com').first()
    a2.set_password('agent2-pw')
    db.session.commit()
client.post('/logout')
client.post('/login', data={'email': 'agent2@example.com', 'password': 'agent2-pw'})
r = client.get(f'/download/{rid}/{fname}')
assert r.status_code == 403, f'expected 403 for cross-agent download, got {r.status_code}'
print('7. cross-agent download blocked (403): OK')
client.post('/logout')

# 8. disabling an agent blocks login
client.post('/login', data={'email': 'xiaohui@fntcolorado.com', 'password': 'admin-test-pw'})
with appmod.app.app_context():
    a1 = Agent.query.filter_by(email='agent1@example.com').first()
    a1.active = False
    db.session.commit()
client.post('/logout')
r = client.post('/login', data={'email': 'agent1@example.com', 'password': 'agent-test-pw'})
assert r.status_code == 200 and b'Incorrect email or password' in r.data, \
    'disabled agent was able to log in'
print('8. disabled agent blocked from logging in: OK')

# 9. profile: blank state, then save text-only info, then upload + replace a headshot
client.post('/login', data={'email': 'xiaohui@fntcolorado.com', 'password': 'admin-test-pw'})
with appmod.app.app_context():
    admin = Agent.query.filter_by(email='xiaohui@fntcolorado.com').first()
    assert admin.brand_dict(str(appmod.AGENT_ASSETS_DIR)) is None, \
        'brand_dict should be None before anything is set'
r = client.get('/profile')
assert r.status_code == 200 and b'Headshot' in r.data
r = client.post('/profile', data={'phone': '(303) 555-0123', 'contact_email': 'x@fntcolorado.com'})
assert r.status_code == 302
with appmod.app.app_context():
    admin = Agent.query.filter_by(email='xiaohui@fntcolorado.com').first()
    bd = admin.brand_dict(str(appmod.AGENT_ASSETS_DIR))
    assert bd and bd['phone'] == '(303) 555-0123' and bd.get('headshot_path') is None
print('9. profile blank state + text-only save + brand_dict: OK')

r = client.post('/profile', data={
    'phone': '(303) 555-0123', 'contact_email': 'x@fntcolorado.com',
    'headshot': (io.BytesIO(b'fake-jpeg'), 'me.jpg'),
}, content_type='multipart/form-data')
with appmod.app.app_context():
    admin = Agent.query.filter_by(email='xiaohui@fntcolorado.com').first()
    assert admin.headshot_filename == 'headshot.jpg'
    bd = admin.brand_dict(str(appmod.AGENT_ASSETS_DIR))
    assert bd.get('headshot_path') and os.path.exists(bd['headshot_path'])
r = client.post('/profile', data={
    'phone': '(303) 555-0123', 'contact_email': 'x@fntcolorado.com',
    'headshot': (io.BytesIO(b'fake-png'), 'me2.png'),
}, content_type='multipart/form-data')
files = sorted(p.name for p in (appmod.AGENT_ASSETS_DIR / str(admin.id)).glob('headshot.*'))
assert files == ['headshot.png'], f'old headshot file orphaned: {files}'
print('10. headshot upload + re-upload replaces (no orphaned file): OK')

# 11. carousel/postcard CTA rendering, all three agent-personalization states
import carousel, postcard
none_html = carousel._s6_cta({}, 'Hilltop', 'Denver, CO', agent=None)
assert 'class="broker"' in none_html and 'agentname' not in none_html
full = {'name': 'X', 'phone': '303-555-0123', 'email': 'x@y.com', 'headshot_path': '/fake.jpg'}
full_html = carousel._s6_cta({}, 'Hilltop', 'Denver, CO', agent=full)
assert 'agentphoto' in full_html and 'Fidelity National Title' in full_html
partial = {'name': 'Y', 'phone': None, 'email': 'y@z.com', 'headshot_path': None}
partial_html = carousel._s6_cta({}, 'Hilltop', 'Denver, CO', agent=partial)
assert '<img class="agentphoto"' not in partial_html and 'Y' in partial_html
pc_none = postcard.side_b_html({'moi':2,'dtc_med':21,'cpo':92,'med':1,'n_cl':1}, 'H',
                               scores={'chance':1,'power':1,'balance':1}, agent=None)
assert 'class="agentrow"' not in pc_none
pc_full = postcard.side_b_html({'moi':2,'dtc_med':21,'cpo':92,'med':1,'n_cl':1}, 'H',
                               scores={'chance':1,'power':1,'balance':1}, agent=full)
assert 'class="agentrow"' in pc_full and 'Fidelity National Title' in pc_full
print('11. carousel + postcard agent personalization (none/full/partial): OK')

# 12. one-pager tier: distinct content, doesn't bleed into the full Brief
import core
import master as _m
_d = core.load('/mnt/user-data/uploads/Hilltop_last_365_days.csv')
_m1, _cl, _act, _exp = core.metrics(_d)
_cfg = core.set_county(_d)
one_pager, brief_h, appendix_h = _m.report_html(_d, _m1, _cl, _act, _exp, 'Hilltop', 'Denver, CO', _cfg)
assert 'HIGH-LEVEL BRIEF' in one_pager and 'MASTER BRIEF' not in one_pager
assert 'Chance of selling, if priced right' not in one_pager, 'one-pager bled into section 02'
assert 'MASTER BRIEF' in brief_h and 'Chance of selling, if priced right' in brief_h
print('12. one-pager tier is genuinely distinct from the full Brief: OK')

# 13. newsletter HTML: standalone, no Playwright needed, real content
import monthly, marketing
_mo = monthly.build(_d)
_nl = marketing.newsletter_html(_m1, 'Hilltop', 'Denver, CO', _mo)
assert _nl.strip().startswith('<!DOCTYPE html>') and 'Subject:' in _nl
assert 'Equal Housing Opportunity' in _nl
print('13. newsletter HTML generation: OK')

# 14. listing_api.py: parses real RealtyAPI responses correctly (both
# /details/byaddress and /search/byzip), and degrades gracefully on a
# sparse one (most real properties won't have every optional field).
import json
import listing_api
_raw_fixture = json.load(open('skill/fixtures/realtyapi_details_sample.json'))
_prop = listing_api.get_property('1380 Bellaire St, Broomfield, CO 80020', _raw=_raw_fixture)
assert _prop['list_price'] == 650000 and _prop['county_fips'] == '08014'
assert _prop['avm_low'] == 664300 and _prop['avm_high'] == 826000
_sparse = listing_api.get_property('x', _raw={"detail": {
    "status": "for_sale", "list_price": 1,
    "details": {}, "address": {}}})
assert _sparse['avm_values'] == [] and _sparse['forecast'] is None

_search_fixture = json.load(open('skill/fixtures/realtyapi_search_sample.json'))
_comps = listing_api.get_comps('80228', _raw=_search_fixture)
assert len(_comps) == 3 and _comps[0]['address_line'] == '14210 W Evans Cir'
assert _comps[0]['list_price'] == 1050000 and _comps[0]['estimate'] == 893000
assert _comps[2]['estimate'] is None  # missing field doesn't crash
print('14. listing_api.py parsing (property details + search/comps, both real fixtures): OK')

# 15. buyer_profile.py: deterministic classifier, tested against real +
# synthetic data across scenarios designed to actually discriminate
# between rules, not just exercise the happy path once.
import buyer_profile
_buyer = buyer_profile.classify_buyer(_prop, comps=_comps, area=None)
assert _buyer['archetype'] == 'Move-up buyer (space + schools)'
_condo = {'beds': 2, 'sqft': 900, 'property_type': 'condos', 'hoa_fee': 250, 'schools': []}
_buyer2 = buyer_profile.classify_buyer(_condo)
assert _buyer2['archetype'] == 'First-time buyer or downsizer'
assert 'a condo -- ' in _buyer2['reasons'][0]  # grammar fix: not "a condos"
print('15. buyer_profile.py classifier (real + synthetic scenarios): OK')

# 16. listing_marketing.py: three creatives, grounded in real property data
import listing_marketing
_creatives = listing_marketing.creatives(_prop)
assert '1380 Bellaire St' in _creatives['print']['message'] and '$650,000' in _creatives['print']['price_line']
assert 'Northmoor' in _creatives['digital']['headline']
print('16. listing_marketing.py creatives (real property data): OK')

# 17. listing_report.py: full assembly, real property + real comps + REAL
# co_data resolution for the property's actual ZIP -- not mocked area data.
import listing_report
_area = co_data.resolve([_prop['zip']]).as_dict()
_html = listing_report.build_html(_prop, comps=_comps, area=_area)
assert all(s in _html for s in ['LISTING REPORT', 'The Property', "What It's Worth",
                                 'Nearby Listings', 'The Neighborhood',
                                 'Ideal Buyer Profile', 'Marketing Blueprint'])
assert 'disagree by' in _html  # AVM spread disclosure present given the real 664K-826K spread
print('17. listing_report.py full assembly (real property + comps + area): OK')

# 18. the actual /listing route, through the real Flask test client -- not
# just calling functions directly. Confirms property lookup, comps lookup,
# and REAL co_data resolution all wire together correctly through the HTTP
# path itself, and that a failure (here, the same missing-chromium wall as
# every PDF this session) cleans up completely rather than leaving an
# orphaned Report row or directory behind.
os.environ['REALTYAPI_KEY'] = 'test-key-for-selftest'
_orig_get_property = listing_api.get_property
_orig_get_comps = listing_api.get_comps
listing_api.get_property = lambda address: _orig_get_property(address, _raw=_raw_fixture)
listing_api.get_comps = lambda zip_code: _orig_get_comps(zip_code, _raw=_search_fixture)

r = client.get('/listing')
assert r.status_code == 200 and b'Property address' in r.data
r = client.post('/listing/generate', data={'address': ''})
assert r.status_code == 302
client.post('/listing/generate', data={'address': '1380 Bellaire St, Broomfield, CO 80020'})
with appmod.app.app_context():
    assert Report.query.count() == 0, 'a failed listing report left an orphaned row'
assert list((appmod.REPORTS_DIR).glob('*/')) == [], 'a failed listing report left an orphaned directory'

listing_api.get_property = _orig_get_property
listing_api.get_comps = _orig_get_comps
print('18. /listing route (real HTTP path, clean failure handling): OK')

# 19. IRS migration (county level, real data) + Census parser (synthetic
# payload in the documented shape -- the live call is untestable here).
import census_api
_orig = co_data.top_origins('80020')
assert _orig['county'] == 'Broomfield County' and _orig['origins'][0]['place'] == 'Adams County, CO'
assert co_data.top_origins('99999') is None
_demo = census_api.get_demographics('80020', _raw=json.load(open('skill/fixtures/census_acs_SYNTHETIC.json')))
assert _demo['median_hh_income'] == 100000 and _demo['owner_pct'] == 70.0
print('19. IRS migration + Census parser: OK')

# 20. Fair Housing: no buyer-type language in any ad creative, and the new
# sections appear only as agent-facing context.
import re
_all = (_creatives['digital']['title'] + _creatives['digital']['headline'] + _creatives['digital']['description']
        + _creatives['print']['headline'] + _creatives['print']['message']
        + (_creatives['print']['location_line'] or '') + _creatives['email']['subject']
        + _creatives['email']['preview'] + _creatives['email']['body']
       ).lower().replace('single-family', '').replace('multi-family', '').replace('family room', '')
for _w in ('family', 'families', 'retiree', 'young', 'couple', 'kids', 'children', 'singles', 'buyer'):
    assert not re.search(rf'\b{_w}\b', _all), f'buyer-type term in ad copy: {_w}'
_html2 = listing_report.build_html(_prop, comps=_comps, area=_area, demo=_demo, origins=_orig)
assert 'Who Lives Here' in _html2 and 'For agent planning only' in _html2
assert 'Who Lives Here' not in listing_report.build_html(_prop, comps=_comps, area=_area)
print('20. Fair Housing ad-copy check + demographics sections: OK')

# 21. Full Ideal Buyer Profile table: every row present for Broomfield, the
# payment math is right, and the report shows ONE payment figure.
_careers = census_api.get_careers('80020', _meta=json.load(open('skill/fixtures/census_dp03_meta_SYNTHETIC.json')),
                                  _raw=json.load(open('skill/fixtures/census_dp03_SYNTHETIC.json')))
import core
_pf = buyer_profile.build_profile(_prop, _comps, _area, _demo, _careers, _orig, core.FIN)
_labels = [re.sub('<[^>]+>', '', l) for l, _ in _pf['rows']]
for _want in ('Age range', 'Household composition', 'Income band', 'Career types', 'Current household status',
              'Core motivations', 'Where they are moving from', 'Lifestyle', 'Data-driven rationale'):
    assert any(l.startswith(_want) for l in _labels), f'missing profile row: {_want}'
_pay = _pf['payment']
assert abs(_pay['pi'] - 3442) <= 2, _pay   # $520K, 30 yr, 6.95%
assert _pay['tax'] == round(3583 / 12) and _pay['hoa'] == 0
_html3 = listing_report.build_html(_prop, _comps, _area, _demo, _orig, _careers)
assert f"${_pay['total']:,}" in _html3 and '$4,154' not in _html3, 'two different payment figures in one report'
assert 'family' not in _pf['persona'].lower() and 'family' not in _pf['persona_line'].lower()
print('21. Ideal Buyer Profile table (all 9 rows, PITI math, single payment figure): OK')

# 22. Target Areas table (real IRS data, more rows than top_origins, real
# tier logic) and the rebuilt marketing creatives (structured layout,
# character budgets, agent personalization, Fair Housing safety).
_targets = co_data.target_areas('80020')
assert len(_targets['areas']) >= 10, 'expected the wider migration.csv (20/county), not the old 5-row cap'
assert _targets['areas'][0]['probability'] == 'High' and _targets['areas'][-1]['probability'] in ('Medium', 'Low')
_states = {a['state'] for a in _targets['areas']}
assert _states - {'CO'}, 'expected at least one real out-of-state origin county'
print('22. co_data.target_areas() (wider IRS list, tiers, out-of-state counties): OK')

_agent = {'name': 'Xiaohui Janecek', 'phone': '303-555-0123', 'email': 'x@fntcolorado.com'}
_c2 = listing_marketing.creatives(_prop, agent=_agent)
assert len(_c2['digital']['title']) <= _c2['digital']['title_budget']
assert len(_c2['digital']['headline']) <= _c2['digital']['headline_budget']
assert len(_c2['digital']['description']) <= _c2['digital']['description_budget']
assert 'Xiaohui Janecek' in _c2['print']['cta'] and '303-555-0123' in _c2['print']['cta']
_c_noagent = listing_marketing.creatives(_prop)
assert '[Agent Name]' in _c_noagent['print']['cta']
_allcopy = (_c2['digital']['title'] + _c2['digital']['headline'] + _c2['digital']['description']
           + _c2['print']['headline'] + _c2['print']['message'] + (_c2['print']['location_line'] or '')
           + _c2['email']['subject'] + _c2['email']['preview'] + _c2['email']['body']).lower()
import re as _re
for _w in ('family', 'families', 'retiree', 'young', 'couple', 'kids', 'children', 'singles', 'buyer'):
    _scrub = _allcopy.replace('single-family', '').replace('multi-family', '').replace('family room', '')
    assert not _re.search(rf'\b{_w}\b', _scrub), _w
print('23. listing_marketing.py structured creatives (budgets, agent info, Fair Housing): OK')

_html4 = listing_report.build_html(_prop, _comps, _area, _demo, _orig, _careers, _targets, _agent)
assert all(s in _html4 for s in ('Target Areas for Advertising', 'Marketing Creatives', '1. Digital Ad',
                                  '2. Print Creative', '3. Email Creative', 'Fair Housing Compliance Statement'))
assert 'Xiaohui Janecek | Fidelity National Title' in _html4
_plain = _re.sub('<[^>]+>', ' ', _html4).lower().replace('single-family', '').replace(
    'multi-family', '').replace('familial status', '').replace('family room', '')
for _w in ('family buyer', 'families', 'retiree', 'young buyer', ' kids ', ' singles'):
    assert _w not in _plain, f'FH violation in full report: {_w}'
print('24. Full report assembly with Target Areas + new creatives + Fair Housing section: OK')

# 25. Photo dimension-aware sizing -- a small source photo must not be
# stretched to full width (the cause of the blurry cover-photo report).
# Tested against a REAL local HTTP server serving real JPEGs, not a mock.
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image
import io as _io
_imgs = {}
for _n, _sz in [('s', (320, 213)), ('l', (1600, 1067))]:
    _b = _io.BytesIO(); Image.new('RGB', _sz, (100, 120, 140)).save(_b, format='JPEG'); _imgs[_n] = _b.getvalue()
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        d = _imgs.get(self.path.strip('/'))
        if d is None: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(d))); self.end_headers(); self.wfile.write(d)
    def log_message(self, *a): pass
_srv = HTTPServer(('127.0.0.1', 8932), _H)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
assert listing_api.photo_dimensions('http://127.0.0.1:8932/s') == (320, 213)
assert listing_api.photo_dimensions('http://127.0.0.1:8932/l') == (1600, 1067)
assert listing_api.photo_dimensions('http://127.0.0.1:8932/missing') is None
assert listing_api.photo_dimensions(None) is None
_srv.shutdown()
assert listing_report._photo_style((320, 213)) == 'width:55%;max-height:160pt'
assert listing_report._photo_style((1600, 1067)) == 'width:100%;max-height:280pt'
assert listing_report._photo_style(None) == 'width:100%;max-height:280pt'
print('25. Photo dimension-aware sizing (real HTTP server, real JPEGs): OK')

# 26. Revise & regenerate: an uploaded CSV persists in the report's own
# directory, the revise form pre-fills prior choices, resubmitting with NO
# file at all still succeeds using the saved CSV, and another agent cannot
# reuse a report_id that isn't theirs. master.build() is patched to a
# trivial stand-in -- this tests the route's own logic (file handling,
# persistence, ownership check), not the PDF pipeline itself, which is
# already covered by the subdivision-brief skill's own tests and blocked
# here by the same missing Chromium binary as every PDF this session.
import io as _io2
import master
_orig_master_build = master.build
def _fake_build(csv, sub, city, outdir='.', enrich_opts=None, **kw):
    _p = __import__('pathlib').Path(outdir) / f'{sub}_Master_Brief.pdf'
    _p.write_bytes(b'%PDF-fake')
    return [str(_p)], {'n_cl': 1}, {'chance': 50, 'power': 50, 'balance': 50}
master.build = _fake_build

with open('/mnt/user-data/uploads/Hilltop_last_365_days.csv', 'rb') as _fh:
    _csv_bytes = _fh.read()
_r = client.post('/generate', data={
    'csv_file': (_io2.BytesIO(_csv_bytes), 'Hilltop_last_365_days.csv'),
    'subdivision': 'Hilltop', 'city': 'Denver, CO', 'brief_tier': 'full', 'carousel': 'on',
}, content_type='multipart/form-data')
assert _r.status_code == 302 and '/reports/' in _r.headers['Location']
_rid = int(_r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
assert (appmod.REPORTS_DIR / str(_rid) / 'source.csv').stat().st_size == len(_csv_bytes)
_opts = json.loads((appmod.REPORTS_DIR / str(_rid) / 'options.json').read_text())
assert _opts == {'brief_tier': 'full', 'carousel': True, 'postcard': False, 'newsletter': False}

_r = client.get(f'/reports/{_rid}')
assert b'Revise options' in _r.data

_r = client.get(f'/subdivision?revise={_rid}')
_html = _r.data.decode()
assert 'value="Hilltop"' in _html and 'Reusing the export uploaded' in _html

_r = client.post('/generate', data={
    'reuse_report_id': str(_rid), 'subdivision': 'Hilltop', 'city': 'Denver, CO', 'brief_tier': 'one_page',
}, content_type='multipart/form-data')  # deliberately no csv_file at all
assert _r.status_code == 302 and '/reports/' in _r.headers['Location']
_new_id = int(_r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
assert _new_id != _rid
assert (appmod.REPORTS_DIR / str(_new_id) / 'source.csv').stat().st_size == len(_csv_bytes)
assert json.loads((appmod.REPORTS_DIR / str(_new_id) / 'options.json').read_text())['brief_tier'] == 'one_page'

with appmod.app.app_context():
    _a2 = Agent(email='revise-agent2@example.com', name='Agent Two', active=True)
    _a2.set_password('pw2')
    db.session.add(_a2); db.session.commit()
_c2 = appmod.app.test_client()
_c2.post('/login', data={'email': 'revise-agent2@example.com', 'password': 'pw2'})
_r = _c2.post('/generate', data={
    'reuse_report_id': str(_rid), 'subdivision': 'Hilltop', 'city': 'Denver, CO', 'brief_tier': 'full',
}, content_type='multipart/form-data')
assert _r.status_code == 302 and _r.headers['Location'].endswith('/subdivision'), \
    "a different agent must not be able to reuse another agent's report_id"

master.build = _orig_master_build
print('26. Revise & regenerate flow (persistence, pre-fill, no re-upload, ownership check): OK')

print('\nALL CHECKS PASSED')
