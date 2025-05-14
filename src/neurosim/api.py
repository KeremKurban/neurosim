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

# Initialize FastAPI app
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
task_manager = SimulationTaskManager()

async def run_simulation_task(sim_id: str, request: SimulationRequest):
    """Background task to run simulation."""
    try:
        # Update simulation status
        simulations[sim_id]["status"] = "running"
        task_manager.update_progress(sim_id, 0.0)
        
        # Check for cancellation
        if task_manager.should_cancel(sim_id):
            simulations[sim_id]["status"] = "cancelled"
            return

        # Load model
        simulator.load_model(request.model_id)
        task_manager.update_progress(sim_id, 10.0)
        
        # Setup recordings
        for rec in request.recordings:
            simulator.setup_recording(rec.section, rec.variable)
        task_manager.update_progress(sim_id, 20.0)
        
        if task_manager.should_cancel(sim_id):
            simulations[sim_id]["status"] = "cancelled"
            return
        
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
        task_manager.update_progress(sim_id, 30.0)
        
        # Run simulation with progress tracking
        total_time = request.conditions.duration
        time_step = request.conditions.dt
        steps = int(total_time / time_step)
        
        results = await asyncio.get_event_loop().run_in_executor(
            None,  # Use default executor
            lambda: simulator.run_simulation(
                duration=total_time,
                dt=time_step,
                v_init=request.conditions.v_init,
                celsius=request.conditions.celsius,
                progress_callback=lambda step: task_manager.update_progress(
                    sim_id, 30.0 + (step / steps) * 70.0
                ) if not task_manager.should_cancel(sim_id) else False
            )
        )
        
        if task_manager.should_cancel(sim_id):
            simulations[sim_id]["status"] = "cancelled"
            return
            
        # Store results
        simulations[sim_id].update({
            "status": "completed",
            "results": results
        })
        task_manager.update_progress(sim_id, 100.0)
        
    except Exception as e:
        simulations[sim_id].update({
            "status": "failed",
            "error": str(e)
        })
    finally:
        simulator.cleanup()
        task_manager.cleanup_task(sim_id)

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
        status=sim["status"]
    )

@app.get("/simulations/{sim_id}/results", response_model=SimulationResults)
async def get_simulation_results(sim_id: str) -> SimulationResults:
    """Get the results of a completed simulation."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    sim = simulations[sim_id]
    if sim["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Simulation results not ready. Current status: {sim['status']}"
        )
    
    if "results" not in sim:
        raise HTTPException(status_code=500, detail="Results not found")
    
    return SimulationResults(**sim["results"])

@app.get("/simulations/{sim_id}/progress")
async def get_simulation_progress(sim_id: str):
    """Get detailed simulation progress."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    return {
        "simulation_id": sim_id,
        "status": simulations[sim_id]["status"],
        "progress": task_manager.get_progress(sim_id)
    }

@app.post("/simulations/{sim_id}/cancel")
async def cancel_simulation(sim_id: str):
    """Cancel a running simulation."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    if simulations[sim_id]["status"] not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail="Simulation cannot be cancelled")
    
    success = await task_manager.cancel_task(sim_id)
    if success:
        simulations[sim_id]["status"] = "cancelled"
        return {"status": "cancelled"}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel simulation")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
