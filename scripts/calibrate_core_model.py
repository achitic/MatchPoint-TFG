"""
Legacy wrapper for backward compatibility.

This script intentionally delegates to `train_core_calibrated.py` so there is
only one authoritative implementation of calibrated training.
"""
from train_core_calibrated import main


if __name__ == "__main__":
    print("calibrate_core_model.py is deprecated. Redirecting to train_core_calibrated.py")
    main()
