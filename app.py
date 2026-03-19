"""
app.py — Automated Sprint Staffing Optimizer
============================================
Streamlit app with 8 tabs:
  Dashboard | Upload Backlog | Team Matrix | Analysis Engine |
  Staffing Plan | Gantt Chart | Utilization Heatmap | PM Override
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# --- Local modules ---
from src.classifier import TaskClassifier
from src.optimizer import StaffingOptimizer
from src.database import (
    init_db, load_testers_df, save_testers_from_df, clear_testers,
    save_tasks_from_df, load_tasks_df, save_assignments, load_assignments_df,
    save_correction, load_corrections_df,
)
from services.api_stub import get_employees, get_departments

init_db()

# ============================================================
# Page Config & Global Styling
# ============================================================
st.set_page_config(page_title="Sprint Staffing Optimizer", page_icon="🚀", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.1);
}
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

.main-header {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.sub-header { color: #94a3b8; font-size: 1rem; margin-bottom: 1.5rem; }

/* Glassmorphism cards */
.kpi-card {
    background: rgba(255,255,255,0.07);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 16px;
    padding: 22px 18px;
    text-align: center;
    transition: transform .2s ease, box-shadow .2s ease;
}
.kpi-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(0,0,0,.4); }
.kpi-value  { font-size: 2.4rem; font-weight: 700; color: #a78bfa; }
.kpi-label  { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }

/* Status badges */
.badge-not-started { background:#334155; color:#94a3b8; padding:2px 10px; border-radius:999px; font-size:0.78rem; }
.badge-in-progress { background:#1e3a5f; color:#60a5fa; padding:2px 10px; border-radius:999px; font-size:0.78rem; }
.badge-complete    { background:#14532d; color:#4ade80; padding:2px 10px; border-radius:999px; font-size:0.78rem; }
.badge-accepted    { background:#3b0764; color:#c084fc; padding:2px 10px; border-radius:999px; font-size:0.78rem; }

/* Override data_editor dark */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* Tab styling */
div[data-baseweb="tab-list"] button { font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Session State
# ============================================================
defaults = {
    "backlog_df": None,
    "classified_df": None,
    "optimizer_result": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.divider()

    st.markdown("### AI Provider")
    provider = st.selectbox("Classification Engine", ["Keyword Only", "Gemini", "OpenAI"],
                            label_visibility="collapsed")

    if provider == "Gemini":
        key = st.text_input("Gemini API Key", type="password",
                            value=os.getenv("GEMINI_API_KEY", ""), placeholder="AIza...")
        if key:
            os.environ["GEMINI_API_KEY"] = key
    elif provider == "OpenAI":
        key = st.text_input("OpenAI API Key", type="password",
                            value=os.getenv("OPENAI_API_KEY", ""), placeholder="sk-...")
        if key:
            os.environ["OPENAI_API_KEY"] = key

    st.divider()
    st.markdown("### HR API Stub")
    if st.button("📡 Load from HR API", use_container_width=True):
        employees = get_employees()
        hr_df = pd.DataFrame([{
            "name": e["name"],
            "experience_years": e["experience_years"],
            "skills": ", ".join(e["skills"]),
            "proficiency": e["proficiency"],
            "available_hours": e["available_hours_per_week"],
        } for e in employees])
        save_testers_from_df(hr_df)
        st.success(f"Loaded {len(hr_df)} employees from HR API.")
        st.rerun()

    st.divider()
    st.markdown("### Sprint Maturity")
    apply_maturity = st.checkbox("Filter roles by sprint maturity", value=False,
                                 help="Suppress non-functional testing roles in early sprints.")

# ============================================================
# Header
# ============================================================
st.markdown('<div class="main-header">🚀 Automated Sprint Staffing Optimizer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Hybrid Intelligence: Gemini + PuLP ILP · PM Override · Learning Loop</div>', unsafe_allow_html=True)

# ============================================================
# Tabs
# ============================================================
(tab_dash, tab_backlog, tab_team, tab_analysis,
 tab_plan, tab_gantt, tab_heat, tab_pm) = st.tabs([
    "🏠 Dashboard", "📋 Backlog", "👥 Team Matrix",
    "🤖 Analysis", "📊 Staffing Plan",
    "📅 Gantt Chart", "🔥 Heatmap", "✏️ PM Override",
])


# ====================================================================
# TAB 1 — Dashboard
# ====================================================================
with tab_dash:
    testers_count = len(load_testers_df())
    backlog_count  = len(st.session_state.backlog_df) if st.session_state.backlog_df is not None else 0
    classified    = st.session_state.classified_df
    assignments   = load_assignments_df()

    kpi_cols = st.columns(4)
    kpis = [
        ("Testers Loaded", testers_count, "👥"),
        ("Backlog Tasks",  backlog_count,  "📋"),
        ("Classified",     len(classified) if classified is not None else 0, "🤖"),
        ("Assignments",    len(assignments), "✅"),
    ]
    for col, (label, val, icon) in zip(kpi_cols, kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-value">{icon} {val}</div>
              <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        if classified is not None and "Required Skills" in classified.columns:
            st.markdown("#### Task Skill Distribution")
            all_skills = []
            for s in classified["Required Skills"]:
                all_skills.extend([x.strip() for x in str(s).split(",") if x.strip()])
            if all_skills:
                skill_counts = pd.Series(all_skills).value_counts().reset_index()
                skill_counts.columns = ["Skill", "Count"]
                fig = px.pie(skill_counts, values="Count", names="Skill", hole=0.45,
                             color_discrete_sequence=px.colors.sequential.Purp)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#e0e0e0", margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Run Analysis to see skill distribution.")
        else:
            st.info("Upload a backlog and run Analysis to see the skill distribution chart.")

    with c2:
        if not assignments.empty:
            st.markdown("#### Tester Workload (Allocated Hours)")
            agg = assignments.groupby("tester_name")["allocated_hours"].sum().reset_index()
            fig2 = px.bar(agg, x="tester_name", y="allocated_hours",
                          color="allocated_hours",
                          color_continuous_scale="Viridis",
                          labels={"tester_name": "Tester", "allocated_hours": "Allocated Hours"})
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#e0e0e0", margin=dict(t=20, b=20),
                               showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Run the optimizer (Staffing Plan tab) to see workload distribution.")

    corrections_df = load_corrections_df()
    if not corrections_df.empty:
        st.markdown("#### Recent PM Corrections")
        st.dataframe(corrections_df[["task_description", "original_tester",
                                     "corrected_tester", "pm_notes", "created_at"]]
                     .head(5), use_container_width=True)


# ====================================================================
# TAB 2 — Upload Backlog
# ====================================================================
with tab_backlog:
    st.subheader("Upload Sprint Backlog")
    st.markdown("""
    **Required columns:** `Sprint Commitment`, `Status`, `Task Description`
    
    Status values: `Not Started` · `In Progress` · `Complete` · `Accepted`
    """)

    up_file = st.file_uploader("Drop your backlog CSV here", type="csv", key="backlog_upload")
    if up_file:
        try:
            df = pd.read_csv(up_file)
            req = ["Sprint Commitment", "Status", "Task Description"]
            missing = [c for c in req if c not in df.columns]
            if missing:
                st.error(f"Missing columns: {missing}")
            else:
                st.session_state.backlog_df = df
                st.success(f"✅ Loaded **{len(df)}** tasks.")
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📂 Load Sample Backlog", use_container_width=True):
                df = pd.read_csv("sample_data/sample_backlog.csv")
                st.session_state.backlog_df = df
                st.success(f"Sample backlog loaded ({len(df)} tasks).")
                st.dataframe(df, use_container_width=True)
        with col_b:
            if st.session_state.backlog_df is not None:
                csv_bytes = st.session_state.backlog_df.to_csv(index=False).encode()
                st.download_button("⬇️ Download Current Backlog", csv_bytes,
                                   "backlog.csv", "text/csv", use_container_width=True)


# ====================================================================
# TAB 3 — Team Matrix
# ====================================================================
with tab_team:
    st.subheader("Tester Skill Matrix")
    st.markdown("""
    **Required CSV columns:** `Name`, `Experience`, `Skills` *(comma-separated)*, `Proficiency` *(Low/Mid/High)*, `Available Hours`
    """)

    db_df = load_testers_df()
    display_df = db_df.rename(columns={
        "name": "Name", "experience_years": "Experience",
        "skills": "Skills", "proficiency": "Proficiency",
        "available_hours": "Available Hours",
    }) if not db_df.empty else pd.DataFrame(
        columns=["Name", "Experience", "Skills", "Proficiency", "Available Hours"])

    # Proficiency as a select column
    proficiency_options = ["Low", "Mid", "High"]

    edited = st.data_editor(
        display_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Proficiency": st.column_config.SelectboxColumn(
                "Proficiency", options=proficiency_options, required=True),
            "Available Hours": st.column_config.NumberColumn(
                "Available Hours", min_value=1, max_value=168, step=1),
            "Experience": st.column_config.NumberColumn(
                "Experience (yrs)", min_value=0, max_value=40, step=1),
        },
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Save Changes", use_container_width=True):
            save_testers_from_df(edited)
            st.success("Database updated!")

    with col2:
        t_file = st.file_uploader("Upload Testers CSV", type="csv", key="tester_upload",
                                  label_visibility="collapsed")
        if t_file:
            new_t = pd.read_csv(t_file)
            save_testers_from_df(new_t)
            st.success("Imported!")
            st.rerun()

    with col3:
        sub_cols = st.columns(2)
        with sub_cols[0]:
            if st.button("📂 Sample Testers", use_container_width=True):
                new_t = pd.read_csv("sample_data/sample_testers.csv")
                save_testers_from_df(new_t)
                st.success("Loaded!")
                st.rerun()
        with sub_cols[1]:
            if st.button("🗑️ Clear DB", type="secondary", use_container_width=True):
                clear_testers()
                st.rerun()


# ====================================================================
# TAB 4 — Analysis Engine
# ====================================================================
with tab_analysis:
    st.subheader("Task Skill Tagging — Semantic Layer")
    st.markdown(f"**Engine:** `{provider}` · Reads Task Descriptions → Tags with required Skills from matrix")

    if st.session_state.backlog_df is None:
        st.warning("Upload a backlog first in the **Backlog** tab.")
    else:
        backlog = st.session_state.backlog_df.copy()
        st.caption(f"{len(backlog)} tasks ready for classification.")

        if st.button("🚀 Start Analysis", type="primary"):
            testers_for_skills = load_testers_df()
            all_skills: list[str] = []
            for sk_str in testers_for_skills["skills"].dropna():
                all_skills.extend([s.strip() for s in str(sk_str).split(",") if s.strip()])
            skill_list = list(set(all_skills))

            classifier = TaskClassifier(provider=provider, skill_list=skill_list)
            results = []
            bar = st.progress(0, text="Classifying tasks…")

            for idx, (_, row) in enumerate(backlog.iterrows()):
                desc = row.get("Task Description", "")
                res  = classifier.classify(desc)
                results.append({
                    "Sprint Commitment": row.get("Sprint Commitment", f"T{idx+1}"),
                    "Status":           row.get("Status", "Not Started"),
                    "Task Description": desc,
                    "Required Skills":  ", ".join(res.get("skills", ["Manual Testing"])),
                    "Confidence":       res.get("confidence", "Unknown"),
                    "AI Reasoning":     res.get("reasoning", ""),
                })
                bar.progress((idx + 1) / len(backlog),
                             text=f"Classified {idx+1}/{len(backlog)}")

            classified_df = pd.DataFrame(results)
            st.session_state.classified_df = classified_df
            save_tasks_from_df(classified_df)
            st.success("✅ Classification complete!")

        if st.session_state.classified_df is not None:
            st.dataframe(
                st.session_state.classified_df,
                use_container_width=True,
                column_config={
                    "AI Reasoning": st.column_config.TextColumn(width="large"),
                    "Confidence":   st.column_config.TextColumn(width="small"),
                },
            )


# ====================================================================
# TAB 5 — Staffing Plan (PuLP)
# ====================================================================
with tab_plan:
    st.subheader("Optimization Layer — PuLP ILP Solver")
    st.markdown("""
    Minimises total sprint duration subject to:
    - **Capacity**: `Σ effort(j) · x(i,j) ≤ capacity(i)` ∀ tester *i*
    - **Coverage**: at least one tester per task
    - **Skill match**: tester must have ≥1 overlapping skill
    - **Proficiency multiplier**: High=1.0× · Mid=0.75× · Low=0.5×
    """)

    if st.session_state.classified_df is None:
        st.warning("Run Analysis first so tasks have skill tags.")
    else:
        if st.button("⚙️ Run Optimizer", type="primary"):
            testers_df = load_testers_df()
            tasks_df   = st.session_state.classified_df.copy().rename(columns={
                "Sprint Commitment": "sprint_commitment",
                "Status":           "status",
                "Task Description": "task_description",
                "Required Skills":  "required_skills",
            })

            if testers_df.empty:
                st.error("No testers in the database. Load them via the Team Matrix tab.")
            else:
                with st.spinner("Solving ILP…"):
                    opt = StaffingOptimizer(tasks_df, testers_df)
                    result = opt.solve()

                st.session_state.optimizer_result = result
                assignments_list = []
                if not result["assignments"].empty:
                    for _, r in result["assignments"].iterrows():
                        assignments_list.append({
                            "task_id":        int(r.get("task_index", 0)),
                            "tester_id":      int(r.get("tester_index", 0)),
                            "allocated_hours": float(r.get("allocated_hours", 0)),
                            "start_day":       int(r.get("start_day", 0)),
                            "end_day":         int(r.get("end_day", 0)),
                        })
                    save_assignments(assignments_list)

                st.success(f"✅ Solver status: **{result['status']}**")

        result = st.session_state.optimizer_result
        if result and not result["assignments"].empty:
            asgn = result["assignments"]
            st.markdown("#### Assignment Table")
            show_cols = ["sprint_commitment", "task_description", "required_skills",
                         "effort_hours", "tester_name", "proficiency",
                         "allocated_hours", "start_day", "end_day"]
            st.dataframe(asgn[[c for c in show_cols if c in asgn.columns]],
                         use_container_width=True)

            # Summary per tester
            st.markdown("#### Tester Load Summary")
            summary = asgn.groupby(["tester_name", "proficiency"]).agg(
                tasks_assigned=("task_description", "count"),
                total_hours=("allocated_hours", "sum"),
            ).reset_index()
            st.dataframe(summary, use_container_width=True)
        elif result:
            st.warning(f"Solver returned status `{result['status']}` with no assignments. "
                       "Check that testers have skills matching the classified tasks.")


# ====================================================================
# TAB 6 — Gantt Chart
# ====================================================================
with tab_gantt:
    st.subheader("Proposed Sprint Schedule — Gantt View")

    result = st.session_state.optimizer_result
    if result is None or result["assignments"].empty:
        st.info("Run the optimizer in the **Staffing Plan** tab to generate a Gantt chart.")
    else:
        asgn = result["assignments"].copy()
        sprint_start = datetime(2026, 3, 18)   # today

        gantt_data = []
        for _, r in asgn.iterrows():
            start = sprint_start + timedelta(days=int(r["start_day"]))
            end   = sprint_start + timedelta(days=int(r["end_day"]) + 1)
            gantt_data.append(dict(
                Task=r["sprint_commitment"] if "sprint_commitment" in r else r["task_description"][:40],
                Start=start.strftime("%Y-%m-%d"),
                Finish=end.strftime("%Y-%m-%d"),
                Resource=r["tester_name"],
                Skills=r.get("required_skills", "–"),
                Description=r["task_description"][:60] + "…" if len(r["task_description"]) > 60
                            else r["task_description"],
            ))

        colors_list = px.colors.qualitative.Vivid
        tester_names = asgn["tester_name"].unique().tolist()
        color_map = {t: colors_list[i % len(colors_list)] for i, t in enumerate(tester_names)}

        fig = ff.create_gantt(
            gantt_data,
            colors={r["Resource"]: color_map[r["Resource"]] for r in gantt_data},
            index_col="Resource",
            show_colorbar=True,
            group_tasks=True,
            showgrid_x=True,
            showgrid_y=True,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,12,41,0.8)",
            font_color="#e0e0e0",
            height=500,
            title_text="Sprint Task Schedule by Tester",
            xaxis_showgrid=True,
            xaxis_gridcolor="rgba(255,255,255,0.1)",
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Raw Gantt Data"):
            st.dataframe(pd.DataFrame(gantt_data), use_container_width=True)


# ====================================================================
# TAB 7 — Utilization Heatmap
# ====================================================================
with tab_heat:
    st.subheader("Tester Utilization Heatmap")
    st.markdown("*Cell values = % of daily effective capacity used.*")

    result = st.session_state.optimizer_result
    if result is None or result["utilization"].empty:
        st.info("Run the optimizer in the **Staffing Plan** tab first.")
    else:
        util = result["utilization"]
        fig = go.Figure(data=go.Heatmap(
            z=util.values,
            x=util.columns.tolist(),
            y=util.index.tolist(),
            colorscale=[
                [0.0,  "#1e293b"],   # 0%   — dark slate
                [0.4,  "#1d4ed8"],   # 40%  — blue
                [0.7,  "#7c3aed"],   # 70%  — violet
                [0.9,  "#dc2626"],   # 90%  — red
                [1.0,  "#ef4444"],   # 100% — bright red
            ],
            zmin=0, zmax=100,
            text=util.values.round(0).astype(int).astype(str),
            texttemplate="%{text}%",
            hovertemplate="Tester: %{y}<br>%{x}: %{z:.1f}%<extra></extra>",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e0e0",
            height=max(300, 50 * len(util) + 100),
            xaxis_title="Sprint Day",
            yaxis_title="Tester",
            margin=dict(l=160, t=40, b=60),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Legend
        st.markdown("""
        | Colour | Utilization |
        |--------|-------------|
        | 🟦 Dark | 0% — Idle |
        | 🟦 Blue | ~40% |
        | 🟣 Violet | ~70% |
        | 🔴 Red | ≥90% — Overloaded risk |
        """)


# ====================================================================
# TAB 8 — PM Override
# ====================================================================
with tab_pm:
    st.subheader("✏️ PM Override — Reassign Tasks")
    st.markdown("""
    Manually reassign tasks here. Saved overrides are stored in the `corrections` table
    and used as **few-shot examples** for future Gemini classifications.
    """)

    assignments_df = load_assignments_df()

    if assignments_df.empty:
        st.info("No assignments yet. Run the optimizer first.")
    else:
        testers_df  = load_testers_df()
        tester_names = testers_df["name"].tolist() if not testers_df.empty else []

        # Show assignments with editable corrected_tester column
        st.markdown("#### Current Assignments")
        # Inject editable column
        edit_df = assignments_df.copy()
        edit_df["corrected_tester"] = edit_df["tester_name"]
        edit_df["pm_notes"] = ""

        override_df = st.data_editor(
            edit_df,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "corrected_tester": st.column_config.SelectboxColumn(
                    "🔄 Reassign To", options=tester_names, required=True),
                "pm_notes": st.column_config.TextColumn("📝 PM Notes", width="medium"),
                "id":              st.column_config.Column(disabled=True),
                "tester_name":     st.column_config.Column("Original Tester", disabled=True),
                "task_description":st.column_config.Column(disabled=True, width="large"),
                "allocated_hours": st.column_config.Column(disabled=True),
                "start_day":       st.column_config.Column(disabled=True),
                "end_day":         st.column_config.Column(disabled=True),
            },
            disabled=["id", "task_description", "tester_name",
                      "allocated_hours", "start_day", "end_day"],
        )

        override_col, learn_col = st.columns(2)

        with override_col:
            if st.button("💾 Save Overrides", type="primary", use_container_width=True):
                saved = 0
                for _, row in override_df.iterrows():
                    if row["corrected_tester"] != row["tester_name"]:
                        save_correction(
                            task_id=int(row["id"]),
                            task_description=row["task_description"],
                            required_skills_original="",
                            original_tester=row["tester_name"],
                            corrected_tester=row["corrected_tester"],
                            pm_notes=row.get("pm_notes", ""),
                        )
                        saved += 1
                if saved:
                    st.success(f"✅ Saved **{saved}** override(s) to corrections table.")
                else:
                    st.info("No changes detected — all assignments match the original.")

        with learn_col:
            if st.button("🧠 Sync & Learn", use_container_width=True,
                         help="Feed correction history as few-shot examples into the LLM on the next analysis run."):
                corrections = load_corrections_df()
                if corrections.empty:
                    st.warning("No corrections to sync yet. Save some overrides first.")
                else:
                    st.success(
                        f"✅ Synced **{len(corrections)}** correction(s) into the few-shot context. "
                        "The next **Analysis** run will use these as guidance examples for Gemini."
                    )
                    with st.expander("📚 Few-shot context preview"):
                        for _, c in corrections.head(5).iterrows():
                            st.markdown(
                                f"- **Task**: _{c['task_description'][:80]}_  \n"
                                f"  ✗ Was: `{c['original_tester']}` → ✓ Changed to: `{c['corrected_tester']}`"
                                + (f"  \n  📝 *{c['pm_notes']}*" if c.get("pm_notes") else "")
                            )

        st.divider()
        st.markdown("#### 📜 All PM Corrections (History)")
        all_corr = load_corrections_df()
        if all_corr.empty:
            st.caption("No corrections recorded yet.")
        else:
            st.dataframe(all_corr, use_container_width=True)
