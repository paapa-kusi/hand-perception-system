#!/bin/bash

# Configuration
ENV_NAME="cv_hand_perception"
YAML_FILE="environment.yml"
MAIN_SCRIPT="cv_hand_perception/main.py"

# Function to check if conda is installed
check_conda() {
    if ! command -v conda &> /dev/null; then
        echo "Error: conda is not installed or not in PATH."
        exit 1
    fi
}

# Function to setup the environment
setup_env() {
    echo "Checking if conda environment '$ENV_NAME' exists..."
    if ! conda info --envs | grep -q "$ENV_NAME"; then
        echo "Environment '$ENV_NAME' not found. Creating from $YAML_FILE..."
        conda env create -f "$YAML_FILE"
    else
        echo "Environment '$ENV_NAME' already exists."
        # Optional: update environment
        # echo "Updating environment..."
        # conda env update -f "$YAML_FILE" --prune
    fi
}

# Main execution
check_conda

# Initialize conda for the script
CONDA_BASE=$(conda info --base)
source "$CONDA_BASE/etc/profile.d/conda.sh"

setup_env

echo "Activating environment '$ENV_NAME'..."
conda activate "$ENV_NAME"

echo "Starting the program..."
# The script expects to be run from the cv_hand_perception directory
cd cv_hand_perception
python main.py "$@"
