# Market Pulse: trustworthy prices for energy traders

## The assignment

Build a small data pipeline that gives energy traders a trustworthy comparison of day-ahead and real-time electricity prices.

**Spend no more than four hours, including setup and documentation.** Stop at the time limit and describe anything unfinished. We want to understand how you reason, build, and make trade-offs, not how much unpaid time you can spend. A simple, understandable solution is preferable to a large platform.

No energy-market background or AWS account is required. All inputs are synthetic and supplied locally.

## The situation

An energy trading desk receives prices for two fictional trading locations, called hubs. Day-ahead (DA) prices cover one hour; real-time (RT) prices cover 15 minutes. All prices are in USD/MWh.

Traders ask: "How did real-time prices compare with day-ahead prices at each hub, and can I trust the comparison?"

The provider sometimes sends the same record again, delivers an interval late, or corrects a previously published price. Some records are malformed. A pipeline can finish successfully while the resulting report is still incomplete.

Your task is to build the local prototype and explain how you would operate an appropriately sized version on AWS. The comparison is a price difference, not a trading strategy or a profit-and-loss calculation.

## What to build

### 1. Ingest and maintain the latest valid prices

Read the supplied deliveries, normalize their timestamps, validate records, and persist a queryable dataset. Preserve earlier accepted data when a later batch arrives.

Use the provider's revision number to select the latest valid price for each market, hub, and interval. A replay or an older revision must not create duplicate prices or undo a correction. Keep invalid records identifiable with their source and rejection reason; do not silently discard them.

Use Python and SQL with tools you know. Python's standard library and SQLite, pandas or Polars with DuckDB, or local Spark are all acceptable. Spark is not expected. A database or queryable files are both fine.

The original fixtures can serve as the prototype's immutable raw layer; copying them into another folder is not necessary. Explain how a curated record can be traced back to its input.

### 2. Produce a trader-facing SQL result

Write and execute SQL that produces the hourly view defined in [DATA_CONTRACT.md](DATA_CONTRACT.md). Include every hub and hour in the configured report window, even when data is missing.

The view must show the DA price, the mean of available RT prices, interval completeness, and the RT-minus-DA difference. Only publish the difference when all four RT intervals and the DA price are available. Never replace a missing price with zero or invent an interval.

Export the small result to CSV or another easily readable format. A terminal result or data file is sufficient; do not build a dashboard or API.

### 3. Demonstrate repeatable behavior and data quality

Document a short command sequence that:

1. Starts with an empty output/state location and processes only `batch_01`.
2. Processes `batch_02` against that existing state.
3. Processes `batch_02` again without resetting state.

Save the hourly results after steps 1 and 2. Step 3 must leave the logical latest-price dataset and hourly results unchanged. Run identifiers, timestamps, and per-run logs may change.

Include a small run summary or structured log showing records read, rejected records, and the resulting data-quality situation. Distinguish a completed run from a complete trader report.

Add a few focused automated tests covering time aggregation, corrections/replays, and invalid or missing data. We value meaningful coverage, not a particular test count or framework.

## The AWS design brief

Provide one simple diagram and approximately one to two pages of notes. A text diagram is fine. Explain the services you would choose, their responsibilities, the data model/storage layout, and why that is enough.

Use these hypothetical production assumptions; you do not need to benchmark or implement them:

| Assumption | Requirement |
| --- | --- |
| Input | Vendor files arrive in an S3 landing location every 15 minutes. |
| Scale | 2,000 hubs: 96 RT intervals and 24 DA intervals per hub per day, about 240,000 logical prices/day before revisions. |
| Freshness | Newly landed data should be available to traders within five minutes of arrival. Late provider delivery must be distinguishable from pipeline delay. |
| Consumers | 50 internal traders, mainly filtering by hub and a one-to-seven-day window; aim for query responses within ten seconds. |
| History | Retain two years; corrections can arrive for the previous 14 days. |

Address all six AWS Well-Architected pillars briefly. For each, connect a concrete decision to this scenario and state a relevant trade-off or trigger for revisiting it. A six-row table is enough; definitions and an exhaustive checklist are not needed.

| Pillar | Question to consider |
| --- | --- |
| Operational excellence | How will someone know that a run completed but a hub's prices are missing, and what should they do? |
| Security | How will ingestion and trader access be separated, with appropriate protection for stored data and any future provider credentials? |
| Reliability | What happens after duplicate delivery or failure partway through publishing corrected data? |
| Performance efficiency | How will the layout and compute choice support the actual query and ingestion patterns? |
| Cost optimization | What would drive costs, and what would you avoid paying for at this scale? Exact AWS pricing is not required. |
| Sustainability | How would you avoid unnecessary processing, storage, or always-running capacity? |

Go a little deeper on reliability, operational excellence, and security. Explain one failure-and-recovery example and one important alternative you rejected. It is acceptable to defer a capability if you explain the risk and what would justify adding it.

You may consult the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html); this is not a memory test.

## What to submit

Submit your code, executable SQL, focused tests, initial and updated sample outputs, and the AWS design. Include a README with installation/run commands, dependencies or runtime version, approximate time spent, assumptions, and known limitations. State what you would do next if you had another hour; do not spend that extra hour.

Use a ZIP or a private repository shared through the recruiting process. Do not include credentials, employer code, or real market/vendor data. You do not need to publish your work publicly.

Documentation, web references, and AI assistance are allowed. Briefly disclose significant assistance and how you checked it. You should be able to explain and modify your submission during the discussion. Tool use itself is not a negative signal.

## How we will review it

All candidates receive the same exercise and criteria.

| Area | Weight |
| --- | --- |
| Data modeling, time handling, and result correctness | 30% |
| Working implementation, repeatability, and focused tests | 25% |
| Proportionate AWS architecture and Well-Architected judgment | 20% |
| Data trust, observability, and recovery thinking | 15% |
| Problem solving, prioritization, and clear explanations | 10% |

Expect a roughly 40-minute conversation about your own solution. We will discuss what works, your choices, limitations, and how you would improve it. This is not a hidden-puzzle exercise.

**Not required and not rewarded as extra scope:** AWS deployment, Terraform, Docker, CI/CD infrastructure, Kubernetes, streaming infrastructure, a UI, exhaustive framework coverage, performance tuning for the tiny fixture, or daylight-saving transition code. Explain production considerations instead of implementing them.

An indicative time budget is 20 minutes understanding/modeling, 110 minutes building the pipeline and SQL, 40 minutes exercising important cases, 50 minutes on the AWS brief and README, and 20 minutes packaging. Adjust it to your strengths. If setup becomes a barrier, tell recruiting rather than spending the whole assessment fighting tools.
