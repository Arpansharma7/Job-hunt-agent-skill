#!/usr/bin/env python
"""Career-page job sweep via company-owned ATS JSON APIs (no aggregators).

Usage:
  python ats_sweep.py                      # sweep the built-in slug list
  python ats_sweep.py zepto phonepe groww  # sweep specific ATS tokens only

Probes every slug against Greenhouse, Lever, Ashby and SmartRecruiters in
parallel — companies often use a token different from their brand name, and
guessing WHICH platform they use produces ~50% 404s, so probe all four.
Requires `scrapling` (already installed here); uses Fetcher only, no
browser/CDP. Filters to intern-level SWE/ML/GenAI roles located in India and
resolves blank/ambiguous Greenhouse locations via the job-detail endpoint.
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from scrapling.fetchers import Fetcher

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ROLE = re.compile(r"\b(intern|internship|co-?op|trainee)\b", re.I)
FIELD = re.compile(
    r"(software|swe|engineer|engineering|\bml\b|machine learning|data scien|"
    r"gen\s?ai|generative|\bai\b|artificial intelligence|research|algorithm|"
    r"quant|infra|backend|front[- ]?end|full[- ]?stack|platform|devops|\bsre\b|"
    r"analytics|\bdata\b)", re.I)
SKIP = re.compile(
    r"(recruit|talent acquisition|\bhr\b|human resources|marketing|sales|video|"
    r"youtube|content|social media|customer|support|success|financial|account|"
    r"legal|moderation|business development|operations|\bops\b|design|graphic|"
    r"writer|payroll|project/ ?program|trading|trade support)", re.I)
# Broad India matcher — metros + tier-2 + states (Chandigarh/Gift City matter:
# Zscaler's India office is Chandigarh, Tower's is Gift City).
INDIA = re.compile(
    r"(india|bengaluru|bangalore|gurgaon|gurugram|\bgyr\b|noida|delhi|"
    r"gandhinagar|gift city|chandigarh|pune|hyderabad|chennai|mumbai|kochi|"
    r"cochin|ahmedabad|indore|bhubaneswar|trivandrum|thiruvananthapuram|"
    r"mysore|mysuru|nagpur|vadodara|karnataka|maharashtra|telangana|haryana|"
    r"tamil nadu|gujarat|uttar pradesh|kerala)", re.I)
ABROAD = re.compile(
    r"(united states|\busa?\b|san francisco|\bsf\b|seattle|new york|"
    r"\bny\b|boston|austin|dallas|atlanta|london|dublin|europe|amsterdam|paris|"
    r"geneva|toronto|canada|singapore|sydney|hong kong|shanghai|tokyo|japan|"
    r"germany|poland|bucharest|romania|remote -|skillbridge)", re.I)


def jget(url, tries=3):
    for _ in range(tries):
        try:
            r = Fetcher.get(url, timeout=40, headers={"User-Agent": UA})
            if r.status == 200:
                return json.loads(r.body)
            if r.status in (400, 403, 404):
                return None
        except Exception:
            time.sleep(1)
    return None


def greenhouse(tok):
    d = jget(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs")
    if not d or "jobs" not in d:
        return None
    return [{"t": x.get("title", ""),
             "l": (x.get("location") or {}).get("name", ""),
             "u": x.get("absolute_url", ""), "p": "greenhouse",
             "tok": tok, "id": x.get("id")} for x in d["jobs"]]


def lever(tok):
    d = jget(f"https://api.lever.co/v0/postings/{tok}?mode=json")
    if not isinstance(d, list) or not d:
        return None
    return [{"t": x.get("text", ""),
             "l": (x.get("categories") or {}).get("location", ""),
             "u": x.get("hostedUrl", ""), "p": "lever"} for x in d]


def ashby(tok):
    d = jget(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
    if not d or "jobs" not in d:
        return None
    return [{"t": x.get("title", ""), "l": x.get("location", ""),
             "u": x.get("jobUrl") or x.get("applyUrl", ""), "p": "ashby"}
            for x in d["jobs"]]


def smartrec(tok):
    d = jget(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100")
    if not d or "content" not in d:
        return None
    items = list(d["content"])
    pages = min((d.get("totalFound", 0) + 99) // 100, 12)
    for p in range(1, pages):
        dd = jget(f"https://api.smartrecruiters.com/v1/companies/{tok}"
                  f"/postings?limit=100&offset={p * 100}")
        if dd and "content" in dd:
            items += dd["content"]
        else:
            break
    out = []
    for x in items:
        L = x.get("location") or {}
        out.append({"t": x.get("name", ""),
                    "l": f"{L.get('city', '')}, {L.get('country', '')}".strip(", "),
                    "u": f"https://jobs.smartrecruiters.com/{tok}/{x.get('id', '')}",
                    "p": "smartrecruiters"})
    return out


def keep(c):
    t = c["t"]
    if not ROLE.search(t) or SKIP.search(t) or not FIELD.search(t):
        return False
    # Location check happens AFTER resolve_gh_location() fills in blanks.
    return True


def resolve_gh_location(c):
    """Greenhouse location.name can be blank/'In-Office' — fetch job detail."""
    if c["p"] != "greenhouse" or not c.get("id"):
        return c
    if c["l"] and INDIA.search(c["l"]):
        return c
    d = jget(f"https://boards-api.greenhouse.io/v1/boards/{c['tok']}/jobs/{c['id']}")
    if d:
        offices = "; ".join(o.get("name", "") for o in d.get("offices", []))
        if offices:
            c["l"] = f"{c['l']} | {offices}".strip(" |")
    return c


DEFAULT_SLUGS = """
zepto blinkit phonepe cred meesho navi groww upstox jupiter razorpay slice bharatpe
paytm finmo smallcase kwik setu juspay refyne zolve neysa sarvam krutrim sharechat moj
dream11 zupee games24x7 winzo getmyhotels makemytrip yatra oyo lenskart flipkart
freescale freshworks zoho chargebee hasura postman keka mygate unacademy physicswallah
byjus vedantu simplilearn upgrad geeksforgeeks scaler inmobi gliff mobilejump woxo
zomato swiggy bigbasket porter shipsy dunzo rapidleash locus shadowfax yubi amerity
boomi highradius kinara leeway haptik yellowai netomi m2p nium cashfree dreamdev zeta
saarthi amdocs commvault nutanix sprinklr linkedin amazon microsoft google meta apple
oracle ibm intel qualcomm cisco servicenow adobe autodesk atlassian workday intuit
netsuite salesforce twilio mulesoft mongodb elastic grafanlabs gitlab cloudflare
zscaler paloaltonetworks crowdstrike datadoghq newrelic splunk vmware citrix netapp
broadcom amd nvidia uber lyft airbnb booking stripe paypal square brex plaid circle
coinbase gemini kraken ripple twosigma jane hudsonriver point725 deshaw millennium
susquehanna optiver flowtraders xtom quadeye aiven confluent dbt dremio starburst
verta towerresearchcapital rubrik medianet angelone rappi nuvama myglamm sonyliv
nykaa cars24 spinny olacabs pharmeasy wego openai anthropic anysphere perplexityai
mistral scale replicate huggingface pika elevenlabs lovable windsurf glean sierra
cognition poolside together sambanova coreweave lambda deepinfra fireworks modal
temporal clickhouse langchain wandb atherenergy kreditbee
""".split()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    slugs = sorted(set(a.lower() for a in args)) if args else DEFAULT_SLUGS
    print(f"probing {len(slugs)} slugs x 4 ATS platforms ...")

    jobs = []
    for s in slugs:
        for fn in (greenhouse, lever, ashby, smartrec):
            jobs.append((s, fn))

    def run(item):
        s, fn = item
        try:
            return s, fn.__name__, fn(s)
        except Exception:
            return s, fn.__name__, None

    boards = {}
    with ThreadPoolExecutor(max_workers=32) as ex:
        for s, plat, data in ex.map(run, jobs):
            if data:
                boards.setdefault(s, {"plats": [], "jobs": []})
                boards[s]["plats"].append(f"{plat}({len(data)})")
                boards[s]["jobs"] += data

    print(f"live boards: {len(boards)} / {len(slugs)}\n" + "=" * 72)
    n = 0
    empty, no_interns = [], []
    for s in sorted(boards):
        allj = boards[s]["jobs"]
        interns = [x for x in allj if ROLE.search(x["t"])]
        inscope = [x for x in interns if keep(x)]
        # resolve blank/ambiguous GH locations, then apply the India filter
        fixed = []
        for c in inscope:
            c = resolve_gh_location(c)
            if INDIA.search(c.get("l", "")):
                fixed.append(c)
        if fixed:
            print(f"\n### {s}  [{', '.join(boards[s]['plats'])}]")
            for c in fixed:
                n += 1
                print(f"  - {c['t']}  |  {c['l']}  |  {c['p']}")
                print(f"    {c['u']}")
        elif not interns:
            empty.append(s)
        else:
            no_interns.append(f"{s}({len(interns)})")

    print("\n" + "=" * 72)
    print(f"TOTAL in-scope India SWE/ML/GenAI intern roles: {n}")
    print(f"\nBoards with interns but none in scope: {', '.join(no_interns)}")
    print(f"\nBoards live, ZERO intern postings: {', '.join(empty)}")
    missed = sorted(set(slugs) - set(boards))
    print(f"\nNo board for slug (wrong token or not on these 4 ATS): {', '.join(missed)}")
    print("\nNOTE: borderline titles (bare 'Intern', 'ENG Program Intern', trading-"
          "support) need a job-detail content check before reporting — see SKILL.md "
          "pitfalls. amazon.jobs / Microsoft careers APIs are known dead ends.")


if __name__ == "__main__":
    main()
