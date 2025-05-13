# Neurosim Service

A neuron simulation service that provides REST API endpoints for running neural simulations, similar to BlueNaaS.

## Features

- Single neuron simulations with NEURON simulator
- REST API for running simulations and retrieving results
- Support for various stimulus protocols (current clamp, voltage clamp)
- Customizable simulation parameters
- Result visualization

## Installation

1. Install NEURON simulator:
```bash
pip install neuron
```

2. Install the package:
```bash
pip install -e .
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

2. Run tests:
```bash
pytest
```

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
