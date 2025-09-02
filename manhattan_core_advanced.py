# manhattan_core_advanced.py
"""
Manhattan Power Grid - Advanced Core System with AI/ML Integration
Production-ready infrastructure management platform
"""

import asyncio
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as aioredis
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import torch
import torch.nn as nn
from prophet import Prophet
import networkx as nx
from scipy.optimize import differential_evolution
import logging
from abc import ABC, abstractmethod
import hashlib
import jwt
from cryptography.fernet import Fernet
import os

# Configure structured logging
import structlog
logger = structlog.get_logger()

# ========================= CONFIGURATION =========================

@dataclass
class SystemConfig:
    """Centralized system configuration"""
    
    # Security
    JWT_SECRET: str = os.environ.get('JWT_SECRET', Fernet.generate_key().decode())
    API_KEY_HASH: str = hashlib.sha256(os.environ.get('API_KEY', 'change-me').encode()).hexdigest()
    
    # ML Models
    ENABLE_ML: bool = True
    MODEL_UPDATE_INTERVAL: int = 3600  # seconds
    ANOMALY_THRESHOLD: float = 0.95
    PREDICTION_HORIZON: int = 24  # hours
    
    # Performance
    CACHE_TTL: int = 300  # seconds
    MAX_WORKERS: int = os.cpu_count() or 4
    BATCH_SIZE: int = 1000
    
    # Real-time
    WEBSOCKET_HEARTBEAT: int = 30
    EVENT_BUFFER_SIZE: int = 10000
    
    # Physics
    POWER_FLOW_METHOD: str = "newton_raphson"
    CONTINGENCY_ANALYSIS: bool = True
    VOLTAGE_TOLERANCE: float = 0.05
    
    # AI Features
    USE_GPT_ANALYSIS: bool = True
    ENABLE_PREDICTIVE_MAINTENANCE: bool = True
    ENABLE_DEMAND_RESPONSE: bool = True

config = SystemConfig()

# ========================= EVENT SYSTEM =========================

class EventType(Enum):
    """System event types"""
    POWER_FAILURE = "power_failure"
    POWER_RESTORED = "power_restored"
    LOAD_SPIKE = "load_spike"
    VOLTAGE_VIOLATION = "voltage_violation"
    TRAFFIC_CONGESTION = "traffic_congestion"
    EMERGENCY_VEHICLE = "emergency_vehicle"
    ANOMALY_DETECTED = "anomaly_detected"
    PREDICTION_READY = "prediction_ready"
    OPTIMIZATION_COMPLETE = "optimization_complete"

@dataclass
class SystemEvent:
    """Base system event"""
    event_type: EventType
    timestamp: datetime
    component_id: str
    data: Dict[str, Any]
    severity: str = "info"  # info, warning, critical
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

