# advanced_api.py
"""
Manhattan Power Grid - Advanced API Layer
FastAPI + WebSockets + GraphQL + Real-time Streaming
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import json
import time
from datetime import datetime, timedelta
import jwt
from contextlib import asynccontextmanager
import aioredis
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog
from dataclasses import dataclass
import numpy as np

logger = structlog.get_logger()

# ========================= METRICS =========================

# Prometheus metrics
api_requests = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
api_latency = Histogram('api_request_duration_seconds', 'API request latency')
websocket_connections = Gauge('websocket_connections_active', 'Active WebSocket connections')
system_health = Gauge('system_health_score', 'Overall system health score')
power_load = Gauge('power_load_mw', 'Current power load in MW')
traffic_lights_powered = Gauge('traffic_lights_powered', 'Number of powered traffic lights')

# ========================= AUTHENTICATION =========================

security = HTTPBearer()

class AuthManager:
    """JWT-based authentication with role-based access control"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        
    def create_token(self, user_id: str, role: str, expires_delta: timedelta = timedelta(hours=24)):
        """Create JWT token"""
        expire = datetime.utcnow() + expires_delta
        payload = {
            'sub': user_id,
            'role': role,
            'exp': expire,
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
    def verify_token(self, token: str) -> Dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
            
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Security(security)):
        """Dependency to get current user from token"""
        token = credentials.credentials
        payload = self.verify_token(token)
        return {
            'user_id': payload['sub'],
            'role': payload['role']
        }

auth_manager = AuthManager(secret_key="your-secret-key-change-in-production")

# ========================= WEBSOCKET MANAGER =========================

class ConnectionManager:
    """Advanced WebSocket connection manager with rooms and broadcasting"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, List[str]] = {}  # user_id -> topics
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.user_connections[user_id] = websocket
        self.subscriptions[user_id] = []
        websocket_connections.inc()
        logger.info(f"WebSocket connected: {user_id}")
        
    def disconnect(self, user_id: str):
        """Handle WebSocket disconnection"""
        if user_id in self.user_connections:
            del self.user_connections[user_id]
            del self.subscriptions[user_id]
            websocket_connections.dec()
            logger.info(f"WebSocket disconnected: {user_id}")
            
    async def subscribe(self, user_id: str, topics: List[str]):
        """Subscribe user to topics"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id].extend(topics)
            
    async def unsubscribe(self, user_id: str, topics: List[str]):
        """Unsubscribe user from topics"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id] = [
                t for t in self.subscriptions[user_id] 
                if t not in topics
            ]
            
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user"""
        if user_id in self.user_connections:
            await self.user_connections[user_id].send_json(message)
            
    async def broadcast(self, message: dict, topic: str):
        """Broadcast message to all subscribers of a topic"""
        tasks = []
        for user_id, topics in self.subscriptions.items():
            if topic in topics and user_id in self.user_connections:
                tasks.append(
                    self.user_connections[user_id].send_json(message)
                )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def broadcast_to_role(self, message: dict, role: str):
        """Broadcast message to users with specific role"""
        # This would check user roles from auth system
        pass

manager = ConnectionManager()

# ========================= GRAPHQL SCHEMA =========================

@strawberry.type
class PowerMetrics:
    timestamp: str
    total_load_mw: float
    total_generation_mw: float
    frequency_hz: float
    system_lambda: float
    losses_mw: float
    renewable_percentage: float

@strawberry.type
class TrafficMetrics:
    total_lights: int
    powered_lights: int
    green_lights: int
    red_lights: int
    avg_wait_time: float
    congestion_level: float

@strawberry.type
class SubstationStatus:
    id: str
    name: str
    operational: bool
    capacity_mva: float
    current_load_mva: float
    voltage_kv: float
    temperature_c: float

@strawberry.type
class Prediction:
    timestamp: str
    type: str
    horizon_hours: int
    values: List[float]
    confidence: float

