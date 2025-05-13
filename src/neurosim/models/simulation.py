"""Models for simulation requests and responses."""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Recording(BaseModel):
    """Recording configuration."""
    section: str = Field(..., description="Section to record from (e.g., 'soma')")
    variable: str = Field(..., description="Variable to record (e.g., 'v' for voltage)")

class Stimulus(BaseModel):
    """Stimulus configuration."""
    type: str = Field(..., description="Type of stimulus (e.g., 'IClamp', 'VClamp')")
    delay: float = Field(100.0, description="Delay before stimulus onset (ms)")
    duration: float = Field(500.0, description="Duration of stimulus (ms)")
    amplitude: float = Field(..., description="Amplitude of stimulus (nA for IClamp, mV for VClamp)")

class SimulationConditions(BaseModel):
    """Simulation conditions."""
    duration: float = Field(1000.0, description="Total simulation duration (ms)")
    dt: float = Field(0.025, description="Time step (ms)")
    v_init: float = Field(-65.0, description="Initial membrane potential (mV)")
    celsius: float = Field(34.0, description="Temperature (°C)")

class SimulationRequest(BaseModel):
    """Request model for running a simulation."""
    model_id: str = Field(..., description="ID of the neuron model to simulate")
    stimulus: Stimulus
    recordings: List[Recording]
    conditions: SimulationConditions

class SimulationStatus(BaseModel):
    """Status of a simulation."""
    simulation_id: str
    status: str = Field(..., description="Status of simulation (queued, running, completed, failed)")
    error: Optional[str] = None

class SimulationResults(BaseModel):
    """Results of a completed simulation."""
    simulation_id: str
    time: List[float] = Field(..., description="Time points (ms)")
    recordings: Dict[str, List[float]] = Field(..., description="Recording data")
    parameters: Dict[str, float] = Field(..., description="Simulation parameters")