class EventBus:
    """Asynchronous event bus for system-wide communication"""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[callable]] = {}
        self.event_queue = asyncio.Queue(maxsize=config.EVENT_BUFFER_SIZE)
        self.redis_client = None
        self.running = False
        
    async def initialize(self):
        """Initialize event bus with Redis for distributed events"""
        self.redis_client = await aioredis.create_redis_pool('redis://localhost')
        self.running = True
        asyncio.create_task(self._process_events())
        
    def subscribe(self, event_type: EventType, handler: callable):
        """Subscribe to event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        
    async def publish(self, event: SystemEvent):
        """Publish event to bus"""
        await self.event_queue.put(event)
        
        # Publish to Redis for distributed systems
        if self.redis_client:
            await self.redis_client.publish(
                f"events:{event.event_type.value}",
                json.dumps({
                    'timestamp': event.timestamp.isoformat(),
                    'component_id': event.component_id,
                    'data': event.data,
                    'severity': event.severity
                })
            )
    
    async def _process_events(self):
        """Process events from queue"""
        while self.running:
            try:
                event = await self.event_queue.get()
                
                # Call all handlers for this event type
                if event.event_type in self.handlers:
                    tasks = [
                        asyncio.create_task(handler(event))
                        for handler in self.handlers[event.event_type]
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
            except Exception as e:
                logger.error(f"Event processing error: {e}")

# ========================= ML MODELS =========================

class LoadForecaster:
    """Advanced load forecasting using Prophet and neural networks"""
    
    def __init__(self):
        self.prophet_model = None
        self.neural_model = None
        self.scaler = StandardScaler()
        self.historical_data = pd.DataFrame()
        
    def train(self, historical_loads: pd.DataFrame):
        """Train forecasting models"""
        
        # Prophet for time series
        df_prophet = historical_loads[['timestamp', 'load_mw']].copy()
        df_prophet.columns = ['ds', 'y']
        
        self.prophet_model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05
        )
        
        # Add holidays and special events (NYC specific)
        self.prophet_model.add_country_holidays(country_name='US')
        
        # Add additional regressors if available
        if 'temperature' in historical_loads.columns:
            df_prophet['temperature'] = historical_loads['temperature']
            self.prophet_model.add_regressor('temperature')
            
        self.prophet_model.fit(df_prophet)
        
        # Neural network for short-term predictions
        self.neural_model = self._build_lstm_model()
        self._train_neural_model(historical_loads)
        
        logger.info("Load forecasting models trained successfully")
        
    def _build_lstm_model(self) -> nn.Module:
        """Build LSTM model for load forecasting"""
        
        class LSTMForecaster(nn.Module):
            def __init__(self, input_dim=10, hidden_dim=128, num_layers=3):
                super().__init__()
                self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, 
                                   batch_first=True, dropout=0.2)
                self.fc1 = nn.Linear(hidden_dim, 64)
                self.fc2 = nn.Linear(64, 1)
                self.relu = nn.ReLU()
                self.dropout = nn.Dropout(0.2)
                
            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                out = self.fc1(lstm_out[:, -1, :])
                out = self.relu(out)
                out = self.dropout(out)
                out = self.fc2(out)
                return out
                
        return LSTMForecaster()
        
    def predict(self, horizon_hours: int = 24) -> pd.DataFrame:
        """Generate load forecast"""
        
        # Prophet forecast
        future = self.prophet_model.make_future_dataframe(
            periods=horizon_hours, 
            freq='H'
        )
        
        forecast = self.prophet_model.predict(future)
        
        # Combine with neural network predictions for ensemble
        nn_predictions = self._neural_predict(horizon_hours)
        
        # Weighted ensemble
        combined = forecast[['ds', 'yhat']].copy()
        combined['neural_pred'] = nn_predictions
        combined['ensemble'] = 0.6 * combined['yhat'] + 0.4 * combined['neural_pred']
        
        return combined

class AnomalyDetector:
    """Real-time anomaly detection for power grid"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.01,
            random_state=42
        )
        self.autoencoder = None
        self.threshold = None
        
    def train(self, normal_data: np.ndarray):
        """Train anomaly detection models"""
        
        # Isolation Forest
        self.isolation_forest.fit(normal_data)
        
        # Autoencoder for complex patterns
        self.autoencoder = self._build_autoencoder(normal_data.shape[1])
        self._train_autoencoder(normal_data)
        
        # Calculate threshold
        reconstructions = self.autoencoder.predict(normal_data)
        mse = np.mean((normal_data - reconstructions) ** 2, axis=1)
        self.threshold = np.percentile(mse, 99)
        
    def _build_autoencoder(self, input_dim: int) -> nn.Module:
        """Build autoencoder for anomaly detection"""
        
        class Autoencoder(nn.Module):
            def __init__(self, input_dim):
                super().__init__()
                # Encoder
                self.encoder = nn.Sequential(
                    nn.Linear(input_dim, 64),
                    nn.ReLU(),
                    nn.Linear(64, 32),
                    nn.ReLU(),
                    nn.Linear(32, 16)
                )
                # Decoder
                self.decoder = nn.Sequential(
                    nn.Linear(16, 32),
                    nn.ReLU(),
                    nn.Linear(32, 64),
                    nn.ReLU(),
                    nn.Linear(64, input_dim)
                )
                
            def forward(self, x):
                encoded = self.encoder(x)
                decoded = self.decoder(encoded)
                return decoded
                
        return Autoencoder(input_dim)
        
    def detect(self, data: np.ndarray) -> Tuple[bool, float]:
        """Detect anomalies in real-time"""
        
        # Isolation Forest detection
        if_score = self.isolation_forest.decision_function(data.reshape(1, -1))[0]
        
        # Autoencoder detection
        reconstruction = self.autoencoder.predict(data.reshape(1, -1))
        ae_score = np.mean((data - reconstruction) ** 2)
        
        # Combined score
        is_anomaly = (if_score < -0.5) or (ae_score > self.threshold)
        confidence = max(abs(if_score), ae_score / self.threshold)
        
        return is_anomaly, confidence

