#!/bin/bash
# Activate the shared virtual environment (lives in Testing_resource_management)
VENV="/home/arnab-das/Documents/BITS/Semester4/Desertation Idea 2/Testing_resource_management/venv"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "ERROR: venv not found at: $VENV"
    echo "Please create it by running:"
    echo "  python3 -m venv \"$VENV\" && \"$VENV/bin/pip\" install -r requirements.txt"
    exit 1
fi

source "$VENV/bin/activate"
echo "✅ Virtual environment activated."
echo "🚀 Starting Streamlit app..."
streamlit run app.py
