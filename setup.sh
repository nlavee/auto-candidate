#!/bin/bash

# AutoCandidate Setup Script

set -e

echo "=== AutoCandidate Setup ==="

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

# Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate and Install
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Setup Complete ==="
echo "To start using AutoCandidate:"
echo "1. Export your API Key: export GEMINI_API_KEY='your-key'"
echo "2. Activate venv:       source venv/bin/activate"
echo "3. Run the tool:        python auto_candidate/main.py start <prompt_file> --repo-url <url>"
echo ""