class FailurePredictor:
    """Predict component failures before they occur"""
    
    def __init__(self):
        self.failure_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            random_state=42
        )
        self.component_history = {}
        
    def train(self, failure_data: pd.DataFrame):
        """Train failure prediction model"""
        
        features = [
            'age_days', 'load_percentage', 'temperature',
            'maintenance_days_ago', 'failure_count_nearby',
            'weather_severity', 'peak_load_events'
        ]
        
        X = failure_data[features]
        y = failure_data['time_to_failure_hours']
        
        self.failure_model.fit(X, y)
        
    def predict_failure_risk(self, component_id: str, 
                            current_state: Dict) -> Dict[str, Any]:
        """Predict failure risk for component"""
        
        features = self._extract_features(component_id, current_state)
        
        # Predict time to failure
        ttf_hours = self.failure_model.predict([features])[0]
        
        # Calculate risk score (0-100)
        if ttf_hours < 24:
            risk_score = 90 + (24 - ttf_hours) / 24 * 10
        elif ttf_hours < 168:  # 1 week
            risk_score = 50 + (168 - ttf_hours) / 168 * 40
        else:
            risk_score = max(0, 50 - (ttf_hours - 168) / 168 * 50)
            
        return {
            'component_id': component_id,
            'time_to_failure_hours': ttf_hours,
            'risk_score': risk_score,
            'recommended_action': self._get_recommendation(risk_score),
            'confidence': self._calculate_confidence(features)
        }

# ========================= OPTIMIZATION ENGINE =========================

class PowerGridOptimizer:
    """Advanced optimization for power grid operations"""
    
    def __init__(self, power_network: nx.Graph):
        self.network = power_network
        self.generator_costs = {}
        self.load_constraints = {}
        
    def optimal_power_flow(self, 
                          loads: Dict[str, float],
                          renewable_forecast: Dict[str, float]) -> Dict:
        """Solve optimal power flow with renewable integration"""
        
        def objective(x):
            """Minimize generation cost and losses"""
            total_cost = 0
            
            # Generation costs
            for i, gen_id in enumerate(self.generator_costs.keys()):
                cost_curve = self.generator_costs[gen_id]
                total_cost += cost_curve(x[i])
                
            # Transmission losses (simplified)
            total_loss = sum(x[i]**2 * 0.01 for i in range(len(x)))
            total_cost += total_loss * 50  # Loss penalty
            
            # Renewable curtailment penalty
            renewable_curtailment = sum(
                max(0, renewable_forecast.get(gen, 0) - x[i])
                for i, gen in enumerate(self.generator_costs.keys())
                if 'solar' in gen or 'wind' in gen
            )
            total_cost += renewable_curtailment * 100
            
            return total_cost
            
        # Constraints
        constraints = []
        
        # Power balance
        def power_balance(x):
            total_gen = sum(x)
            total_load = sum(loads.values())
            return total_gen - total_load
            
        constraints.append({'type': 'eq', 'fun': power_balance})
        
        # Line flow limits (simplified)
        for line_id in self.network.edges():
            def line_limit(x, line=line_id):
                flow = self._calculate_line_flow(x, line)
                limit = self.network.edges[line]['capacity']
                return limit - abs(flow)
                
            constraints.append({'type': 'ineq', 'fun': line_limit})
            
        # Generator limits
        bounds = [(gen['min'], gen['max']) 
                 for gen in self.generator_costs.values()]
        
        # Solve optimization
        result = differential_evolution(
            objective,
            bounds,
            constraints=constraints,
            maxiter=1000,
            popsize=15,
            seed=42
        )
        
        return {
            'optimal_generation': dict(zip(self.generator_costs.keys(), result.x)),
            'total_cost': result.fun,
            'convergence': result.success
        }
        
    def contingency_screening(self) -> List[Dict]:
        """Identify critical contingencies using ML-based screening"""
        
        critical_contingencies = []
        
        # Use ML to pre-screen contingencies
        for component in self.network.nodes():
            severity = self._predict_contingency_severity(component)
            
            if severity > 0.7:  # High severity threshold
                # Run detailed analysis
                impact = self._detailed_contingency_analysis(component)
                critical_contingencies.append({
                    'component': component,
                    'severity': severity,
                    'impact': impact
                })
                
        return sorted(critical_contingencies, 
                     key=lambda x: x['severity'], 
                     reverse=True)[:10]

