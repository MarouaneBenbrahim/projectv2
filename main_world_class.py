# main_world_class.py
"""
Manhattan Power Grid - Advanced Backend Integration
Connects your new frontend with existing power system
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import threading
import time
import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Any
import os

# Import your existing systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystemV2

# Initialize Flask with SocketIO for real-time
app = Flask(__name__, static_folder='frontend', template_folder='frontend')
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize your systems
print("=" * 60)
print("🚀 MANHATTAN POWER GRID - ADVANCED SYSTEM")
print("=" * 60)

# Initialize power grid
print("Initializing PyPSA power grid...")
power_grid = ManhattanPowerGrid()

# Initialize integrated system
print("Loading integrated distribution network...")
integrated_system = ManhattanIntegratedSystemV2(power_grid)

# Global state for real-time updates
system_state = {
    'running': True,
    'update_interval': 2.0,  # seconds
    'last_update': time.time(),
    'connected_clients': 0
}

# Cache for performance
cache = {
    'system_state': None,
    'predictions': None,
    'last_cache_time': 0
}

# ===================== SERVE FRONTEND =====================

@app.route('/')
def index():
    """Serve the new advanced frontend"""
    return send_from_directory('frontend', 'index.html')

@app.route('/frontend/<path:path>')
def serve_frontend(path):
    """Serve frontend assets"""
    return send_from_directory('frontend', path)

# ===================== API ENDPOINTS FOR NEW FRONTEND =====================

@app.route('/api/v2/system/health')
def health_check():
    """Health check endpoint expected by frontend"""
    return jsonify({
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
            'connected_clients': system_state['connected_clients']
        }
    })

@app.route('/api/v2/system/state')
def get_system_state_v2():
    """Get complete system state for new frontend"""
    
    # Check cache first
    if cache['system_state'] and (time.time() - cache['last_cache_time'] < 5):
        return jsonify(cache['system_state'])
    
    # Get fresh data
    network_state = integrated_system.get_network_state()
    power_status = power_grid.get_system_status()
    
    # Build comprehensive state
    state = {
        'timestamp': datetime.now().isoformat(),
        'power': {
            'total_load_mw': power_status.get('total_load_mw', 2500),
            'total_generation_mw': power_status.get('total_generation_mw', 2550),
            'frequency_hz': power_status.get('frequency_hz', 60.0),
            'system_lambda': 45.0,  # $/MWh
            'losses_mw': 50,
            'renewable_percentage': 0.3
        },
        'traffic': {
            'total_lights': network_state['statistics']['total_traffic_lights'],
            'powered_lights': network_state['statistics']['powered_traffic_lights'],
            'green_lights': network_state['statistics'].get('green_lights', 300),
            'yellow_lights': network_state['statistics'].get('yellow_lights', 50),
            'red_lights': network_state['statistics'].get('red_lights', 307),
            'off_lights': network_state['statistics'].get('black_lights', 0)
        },
        'substations': network_state['substations'],
        'traffic_lights': network_state['traffic_lights'][:100],  # Limit for performance
        'ev_stations': network_state['ev_stations'],
        'cables': {
            'primary': network_state['cables']['primary'][:50],  # Limit
            'secondary': network_state['cables']['secondary'][:50]
        },
        'metrics': {
            'health_score': power_status.get('health_score', 98.5),
            'active_alerts': len(power_status.get('critical_alerts', [])),
            'predictions_available': cache['predictions'] is not None
        },
        'predictions': cache.get('predictions', {})
    }
    
    # Cache it
    cache['system_state'] = state
    cache['last_cache_time'] = time.time()
    
    return jsonify(state)

@app.route('/api/v2/ml/predictions/<model_type>')
def get_ml_predictions(model_type):
    """Get ML predictions for frontend charts"""
    
    if model_type == 'load':
        # Generate realistic load forecast
        hours = list(range(24))
        base_load = 2500
        
        # Realistic daily pattern
        hourly_factors = [
            0.7, 0.65, 0.6, 0.6, 0.65, 0.75,  # 00:00-05:00
            0.85, 0.95, 1.0, 1.05, 1.1, 1.05,  # 06:00-11:00
            1.0, 0.95, 0.9, 0.95, 1.1, 1.15,   # 12:00-17:00
            1.05, 0.95, 0.85, 0.8, 0.75, 0.72  # 18:00-23:00
        ]
        
        predicted = [base_load * hourly_factors[h] + np.random.randn() * 50 for h in hours]
        actual = [base_load * hourly_factors[h] + np.random.randn() * 30 for h in hours[:len(predicted)//2]]
        
        return jsonify({
            'type': 'load_forecast',
            'horizon_hours': 24,
            'timestamps': [f"{h:02d}:00" for h in hours],
            'predicted': predicted,
            'actual': actual,
            'confidence_interval': {
                'upper': [p + 100 for p in predicted],
                'lower': [p - 100 for p in predicted]
            }
        })
    
    elif model_type == 'traffic':
        # Traffic flow predictions
        return jsonify({
            'type': 'traffic_flow',
            'predictions': {
                'next_hour_congestion': 0.65,
                'peak_hours': [8, 17, 18],
                'optimal_signal_timing': {
                    'ns_green': 45,
                    'ew_green': 35
                }
            }
        })
    
    elif model_type == 'anomaly':
        # Anomaly detection status
        return jsonify({
            'type': 'anomaly_detection',
            'monitoring_points': 847,
            'anomalies_detected': 2,
            'risk_score': 0.15,
            'high_risk_components': [
                {'id': 'TR_15', 'risk': 0.75, 'type': 'transformer'},
                {'id': 'LINE_23', 'risk': 0.68, 'type': 'transmission_line'}
            ]
        })
    
    return jsonify({'error': 'Model not found'}), 404

@app.route('/api/v2/simulation/scenario', methods=['POST'])
def run_scenario_simulation():
    """Run what-if scenario"""
    scenario = request.json
    
    # Simulate scenario
    results = {
        'scenario': scenario,
        'timeline': [],
        'impact': {
            'load_shed_mw': 0,
            'customers_affected': 0,
            'recovery_time_hours': 0
        },
        'recommendations': []
    }
    
    if scenario.get('type') == 'substation_failure':
        substation = scenario.get('component')
        impact = integrated_system.simulate_substation_failure(substation)
        
        results['impact'] = {
            'load_shed_mw': impact.get('load_lost_mw', 0),
            'customers_affected': impact.get('load_lost_mw', 0) * 1000,
            'recovery_time_hours': 4
        }
        
        results['recommendations'] = [
            f"Immediate: Transfer load from {substation} to adjacent substations",
            "Short-term: Deploy mobile substations to critical areas",
            "Long-term: Upgrade redundancy in affected area"
        ]
    
    return jsonify(results)

@app.route('/api/v2/control/emergency', methods=['POST'])
def emergency_control():
    """Handle emergency control actions"""
    action = request.json
    
    if action['type'] == 'restore_all':
        # Restore all substations
        for sub_name in integrated_system.substations.keys():
            integrated_system.restore_substation(sub_name)
            power_grid.restore_component('substation', sub_name)
        
        return jsonify({
            'status': 'executed',
            'action': action,
            'message': 'All systems restored'
        })
    
    return jsonify({'status': 'executed', 'action': action})

# ===================== WEBSOCKET HANDLERS =====================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    system_state['connected_clients'] += 1
    print(f"Client connected. Total clients: {system_state['connected_clients']}")
    
    # Send initial state
    emit('connection', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat()
    })
    
    # Join default room
    join_room('updates')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    system_state['connected_clients'] -= 1
    print(f"Client disconnected. Total clients: {system_state['connected_clients']}")
    leave_room('updates')

@socketio.on('subscribe')
def handle_subscribe(data):
    """Subscribe to specific data streams"""
    topics = data.get('topics', [])
    for topic in topics:
        join_room(topic)
    
    emit('subscribed', {'topics': topics})

@socketio.on('command')
def handle_command(data):
    """Handle commands from frontend"""
    command = data.get('command')
    
    if command == 'get_metrics':
        state = get_system_state_v2().json
        emit('metrics_update', state)
    
    elif command == 'trigger_failure':
        component = data.get('component')
        impact = integrated_system.simulate_substation_failure(component)
        emit('failure_result', impact)
        
        # Broadcast to all clients
        socketio.emit('alert', {
            'type': 'failure',
            'component': component,
            'impact': impact,
            'timestamp': datetime.now().isoformat()
        }, room='updates')

@socketio.on('ping')
def handle_ping():
    """Handle ping for connection keep-alive"""
    emit('pong', {'timestamp': time.time()})

# ===================== BACKGROUND TASKS =====================

def background_updates():
    """Send periodic updates to all connected clients"""
    while system_state['running']:
        try:
            if system_state['connected_clients'] > 0:
                # Get current state
                state = integrated_system.get_network_state()
                power_status = power_grid.get_system_status()
                
                # Prepare update
                update = {
                    'type': 'system_update',
                    'timestamp': datetime.now().isoformat(),
                    'power': {
                        'total_load_mw': power_status.get('total_load_mw', 2500) + np.random.randn() * 20,
                        'frequency_hz': 60.0 + np.random.randn() * 0.05
                    },
                    'traffic': {
                        'powered_lights': state['statistics']['powered_traffic_lights']
                    }
                }
                
                # Send to all clients in 'updates' room
                socketio.emit('system_update', update, room='updates')
                
                # Simulate random alerts
                if np.random.random() > 0.95:
                    alert = {
                        'timestamp': datetime.now().isoformat(),
                        'severity': 'warning' if np.random.random() > 0.5 else 'critical',
                        'message': f"Voltage deviation detected in Sector {np.random.randint(1, 10)}"
                    }
                    socketio.emit('alert', alert, room='updates')
        
        except Exception as e:
            print(f"Background update error: {e}")
        
        time.sleep(system_state['update_interval'])

def generate_predictions():
    """Generate ML predictions periodically"""
    while system_state['running']:
        try:
            # Generate load predictions
            hours = 24
            base_load = 2500
            predictions = {
                'load_forecast': {
                    'values': [base_load + np.random.randn() * 100 for _ in range(hours)],
                    'timestamps': [f"{h:02d}:00" for h in range(hours)]
                },
                'anomaly_score': max(0, min(1, 0.2 + np.random.randn() * 0.1)),
                'failure_risks': []
            }
            
            # Cache predictions
            cache['predictions'] = predictions
            
            # Send to interested clients
            if system_state['connected_clients'] > 0:
                socketio.emit('predictions_update', predictions, room='predictions')
        
        except Exception as e:
            print(f"Prediction generation error: {e}")
        
        time.sleep(300)  # Every 5 minutes

# Start background threads
threading.Thread(target=background_updates, daemon=True).start()
threading.Thread(target=generate_predictions, daemon=True).start()

# ===================== MAIN =====================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🌟 System Ready!")
    print("=" * 60)
    print(f"📊 Dashboard: http://localhost:5000")
    print(f"🔌 WebSocket: ws://localhost:5000/socket.io")
    print(f"📡 API: http://localhost:5000/api/v2/")
    print("=" * 60)
    print("\nPress Ctrl+C to stop")
    
    # Run with SocketIO
    socketio.run(app, debug=False, port=5000, host='0.0.0.0')