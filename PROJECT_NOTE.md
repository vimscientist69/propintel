# 🧠 PropIntel — Real Estate Lead Intelligence Platform (MVP)

- [x] leads_20260326_134940.json serper website html validation logic is incorrect, as first lead "Southern Cape Properties" has a website, but website is not found.
- [x] Test other sample inputs as well for basic website enrichment

---

Update project on portfolio, LinkedIn and Upwork

## 🎯 Goal

Build a **production-style lead intelligence system** that takes structured real estate data (e.g. from PropFlux or CSV input), enriches it using multiple external sources, verifies contact information, and produces **high-quality, scored leads** ready for outreach or CRM systems.

This project will serve as a **portfolio-quality reference** for:

- lead generation systems  
- data enrichment pipelines  
- automation + API-based backend systems  

---

# 🧩 MVP Scope

## Supported Inputs (initial)

1. PropFlux output (native integration)  
2. CSV file (flexible schema)  

> Note: Input should contain at minimum:
- business / agency name OR listing context  
- optional website or location  

---

# 📥 Input

The system should accept:

- CSV file upload  
- JSON input (optional)  
- PropFlux output (direct ingestion)  

Example:
```

POST /upload
POST /jobs

```
---

# 📤 Output

The system must output **enriched and structured lead data** in:

- CSV file  
- JSON file  
- SQLite database (optional)  

### Fields to Extract / Generate

Each lead should include:

- `company_name`  
- `agent_name` (if available)  
- `website`  
- `email`  
- `phone`  
- `location`  
- `source` (origin of data)  
- `confidence_score`  

### Enrichment Fields

- `has_chatbot` (Yes/No)  
- `website_speed_score` (optional basic)  
- `last_updated_signal` (approximate)  
- `contact_quality` (verified / likely / low)  

### Lead Intelligence

- `lead_score` (0–100)  
- `lead_reason` (explanation for score)  

---

# 🧠 Core Features

## 1. Multi-Source Enrichment

For each lead:

- scrape website for emails/phones  
- fetch Google Maps data (business info, phone, validation)  
- optionally cross-check basic registry info  

---

## 2. Cross-Referencing

- match entities across sources  
- merge data into a single profile  
- remove inconsistencies  

---

## 3. Contact Extraction

- extract emails from HTML  
- extract phone numbers  
- normalize formats  

---

## 4. Verification Logic

- email: regex + domain validation  
- phone: format + region consistency  
- assign confidence levels  

---

## 5. Lead Scoring

Score based on:

- missing chatbot / automation  
- outdated website signals  
- missing or weak contact info  
- business activity indicators  

---

## 6. Deduplication

- remove duplicates based on:
  - website  
  - company name  
  - phone/email  

---

## 7. Logging

Track:

- enrichment progress  
- sources used per lead  
- failures / missing data  
- total leads processed  

---

## 8. Retry & Error Handling

- retry failed requests  
- skip invalid sources  
- continue processing pipeline safely  

---

# ⚙️ Architecture

```
/backend
    api/
        routes.py
        jobs.py

    services/
        enrichment.py
        scraper.py
        verifier.py
        scorer.py

    core/
        parser.py
        normalizer.py
        deduplicator.py

/frontend
    dashboard/

/config
    sources.yaml

/output
    leads.csv
    leads.json

runner.py
requirements.txt
README.md
```

---

# 🛠 Tech Stack

- Python 3.11+  
- FastAPI (API layer)  
- Requests / BeautifulSoup (scraping)  
- Playwright (optional dynamic extraction)  
- pandas (data processing)  
- PostgreSQL (storage)  
- Next.js (dashboard frontend)  
- Docker (optional)  
- Railway / Render (deployment)  

---

# 🔧 Config System

Create a config file:
```

/config/sources.yaml

````
Example:

```yaml
sources:
  website:
    email_selectors:
      - "mailto:"
      - ".contact-email"
    phone_patterns:
      - "+27"
      - "+1"

  google_maps:
    enabled: true
````

This allows easy extension to new enrichment sources.

---

# **🚀 API Endpoints**

Core endpoints:

```
POST /upload
POST /jobs
GET /jobs/{id}
GET /results/{id}
```

Responsibilities:
- trigger enrichment jobs
- fetch results
- manage input data

---

# 🖥 CLI Interface

The tool should be executable via CLI from `runner.py` with explicit arguments:

```bash
python runner.py api --host 127.0.0.1 --port 8000 --reload
python runner.py run --input data/leads.csv --input-format csv --config config/sources.yaml --output output/run_summary.txt
```

### CLI Requirements

- single CLI entrypoint (`runner.py`)
- subcommands for API mode and pipeline mode
- support configurable host, port, log level, and reload flag for API
- support configurable input path, input format, config path, and output path for pipeline
- CLI arguments should be documented in `README.md`

---

# **📊 Dashboard (Frontend)**

Features:
- upload dataset
- run enrichment job
- view enriched leads
- filter by lead score
- export results

---

# **📦 Deliverables (for portfolio)**

The final project must include:
- working enrichment system
- API endpoints
- dashboard UI
- clean structured output
- sample dataset
- README with usage instructions
- deployed version (cloud)

---

# **🧪 Example Output (CSV)**

| **company** | **email**    | **phone** | **website** | **score** | **reason**                |
| ----------- | ------------ | --------- | ----------- | --------- | ------------------------- |
| XYZ Realty  | info@xyz.com | +27…      | xyz.com     | 82        | No chatbot, outdated site |

---

# **🧱 Development Plan (3–4 weeks, ~10h/week)**

## **Week 1**

- [x] input system (CSV + schema handling)
- [x] basic website enrichment

## **Week 2**

- [x] Google Maps integration
- [x] contact extraction + normalization

## **Week 3**

- [x] verification logic
- [ ] lead scoring system
- [ ] API endpoints

## **Week 4**

- [ ] dashboard
- [ ] deployment
- [ ] polish + documentation

---

# **🧠 Future Enhancements (Optional)**

- [ ] email validation APIs
- [ ] LinkedIn enrichment
- [ ] CRM integrations (HubSpot, Pipedrive)
- [ ] scheduling / recurring jobs
- [ ] multi-region scaling

---

# **💼 How This Will Be Used**

This project will be referenced in job proposals as:

> “A multi-source lead intelligence platform that enriches, verifies, and scores real estate leads using automated data pipelines and APIs.”

This demonstrates:
- real-world data enrichment capability
- backend/API system design
- automation workflows
- business-focused engineering

---

# **✅ Definition of Done (MVP)**

The MVP is complete when:
- input data is processed correctly
- leads are enriched from multiple sources
- contact info is extracted + validated
- lead scoring works
- API + dashboard function correctly
- system runs end-to-end without manual fixes

---

# **🧭 Guiding Principles**

- Focus on business value, not just data
- Keep architecture simple but scalable
- Build reusable enrichment components
- Design for extension (new sources later)

---

# **🎯 End Result**

A **production-grade lead intelligence system** you can confidently show to clients to win jobs in:
- lead generation
- data enrichment
- web scraping + automation
- backend/API development
- real estate data pipelines