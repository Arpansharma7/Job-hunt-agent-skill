[ats-platforms.md](https://github.com/user-attachments/files/32154157/ats-platforms.md)
# ATS Platforms — search patterns

Most company career pages are actually thin wrappers around one of these
Applicant Tracking Systems. Searching `site:` on the ATS domain, combined with
the company name, finds the live listing page directly — faster and more
reliable than crawling the marketing `/careers` page, which often just embeds
or links out to the ATS board.

These ATS domains are the company's **own** system — never treat them as
job-board aggregators to exclude.

| ATS | Domain pattern | Example query |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/<company>`, `job-boards.greenhouse.io/<company>` | `"<company>" site:greenhouse.io internship` |
| Lever | `jobs.lever.co/<company>` | `"<company>" site:lever.co intern` |
| Workday | `<company>.wd1.myworkdayjobs.com`, `.wd3.`, `.wd5.` etc. | `"<company>" site:myworkdayjobs.com internship` |
| Ashby | `jobs.ashbyhq.com/<company>` | `"<company>" site:jobs.ashbyhq.com intern` |
| SmartRecruiters | `careers.smartrecruiters.com/<company>` | `"<company>" site:smartrecruiters.com internship` |
| iCIMS | `<company>.icims.com` | `"<company>" site:icims.com internship` |
| Workable | `apply.workable.com/<company>` | `"<company>" site:workable.com intern` |
| BambooHR | `<company>.bamboohr.com/careers` | `"<company>" site:bamboohr.com internship` |
| Taleo (older enterprises) | `<company>.taleo.net` | `"<company>" site:taleo.net internship` |
| SAP SuccessFactors | `<company>.career.successfactors.com` | `"<company>" site:successfactors.com internship` |

## Notes on reliability

- Workday and iCIMS boards are almost always client-rendered — expect
  `web_extract` to come back thin and plan to fall back to
  `browser_navigate` + `browser_snapshot` for these two in particular.
- Greenhouse and Lever boards are frequently static HTML/server-rendered and
  usually extract cleanly with `web_extract` alone.
- Some large companies run separate ATS boards per region or per business
  unit (e.g. a distinct board for "early careers"/"university recruiting") —
  if a search for the main company name surfaces no internship-specific
  results, retry with "<company> early careers" or "<company> university
  program" appended, since interns are often siloed off the general board.
