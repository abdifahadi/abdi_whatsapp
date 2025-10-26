"""
Railway app entry point
This file is used by Railway to start the WhatsApp bot application
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main WhatsApp bot app
from whatsapp_bot import app

if __name__ == "__main__":
    # Import uvicorn only when needed
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)