# Automated Sprint Staffing Optimizer (QE-Predictor)
## In-Depth Documentation

### 1. Abstract
The Automated Sprint Staffing Optimizer (also known as QE-Predictor) is an advanced tool designed to solve the complex problem of pairing Quality Engineering (QE) and testing resources with sprint backlog items. By leveraging Natural Language Understanding (NLU) and Operations Research (Integer Linear Programming), the application dynamically matches tester skills, capacity, and proficiency against the required skills of incoming tasks. The tool minimises overall sprint duration and allows for continuous adaptation through a "Human-in-the-Loop" PM override system, ensuring staffing plans remain highly optimal and context-aware.

---

### 2. Modules in the Application
The application is architected into modular components, cleanly separating the user interface, data processing, optimization routines, and data persistence:

- **Frontend Interface (`app.py`)**: 
  A modern, glassmorphism-styled Streamlit application divided into 8 distinct tabs:
  1. *Dashboard*: High-level KPIs and visualizations (Task distributions, Tester workloads).
  2. *Upload Backlog*: CSV ingestion for sprint tasks.
  3. *Team Matrix*: Interactive grid for managing the tester roster and HR API syncing.
  4. *Analysis Engine*: Semantic classification of tasks to extract required skills.
  5. *Staffing Plan*: Execution of the ILP solver to generate assignments.
  6. *Gantt Chart*: Visual timeline of the proposed sprint schedule.
  7. *Utilization Heatmap*: Matrix showing tester capacity usage over the sprint days.
  8. *PM Override*: Manual task reassignment interface that records corrections for continuous learning.

- **NLU Engine (`src/classifier.py`)**:
  Handles the semantic tagging of task descriptions. It interacts with LLMs (Gemini or OpenAI) to extract required skills based on the existing tester matrix. It employs few-shot learning by injecting historical PM corrections into the prompt context. A regex/keyword fallback ensures robustness if APIs fail.

- **Staffing Optimizer (`src/optimizer.py`)**:
  Formulates the staffing problem as an Integer Linear Program (ILP) using the `PuLP` library. It guarantees that tasks are covered by skilled testers while respecting daily hour capacities and proficiency multipliers, optimising for the shortest overall sprint timeline.

- **Database Manager (`src/database.py`)**:
  A unified `SQLite` interface providing robust CRUD operations and automated schema initialization. It manages the relational integrity between `testers`, `tasks`, `assignments`, and PM `corrections`.

- **External Services (`services/api_stub.py`)**:
  Provides simulated HR endpoints to import employee records, acting as a placeholder for enterprise HRMS integration.

---

### 3. Major Technical Specifications
- **Core Language & Framework**: Python 3.10+, Streamlit (Frontend UI).
- **Optimization formulation**: `PuLP` library using the CBC backend solver.
- **AI / Semantic Analysis**:
  - `google-generativeai` utilizing the `gemini-2.0-flash` model.
  - `openai` utilizing the `gpt-4o-mini` model.
- **Data Manipulation**: `pandas` for dataframe operations, state management, and ETL bridging.
- **Visualizations**: `plotly.express`, `plotly.figure_factory`, and `plotly.graph_objects` for rendering interactive Gantt charts and Heatmaps.
- **Database**: `SQLite3` (local `staffing.db`) persisting data across stateless Streamlit reruns.

---

### 4. Design Considerations
- **Human-in-the-Loop Continuous Learning**: The system does not assume AI infallibility. The PM Override tab allows project managers to manually reassign tasks. These corrections are saved and automatically fed back into the LLM as few-shot prompt examples, allowing the AI to learn organizational quirks over time.
- **Idempotent Data Operations**: Functions saving pandas DataFrames to the database use deliberate `INSERT` and `UPDATE` strategies rather than destructive schema replacements, protecting SQLite `AUTOINCREMENT` primary keys and relational foreign keys.
- **Proficiency-Weighted Capacity**: The optimizer adjusts a tester's effective capacity based on their proficiency level (High = 1.0x, Mid = 0.75x, Low = 0.5x), reflecting the real-world scenario that juniors take longer to execute identical tasks.
- **Graceful Degradation**: If the configured LLM API keys are missing or the API rate-limits the user, the NLU engine seamlessly falls back to a deterministic `Keyword Only` parsing mechanism.

---

### 5. Future Plans
- **Enterprise Integrations**: Bi-directional integration with Jira, Azure DevOps, or Linear to automatically pull sprint backlogs and push approved assignments directly to task tickets.
- **Real HRMS Hooks**: Replace the `api_stub` with active endpoints connecting to Workday or BambooHR to dynamically fetch holiday schedules, PTO, and current availability.
- **Advanced Constraint Modeling**: Add optimizer constraints for geographical timezone overlaps (e.g., forcing testers to overlap at least 2 hours with developers) and context-switching penalties.
- **Multi-Sprint Forecasting**: Expand the ILP window to handle Epics and multi-sprint planning, forecasting hiring needs based on long-term backlog NLU analysis.
- **Containerization**: Provide a canonical `Dockerfile` and `docker-compose.yml` for simplified deployment in Kubernetes or ECS environments.
