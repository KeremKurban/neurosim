"""Visualize neuron simulation results with voltage trace and morphology."""
import httpx
import time
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from neuron import h, gui  # gui is needed for shape plots

def run_simulation():
    """Run a simulation and return the results."""
    simulation_request = {
        "model_id": "simple_neuron",
        "stimulus": {
            "type": "IClamp",
            "delay": 100,    # Start stimulus after 100ms
            "duration": 50,   # Short stimulus to trigger single spike
            "amplitude": 1.0  # Strong enough to trigger spike
        },
        "recordings": [
            {
                "section": "soma",
                "variable": "v"
            }
        ],
        "conditions": {
            "duration": 300,     # Shorter simulation to see spike clearly
            "dt": 0.025,
            "v_init": -65,
            "celsius": 34
        }
    }

    # Start simulation
    response = httpx.post(
        "http://localhost:8000/simulations",
        json=simulation_request
    )
    sim_id = response.json()["simulation_id"]

    # Wait for completion
    while True:
        status_response = httpx.get(f"http://localhost:8000/simulations/{sim_id}")
        status = status_response.json()
        if status["status"] in ["completed", "failed"]:
            break
        time.sleep(0.1)

    if status["status"] == "failed":
        raise Exception(f"Simulation failed: {status.get('error', 'Unknown error')}")

    # Get results
    results = httpx.get(f"http://localhost:8000/simulations/{sim_id}/results")
    return results.json()

def create_visualization(results_data):
    """Create a figure with voltage trace and neuron morphology."""
    # Create figure with grid layout
    fig = plt.figure(figsize=(12, 6))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[2, 1])

    # Plot voltage trace
    ax1 = fig.add_subplot(gs[0])
    time = results_data['time']
    v_trace = results_data['recordings']['soma_v']
    ax1.plot(time, v_trace, 'b-', label='Membrane Potential')
    ax1.set_xlabel('Time (ms)')
    ax1.set_ylabel('Membrane Potential (mV)')
    ax1.set_title('Voltage Trace')
    ax1.grid(True)

    # Add stimulus indication
    stim_start = 100  # from our simulation parameters
    stim_end = 150    # start + duration
    ax1.axvspan(stim_start, stim_end, color='yellow', alpha=0.3, label='Stimulus')
    ax1.legend()

    # Create shape plot
    ax2 = fig.add_subplot(gs[1])
    ax2.set_title('Neuron Morphology')
    
    # Draw simple soma representation (since we have a single compartment)
    circle = plt.Circle((0.5, 0.5), 0.3, color='b', fill=False)
    ax2.add_patch(circle)
    ax2.text(0.5, 0.8, 'Soma', horizontalalignment='center')
    
    # Set axis properties
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.set_aspect('equal')
    ax2.axis('off')

    # Adjust layout
    plt.tight_layout()
    
    # Save the figure
    plt.savefig('simulation_results.png')
    print("\nVisualization saved as 'simulation_results.png'")

def main():
    """Run simulation and create visualization."""
    print("Running simulation...")
    results = run_simulation()
    
    print("Creating visualization...")
    create_visualization(results)
    
    # Print some analysis
    v_trace = results['recordings']['soma_v']
    print("\nSimulation Analysis:")
    print(f"- Maximum voltage: {max(v_trace):.2f} mV")
    print(f"- Minimum voltage: {min(v_trace):.2f} mV")
    print(f"- Resting potential: {v_trace[0]:.2f} mV")
    
    # Detect spikes
    spike_times = []
    for i in range(1, len(v_trace)):
        if v_trace[i-1] < 0 and v_trace[i] >= 0:
            spike_times.append(results['time'][i])
    
    if spike_times:
        print(f"- Number of spikes: {len(spike_times)}")
        print(f"- First spike at: {spike_times[0]:.2f} ms")

if __name__ == "__main__":
    main()
