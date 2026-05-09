#!/bin/bash
# Start Professional AI Beam Solver

echo "Starting Professional AI Beam Solver..."
echo ""
echo "Setting up Python environment..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env and add your DEEPSEEK_API_KEY"
fi

# Start Flask backend
echo ""
echo "Starting Flask server on http://localhost:5000..."
cd backend
python app.py
