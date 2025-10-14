"""
FastAPI Backend Application
A simple FastAPI application with CORS enabled for QuickBooks Automation API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Initialize FastAPI application
app = FastAPI(
    title="QuickBooks Automation API",
    description="A FastAPI backend for QuickBooks automation services",
    version="1.0.0"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    
    Returns:
        dict: JSON response with API status message
    """
    return {"message": "QuickBooks Automation API is live!"}

@app.get("/ping")
async def ping():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        dict: JSON response with status confirmation
    """
    return {"status": "ok"}

if __name__ == "__main__":
    # Run the application with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)