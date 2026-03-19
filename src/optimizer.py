"""
src/optimizer.py
----------------
PuLP-based Integer Linear Program for sprint task assignment.

Objective : minimise total weighted sprint duration
Constraints:
  - Capacity:  Σ_j x[i][j] * effort[j] ≤ capacity[i]   ∀ tester i
  - Coverage:  Σ_i x[i][j] ≥ 1                          ∀ task j  (if any skilled tester exists)
  - Skill:     x[i][j] = 0  if tester i lacks the required skills for task j
  - Binary:    x[i][j] ∈ {0, 1}

Proficiency multiplies effective capacity:
  High → 1.0x   Mid → 0.75x   Low → 0.5x
"""
from __future__ import annotations

import math
import pandas as pd
from pulp import (
    LpProblem, LpMinimize, LpVariable, LpBinary, lpSum,
    value, PULP_CBC_CMD, LpStatus
)

PROFICIENCY_MULTIPLIER = {"High": 1.0, "Mid": 0.75, "Low": 0.5}
HOURS_PER_DAY = 8   # working hours per day for Gantt scheduling


def _skills_set(skills_raw: str) -> set[str]:
    """Parse a comma-separated skills string into a normalised set."""
    return {s.strip().lower() for s in str(skills_raw).split(",") if s.strip()}


def _task_effort(task_description: str, required_skills: str) -> float:
    """
    Estimate effort hours from skill count.
    Each required skill adds 4h base effort; minimum 4h.
    """
    n = len(_skills_set(required_skills))
    return max(4.0, n * 4.0)


