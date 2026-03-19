# QE-Predictor: Sprint Staffing Intelligence Tool

A Streamlit application that intelligently predicts QA staffing needs based on sprint backlog items. It uses keyword-based classification, optional LLM augmentation (Gemini/OpenAI), and sprint-maturity heuristics to recommend the right testers for each sprint.

## System Architecture

```mermaid
graph TD
    %% Inputs
    subgraph Inputs ["1. Inputs Layer"]
        B[Sprint Backlog CSV] --> |Story Details| UI
        T[Team Matrix CSV] --> |Skills & Availability| UI
    end

    %% UI & Controller
    subgraph Streamlit ["2. Frontend & Controller (app.py)"]
        UI[Streamlit UI Dashboard]
        DB[(Skills SQLite DB)]
        T --> DB
        DB -.-> |Persisted Data| UI
    end

    %% AI Engine
    subgraph AI ["3. Classification Engine (classifier.py)"]
        UI -->|Analyze Stories| CL[Task Classifier]
        CL -.-> |Offline Mode| KW[Keyword Matching Logic]
        CL -.-> |LLM Mode| LLM[Gemini / OpenAI API]
        KW --> |Assigned Tester Types| CL
        LLM --> |Assigned Tester Types| CL
    end

    %% Staffing Engine
    subgraph Logic ["4. Staffing Logic (staffing_engine.py)"]
        CL --> |Classified Backlog| SE[Staffing Engine]
        DB --> |Available Testers| SE
        
        SE --> |Apply Rules| Rules{Sprint Maturity Rules}
        Rules --> |e.g., Skip Security in Sprint 1| Calc[Calculate Headcount & Allocate Hours]
    end

    %% Outputs
    subgraph Outputs ["5. Outputs"]
        Calc --> |Recommendations| UI
        UI --> D1[Resource Allocation Dashboard]
        UI --> D2[Specific Tester Assignments]
    end
    
    %% Styling
    classDef ui fill:#4bc0c0,stroke:#333,stroke-width:2px,color:#fff;
    classDef logic fill:#ff9f40,stroke:#333,stroke-width:2px,color:#fff;
    classDef db fill:#ffcd56,stroke:#333,stroke-width:2px,color:#333;
    classDef ai fill:#9966ff,stroke:#333,stroke-width:2px,color:#fff;
    
    class UI,D1,D2 ui;
    class SE,Rules,Calc logic;
    class DB,B,T db;
    class CL,KW,LLM ai;
```

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. (Optional) Copy `.env.example` to `.env` and add your API keys:
   ```bash
   cp .env.example .env
   ```
   *Note: Without an API key, the tool will fall back to keyword-based classification.*

## Running the App

Start the Streamlit development server:

```bash
streamlit run app.py
```

## How It Works

1. **Upload Backlog**: Upload a CSV of your sprint tasks containing `Title`, `Description`, `Story Points`, and `Sprint Number`. (See `sample_data/sample_backlog.csv`).
2. **Upload Testers**: Upload a CSV of your available testers with `Name`, `Type`, `Proficiency`, and `Available Hours`. (See `sample_data/sample_testers.csv`).
3. **Run Analysis**: The app classifies each User Story (Manual, Automation, Performance, Security, Accessibility) and applies heuristics.
4. **View Recommendations**: Explore the Dashboard to see recommended team composition and task-level assignments.
