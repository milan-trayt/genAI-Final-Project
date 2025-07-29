#!/bin/bash
cd /workspace

# Start API server in background
python api_server.py &

# Start Jupyter notebook
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''