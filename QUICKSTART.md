# Quick Start Guide

## Installation

### 1. Prerequisites
- Python 3.8+ installed
- pip package manager
- DEEPSEEK_API_KEY (get from [DeepSeek](https://platform.deepseek.com))

### 2. Setup

```bash
# Clone or download the project
cd professional_ai_beam_solver

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
```

### 3. Start the Application

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```bash
start.bat
```

**Manual start:**
```bash
cd backend
python app.py
```

The backend will start at `http://localhost:5000`

### 4. Open Frontend

In another terminal/tab:
```bash
cd frontend
python -m http.server 8000
```

Open in browser: `http://localhost:8000`

## First Model

1. **Add Nodes** (Tool: N)
   - Click on canvas to place nodes
   - Grid snapping helps with alignment

2. **Create Beams** (Tool: B)
   - Click first node, then second node
   - Creates a beam element

3. **Add Supports** (Tool: P)
   - Click on node
   - Select support type (Pin, Fixed, etc.)

4. **Apply Loads** (Tool: L or U)
   - Point Load: Click node
   - Distributed Load: Click element

5. **Validate** (Button: Validate)
   - Checks structure before solving

6. **Solve** (Button: Solve or Enter)
   - Runs FEM analysis
   - Shows results and diagrams

7. **Export**
   - PDF report
   - DXF file

## Tips

- **Zoom**: Use mouse wheel or +/- keys
- **Pan**: Middle-click drag or right-click drag
- **Fit View**: Press 0 or click "Fit View"
- **Delete**: Select element and press Delete
- **Undo**: Not yet implemented (save/load instead)

## Troubleshooting

### "DEEPSEEK_API_KEY not found"
- Create `.env` file with `DEEPSEEK_API_KEY=your_key`
- Restart the server

### "Port 5000 already in use"
- Change port in `backend/app.py`
- Run on different port: `FLASK_PORT=5001 python app.py`

### Frontend not loading
- Check if frontend server is running
- Try port 8000: `python -m http.server 8000`
- Check browser console for errors

### Solving fails
- Validate structure first
- Ensure minimum 3 constrained DOF
- Check for zero-length elements
- Review validation report

## API Usage Example

```python
import requests

# Create new model
response = requests.post('http://localhost:5000/api/model/new', json={'name': 'My Structure'})

# Add nodes
requests.post('http://localhost:5000/api/node/add', json={'x': 0, 'y': 0})
requests.post('http://localhost:5000/api/node/add', json={'x': 5000, 'y': 0})

# Add element
requests.post('http://localhost:5000/api/element/add', json={
    'node_i': 1,
    'node_j': 2,
    'material': 'steel',
    'section': 'IPE-200'
})

# Add support
requests.post('http://localhost:5000/api/support/add', json={
    'node_id': 1,
    'type': 'pin'
})

# Add load
requests.post('http://localhost:5000/api/load/point/add', json={
    'node_id': 2,
    'fx': 0,
    'fy': -50
})

# Solve
response = requests.post('http://localhost:5000/api/solve')
print(response.json())
```

## Next Steps

1. Read [README.md](README.md) for complete documentation
2. Explore [FEM Theory](docs/fem_theory.md) for solver details
3. Check [API Reference](docs/api_reference.md)
4. Try [Examples](examples/)

---

For issues or questions, refer to the main README or create an issue.
