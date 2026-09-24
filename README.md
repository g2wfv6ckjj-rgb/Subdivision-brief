# Subdivision Brief — web app

Agents log in with their own account, upload an MLS export, and get back the
Master Brief, Appendix, carousel and postcard — the exact pipeline built and
tested in the Subdivision Briefs project, running as a web request instead of
inside a Claude conversation. Nothing in this app calls the Anthropic API;
Claude wrote the code, but generating a report costs server compute, not
Claude usage.

**Tested locally end to end** before this was packaged: bootstrap, login,
report generation (Brief + Appendix + carousel + all three postcard
variants) against the real Hilltop export, cross-agent download blocking,
disabled-agent lockout, and 30-day report expiration all pass — see
`_selftest.py`.

## What you're deploying

- `app.py`, `models.py`, `auth.py` — the web app itself
- `templates/` — pages (matches the brand system already used in the PDFs)
- `skill/` — the actual report pipeline, vendored in unchanged from the
  tested skill package (`core.py`, `master.py`, `carousel.py`, `postcard.py`,
  `co_data.py`, `dials.py`, and the bundled Colorado reference pack)
- `Dockerfile` — Python + a real headless Chromium (Playwright needs one for
  every PDF/PNG this pipeline renders)
- `render.yaml` — tells Render how to set the service up automatically; see
  Part B below. You won't need to open or edit this file.

## Report retention

Each agent's reports are saved to their account and stay listed until
they're 30 days old, then are deleted automatically — files and database
row both, not just hidden from the list. A bookmarked link to an expired
report 404s rather than quietly still working. No separate scheduled job or
cron service needed for this; it's checked once per request, which is cheap
at this app's scale. Change the window with the `RETENTION_DAYS` environment
variable (a plain number of days) if 30 isn't right — no code change needed.

## Deploy — click-only, no commands, no terminal

The CLI path (Railway) turned out to be the wrong recommendation for a
click-through workflow -- it needs a terminal, which is a different skill
from clicking through a website. This is the version with zero typed
commands. Two parts: get the code onto GitHub (just uploading files, like
attaching them to an email), then one click on Render that sets almost
everything up for you.

### Part A — Put the code on GitHub (no git, no commands)

GitHub is just a place to store the code files online so Render can see
them. You won't type anything technical here, only upload files.

1. Go to **github.com** and click **Sign up** (skip this if you already
   have an account). Free.
2. Once logged in, click the **+** in the top-right corner → **New
   repository**.
3. Name it `subdivision-brief` (or anything you like). Leave everything
   else as-is. Click **Create repository**.
4. On the page that appears, click **uploading an existing file** (a blue
   link partway down the page).
5. Open the `webapp` folder on your computer (the one from the zip I gave
   you). Select everything inside it — all the files and folders — and
   **drag them into the browser window**, the same way you'd attach files
   to an email.
6. Scroll down, click the green **Commit changes** button. Done with
   GitHub — you won't come back here again.

### Part B — One click on Render

1. Go to **render.com**, click **Sign up** (or log in). Free to sign up.
2. Click **New** (top right) → **Blueprint**.
3. Render will ask to connect your GitHub — click **Connect GitHub**, then
   **Authorize** in the popup that appears.
4. Pick the `subdivision-brief` repo you just created from the list.
5. Render reads the setup file already included in this app
   (`render.yaml`) and fills in almost everything by itself — the server
   type, a private storage disk so nothing gets lost, a security key. You
   don't need to touch any of that.
6. It'll show you **four boxes to fill in**:
   - `ADMIN_EMAIL` — your email
   - `ADMIN_PASSWORD` — a password you're choosing right now, for your own
     first login
   - `ADMIN_NAME` — your name
   - `RETENTION_DAYS` — already filled in as 30, leave it
7. Click **Apply** (or **Deploy Blueprint**).
8. Wait a few minutes — the progress log will scroll by on its own. It's
   installing everything it needs, including a small web browser it uses
   behind the scenes to build the PDFs. Nothing for you to do here.
9. When it says **Live**, click the link near the top of the page (it
   looks like `subdivision-brief.onrender.com`). That's your website.
10. Log in with the email and password you chose in step 6.

That's the whole thing. No commands, nothing typed except into those four
boxes.

**One optional cleanup, whenever you get to it:** open the service in
Render, click **Environment** on the left, and delete the `ADMIN_PASSWORD`
entry. Your account already works without it from here on — that box was
only needed the first time it started up, and there's no reason to leave a
real password sitting in a settings page after that.

**Cost:** the Blueprint is set to Render's Starter plan, **$7/month**, plus
the small storage disk, **about $1/month**. Roughly **$8/month** total,
billed by Render directly — nothing further from me or Claude.
## Adding and removing agents

Log in as admin → **Admin** in the top nav. **Add an agent** generates a
one-time password shown once on screen — copy it to send to them before
navigating away, it won't be shown again. **Disable** on any agent ends
their access immediately, including any browser session they already have
open; **Re-enable** restores it without losing their report history.
**Reset password** works the same way if someone forgets theirs — no email
sending is wired up (keeps this simple and free of a mail-service
dependency), so a new one-time password is generated and you relay it the
same way.

## Two maintenance things that need periodic attention

These aren't bugs — they're real-world inputs that go stale over time
regardless of where this runs, and they already needed periodic attention
when this ran inside a Claude conversation. Now that it's unattended, they
need a person to own them:

- **The mortgage rate** (`skill/core.py`, the `FIN` dict) is current as of
  this deploy but goes stale in 14 days (skill rule 6). Once it does, every
  report generation will fail with a clear "mortgage rate is N days old"
  message rather than silently using an old rate — that's the pipeline
  correctly refusing, not a bug — but someone needs to update `core.FIN`'s
  `rate`/`rate_src`/`rate_date` from the current Freddie Mac PMMS and
  redeploy. Worth a recurring calendar reminder.
- **The Colorado reference pack** (`skill/assets/co_reference/`) should be
  rebuilt roughly quarterly via `skill/refresh_reference.py` — see skill rule
  62 for what it pulls and why each source matters. This one degrades
  gracefully (stale data, not a hard failure) but the numbers drift.

## Running it locally first (recommended before your first real deploy)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
export ADMIN_EMAIL=you@fntcolorado.com ADMIN_PASSWORD=test123 ADMIN_NAME=You SECRET_KEY=dev
python3 app.py
```

Then open `http://localhost:5000`. `python3 _selftest.py` re-runs the same
automated check this app shipped with, against whatever's currently in
`skill/` — worth running again after any future change to the pipeline.
