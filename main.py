"""
GPU Job Queue Server - Main Entry Point
"""

import uvicorn
import signal
import sys
import os

import config
import models
from worker import worker_pool
from api import app


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("\nShutting down server...")
    worker_pool.stop()
    sys.exit(0)


def main():
    """Main function to start the server"""
    print("=" * 60)
    print("GPU Job Queue Server Starting...")
    print("=" * 60)
    
    # Ensure jobs directory exists
    os.makedirs(config.JOBS_DIR, exist_ok=True)
    
    # Initialize database
    print("Initializing database...")
    models.init_db()
    print("✓ Database initialized")
    
    # Start worker threads
    print("Starting worker threads...")
    worker_pool.start()
    print("✓ Workers started")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start API server
    print(f"\nStarting API server on {config.SERVER_HOST}:{config.SERVER_PORT}")
    print("=" * 60)
    print(f"API Documentation: http://{config.SERVER_HOST}:{config.SERVER_PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()

