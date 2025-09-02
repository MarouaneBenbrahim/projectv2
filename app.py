"""
Manhattan Power Grid - Main Application
Professional integrated power and traffic management system
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime
from typing import Dict, List

# Import our modules
from core.power_system import ManhattanPowerGrid
from config.settings import settings
from config.database import db_manager

# Initialize FastAPI
app = FastAPI(
    title="Manhattan Power Grid",
    version=settings.version,
    description="Professional Power Grid Management System"
)

# Initialize systems
power_grid = ManhattanPowerGrid()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """Initialize systems on startup"""
    db_manager.initialize()
    print(f"🚀 Manhattan Power Grid v{settings.version} started")
    print(f"📊 Environment: {settings.environment}")
    print(f"🔌 Power System: Online")
    print(f"🚦 Traffic System: Initializing...")
    
    # Start background tasks
    asyncio.create_task(simulation_loop())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await db_manager.close_async()

async def simulation_loop():
    """Main simulation loop"""
    while True:
        # Run power flow
        result = power_grid.run_power_flow()
        
        # Get system status
        status = power_grid.get_system_status()
        
        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "status_update",
            "data": status
        })
        
        # Sleep for simulation interval
        await asyncio.sleep(1)

@app.get("/")
async def root():
    """Serve main dashboard"""
    return HTMLResponse(content=open("frontend/index.html").read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle commands from client
            command = json.loads(data)
            
            if command["type"] == "trigger_failure":
                result = power_grid.trigger_failure(
                    command["component_type"],
                    command["component_id"]
                )
                await websocket.send_json({"type": "failure_result", "data": result})
            
            elif command["type"] == "restore":
                power_grid.restore_component(
                    command["component_type"],
                    command["component_id"]
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/status")
async def get_status():
    """Get current system status"""
    return power_grid.get_system_status()

@app.post("/api/failure/{component_type}/{component_id}")
async def trigger_failure(component_type: str, component_id: str):
    """Trigger component failure"""
    result = power_grid.trigger_failure(component_type, component_id)
    return result

@app.post("/api/restore/{component_type}/{component_id}")
async def restore_component(component_type: str, component_id: str):
    """Restore failed component"""
    success = power_grid.restore_component(component_type, component_id)
    return {"success": success}

@app.get("/api/contingency")
async def run_contingency():
    """Run N-1 contingency analysis"""
    from core.power_system import ContingencyType
    results = power_grid.run_contingency_analysis(ContingencyType.N_1)
    return {"contingencies": [r.__dict__ for r in results]}

@app.get("/api/optimize")
async def optimize_dispatch():
    """Run optimal power flow"""
    result = power_grid.optimize_dispatch()
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)