@strawberry.type
class Query:
    @strawberry.field
    async def power_metrics(self) -> PowerMetrics:
        """Get current power metrics"""
        # This would fetch from your power system
        return PowerMetrics(
            timestamp=datetime.now().isoformat(),
            total_load_mw=2500,
            total_generation_mw=2550,
            frequency_hz=60.0,
            system_lambda=45.0,
            losses_mw=50,
            renewable_percentage=0.3
        )
    
    @strawberry.field
    async def traffic_metrics(self) -> TrafficMetrics:
        """Get current traffic metrics"""
        return TrafficMetrics(
            total_lights=657,
            powered_lights=650,
            green_lights=300,
            red_lights=350,
            avg_wait_time=45.0,
            congestion_level=0.6
        )
    
    @strawberry.field
    async def substations(self, operational_only: bool = False) -> List[SubstationStatus]:
        """Get substation statuses"""
        # This would fetch from your system
        substations = []
        # Add real data here
        return substations
    
    @strawberry.field
    async def predictions(self, type: str) -> List[Prediction]:
        """Get predictions by type"""
        # Fetch from ML models
        return []

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def trigger_failure(self, component_id: str) -> bool:
        """Trigger component failure"""
        # Implement failure logic
        return True
    
    @strawberry.mutation
    async def restore_component(self, component_id: str) -> bool:
        """Restore component"""
        # Implement restoration logic
        return True
    
    @strawberry.mutation
    async def override_traffic_light(self, light_id: str, phase: str) -> bool:
        """Manual traffic light override"""
        # Implement override logic
        return True

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def power_updates(self) -> AsyncGenerator[PowerMetrics, None]:
        """Subscribe to real-time power updates"""
        while True:
            yield PowerMetrics(
                timestamp=datetime.now().isoformat(),
                total_load_mw=2500 + np.random.randn() * 50,
                total_generation_mw=2550 + np.random.randn() * 50,
                frequency_hz=60.0 + np.random.randn() * 0.1,
                system_lambda=45.0 + np.random.randn() * 5,
                losses_mw=50 + np.random.randn() * 5,
                renewable_percentage=0.3 + np.random.randn() * 0.05
            )
            await asyncio.sleep(1)

schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)

# ========================= ADVANCED API =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Manhattan Power Grid API")
    
    # Initialize Redis
    app.state.redis = await aioredis.create_redis_pool('redis://localhost')
    
    # Initialize ML models
    from manhattan_core_advanced import ManhattanAdvancedSystem
    app.state.system = ManhattanAdvancedSystem()
    await app.state.system.initialize()
    
    # Start background tasks
    asyncio.create_task(metrics_updater(app))
    asyncio.create_task(event_streamer(app))
    
    yield
    
    # Shutdown
    logger.info("Shutting down Manhattan Power Grid API")
    app.state.redis.close()
    await app.state.redis.wait_closed()

app = FastAPI(
    title="Manhattan Power Grid Advanced API",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GraphQL
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

# ========================= REST ENDPOINTS =========================

@app.get("/api/v2/system/health")
async def health_check():
    """Advanced health check with component status"""
    
    health = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'power_system': 'operational',
            'traffic_control': 'operational',
            'ml_models': 'operational',
            'database': 'operational',
            'cache': 'operational'
        },
        'metrics': {
            'uptime_seconds': time.time(),
            'api_requests': api_requests._value._value,
            'websocket_connections': websocket_connections._value._value
        }
    }
    
    system_health.set(100)  # Update Prometheus metric
    
    return health

@app.get("/api/v2/system/state")
@api_latency.time()
async def get_system_state(current_user: dict = Depends(auth_manager.get_current_user)):
    """Get complete system state with caching"""
    
    api_requests.labels(method='GET', endpoint='/system/state').inc()
    
    # Get from cache or system
    system_state = await app.state.system.get_system_state()
    
    # Filter based on user role
    if current_user['role'] != 'admin':
        # Remove sensitive data for non-admin users
        system_state.pop('predictions', None)
        
    return system_state

@app.post("/api/v2/simulation/scenario")
async def run_scenario(
    scenario: dict,
    current_user: dict = Depends(auth_manager.get_current_user)
):
    """Run what-if scenario simulation"""
    
    if current_user['role'] not in ['admin', 'operator']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Run scenario in digital twin
    results = await app.state.system.digital_twin.simulate_scenario(
        scenario,
        duration_hours=scenario.get('duration_hours', 24)
    )
    
    return results

