@echo off
REM Start Professional AI Beam Solver on Windows

echo Starting Professional AI Beam Solver...
echo.
echo Setting up Python environment...

REM Activate virtual environment if it exists
if exist venv\ (
    call venv\Scripts\activate.bat
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check for .env file
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env and add your DEEPSEEK_API_KEY
    pause
)

REM Start Flask backend
echo.
echo Starting Flask server on http://localhost:5000...
cd backend
python app.py
