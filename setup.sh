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
echo ""
echo "To start using AutoCandidate, you have two options:"
echo ""
echo "Option 1: Interactive Mode (Recommended for beginners)"
echo "  ./run.sh"
echo ""
echo "Option 2: Direct Command"
echo "  1. Activate venv:       source venv/bin/activate"
echo "  2. Run the tool:        python auto_candidate/main.py start <prompt_file> --local-path <path>"
echo ""
echo "API Key Configuration:"
echo "  • Create a .env file with your API keys (recommended):"
echo "    GEMINI_API_KEY=your_key_here"
echo "    ANTHROPIC_API_KEY=your_key_here"
echo "  • Or export them: export GEMINI_API_KEY='your-key'"
echo ""
echo "For more information, see README.md"
echo ""