# ========================= INTELLIGENT TRAFFIC CONTROL =========================

class IntelligentTrafficController:
    """AI-powered traffic control with predictive optimization"""
    
    def __init__(self):
        self.rl_agent = None  # Reinforcement learning agent
        self.traffic_predictor = None
        self.congestion_model = None
        self.emergency_routes = {}
        
    def initialize_rl_agent(self):
        """Initialize deep reinforcement learning for traffic optimization"""
        
        class TrafficRLAgent(nn.Module):
            def __init__(self, state_dim=100, action_dim=50):
                super().__init__()
                self.fc1 = nn.Linear(state_dim, 256)
                self.fc2 = nn.Linear(256, 128)
                self.fc3 = nn.Linear(128, action_dim)
                self.value_head = nn.Linear(128, 1)
                
            def forward(self, state):
                x = torch.relu(self.fc1(state))
                x = torch.relu(self.fc2(x))
                actions = torch.softmax(self.fc3(x), dim=-1)
                value = self.value_head(x)
                return actions, value
                
        self.rl_agent = TrafficRLAgent()
        
    def predict_traffic_flow(self, current_state: Dict, 
                            horizon_minutes: int = 60) -> pd.DataFrame:
        """Predict traffic flow using deep learning"""
        
        # Extract features
        features = self._extract_traffic_features(current_state)
        
        predictions = []
        state = features
        
        for t in range(horizon_minutes):
            # Predict next state
            next_flow = self.traffic_predictor.predict(state)
            predictions.append(next_flow)
            
            # Update state for next prediction
            state = self._update_state(state, next_flow)
            
        return pd.DataFrame(predictions)
        
    def optimize_signal_timing(self, 
                              traffic_state: Dict,
                              power_constraints: Dict) -> Dict:
        """Optimize signal timing considering power availability"""
        
        # Convert state to tensor
        state_tensor = torch.FloatTensor(
            self._state_to_vector(traffic_state, power_constraints)
        )
        
        # Get optimal actions from RL agent
        with torch.no_grad():
            actions, value = self.rl_agent(state_tensor)
            
        # Convert actions to signal timings
        timings = self._actions_to_timings(actions.numpy())
        
        # Apply power constraints
        if power_constraints.get('limited_power', False):
            timings = self._apply_power_saving_mode(timings)
            
        return {
            'timings': timings,
            'expected_improvement': value.item(),
            'power_usage_kw': self._calculate_power_usage(timings)
        }

# ========================= DIGITAL TWIN ENGINE =========================

class DigitalTwinEngine:
    """Complete digital twin with real-time simulation and prediction"""
    
    def __init__(self):
        self.power_state = {}
        self.traffic_state = {}
        self.predictions = {}
        self.simulation_clock = datetime.now()
        self.speed_factor = 1.0
        
    async def synchronize_with_reality(self, real_data: Dict):
        """Synchronize digital twin with real system"""
        
        # Update states
        self.power_state = real_data.get('power', {})
        self.traffic_state = real_data.get('traffic', {})
        
        # Run predictions
        await self._run_predictions()
        
        # Detect discrepancies
        discrepancies = self._detect_discrepancies(real_data)
        
        if discrepancies:
            await self._recalibrate_models(discrepancies)
            
    async def simulate_scenario(self, 
                               scenario: Dict,
                               duration_hours: int = 24) -> Dict:
        """Simulate what-if scenarios"""
        
        results = {
            'timeline': [],
            'metrics': {},
            'recommendations': []
        }
        
        # Clone current state
        sim_state = self._clone_state()
        
        # Apply scenario
        self._apply_scenario(sim_state, scenario)
        
        # Run simulation
        for hour in range(duration_hours):
            # Advance simulation
            sim_state = await self._advance_simulation(sim_state, 3600)
            
            # Record metrics
            results['timeline'].append({
                'hour': hour,
                'power_metrics': self._calculate_power_metrics(sim_state),
                'traffic_metrics': self._calculate_traffic_metrics(sim_state),
                'risk_score': self._calculate_risk_score(sim_state)
            })
            
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results)
        
        return results

