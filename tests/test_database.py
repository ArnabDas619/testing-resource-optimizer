import os
import sqlite3
import pytest
import pandas as pd
from src.database import init_db, DB_PATH, load_testers_df, save_testers_from_df, clear_testers, save_correction, load_corrections_df

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    
    yield
    
    # Teardown
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_testers_crud():
    testers_df = pd.DataFrame([
        {'Name': 'Test Bob', 'Experience': 5, 'Skills': 'Manual', 'Proficiency': 'High', 'Available Hours': 40}
    ])
    save_testers_from_df(testers_df)
    
    loaded_df = load_testers_df()
    assert len(loaded_df) == 1
    assert loaded_df.iloc[0]['name'] == 'Test Bob'
    assert loaded_df.iloc[0]['proficiency'] == 'High'
    
    clear_testers()
    loaded_df = load_testers_df()
    assert len(loaded_df) == 0

def test_corrections():
    save_correction(
        task_id=1,
        task_description="Sample Task",
        required_skills_original="Manual",
        original_tester="Alice",
        corrected_tester="Bob",
        pm_notes="Bob is better for this"
    )
    
    df = load_corrections_df()
    assert len(df) == 1
    assert df.iloc[0]['corrected_tester'] == 'Bob'
    assert df.iloc[0]['pm_notes'] == 'Bob is better for this'
