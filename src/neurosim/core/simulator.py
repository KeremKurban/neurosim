"""Core simulation engine using NEURON simulator."""
from typing import Dict, List, Optional, Tuple
import numpy as np
from pathlib import Path
import json

try:
    from neuron import h
    HAS_NEURON = True
except ImportError:
    print("NEURON simulator not available. Running in mock mode.")
    HAS_NEURON = False

class NeuronSimulator:
    """NEURON simulator wrapper for single cell simulations."""
    
    def __init__(self):
        """Initialize NEURON simulator."""
        self._mock_mode = not HAS_NEURON
        if HAS_NEURON:
            h.load_file('stdrun.hoc')
        self.cell = None
        self.recordings = {}
        
    def load_model(self, model_path: str) -> None:
        """Load a NEURON model."""
        if model_path == "simple_neuron":
            from neurosim.models.cells.simple_neuron import SimpleNeuron
            self.cell = SimpleNeuron()
        else:
            model_path = Path(model_path)
            if model_path.suffix == '.hoc' and HAS_NEURON:
                h.load_file(str(model_path))
            elif model_path.suffix == '.py':
                # For Python cell models
                pass
            
    def setup_recording(self, section: str, variable: str = 'v') -> None:
        """Set up recording for a specific section and variable."""
        if self._mock_mode:
            self.recordings[f"{section}_{variable}"] = []
            return

        section_obj = self.cell.get_section(section)
        rec = h.Vector()
        
        # Record from the middle of the section (0.5)
        if variable == 'v':
            rec.record(section_obj(0.5)._ref_v)
        elif variable == 'i':
            rec.record(section_obj(0.5)._ref_i)
            
        self.recordings[f"{section}_{variable}"] = rec
        
    def setup_stimulus(self, section: str, stim_type: str, params: Dict) -> None:
        """Set up stimulation protocol."""
        if self._mock_mode:
            self.stimulus = {
                'type': stim_type,
                'params': params,
                'section': section
            }
            return
            
        sec = self.cell.get_section(section)
        
        if stim_type == "IClamp":
            stim = h.IClamp(sec(0.5))
            stim.delay = params.get('delay', 100)  # ms
            stim.dur = params.get('duration', 500)  # ms
            stim.amp = params.get('amplitude', 0.1)  # nA
        elif stim_type == "VClamp":
            stim = h.SEClamp(sec(0.5))
            stim.rs = params.get('rs', 0.1)  # MΩ
            stim.dur1 = params.get('duration', 500)  # ms
            stim.amp1 = params.get('amplitude', -65)  # mV
            
        self.stimulus = stim
        
    def run_simulation(self, 
                      duration: float = 1000.0,
                      dt: float = 0.025,
                      v_init: float = -65.0,
                      celsius: float = 34.0) -> Dict:
        """Run simulation and return results."""
        if self._mock_mode:
            # Generate mock data for testing
            time = np.arange(0, duration, dt)
            mock_v = v_init + np.sin(time/100) * 10  # Simple oscillating voltage
            
            results = {
                'time': list(time),
                'recordings': {
                    name: list(mock_v) for name in self.recordings.keys()
                },
                'params': {
                    'duration': duration,
                    'dt': dt,
                    'v_init': v_init,
                    'celsius': celsius
                }
            }
            return results
            
        h.celsius = celsius
        h.dt = dt
        h.tstop = duration
        h.v_init = v_init
        
        # Record time
        time = h.Vector()
        time.record(h._ref_t)
        
        h.finitialize(v_init)
        h.continuerun(duration)
        
        # Collect results
        results = {
            'time': list(time),
            'recordings': {
                name: list(rec) for name, rec in self.recordings.items()
            },
            'params': {
                'duration': duration,
                'dt': dt,
                'v_init': v_init,
                'celsius': celsius
            }
        }
        
        return results
    
    def cleanup(self):
        """Clean up NEURON objects."""
        self.recordings.clear()
        if hasattr(self, 'stimulus'):
            del self.stimulus
        if hasattr(self, 'cell'):
            del self.cell
