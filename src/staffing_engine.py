# src/staffing_engine.py
import pandas as pd
from src.config import SPRINT_MATURITY_THRESHOLDS

class StaffingEngine:
    def __init__(self, backlog_df, testers_df, apply_maturity_rules=True):
        self.backlog = backlog_df
        self.testers = testers_df
        self.apply_maturity_rules = apply_maturity_rules

    def get_recommendations(self):
        """Calculates needed staffing based on classified backlog."""
        
        # 1. Flatten the required roles to calculate total demand
        role_demand = {"Manual": 0, "Automation": 0, "Performance": 0, "Security": 0, "Accessibility": 0}
        
        for _, row in self.backlog.iterrows():
            sprint_num = row.get("Sprint Number", 1)
            story_points = row.get("Story Points", 3)
            roles = row.get("Required Roles", ["Manual"])
            
            if isinstance(roles, str): # Handle string representation of lists from CSV/LLM
                import ast
                try:
                    roles = ast.literal_eval(roles)
                except:
                    roles = [roles]
                    
            for role in roles:
                # Apply heuristic rules: Suppress role if sprint is too early
                if self.apply_maturity_rules:
                    threshold = SPRINT_MATURITY_THRESHOLDS.get(role, 1)
                    if int(sprint_num) < threshold:
                        continue # Skip adding points for this role
                
                # Basic heuristic: 1 Story Point = ~2 hours of testing per role required
                role_demand[role] += (story_points * 2)

        # 2. Map demand to available testers
        recommendation_details = []
        
        for role, needed_hours in role_demand.items():
            if needed_hours <= 0:
                continue
                
            # Filter testers by role
            available_for_role = self.testers[self.testers['Type'] == role]
            
            # Simple assignment strategy (greedy)
            hours_remaining = needed_hours
            assigned_testers = []
            
            for _, tester in available_for_role.sort_values(by="Proficiency", ascending=False).iterrows():
                if hours_remaining <= 0:
                    break
                    
                tester_avail = tester["Available Hours"]
                allocated = min(tester_avail, hours_remaining)
                
                assigned_testers.append({
                    "Name": tester["Name"],
                    "Proficiency": tester["Proficiency"],
                    "Allocated Hours": allocated
                })
                hours_remaining -= allocated
                
            recommendation_details.append({
                "Role": role,
                "Total Hours Needed": needed_hours,
                "Headcount Needed": round(needed_hours / 40, 1), # Assuming 40h/week
                "Assigned Testers": assigned_testers,
                "Unmet Hours": max(0, hours_remaining)
            })
            
        return pd.DataFrame(recommendation_details)
