"""Core simulation engine using NEURON simulator."""
from typing import Dict, Optional
import numpy as np
from pathlib import Path

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
        self.recordings: Dict[str, 'h.Vector'] = {}
        self.stimulus = None

    def load_model(self, model_path: str) -> None:
        """Load a NEURON model."""
        if model_path == "simple_neuron":
            from neurosim.models.cells.simple_neuron import SimpleNeuron
            self.cell = SimpleNeuron()
        else:
            model_path = Path(model_path)
            if HAS_NEURON:
                if model_path.suffix == '.hoc':
                    h.load_file(str(model_path))
                elif model_path.suffix == '.py':
                    # Add your logic to import and initialize the Python-based model
                    raise NotImplementedError("Python model loading not yet implemented.")

    def setup_recording(self, section: str, variable: str = 'v') -> None:
        """Set up recording for a specific section and variable."""
        key = f"{section}_{variable}"
        if self._mock_mode:
            self.recordings[key] = []
            return

        section_obj = self.cell.get_section(section)
        point = section_obj(0.5)
        rec = h.Vector()

        h.finitialize(-65)

        if variable == 'v':
            rec.record(point._ref_v)
        elif variable == 'i_membrane':
            h.cvode.use_fast_imem(1)  # Required for i_membrane_ recording
            try:
                rec.record(point._ref_i_membrane_)
            except AttributeError:
                raise RuntimeError(
                    f"Cannot record {variable}: _ref_i_membrane_ not available in section '{section}'"
                )
        else:
            raise ValueError(f"Unsupported recording variable: {variable}")

        self.recordings[key] = rec

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
            stim.delay = params.get('delay', 100)
            stim.dur = params.get('duration', 500)
            stim.amp = params.get('amplitude', 0.1)
        elif stim_type == "VClamp":
            stim = h.SEClamp(sec(0.5))
            stim.rs = params.get('rs', 0.1)
            stim.dur1 = params.get('duration', 500)
            stim.amp1 = params.get('amplitude', -65)
        else:
            raise ValueError(f"Unsupported stimulation type: {stim_type}")

        self.stimulus = stim

    def run_simulation(
        self,
        duration: float = 1000.0,
        dt: float = 0.025,
        v_init: float = -65.0,
        celsius: float = 34.0
    ) -> Dict:
        """Run simulation and return results."""
        if self._mock_mode:
            time = np.arange(0, duration, dt)
            mock_v = v_init + np.sin(time / 100) * 10
            return {
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

        h.dt = dt
        h.celsius = celsius
        h.tstop = duration

        time_vec = h.Vector().record(h._ref_t)

        h.finitialize(v_init)
        h.fcurrent()
        h.continuerun(duration)

        return {
            'time': list(time_vec),
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

    def cleanup(self) -> None:
        """Clean up NEURON objects."""
        self.recordings.clear()
        if hasattr(self, 'stimulus'):
            del self.stimulus
        if hasattr(self, 'cell'):
            del self.cell
