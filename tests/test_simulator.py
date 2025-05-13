"""Test the neuron simulation core functionality."""
import pytest
from neurosim.core.simulator import NeuronSimulator
from neurosim.models.cells.simple_neuron import SimpleNeuron

def test_simulator_initialization():
    """Test that the simulator initializes correctly."""
    sim = NeuronSimulator()
    assert sim is not None
    assert sim.recordings == {}
    
def test_simple_neuron_creation():
    """Test that we can create a simple neuron model."""
    neuron = SimpleNeuron()
    assert neuron is not None
    assert hasattr(neuron, 'soma')
    assert neuron.soma.name() == 'soma'
    
def test_recording_setup():
    """Test setting up voltage recording."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()
    sim.setup_recording('soma', 'v')
    assert 'soma_v' in sim.recordings
    
def test_iclamp_stimulus():
    """Test setting up current clamp stimulus."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()
    
    stim_params = {
        'delay': 100,
        'duration': 500,
        'amplitude': 0.5
    }
    
    sim.setup_stimulus('soma', 'IClamp', stim_params)
    assert hasattr(sim, 'stimulus')
    
def test_run_simulation():
    """Test running a complete simulation."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()
    
    # Setup recording
    sim.setup_recording('soma', 'v')
    
    # Setup stimulus
    stim_params = {
        'delay': 100,
        'duration': 500,
        'amplitude': 0.5
    }
    sim.setup_stimulus('soma', 'IClamp', stim_params)
    
    # Run simulation
    results = sim.run_simulation(duration=1000.0, dt=0.025)
    
    assert 'time' in results
    assert 'recordings' in results
    assert 'soma_v' in results['recordings']
    assert len(results['time']) > 0
    assert len(results['recordings']['soma_v']) == len(results['time'])
