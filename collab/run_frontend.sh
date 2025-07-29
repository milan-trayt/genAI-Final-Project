#!/bin/bash
# Run the Streamlit ingestion frontend

echo "🚀 Starting RAG Document Ingestion Frontend..."
streamlit run ingestion_frontend.py --server.port 8502 --server.address 0.0.0.0