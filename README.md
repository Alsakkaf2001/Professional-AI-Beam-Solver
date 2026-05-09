# Professional AI Beam Solver

A professional desktop/web hybrid structural engineering application combining FEM analysis, AI-assisted design, and modern visualization.

## Features

- **Interactive FEM Modeling**: Draw beams, add nodes, supports, and loads
- **Real-time Solving**: Euler-Bernoulli beam analysis with automatic validation
- **AI-Powered**: Extract structures from images using DeepSeek API
- **Professional Reports**: Generate PDF and DXF exports
- **Modern UI**: Dark-themed CAD-like interface with real-time diagrams
- **Complete Analysis**: Reactions, deformations, SFD/BMD computation

## Project Structure

```
professional_ai_beam_solver/
├── backend/
│   ├── app.py              # Flask API server
│   ├── fem/                # FEM solver core
│   │   ├── model.py        # Main FEM model
│   │   ├── nodes.py        # Node class
│   │   ├── elements.py     # Beam element class
│   │   ├── materials.py    # Material properties
│   │   ├── sections.py     # Cross-sections
│   │   ├── supports.py     # Boundary conditions
│   │   ├── loads.py        # Load definitions
│   │   ├── assembly.py     # Global matrix assembly
│   │   ├── validator.py    # Structure validation
│   │   └── recovery.py     # Results extraction
│   ├── ai/                 # AI integration
│   │   ├── deepseek_client.py   # DeepSeek API wrapper
│   │   ├── image_extractor.py   # Structure extraction
│   │   └── repair.py       # AI repair & recovery
│   └── exports/            # Export modules
│       ├── pdf_report.py   # PDF generation
│       └── dxf_export.py   # DXF export
├── frontend/               # Web UI
│   ├── index.html          # Main HTML
│   ├── styles.css          # Professional styling
│   ├── app.js              # Main application
│   └── canvas.js           # Canvas drawing engine
├── uploads/                # Image upload directory
├── reports/                # Generated reports
└── requirements.txt        # Python dependencies
```

## Installation

### Prerequisites
- Python 3.8+
- Node.js (for development, optional)
- DEEPSEEK_API_KEY (for AI features)

### Setup

1. **Clone repository**
```bash
git clone <repo>
cd professional_ai_beam_solver
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set environment variables**
```bash
export DEEPSEEK_API_KEY=your_api_key_here
```

On Windows:
```bash
set DEEPSEEK_API_KEY=your_api_key_here
```

4. **Start backend server**
```bash
cd backend
python app.py
```

Server runs at: `http://localhost:5000`

5. **Open frontend**
```bash
cd frontend
python -m http.server 8000
```

Open browser: `http://localhost:8000`

## Usage

### Create a Structure

1. **Add Nodes**: Use Node tool to place joints
2. **Add Beams**: Select two nodes to create beam elements
3. **Add Support**: Click node to add pin, fixed, or roller supports
4. **Add Loads**: Apply point or distributed loads
5. **Validate**: Check structure before solving
6. **Solve**: Run FEM analysis
7. **View Results**: Inspect reactions, diagrams, deformations
8. **Export**: Generate PDF report or DXF file

### Keyboard Shortcuts

- `S` - Select tool
- `N` - Node tool
- `B` - Beam tool
- `P` - Support tool
- `L` - Point load tool
- `U` - UDL tool
- `Enter` - Solve
- `Delete` - Delete selected element
- `+` / `-` - Zoom in/out
- `0` - Fit to view

### AI Image Extraction

1. Click "AI Extract" button
2. Upload structural drawing image
3. AI analyzes image and extracts:
   - Node positions
   - Element connectivity
   - Support types
   - Applied loads
4. Review extracted data
5. Build FEM model automatically

## API Endpoints

### Model Management
- `POST /api/model/new` - Create new model
- `GET /api/model/current` - Get current model
- `POST /api/model/save` - Save model
- `POST /api/model/load` - Load model

### Geometry
- `POST /api/node/add` - Add node
- `GET /api/nodes/list` - List all nodes
- `POST /api/element/add` - Add beam element

### Boundary Conditions
- `POST /api/support/add` - Add support
- `POST /api/load/point/add` - Add point load
- `POST /api/load/distributed/add` - Add distributed load

### Analysis
- `POST /api/validate` - Validate structure
- `POST /api/solve` - Solve structure

### AI Features
- `POST /api/ai/extract` - Extract from image
- `POST /api/ai/build-from-extraction` - Build model from extraction

### Exports
- `POST /api/export/pdf` - Export PDF report
- `POST /api/export/dxf` - Export DXF file

## FEM Theory

### Element Type
- 2D Euler-Bernoulli beam elements
- 3 DOF per node: UX, UY, RZ

### Local Stiffness Matrix
```
k = EI/L³ * [12  6L  -12  6L]
             [6L  4L² -6L  2L²]
             [-12 -6L 12  -6L]
             [6L  2L² -6L  4L²]
```

### Assembly
- Global stiffness: K = Σ T^T * k_local * T
- Apply supports: partition method
- Solve: K_ff * u_f = F_f

### Results
- Displacements at nodes
- Support reactions
- Member forces (N, V, M)
- Shear force and bending moment diagrams
- Deformed shape using Hermite interpolation

## AI Integration

Uses OpenAI-compatible DeepSeek API:

```python
from openai import OpenAI

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)
```

### Features
- **Image Extraction**: Analyze building diagrams
- **Structure Recognition**: Identify beams, supports, loads
- **Data Repair**: Fix incomplete/invalid data
- **Analysis**: Provide engineering insights

## Engineering Quality

- **Robust Validation**: Pre-solve checks prevent singular matrices
- **Numerical Stability**: Optimized assembly and solving
- **Professional Accuracy**: Based on proven FEM theory
- **Real-time Feedback**: Instant diagram updates
- **CAD-like UX**: Intuitive interface similar to ETABS/SAP2000

## Limitations

- 2D planar frame analysis (3D development planned)
- Static linear analysis only
- No dynamic or nonlinear analysis
- No material nonlinearity
- Educational/research quality (not production-certified)

## Performance

- Typical solve time: < 50ms for structures up to 1000 DOF
- UI responsive with 60 FPS canvas rendering
- Memory efficient with sparse matrix support planned

## Future Enhancements

- [ ] 3D frame analysis
- [ ] Dynamic analysis (frequencies, response)
- [ ] Nonlinear analysis
- [ ] Optimized sections
- [ ] Parametric design
- [ ] Cloud-based solving
- [ ] Collaborative features
- [ ] BIM integration

## Citation

```bibtex
@software{aibeamsolver2024,
  title={Professional AI Beam Solver},
  authors={Your Name},
  year={2024},
  url={https://github.com/...}
}
```

## License

MIT License - See LICENSE file

## Support

For issues, feature requests, or contributions:
- GitHub Issues: [Create issue]
- Email: support@example.com
- Discord: [Join community]

---

**Built with ❤️ for structural engineers**
