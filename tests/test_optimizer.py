import pytest
import pandas as pd
from src.optimizer import StaffingOptimizer

def test_optimizer_basic_assignment():
    # Arrange
    tasks = pd.DataFrame([
        {'task_description': 'Test login', 'required_skills': 'Selenium,Manual Testing', 'status': 'Not Started', 'effort_hours': 8},
        {'task_description': 'Perf test',  'required_skills': 'Performance Testing,JMeter', 'status': 'Not Started', 'effort_hours': 16},
    ])
    testers = pd.DataFrame([
        {'name': 'Alice', 'skills': 'Selenium,Manual Testing', 'proficiency': 'High', 'available_hours': 40},
        {'name': 'Bob',   'skills': 'Performance Testing,JMeter', 'proficiency': 'Mid', 'available_hours': 30},
    ])
    
    # Act
    optimizer = StaffingOptimizer(tasks, testers)
    result = optimizer.solve()
    
    # Assert
    assert result['status'] == 'Optimal'
    
    assignments = result['assignments']
    assert len(assignments) == 2
    
    alice_assigned = assignments[assignments['tester_name'] == 'Alice'].iloc[0]
    bob_assigned = assignments[assignments['tester_name'] == 'Bob'].iloc[0]
    
    assert 'Test login' in alice_assigned['task_description']
    assert 'Perf test' in bob_assigned['task_description']

def test_optimizer_unskilled_task():
    # Arrange
    tasks = pd.DataFrame([
        {'task_description': 'Unknown task', 'required_skills': 'Blockchain', 'status': 'Not Started', 'effort_hours': 8},
    ])
    testers = pd.DataFrame([
        {'name': 'Alice', 'skills': 'Selenium', 'proficiency': 'High', 'available_hours': 40},
    ])
    
    # Act
    optimizer = StaffingOptimizer(tasks, testers)
    result = optimizer.solve()
    
    # Assert
    # The task should not be assigned because no tester has the required skills.
    assert result['assignments'].empty

def test_optimizer_capacity_limit():
    # Arrange
    tasks = pd.DataFrame([
        {'task_description': 'Task 1', 'required_skills': 'Manual', 'status': 'Not Started', 'effort_hours': 30},
        {'task_description': 'Task 2', 'required_skills': 'Manual', 'status': 'Not Started', 'effort_hours': 20},
    ])
    testers = pd.DataFrame([
        # Low proficiency multiplier is 0.5x, so 40 hours = 20 effective hours capacity
        # Mid proficiency multiplier is 0.75x, so 40 hours = 30 effective hours capacity
        # High proficiency multiplier is 1.0x, so 40 hours = 40 effective hours capacity
        {'name': 'Alice', 'skills': 'Manual', 'proficiency': 'Low', 'available_hours': 40},
    ])
    
    # Act
    optimizer = StaffingOptimizer(tasks, testers)
    result = optimizer.solve()
    
    # Assert
    # Alice only has 20 effective hours, while tasks require 50. The hard coverage constraint 
    # makes this Infeasible.
    assert result['status'] == 'Infeasible'
    assert result['assignments'].empty
