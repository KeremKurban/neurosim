# Neurosim Service

[![Tests](https://github.com/KeremKurban/neurosim/actions/workflows/tests.yml/badge.svg)](https://github.com/KeremKurban/neurosim/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/KeremKurban/neurosim/branch/main/graph/badge.svg)](https://codecov.io/gh/KeremKurban/neurosim)
[![License](https://img.shields.io/github/license/KeremKurban/neurosim)](https://github.com/KeremKurban/neurosim/blob/main/LICENSE)

A neuron simulation service that provides REST API endpoints for running neural simulations, similar to BlueNaaS.

## Features

- Single neuron simulations with NEURON simulator
- REST API for running simulations and retrieving results
- Support for various stimulus protocols (current clamp, voltage clamp)
- Customizable simulation parameters
- Result visualization

## Installation

### Option 1: Docker (Recommended)

1. Build and run using Docker Compose:
```bash
docker-compose up --build -d
```

The service will be available at `http://localhost:8000`

2. To view logs:
```bash
docker-compose logs -f
```

3. To stop the service:
```bash
docker-compose down
```

### Option 2: Local Installation

1. Install NEURON simulator:
```bash
pip install neuron
```

2. Install the package:
```bash
pip install -e .
```

## WSL Guidelines (Windows Users)

If you're using Windows, it's recommended to run the service through WSL (Windows Subsystem for Linux):

1. Enable WSL if not already enabled:
```powershell
# Run in PowerShell as Administrator
wsl --install
```

2. Install Docker Desktop for Windows with WSL 2 backend:
   - Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Ensure WSL 2 backend is enabled in Docker Desktop settings

3. Clone and run in WSL:
```bash
# In WSL terminal
git clone <repository-url>
cd neurosim-service
docker-compose up --build -d
```

## Usage

Start the server:
```bash
python -m neurosim.run
```

The API will be available at `http://localhost:8000`

## API Endpoints

- `POST /simulations` - Run a new simulation
- `GET /simulations/{sim_id}` - Get simulation status
- `GET /simulations/{sim_id}/results` - Get simulation results
- `GET /models` - List available neuron models
- `POST /models/upload` - Upload a new neuron model

## Development

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. For visualization support:
```bash
pip install -e ".[viz]"
```

2. Run tests with coverage:
```bash
# Run tests with coverage
pytest --cov=neurosim --cov-report=term-missing --cov-report=html

# View the coverage report in your browser (Windows)
start coverage_html/index.html

# View the coverage report in your browser (Linux/WSL)
xdg-open coverage_html/index.html
```

The coverage report will show:
- Line coverage percentage for each module
- Missing lines that need test coverage
- Branch coverage statistics
- An interactive HTML report for detailed analysis

## Examples

Run a simulation:
```bash
curl -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "simple_neuron",
    "stimulus": {
      "type": "IClamp",
      "delay": 100,
      "duration": 500,
      "amplitude": 0.5
    },
    "recordings": [
      {
        "section": "soma",
        "variable": "v"
      }
    ],
    "conditions": {
      "duration": 1000,
      "dt": 0.025,
      "v_init": -65,
      "celsius": 34
    }
  }'
```
