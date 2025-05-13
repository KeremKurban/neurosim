"""FastAPI application for the neuron simulation service."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uuid
from typing import Dict

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
        simulator.load_model(f"models/{request.model_id}.hoc")
        
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

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
