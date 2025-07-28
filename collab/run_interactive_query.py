#!/usr/bin/env python3
"""
Simple launcher script for Interactive RAG Query System.
"""

import sys
import os
from pathlib import Path

# Add the collab directory to Python path
collab_dir = Path(__file__).parent
sys.path.insert(0, str(collab_dir))

# Import and run the main application
from interactive_rag_query import main
import asyncio

if __name__ == "__main__":
    print("🚀 Starting Interactive RAG Query System...")
    print("📁 Working directory:", os.getcwd())
    print("🐍 Python path:", sys.executable)
    print("=" * 60)
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)