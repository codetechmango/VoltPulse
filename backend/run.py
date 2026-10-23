import uvicorn
import os

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting VoltPulse FastAPI backend on http://{host}:{port} (listening for ESP32 and web clients)...")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
