[SKILL.md](https://github.com/user-attachments/files/32154128/SKILL.md)
---
name: career-page-internship-finder
description: Find internships directly on company career pages, never job boards
version: 1.0.0
metadata:
  hermes:
    tags: [internships, jobs, career-pages, web-search, ats]
    category: research
    config:
      - key: internship_finder.target_field
        description: "Default field/role to search internships for (e.g. 'software engineering', 'ML')"
        default: ""
        prompt: "What field or role should internship searches default to?"
      - key: internship_finder.excluded_domains
        description: "Comma-separated domains to always exclude from results (job boards etc.)"
        default: "linkedin.com,indeed.com,glassdoor.com,ziprecruiter.com,simplyhired.com,monster.com,dice.com,ycombinator.com/jobs,wellfound.com,ashbyhq.com/jobs-search,builtin.com"
        prompt: "Any extra job-board domains to always exclude?"
---

# Career Page Internship Finder

Finds internship postings by going straight to company **career pages** —
never LinkedIn, Indeed, Glassdoor, or any other third-party job board/aggregator.
**Preferred path (fast, no browser): the company's ATS JSON API fetched via
`scrapling`** (`extract_backend: scrapling` is configured here) — see step 3 and
`scripts/ats_sweep.py`. `web_search` locates candidate companies/tokens;
`web_extract`/`browser_exec` are fallbacks for JS-rendered pages that expose
no API.

> **Browser backend is the fallback, not the default.** Many career/ATS
> pages (Workday, iCIMS, most React career sites, and bot-protected pages)
> only render via JavaScript. Use the ATS-API path first; reach for
> `browser_exec` only when no API exists. If `browser_exec` fails with a
> *connection* error (not a page error), the Chromium/CDP endpoint is down —
> relaunch it per `## Browser Backend Setup` at the bottom. Note some boards
> (amazon.jobs) are bot-gated even under real Chromium — see pitfalls before
> spending calls there.

## When to Use

- User asks to "find internships," "search for internship openings," or similar,
  and specifies (or has previously specified) that results must come from
  **company career pages**, not job portals/aggregators.
- User names specific companies to check, or asks for a broad sweep across a
  sector (e.g. "internships at fintech startups," "any ML internships at big
  labs").
- Do NOT use this skill if the user explicitly wants LinkedIn/Indeed/etc.
  results — that's a plain `web_search` task, not this skill.

## Procedure

**User defaults (saved 2026-09-07 — do NOT re-ask these):**
- Fields: software engineering, ML/data science, GenAI
- Company targets: Indian startups/fintech AND big tech / major product companies
- Location: India (on-site/hybrid)

### 1. Scope the search

Before searching, pin down (ask only if genuinely ambiguous, otherwise infer
from context/config):
- Field/role (e.g. software engineering, data science, hardware, marketing)
- Target companies, sector, or "open sweep across notable companies in X"
- Location/remote constraint, if any
- Experience level confirmation (internship, not new-grad)

Load `internship_finder.target_field` from config as the default field if the
user didn't specify one.

### 2. Find the career page — never the job board

For each target company (or to discover companies in a sector), run
`web_search` with queries structured to land on the **official domain**, e.g.:

```
"<company name>" careers internships
site:<company-domain> internships
"<company name>" site:greenhouse.io
"<company name>" site:lever.co
"<company name>" site:myworkday.com
"<company name>" site:jobs.ashbyhq.com
```

Most companies host their live listings on one of a handful of ATS
(Applicant Tracking System) platforms, even when the public-facing URL is
`company.com/careers`. Company-branded ATS subdomains (`boards.greenhouse.io/x`,
`jobs.lever.co/x`, `x.wd1.myworkdayjobs.com`) **count as the career page** —
they are the company's own listing system, not a third-party aggregator. What
to exclude is job-board *aggregators* that list postings scraped or fed from
many different employers (LinkedIn Jobs, Indeed, Glassdoor, ZipRecruiter,
Wellfound, Built In, etc.) — check `internship_finder.excluded_domains` from
config and filter any `web_search` hit whose domain matches before it's ever
opened.

If `web_search` returns a job-board result discussing/mirroring a company's
posting, do not use it as a source — go find that same company's own
career/ATS page instead and pull the listing from there.

### 3. Pull the actual listings

**Fastest path — use this FIRST: the company's ATS JSON API, fetched with
scrapling.** Every major ATS exposes an unauthenticated JSON endpoint that
returns the company's *entire* live board in one request — no JS rendering,
no 403s, no browser/CDP needed:

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
  (single job + description: `/jobs/<id>`; `?content=true` for all)
- Lever: `https://api.lever.co/v0/postings/<token>?mode=json`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/<token>`
- SmartRecruiters: `https://api.smartrecruiters.com/v1/companies/<token>/postings?limit=100`
  (paginate with `offset`; `totalFound` gives the count)

A ready-made sweep ships with this skill: **`scripts/ats_sweep.py`** — probes
each slug against all four platforms in parallel (32 threads, ~170 slugs in
seconds), filters to intern-level SWE/ML/GenAI roles in India, resolves
blank/ambiguous Greenhouse locations via job detail, and prints deep links.
Run `python <skill-dir>/scripts/ats_sweep.py` (or pass slugs as argv). Do NOT
hand-curate which platform a company uses or guess its token — guessing
produces ~50% 404s; probing all four platforms per slug fixes that. The token
is usually the lowercase brand name, but watch for variants (`towerresearchcapital`,
`twosigma`, `toasttab`, `deutschebank`).

For each confirmed career-page URL (non-API path):

1. Try `web_extract` first — it's cheaper and faster. Many career pages
   (including static Greenhouse/Lever boards) return usable markdown directly.
2. If `web_extract` comes back thin/empty (common for Workday, client-rendered
   React career sites, or any page that needs JS to populate the listing
   table), fall back to `browser_exec` with Python driving the built-in
   `goto_url` / `js` / `cdp` helpers:
   - `goto_url(url)` to load the page, `wait_for_load()` if available
   - `js("document.body.innerText")` (or `js("document.querySelector(...).innerText")`)
     to read the rendered text — this is the equivalent of a snapshot for text
     extraction
   - If the internship listings are paginated or hidden behind a filter/search
     box (Workday almost always is), use `js(...)` to read input values and the
     `cdp('Runtime.evaluate', ...)` / DOM helpers to interact, or drive the
     page via `js(...)` clicks. Re-read `document.body.innerText` after each
     interaction.
   - For hard evidence, dump rendered text to a file in the browser workspace
     (`open(path,'w').write(...)`) and read it back, so the result is verifiable.
   NOTE: helpers are injected as globals — do NOT `import agent_helpers` or
   `from agent_helpers import *` (that import fails in this CLI version).
3. If a backend with `web_crawl` is configured (Firecrawl/Tavily), and the
   task is a broad sweep of one company's entire careers subdomain rather than
   one known URL, `web_crawl` the careers subdomain once instead of issuing
   many individual `web_extract` calls — cheaper for "get every posting" tasks.

Extract for each posting found: title, location, team/department (if listed),
posting URL (deep link to the specific role, not just the board), and
application deadline if stated.

### 4. Verify before reporting

- Confirm the role is actually an internship (title/description says intern,
  co-op, or explicit student program) — don't include new-grad or full-time
  roles that merely mention "internship program" in unrelated boilerplate.
- Confirm the posting URL resolves to the company's own domain/ATS instance,
  not a cached/mirrored copy on a board.
- Drop anything you can't verify is currently open (some ATS boards list
  closed reqs; check for a status/closed marker in the snapshot or extracted
  text).

### 5. Report

Present results grouped by company, each with: role title, location, one-line
summary if useful, and the direct application link. Note if a company's page
had no current internship postings rather than silently omitting it, so the
user knows it was checked.

## Pitfalls

- Search engines rank job-board aggregators far above the original company
  posting — a bare `web_search` for "<role> internship" surfaces LinkedIn/Indeed
  almost exclusively. Always search with `site:` scoped to the company domain
  or a known ATS platform (see step 2) rather than an unscoped query, or the
  excluded-domains filter ends up discarding most of the result set.
- `web_extract` (keyless Firecrawl) returns **403 Forbidden / empty** on
  bot-protected career pages (e.g. Cars24, Spinny, CRED, Nykaa, Upstox). That
  is NOT "no postings" — route those through `browser_exec` instead.
- `web_extract` also silently returns near-empty content on Workday and other
  client-rendered boards because the listing table loads via a JS fetch after
  initial paint — treat a suspiciously short/empty extract on a known ATS
  domain as a signal to switch to the browser tools, not as "no postings."
- A bare company-name `web_search` surfaces almost entirely job-board
  aggregators and is low-signal. The effective discovery step is the
  **ATS-scoped `site:` query** (e.g. `"<company>" site:greenhouse.io`,
  `site:lever.co`, `site:myworkday.com`, `site:jobs.ashbyhq.com`) — use those
  first, not an unscoped name search.
- Company-hosted ATS subdomains (`boards.greenhouse.io`, `jobs.lever.co`,
  `*.myworkdayjobs.com`) are frequently miscategorized as "third-party boards"
  — they are not; they're the company's own system. Only filter true
  aggregators (LinkedIn, Indeed, Glassdoor, etc.), listed in
  `internship_finder.excluded_domains`.
- Old cached search snippets can show a posting as open when the live career
  page has since closed or removed it — always confirm against the freshly
  extracted/snapshotted page, not the search snippet text.
- **ATS location fields are unreliable — never report a role as India-based
  on a blank/ambiguous location.** Greenhouse `location.name` can be just
  `"In-Office"` (Cloudflare) with an empty `locations: []` array; Workday's
  `locationsText` is often blank and its `searchText:"intern"` query is NOT
  location-filtered (Nvidia returned 40 interns, all US/EU — fetch each job's
  detail JSON `.../wday/cxs/<tenant>/<site>/job<path>` to get the real
  location, or drop the hit).
- **Title-only classification both misses and misincludes.** "Intern | Gift
  City" (Tower) turned out to be trading-desk support, and "ENG Project/
  Program - Intern" (Rubrik) is a PM role — neither is SWE/ML despite the
  wording. For borderline titles, fetch the Greenhouse job detail
  (`/jobs/<id>`) and check Responsibilities/Qualifications before including.
- **amazon.jobs is a dead end for scripted sweeps**: its `search.json` API
  silently ignores `base_location`/`country`/`keyword` filters (returns
  global results or 0), and the rendered page is client-side React that shows
  zero job links even under real CDP Chromium (bot-gated). Microsoft's
  `careers.microsoft.com/prod-api` refuses connections outright. Mark these
  "not verifiable via API" after ONE attempt each — don't burn calls.
- **Never name a scratch script after a stdlib module** (`inspect.py`,
  `json.py`, `types.py`, …) in the directory you run from — scrapling imports
  stdlib `inspect` at load time, silently picks up your file, and dies with a
  confusing ImportError far from the real cause.
- **Broaden the India city regex beyond the metros**: include Chandigarh,
  Gift City/Gandhinagar, Gurugram, Indore, Bhubaneswar, Trivandrum, Mysore,
  Nagpur, Vadodara + state names (Karnataka, Telangana, Haryana, Gujarat…).
  Zscaler's India office is Chandigarh and Tower's is Gift City — a
  Bangalore/Delhi/Mumbai-only filter drops real hits.
- **The CDP browser backend dies between sessions** (attached-Chrome mode).
  If `browser_exec` throws a *connection* error, relaunch headless Chrome on
  9222 per `## Browser Backend Setup` — but prefer the ATS-API path above,
  which needs no browser at all and is what made this sweep finish in one
  pass.

## Verification

- Every reported posting's link opens directly on the company's own domain or
  ATS instance (spot-check the domain against `internship_finder.excluded_domains`
  — none should match).
- Every reported posting is confirmed as an internship-level role from the
  page content itself, not inferred from the search query.
- No LinkedIn/Indeed/Glassdoor/other aggregator URL appears anywhere in the
  final report, either as a source or as a link.

## Browser Backend Setup (fixes the "connection error" failure mode)

`browser_exec` connects to a Chromium via CDP at `BU_CDP_URL`
(default `http://127.0.0.1:9222`). If nothing is listening there, every call
fails with a connection error. To make the backend available:

1. Pick a Chromium binary: bundled Playwright Chromium at
   `C:/Users/<user>/AppData/Local/ms-playwright/chromium-XXXX/chrome-win/chrome.exe`,
   or system Chrome at
   `C:/Program Files/Google/Chrome/Application/chrome.exe`.
2. Launch it (headless is fine) with CDP on 9222, using a **native Windows
   path** for the profile dir (MSYS-style `/d/...` paths get mangled and the
   profile fails to create — a silent failure that leaves no CDP listener):
   ```
   chrome.exe --headless=new --remote-debugging-port=9222 \
     --user-data-dir="D:/07_hermes_home/cache/browser-use/cdp-profile" \
     --no-first-run --no-default-browser-check --disable-gpu about:blank
   ```
   Keep this process running for the whole Hermes session.
3. Verify before searching:
   - `python -c "import socket;s=socket.socket();s.settimeout(3);s.connect(('127.0.0.1',9222));print('OK')"`
   - `/d/07_hermes_home/bin/browser-use doctor` should report `chrome running`
     and `daemon alive`.
   - A real `browser_exec` run that returns page text (not a connection
     error) confirms the fix.

**Durability caveat:** this is the "attach to your own Chrome" mode (Option B).
The launched Chrome process must stay running for the session; it does NOT
auto-relaunch after a full Hermes restart. If `browser_exec` starts failing
again after a restart, re-launch Chrome with the command in step 2 and
re-verify. A managed/local-engine mode that Hermes launches itself would be
more durable — prefer that if available in your install.