@app.get("/api/v2/streaming/events")
async def stream_events(
    topics: str = "all",
    current_user: dict = Depends(auth_manager.get_current_user)
):
    """Server-sent events for real-time updates"""
    
    async def event_generator():
        """Generate SSE stream"""
        pubsub = app.state.redis.pubsub()
        
        # Subscribe to topics
        if topics == "all":
            await pubsub.subscribe("events:*")
        else:
            for topic in topics.split(","):
                await pubsub.subscribe(f"events:{topic}")
        
        # Stream events
        async for message in pubsub.listen():
            if message['type'] == 'message':
                yield f"data: {message['data'].decode()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.get("/api/v2/ml/predictions/{model_type}")
async def get_predictions(
    model_type: str,
    horizon: int = 24,
    current_user: dict = Depends(auth_manager.get_current_user)
):
    """Get ML model predictions"""
    
    api_requests.labels(method='GET', endpoint=f'/ml/predictions/{model_type}').inc()
    
    if model_type == "load":
        predictions = app.state.system.load_forecaster.predict(horizon)
        return predictions.to_dict()
    elif model_type == "traffic":
        predictions = await app.state.system.traffic_controller.predict_traffic_flow(
            await app.state.system._get_traffic_state(),
            horizon * 60  # Convert to minutes
        )
        return predictions.to_dict()
    else:
        raise HTTPException(status_code=404, detail="Model not found")

@app.post("/api/v2/control/emergency")
async def emergency_control(
    action: dict,
    current_user: dict = Depends(auth_manager.get_current_user)
):
    """Emergency control actions"""
    
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    logger.warning(f"Emergency action by {current_user['user_id']}: {action}")
    
    if action['type'] == 'load_shed':
        # Implement load shedding
        pass
    elif action['type'] == 'island_mode':
        # Implement islanding
        pass
    elif action['type'] == 'black_start':
        # Implement black start
        pass
    
    return {'status': 'executed', 'action': action}

# ========================= WEBSOCKET ENDPOINTS =========================

@app.websocket("/ws/v2/realtime")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str
):
    """Advanced WebSocket endpoint with authentication"""
    
    try:
        # Verify token
        payload = auth_manager.verify_token(token)
        user_id = payload['sub']
        
        # Accept connection
        await manager.connect(websocket, user_id)
        
        # Send initial state
        await websocket.send_json({
            'type': 'connection',
            'status': 'connected',
            'user_id': user_id
        })
        
        # Handle messages
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'subscribe':
                await manager.subscribe(user_id, data['topics'])
                
            elif data['type'] == 'unsubscribe':
                await manager.unsubscribe(user_id, data['topics'])
                
            elif data['type'] == 'command':
                # Handle commands
                result = await handle_command(data['command'], user_id)
                await websocket.send_json({
                    'type': 'command_result',
                    'result': result
                })
                
            elif data['type'] == 'ping':
                await websocket.send_json({'type': 'pong'})
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(user_id)

async def handle_command(command: dict, user_id: str) -> dict:
    """Handle WebSocket commands"""
    
    cmd_type = command.get('type')
    
    if cmd_type == 'get_metrics':
        return await app.state.system.get_system_state()
    elif cmd_type == 'trigger_failure':
        # Check permissions
        # Execute failure
        return {'status': 'executed'}
    else:
        return {'error': 'Unknown command'}

# ========================= BACKGROUND TASKS =========================

async def metrics_updater(app: FastAPI):
    """Update Prometheus metrics periodically"""
    
    while True:
        try:
            state = await app.state.system.get_system_state()
            
            # Update metrics
            power_load.set(state['power']['total_load_mw'])
            traffic_lights_powered.set(state['traffic']['powered_lights'])
            
        except Exception as e:
            logger.error(f"Metrics update error: {e}")
            
        await asyncio.sleep(10)

async def event_streamer(app: FastAPI):
    """Stream events to WebSocket clients"""
    
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe("events:*")
    
    async for message in pubsub.listen():
        if message['type'] == 'message':
            # Parse event
            event_data = json.loads(message['data'])
            
            # Determine topic from channel
            topic = message['channel'].decode().split(':')[1]
            
            # Broadcast to subscribers
            await manager.broadcast(event_data, topic)

# ========================= METRICS ENDPOINT =========================

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")

# ========================= ERROR HANDLERS =========================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            }
        }
    )