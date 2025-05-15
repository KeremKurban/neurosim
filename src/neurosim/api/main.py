"""FastAPI application for the neuron simulation service."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uuid
from typing import Dict
import csv
from pathlib import Path
from fastapi.responses import FileResponse

from neurosim.models.simulation import (
    SimulationRequest,
    SimulationStatus,
    SimulationResults
)
from neurosim.core.simulator import NeuronSimulator

app = FastAPI(
    title="Neuron Simulation Service",
    description="A service for running neural simulations using NEURON simulator",
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store simulation states and results in memory (replace with proper database in production)
simulations: Dict[str, Dict] = {}
simulator = NeuronSimulator()

async def run_simulation_task(sim_id: str, request: SimulationRequest):
    """Background task to run simulation."""
    try:
        # Update simulation status
        simulations[sim_id]["status"] = "running"
          # Load model
        simulator.load_model(request.model_id)
        
        # Setup recordings
        for rec in request.recordings:
            simulator.setup_recording(rec.section, rec.variable)
        
        # Setup stimulus
        simulator.setup_stimulus(
            section="soma",  # TODO: Make this configurable
            stim_type=request.stimulus.type,
            params={
                "delay": request.stimulus.delay,
                "duration": request.stimulus.duration,
                "amplitude": request.stimulus.amplitude
            }
        )
        
        # Run simulation
        results = simulator.run_simulation(
            duration=request.conditions.duration,
            dt=request.conditions.dt,
            v_init=request.conditions.v_init,
            celsius=request.conditions.celsius
        )
        
        # Store results
        simulations[sim_id].update({
            "status": "completed",
            "results": results
        })
        
    except Exception as e:
        simulations[sim_id].update({
            "status": "failed",
            "error": str(e)
        })
    finally:
        simulator.cleanup()

@app.post("/simulations", response_model=SimulationStatus)
async def create_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks
) -> SimulationStatus:
    """Create and start a new simulation."""
    sim_id = str(uuid.uuid4())
    
    simulations[sim_id] = {
        "status": "queued",
        "request": request.model_dump()
    }
    
    background_tasks.add_task(run_simulation_task, sim_id, request)
    
    return SimulationStatus(
        simulation_id=sim_id,
        status="queued"
    )

@app.get("/simulations/{sim_id}", response_model=SimulationStatus)
async def get_simulation_status(sim_id: str) -> SimulationStatus:
    """Get the status of a simulation."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
        
    sim = simulations[sim_id]
    return SimulationStatus(
        simulation_id=sim_id,
        status=sim["status"],
        error=sim.get("error")
    )

@app.get("/simulations/{sim_id}/results", response_model=SimulationResults)
async def get_simulation_results(sim_id: str) -> SimulationResults:
    """Get the results of a completed simulation."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
        
    sim = simulations[sim_id]
    if sim["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Simulation is {sim['status']}")
        
    results = sim["results"]
    return SimulationResults(
        simulation_id=sim_id,
        time=results["time"],
        recordings=results["recordings"],
        parameters=results["params"]
    )

@app.post("/simulations/{sim_id}/save", response_class=FileResponse)
async def save_simulation_results(sim_id: str) -> FileResponse:
    """Save simulation results to a CSV file."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
        
    sim = simulations[sim_id]
    if sim["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Simulation is {sim['status']}")
        
    results = sim["results"]
    
    # Create output directory if it doesn't exist
    output_dir = Path("simulation_results")
    output_dir.mkdir(exist_ok=True)
    
    # Create CSV file path
    output_file = output_dir / f"simulation_{sim_id}.csv"
    
    # Write results to CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write header
        header = ['time'] + list(results['recordings'].keys())
        writer.writerow(header)
        
        # Write data rows
        time = results['time']
        recordings = results['recordings']
        for i in range(len(time)):
            row = [time[i]] + [recordings[var][i] for var in header[1:]]
            writer.writerow(row)
    
    return FileResponse(
        path=str(output_file),
        filename=output_file.name,
        media_type="text/csv"
    )