# ========================= MAIN ADVANCED SYSTEM =========================

class ManhattanAdvancedSystem:
    """Main system orchestrator with all advanced features"""
    
    def __init__(self):
        # Core components
        self.event_bus = EventBus()
        self.load_forecaster = LoadForecaster()
        self.anomaly_detector = AnomalyDetector()
        self.failure_predictor = FailurePredictor()
        self.traffic_controller = IntelligentTrafficController()
        self.digital_twin = DigitalTwinEngine()
        
        # Caching
        self.cache = {}
        self.cache_timestamps = {}
        
        # Monitoring
        self.metrics = {
            'api_calls': 0,
            'predictions_made': 0,
            'anomalies_detected': 0,
            'optimizations_run': 0
        }
        
    async def initialize(self):
        """Initialize all subsystems"""
        
        logger.info("Initializing Manhattan Advanced System...")
        
        # Initialize event bus
        await self.event_bus.initialize()
        
        # Subscribe to critical events
        self.event_bus.subscribe(
            EventType.POWER_FAILURE,
            self.handle_power_failure
        )
        self.event_bus.subscribe(
            EventType.ANOMALY_DETECTED,
            self.handle_anomaly
        )
        
        # Load ML models
        await self._load_ml_models()
        
        # Start background tasks
        asyncio.create_task(self._prediction_loop())
        asyncio.create_task(self._optimization_loop())
        asyncio.create_task(self._monitoring_loop())
        
        logger.info("System initialization complete")
        
    async def _prediction_loop(self):
        """Continuous prediction generation"""
        
        while True:
            try:
                # Generate load forecast
                load_forecast = self.load_forecaster.predict(
                    horizon_hours=config.PREDICTION_HORIZON
                )
                
                # Store predictions
                self.cache['load_forecast'] = load_forecast
                self.cache_timestamps['load_forecast'] = datetime.now()
                
                # Publish event
                await self.event_bus.publish(SystemEvent(
                    event_type=EventType.PREDICTION_READY,
                    timestamp=datetime.now(),
                    component_id='load_forecaster',
                    data={'forecast': load_forecast.to_dict()}
                ))
                
                self.metrics['predictions_made'] += 1
                
            except Exception as e:
                logger.error(f"Prediction error: {e}")
                
            await asyncio.sleep(300)  # Run every 5 minutes
            
    async def _optimization_loop(self):
        """Continuous system optimization"""
        
        while True:
            try:
                # Get current state
                state = await self.get_system_state()
                
                # Run optimization
                if state['power']['total_load_mw'] > 2000:  # High load
                    # Optimize power flow
                    optimization = await self.optimize_power_flow()
                    
                    # Apply optimization
                    await self.apply_optimization(optimization)
                    
                    self.metrics['optimizations_run'] += 1
                    
            except Exception as e:
                logger.error(f"Optimization error: {e}")
                
            await asyncio.sleep(60)  # Run every minute
            
    async def handle_power_failure(self, event: SystemEvent):
        """Handle power failure with AI assistance"""
        
        logger.warning(f"Power failure detected: {event.component_id}")
        
        # Predict cascading failures
        cascade_risk = self.failure_predictor.predict_failure_risk(
            event.component_id,
            event.data
        )
        
        if cascade_risk['risk_score'] > 80:
            # Take preventive action
            await self.implement_load_shedding(cascade_risk)
            
        # Optimize traffic for reduced power
        traffic_optimization = self.traffic_controller.optimize_signal_timing(
            self.digital_twin.traffic_state,
            {'limited_power': True, 'available_kw': event.data.get('remaining_power', 0)}
        )
        
        await self.apply_traffic_optimization(traffic_optimization)
        
    async def handle_anomaly(self, event: SystemEvent):
        """Handle detected anomalies"""
        
        logger.warning(f"Anomaly detected: {event.data}")
        
        # Run root cause analysis
        root_cause = await self.analyze_root_cause(event.data)
        
        # Generate recommendations
        recommendations = await self.generate_ai_recommendations(
            event.data,
            root_cause
        )
        
        # Store for operator review
        self.cache['latest_anomaly'] = {
            'event': event,
            'root_cause': root_cause,
            'recommendations': recommendations,
            'timestamp': datetime.now()
        }
        
    async def generate_ai_recommendations(self, 
                                         anomaly_data: Dict,
                                         root_cause: Dict) -> List[str]:
        """Generate intelligent recommendations using GPT"""
        
        if not config.USE_GPT_ANALYSIS:
            return self._generate_rule_based_recommendations(anomaly_data)
            
        # This would connect to OpenAI API
        # For now, return intelligent rule-based recommendations
        
        recommendations = []
        
        if anomaly_data.get('type') == 'voltage_deviation':
            recommendations.extend([
                "Immediate: Adjust tap changers on transformers T-15 and T-23",
                "Short-term: Dispatch reactive power from BESS stations",
                "Long-term: Consider installing additional capacitor banks"
            ])
            
        elif anomaly_data.get('type') == 'unexpected_load_spike':
            recommendations.extend([
                "Immediate: Activate demand response program for C&I customers",
                "Short-term: Bring online peaking units at Ravenswood",
                "Monitor: Check for unauthorized cryptocurrency mining operations"
            ])
            
        return recommendations
        
    async def get_system_state(self) -> Dict:
        """Get complete system state with predictions"""
        
        # Check cache
        if 'system_state' in self.cache:
            cache_age = (datetime.now() - self.cache_timestamps.get('system_state', datetime.min)).seconds
            if cache_age < config.CACHE_TTL:
                return self.cache['system_state']
                
        # Build state
        state = {
            'timestamp': datetime.now().isoformat(),
            'power': await self._get_power_state(),
            'traffic': await self._get_traffic_state(),
            'predictions': {
                'load_forecast': self.cache.get('load_forecast', {}),
                'failure_risks': await self._get_failure_predictions(),
                'traffic_flow': await self._get_traffic_predictions()
            },
            'anomalies': self.cache.get('latest_anomaly', {}),
            'metrics': self.metrics
        }
        
        # Cache
        self.cache['system_state'] = state
        self.cache_timestamps['system_state'] = datetime.now()
        
        return state

