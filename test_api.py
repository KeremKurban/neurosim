"""Test script to run a simulation through the API."""
import httpx
import time
import json

# The simulation request
simulation_request = {
    "model_id": "simple_neuron",
    "stimulus": {
        "type": "IClamp",
        "delay": 100,    # Start stimulus after 100ms
        "duration": 1000,  # Apply stimulus for 1000ms
        "amplitude": 1.0   # Increased to 1.0 nA to trigger action potentials
    },
    "recordings": [
        {
            "section": "soma",
            "variable": "v"   # Record membrane voltage
        }
    ],
    "conditions": {
        "duration": 1500,    # Run for 1.5 seconds total
        "dt": 0.025,        # Fine timescale for accurate spike timing
        "v_init": -65,      # Starting membrane potential
        "celsius": 34       # Temperature affects channel kinetics
    }
}

# Create a new simulation
try:
    response = httpx.post(
        "http://localhost:8000/simulations",
        json=simulation_request
    )
    response.raise_for_status()  # Will raise an exception for 4XX/5XX status codes
    print("\nStarting simulation:")
    print(response.json())
except httpx.RequestError as e:
    print(f"\nError connecting to server: {e}")
    exit(1)
except httpx.HTTPStatusError as e:
    print(f"\nHTTP error occurred: {e}")
    exit(1)
except Exception as e:
    print(f"\nUnexpected error: {e}")
    exit(1)

sim_id = response.json()["simulation_id"]

# Poll for status until complete
while True:
    status_response = httpx.get(f"http://localhost:8000/simulations/{sim_id}")
    status = status_response.json()
    print(f"\nSimulation status: {status['status']}")
    
    if status["status"] in ["completed", "failed"]:
        break
        
    time.sleep(1)  # Wait a second before checking again

# If simulation completed successfully, get results
if status["status"] == "completed":
    results = httpx.get(f"http://localhost:8000/simulations/{sim_id}/results")
    results_data = results.json()
    
    print("\nSimulation results:")
    print(f"- Time points: {len(results_data['time'])} samples")
    print(f"- Recordings: {list(results_data['recordings'].keys())}")
    print(f"- Parameters: {json.dumps(results_data['parameters'], indent=2)}")
      # Analyze the voltage trace
    v_trace = results_data['recordings']['soma_v']
    time = results_data['time']
    
    # Simple spike detection (threshold crossing at 0 mV)
    spike_times = []
    for i in range(1, len(v_trace)):
        if v_trace[i-1] < 0 and v_trace[i] >= 0:
            spike_times.append(time[i])
    
    print(f"\nSimulation Analysis:")
    print(f"- Maximum voltage: {max(v_trace):.2f} mV")
    print(f"- Minimum voltage: {min(v_trace):.2f} mV")
    print(f"- Number of spikes: {len(spike_times)}")
    if spike_times:
        print(f"- First spike at: {spike_times[0]:.2f} ms")
        if len(spike_times) > 1:
            intervals = [spike_times[i] - spike_times[i-1] for i in range(1, len(spike_times))]
            print(f"- Average inter-spike interval: {sum(intervals)/len(intervals):.2f} ms")
elif status["status"] == "failed":
    print(f"\nSimulation failed with error: {status.get('error', 'Unknown error')}")
    # Get full traceback if available
    try:
        error_details = httpx.get(f"http://localhost:8000/simulations/{sim_id}").json()
        if 'error' in error_details:
            print(f"\nFull error details: {error_details['error']}")
    except Exception as e:
        print(f"Could not fetch detailed error: {e}")
