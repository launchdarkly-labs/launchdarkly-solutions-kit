#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip3 install -e .

# Print success message
echo "Virtual environment setup complete. Activate it with: source venv/bin/activate" 