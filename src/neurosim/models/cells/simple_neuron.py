"""A simple single-compartment neuron model."""
try:
    from neuron import h
    HAS_NEURON = True
except ImportError:
    print("NEURON simulator not available. Using mock neuron model.")
    HAS_NEURON = False

class MockSection:
    """Mock section for testing without NEURON."""
    def __init__(self, name):
        self.name_ = name
        self.L = 20    # Length in um 
        self.diam = 20 # Diameter in um
        self.Ra = 100    # Axial resistance in ohm-cm
        self.cm = 1      # Membrane capacitance in uF/cm2
        
    def name(self):
        return self.name_
        
    def __call__(self, position):
        return self

class SimpleNeuron:
    """A basic single-compartment neuron model."""
    
    def __init__(self):
        """Initialize the neuron model."""
        if HAS_NEURON:            # Create soma
            self.soma = h.Section(name='soma')
            
            # Set geometry
            self.soma.L = 20    # Length in um 
            self.soma.diam = 20 # Diameter in um
            
            # Insert mechanisms
            self.soma.insert('hh')   # Hodgkin-Huxley channels - includes leak and membrane currents
            
            # Initialize
            h.finitialize(-65)  # Initialize at resting potential
            
            # Set parameters
            self.soma.Ra = 100    # Axial resistance in ohm-cm
            self.soma.cm = 1      # Membrane capacitance in uF/cm2
            
            # HH parameters are at their defaults which should work well
        else:
            # Create mock soma for testing
            self.soma = MockSection('soma')
        
    def get_section(self, name: str):
        """Get a section by name."""
        if name.lower() == 'soma':
            return self.soma
        raise ValueError(f"Section {name} not found")
