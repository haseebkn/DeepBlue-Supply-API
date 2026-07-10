# DeepBlue Agentic Blueprint

This document acts as the master blueprint for the autonomous agent workflows, context programming, and unstructured data parsing pipeline within the **DeepBlue Supply API**. 

Our primary agentic goal is to ingest messy, unstructured technician field notes (e.g., *"Thruster oil seals leaking, need two neoprene O-rings size 4B from Parker immediately"*), parse them, check for errors, resolve exact inventory matches, and log structured data into the database.

---

## 1. Agentic Frameworks and Repositories Reference

Our autonomous agents leverage a set of foundational libraries and repositories to execute, reason, search, and self-correct. Below is the mapping of how these frameworks are integrated.

```
       [Unstructured Field Note]
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 1: Ingestion & Task Planning          │
│  - tasks-axi (Dynamic DAG breakdown)          │
│  - lavish-axi (LLM reasoning & prompt context)│
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 2: Part Search & Identification       │
│  - skills (Part catalog lookup skill)        │
│  - autoresearch (Web searching catalogs)     │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 3: Structured Extraction & Guardrails │
│  - treehouse (Pydantic / Structured JSON)   │
│  - no-mistakes (Validation retry loop)       │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 4: Feedback & DB Persistence          │
│  - gnhf (Human-in-the-loop fallback check)   │
│  - firstmate (Agent workspace orchestrator)  │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
     [Structured API Response & DB]
```

### 1.1. Reasoning and Execution Task Tracking
*   **[tasks-axi](https://github.com/kunchenguid/tasks-axi)**: Used to model the extraction sequence as a Directed Acyclic Graph (DAG) of micro-tasks (e.g., `[IdentifyAsset] -> [ExtractParts] -> [ValidatePartNumbers] -> [MatchInventory]`). If one task fails, the DAG executor handles dependencies and retries.
*   **[lavish-axi](https://github.com/kunchenguid/lavish-axi)**: Provides the execution environment and context management for the agents. It structures agent prompts, tracks system parameters, and injects runtime context (like database schemas and current inventory states) directly into the agent's prompt window.

### 1.2. Error-Correction and Execution Guardrails
*   **[no-mistakes](https://github.com/kunchenguid/no-mistakes)**: An error-correction layer that intercepts parsing errors. If the LLM generates a part number that is invalid or missing a digit, `no-mistakes` executes a self-reflection loop, feeding the error back to the LLM to auto-correct the string format before returning a failure.
*   **[firstmate](https://github.com/kunchenguid/firstmate)**: Acts as the primary agent workspace manager and executive supervisor. It monitors the latency and token usage of our extraction pipeline, handles API rate-limits, and coordinates standard skills.

### 1.3. Structured Generation & Human Feedback
*   **[treehouse](https://github.com/kunchenguid/treehouse)**: Focuses on structured JSON generation and strict schema constraints. It guarantees that the extraction agent conforms directly to the Pydantic schemas defined in our FastAPI code, avoiding raw string outputs or hallucinated fields.
*   **[gnhf](https://github.com/kunchenguid/gnhf)** (Generative Net Human Feedback): Handles Human-in-the-Loop (HITL) checkpoints. If the extraction confidence score falls below a threshold (e.g., 0.70) or a critical mismatch is detected, `gnhf` flags the report status as `pending_review` and creates a notification task for a supply coordinator to approve the match.

### 1.4. Skill Libraries & Autonomous Research
*   **[skills](https://github.com/anthropics/skills)**: A library of pre-built reusable tool sets (e.g., calculating structural metadata, formatting date-times, querying standard parts APIs).
*   **[autoresearch](https://github.com/karpathy/autoresearch)**: An autonomous web-search and documentation scraping tool. When a technician mentions an obscure part or manufacturer that is not in our local DB, `autoresearch` initiates a search, reads web documentation, and retrieves the correct serial number or manufacturer name to enrich the inventory match.

---

## 2. Unstructured Field Notes Parsing Pipeline

When a technician POSTs unstructured field notes to `/api/v1/extract`, the system runs the following pipeline:

1.  **Ingestion & Framing (`lavish-axi` / `tasks-axi`)**
    *   The API receives the raw string.
    *   `tasks-axi` spins up a workflow instance.
    *   `lavish-axi` injects context (e.g., current assets, active components, matching inventory categories).
2.  **Structured Extraction (`treehouse` / `skills`)**
    *   The LLM agent extracts critical information (asset name, condition, recommended actions, urgency, and parts needed).
    *   `treehouse` forces the LLM to output a clean JSON mapping directly to `ExtractedMaintenanceData`.
3.  **Part & Entity Resolution (`autoresearch` / `skills`)**
    *   The agent maps extracted parts against the existing database inventory using semantic similarity.
    *   If a part is not found locally, `autoresearch` checks vendor databases/catalogs online.
4.  **Error Correction (`no-mistakes`)**
    *   Extracted fields are run through database checks (e.g., checking if part formatting matches manufacturer patterns).
    *   If a mismatch occurs, `no-mistakes` requests a corrected extraction from the LLM.
5.  **Human Validation Check (`gnhf`)**
    *   If validation passes, the record is flagged `auto_approved` and committed to PostgreSQL.
    *   If confidence is low, `gnhf` routes it to `pending_review`.
6.  **Pipeline Orchestration (`firstmate`)**
    *   Tracks the state of all running extractions and feeds the final response back to the FastAPI endpoint.
