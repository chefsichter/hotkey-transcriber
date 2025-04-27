#!/usr/bin/env bash
# run_tray.sh: Launch the Hotkey Transcriber tray application

## Load Conda if available
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
fi

# Activate the project environment
conda activate hotkey_transcriber

## Execute the installed entrypoint
exec "$CONDA_PREFIX/bin/hotkey-transcriber" "$@"
