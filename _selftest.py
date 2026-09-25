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
assert _buyer['archetype'] == 'Move-up family buyer'
_condo = {'beds': 2, 'sqft': 900, 'property_type': 'condos', 'hoa_fee': 250, 'schools': []}
_buyer2 = buyer_profile.classify_buyer(_condo)
assert _buyer2['archetype'] == 'First-time buyer or downsizer'
assert 'a condo -- ' in _buyer2['reasons'][0]  # grammar fix: not "a condos"
print('15. buyer_profile.py classifier (real + synthetic scenarios): OK')

# 16. listing_marketing.py: three creatives, grounded in real property data
import listing_marketing
_creatives = listing_marketing.creatives(_prop, _buyer)
assert '1380 Bellaire St' in _creatives['digital'] and '$650,000' in _creatives['digital']
assert 'Just listed: 1380 Bellaire St' in _creatives['email']['subject']
print('16. listing_marketing.py creatives (real property data): OK')

# 17. listing_report.py: full assembly, real property + real comps + REAL
# co_data resolution for the property's actual ZIP -- not mocked area data.
import listing_report
_area = co_data.resolve([_prop['zip']]).as_dict()
_html = listing_report.build_html(_prop, comps=_comps, area=_area)
assert all(s in _html for s in ['LISTING REPORT', 'The Property', "What It's Worth",
                                 'Nearby Listings', 'The Neighborhood',
                                 'Who Is The Ideal Buyer', 'Marketing Blueprint'])
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
_all = (_creatives['digital'] + _creatives['print'] + _creatives['email']['subject']
        + _creatives['email']['body']).lower().replace('single-family', '').replace('multi-family', '')
for _w in ('family', 'families', 'retiree', 'young', 'couple', 'kids', 'children', 'singles', 'buyer'):
    assert not re.search(rf'\b{_w}\b', _all), f'buyer-type term in ad copy: {_w}'
_html2 = listing_report.build_html(_prop, comps=_comps, area=_area, demo=_demo, origins=_orig)
assert 'Who Lives Here' in _html2 and 'For agent planning only' in _html2
assert 'Who Lives Here' not in listing_report.build_html(_prop, comps=_comps, area=_area)
print('20. Fair Housing ad-copy check + demographics sections: OK')

print('\nALL CHECKS PASSED')