class StaffingOptimizer:
    """
    Solves the assignment ILP and returns schedule DataFrames for the UI.
    """

    def __init__(self, tasks_df: pd.DataFrame, testers_df: pd.DataFrame):
        """
        Parameters
        ----------
        tasks_df   : DataFrame with columns [task_description, required_skills, status]
        testers_df : DataFrame with columns [name, skills, proficiency, available_hours]
        """
        self.tasks_df = tasks_df.reset_index(drop=True).copy()
        self.testers_df = testers_df.reset_index(drop=True).copy()

        # Pre-compute effort hours per task
        if "effort_hours" not in self.tasks_df.columns:
            self.tasks_df["effort_hours"] = self.tasks_df.apply(
                lambda r: _task_effort(r.get("task_description", ""),
                                       r.get("required_skills", "")), axis=1
            )

        # Pre-compute effective capacity per tester
        self.testers_df["eff_capacity"] = self.testers_df.apply(
            lambda r: r["available_hours"] * PROFICIENCY_MULTIPLIER.get(
                str(r.get("proficiency", "Mid")).strip(), 0.75), axis=1
        )

    # ------------------------------------------------------------------
    def _can_assign(self, tester_skills: set, task_skills: set) -> bool:
        """True when tester has *any* overlap with required task skills."""
        if not task_skills:
            return True   # untagged task → any tester can pick it up
        return bool(tester_skills & task_skills)

    # ------------------------------------------------------------------
    def solve(self) -> dict:
        """
        Run the ILP and return:
          {
            "status": str,
            "assignments": pd.DataFrame (task × tester assignments with schedule),
            "utilization": pd.DataFrame (tester × day utilization matrix),
          }
        """
        tasks   = self.tasks_df
        testers = self.testers_df

        n_tasks   = len(tasks)
        n_testers = len(testers)

        if n_tasks == 0 or n_testers == 0:
            return {"status": "No data", "assignments": pd.DataFrame(),
                    "utilization": pd.DataFrame()}

        # Pre-compute skill sets
        tester_skills = [
            _skills_set(testers.at[i, "skills"]) for i in range(n_testers)
        ]
        task_skills = [
            _skills_set(tasks.at[j, "required_skills"]
                        if "required_skills" in tasks.columns else "")
            for j in range(n_tasks)
        ]
        efforts = tasks["effort_hours"].tolist()
        capacities = testers["eff_capacity"].tolist()

        # ---- Build ILP -----------------------------------------------
        prob = LpProblem("SprintStaffing", LpMinimize)

        # x[i][j] = 1 if tester i assigned to task j
        x = [[LpVariable(f"x_{i}_{j}", cat=LpBinary) for j in range(n_tasks)]
             for i in range(n_testers)]

        # Objective: minimise total weighted effort (proxy for duration)
        prob += lpSum(
            x[i][j] * efforts[j]
            for i in range(n_testers)
            for j in range(n_tasks)
        )

        # Capacity constraint
        for i in range(n_testers):
            prob += (
                lpSum(x[i][j] * efforts[j] for j in range(n_tasks))
                <= capacities[i],
                f"cap_{i}"
            )

        # Skill + coverage constraints
        for j in range(n_tasks):
            eligible = [i for i in range(n_testers)
                        if self._can_assign(tester_skills[i], task_skills[j])]
            if not eligible:
                continue   # skip tasks no one can do (soft — leave unassigned)

            # Hard skill gate: force x[i][j]=0 for ineligible testers
            for i in range(n_testers):
                if i not in eligible:
                    prob += (x[i][j] == 0, f"skill_{i}_{j}")

            # At least one eligible tester must cover the task
            prob += (
                lpSum(x[i][j] for i in eligible) >= 1,
                f"cover_{j}"
            )

        # ---- Solve ---------------------------------------------------
        prob.solve(PULP_CBC_CMD(msg=0))
        status = LpStatus[prob.status]

        if prob.status != 1:  # Not Optimal
            return {
                "status": status,
                "assignments": pd.DataFrame(),
                "utilization": pd.DataFrame(),
            }

        # ---- Extract results -----------------------------------------
        assignment_rows = []
        tester_load = {i: 0.0 for i in range(n_testers)}

        for j in range(n_tasks):
            for i in range(n_testers):
                if value(x[i][j]) is not None and value(x[i][j]) > 0.5:
                    load_before = tester_load[i]
                    tester_load[i] += efforts[j]
                    start_day = math.ceil(load_before / HOURS_PER_DAY)
                    end_day   = math.ceil(tester_load[i] / HOURS_PER_DAY)
                    assignment_rows.append({
                        "task_index":     j,
                        "task_description": tasks.at[j, "task_description"]
                            if "task_description" in tasks.columns
                            else tasks.at[j, "Task Description"],
                        "sprint_commitment": tasks.at[j, "sprint_commitment"]
                            if "sprint_commitment" in tasks.columns else f"T{j+1}",
                        "status":         tasks.at[j, "status"]
                            if "status" in tasks.columns else "Not Started",
                        "required_skills": ", ".join(task_skills[j]) if task_skills[j] else "–",
                        "effort_hours":   efforts[j],
                        "tester_index":   i,
                        "tester_name":    testers.at[i, "name"],
                        "proficiency":    testers.at[i, "proficiency"],
                        "allocated_hours": efforts[j],
                        "start_day":      start_day,
                        "end_day":        end_day,
                    })

        assignments_df = pd.DataFrame(assignment_rows)

        # ---- Utilization matrix (tester × day) -----------------------
        if not assignments_df.empty:
            max_day = int(assignments_df["end_day"].max()) + 1
            tester_names = testers["name"].tolist()
            util_data = {t: [0.0] * max_day for t in tester_names}

            for _, row in assignments_df.iterrows():
                tname = row["tester_name"]
                s, e  = int(row["start_day"]), int(row["end_day"])
                daily = row["effort_hours"] / max(1, e - s)
                for d in range(s, e):
                    if d < max_day:
                        util_data[tname][d] += daily

            util_df = pd.DataFrame(util_data,
                                   index=[f"Day {d+1}" for d in range(max_day)]).T
            # Convert to percent of daily capacity
            cap_per_day = (testers.set_index("name")["eff_capacity"] / 5).to_dict()
            for tname in tester_names:
                cap = cap_per_day.get(tname, 8.0)
                util_df.loc[tname] = (util_df.loc[tname] / cap * 100).clip(0, 100)
        else:
            util_df = pd.DataFrame()

        return {
            "status": status,
            "assignments": assignments_df,
            "utilization": util_df,
        }