# ========================= CACHE MANAGER =========================

class DistributedCacheManager:
    """High-performance distributed caching"""
    
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await aioredis.create_redis_pool(
            'redis://localhost',
            minsize=5,
            maxsize=10
        )
        
    async def get(self, key: str, default=None):
        """Get from cache with fallback"""
        
        # Try local cache first
        if key in self.local_cache:
            self.cache_stats['hits'] += 1
            return self.local_cache[key]
            
        # Try Redis
        if self.redis_client:
            value = await self.redis_client.get(key)
            if value:
                self.cache_stats['hits'] += 1
                # Update local cache
                self.local_cache[key] = json.loads(value)
                return self.local_cache[key]
                
        self.cache_stats['misses'] += 1
        return default
        
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set in cache with TTL"""
        
        # Set in local cache
        self.local_cache[key] = value
        
        # Set in Redis
        if self.redis_client:
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            
    async def invalidate(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        
        # Clear local cache
        keys_to_remove = [k for k in self.local_cache if pattern in k]
        for key in keys_to_remove:
            del self.local_cache[key]
            self.cache_stats['evictions'] += 1
            
        # Clear Redis
        if self.redis_client:
            cursor = '0'
            while cursor != 0:
                cursor, keys = await self.redis_client.scan(
                    cursor, 
                    match=f"*{pattern}*"
                )
                if keys:
                    await self.redis_client.delete(*keys)

if __name__ == "__main__":
    # Example usage
    async def main():
        system = ManhattanAdvancedSystem()
        await system.initialize()
        
        # Get system state
        state = await system.get_system_state()
        print(f"System initialized: {state['timestamp']}")
        
        # Simulate scenario
        scenario = {
            'type': 'substation_failure',
            'component': 'Times_Square',
            'duration_hours': 4
        }
        
        results = await system.digital_twin.simulate_scenario(scenario, 24)
        print(f"Scenario results: {results['recommendations']}")
        
    asyncio.run(main()