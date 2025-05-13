"""A simple single-compartment neuron model."""
from neuron import h

class SimpleNeuron:
    """A basic single-compartment neuron model."""
    
    def __init__(self):
        """Initialize the neuron model."""
        # Create soma
        self.soma = h.Section(name='soma')
        
        # Set geometry
        self.soma.L = 20    # Length in um 
        self.soma.diam = 20 # Diameter in um
        
        # Insert passive and active conductances
        self.soma.insert('pas')        # Passive channel
        self.soma.insert('hh')         # Hodgkin-Huxley channels
        
        # Set parameters
        self.soma.Ra = 100    # Axial resistance in ohm-cm
        self.soma.cm = 1      # Membrane capacitance in uF/cm2
        
        self.soma.g_pas = 0.0001     # Passive conductance in S/cm2
        self.soma.e_pas = -65        # Leak reversal potential in mV
        
    def get_section(self, name: str):
        """Get a section by name."""
        if name.lower() == 'soma':
            return self.soma
        raise ValueError(f"Section {name} not found")
