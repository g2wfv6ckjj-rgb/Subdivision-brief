"""Not part of the deployed app -- a one-off local check before shipping."""
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
assert r.status_code == 200 and b'Generate a brief' in r.data
print('3. agent login + dashboard: OK')

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

print('\nALL CHECKS PASSED')
