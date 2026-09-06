"""
Recomputes baselines for every stock found in the imported historical
data.
"""
from app.services.baseline_worker import run_baseline_worker

if __name__ == "__main__":
    run_baseline_worker()
