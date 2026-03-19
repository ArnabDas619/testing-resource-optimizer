# src/skills_db.py
# Thin compatibility wrapper — delegates to src.database
# Keeps backward compatibility for any legacy calls.
from src.database import (
    init_db,
    load_testers_df,
    save_testers_from_df,
    clear_testers,
)

__all__ = ["init_db", "load_testers_df", "save_testers_from_df", "clear_testers"]
