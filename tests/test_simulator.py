"""Test the neuron simulation core functionality."""
import pytest
import numpy as np
from neurosim.core.simulator import NeuronSimulator
from neurosim.models.cells.simple_neuron import SimpleNeuron

def test_simulator_initialization():
    """Test that the simulator initializes correctly."""
    sim = NeuronSimulator()
    assert sim is not None
    assert sim.recordings == {}
    assert sim.cell is None

def test_simple_neuron_creation():
    """Test that we can create a simple neuron model."""
    neuron = SimpleNeuron()
    assert neuron is not None
    assert hasattr(neuron, 'soma')
    assert neuron.soma.name() == 'soma'
    
    # Test basic properties
    assert neuron.soma.L == 20  # Length
    assert neuron.soma.diam == 20  # Diameter
    assert neuron.soma.Ra == 100  # Axial resistance
    assert neuron.soma.cm == 1  # Membrane capacitance

def test_recording_setup():
    """Test setting up voltage recording."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()      # Test voltage recording
    sim.setup_recording('soma', 'v')
    assert 'soma_v' in sim.recordings
    
    # Test membrane current recording
    sim.setup_recording('soma', 'i_membrane')
    assert 'soma_i_membrane' in sim.recordings
    
    # Test invalid section
    with pytest.raises(ValueError):
        sim.setup_recording('dendrite', 'v')

def test_iclamp_stimulus():
    """Test setting up current clamp stimulus."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()
    
    # Test basic current clamp
    stim_params = {
        'delay': 100,
        'duration': 500,
        'amplitude': 0.5
    }
    sim.setup_stimulus('soma', 'IClamp', stim_params)
    assert hasattr(sim, 'stimulus')
    
    # Test voltage clamp
    vclamp_params = {
        'duration': 500,
        'amplitude': -65,
        'rs': 0.1
    }
    sim.setup_stimulus('soma', 'VClamp', vclamp_params)
    assert hasattr(sim, 'stimulus')
    
    # Test invalid section
    with pytest.raises(ValueError):
        sim.setup_stimulus('dendrite', 'IClamp', stim_params)

def test_run_simulation():
    """Test running a complete simulation."""
    sim = NeuronSimulator()
    sim.cell = SimpleNeuron()
    
    # Setup recording
    sim.setup_recording('soma', 'v')
      # Setup stimulus - use parameters that should trigger an action potential
    stim_params = {
        'delay': 100,
        'duration': 50,
        'amplitude': 2.0  # Stronger stimulus to ensure spike
    }
    sim.setup_stimulus('soma', 'IClamp', stim_params)
    
    # Run simulation
    results = sim.run_simulation(
        duration=300.0,
        dt=0.025,
        v_init=-65.0,
        celsius=34.0
    )
    
    # Basic result structure tests
    assert 'time' in results
    assert 'recordings' in results
    assert 'soma_v' in results['recordings']
    assert len(results['time']) > 0
    assert len(results['recordings']['soma_v']) == len(results['time'])
    
    # Test time array properties
    time = np.array(results['time'])
    assert time[0] == 0.0
    assert time[-1] == pytest.approx(300.0)
    assert np.all(np.diff(time) == pytest.approx(0.025))
    
    # Test voltage array properties
    v = np.array(results['recordings']['soma_v'])
    assert v[0] == pytest.approx(-65.0)  # Initial voltage
    assert np.min(v) <= -65.0  # Should have hyperpolarization
    if not sim._mock_mode:
        assert np.max(v) > 0.0  # Should have spike

def test_cleanup():
    """Test cleanup of simulator objects."""
    sim = NeuronSimulator()
    
    if sim._mock_mode:
        sim.recordings['soma_v'] = [0]  # Fake a mock recording
        sim.stimulus = {'type': 'IClamp', 'params': {}, 'section': 'soma'}
    else:
        sim.load_model("simple_neuron")
        sim.setup_recording('soma', 'v')
        sim.setup_stimulus('soma', 'IClamp', {'delay': 100, 'duration': 500, 'amplitude': 0.5})
    
    sim.cleanup()
    assert not hasattr(sim, 'stimulus')
    assert sim.recordings == {}