# AI Usage

> **Candidate: review and edit this file so it reflects what *you* actually did.** The draft below is accurate about
> what the AI did in this project; the bracketed parts are yours to fill in. You must be able to explain every part of the code.

## Tool used
**Claude (Anthropic)** - generated the first full version of the project from the assignment text.

## What it was used for
* Project structure, schema design and the pipeline architecture.
* Scrapers, HTTP client (retry/backoff/robots), cleaning, validation, deduplication, CLI.
* Unit and end-to-end tests, README and this file.

## Representative prompts
1. "Build the Python web scraping assignment described in this document" (the full assignment text was provided).
2. [EDIT: add your own follow-up prompts, e.g. "Why does the pagination href differ between page 1 and page 2 of Books to Scrape?"]

## AI-assisted parts
Essentially all code in this repository was AI-generated: [EDIT: list what you wrote, changed or refactored yourself].

## Changes after reviewing AI output
[EDIT: fill in from your own review. Things worth checking yourself:]
* Selectors against the live pages (`article.product_pod`, `li.next a`, `#product_description + p`, breadcrumb index 2, `div.author-description`).
* The dedup key and the decision to remove (not just flag) duplicates.
* The default rate limit and retry settings.

## Incorrect / incomplete AI output found
Found while testing the generated code:
* Directory creation script initially failed (shell brace expansion under `sh`) and was redone.
* One test had an off-by-one string slice (`[-6:]` vs `[-7:]`) - a test bug, not a code bug.
* `mongomock` was incompatible with the newest `pymongo` bulk API, so MongoDB writes use per-document upserts.
* Ratings were first exported as `3.0`; changed to integers.
* [EDIT: add anything you discover when running against the real sites.]

## Testing and verification
* 41 automated offline tests pass (`python -m pytest -q`).
* The full pipeline was run through the real HTTP client against a **local mock server** (3 pages per source, a transient 503, a case-variant duplicate); log in `logs/sample_run_LOCAL_MOCK_server.log`.
* **The AI environment could not reach books.toscrape.com / quotes.toscrape.com**, so the live run was NOT verified by the AI.
  [EDIT after running `python main.py` yourself: record the real counts - expected roughly 1,000 books and 100 quotes - and spot-check some rows against the websites.]
