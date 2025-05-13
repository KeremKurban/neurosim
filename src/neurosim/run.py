"""Run the neuron simulation service."""
import uvicorn

def main():
    """Run the FastAPI application."""
    uvicorn.run("neurosim.api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
