"""
Minimal API Service for testing Docker build
"""

from fastapi import FastAPI
import os

app = FastAPI(title="Voice Agent API Service")

@app.get("/")
def root():
    return {"message": "Voice Agent API Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
