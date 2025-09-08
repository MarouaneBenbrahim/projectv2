"""
MANHATTAN POWER GRID - ULTIMATE WORLD-CLASS SYSTEM
Complete Integration: Power + Traffic + EVs + Real-time Visualization
Professional Infrastructure Simulation for NYC
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
import os
import sys
import random
import math

# Add SUMO to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    import traci
    import sumolib
    SUMO_AVAILABLE = True
else:
    SUMO_AVAILABLE = False
    print("⚠️ SUMO not configured - traffic simulation disabled")

# Import our systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from manhattan_ultimate import ManhattanUltimateSimulation

app = Flask(__name__)
CORS(app)

# ============================================================
# SYSTEM INITIALIZATION
# ============================================================

print("\n" + "="*60)
print("MANHATTAN ULTIMATE INFRASTRUCTURE SYSTEM")
print("Power Grid + Traffic + EV Charging + Real-time Analytics")
print("="*60)

# Initialize power grid
print("\n⚡ Initializing Power Grid (PyPSA)...")
power_grid = ManhattanPowerGrid()

# Initialize distribution network
print("🔌 Loading Distribution Network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# Initialize SUMO ultimate simulation
sumo_sim = None
if SUMO_AVAILABLE:
    print("🚦 Initializing Ultimate Traffic Simulation...")
    sumo_sim = ManhattanUltimateSimulation(integrated_system)
    
    # Setup SUMO if needed
    if not os.path.exists(sumo_sim.net_file):
        print("   Building Manhattan network...")
        # Use existing network or generate new one
        if os.path.exists('data/sumo/manhattan.net.xml'):
            sumo_sim.net_file = 'data/sumo/manhattan.net.xml'
        
    # Generate continuous traffic patterns
    print("   Generating continuous traffic patterns...")
    sumo_sim.generate_continuous_traffic()
    sumo_sim.generate_additional_infrastructure()
    sumo_sim.generate_config()

# ============================================================
# GLOBAL STATE
# ============================================================

system_state = {
    'running': True,
    'simulation_time': 0,
    'current_hour': datetime.now().hour,
    'power_ok': True,
    'traffic_ok': SUMO_AVAILABLE,
    'failed_substations': set(),
    'vehicles': {},
    'charging_stations': {},
    'traffic_metrics': {
        'total_vehicles': 0,
        'active_vehicles': 0,
        'avg_speed_kmh': 0,
        'evs_active': 0,
        'evs_charging': 0,
        'co2_emissions': 0,
        'congestion_level': 0
    },
    'power_metrics': {
        'total_load_mw': 0,
        'ev_load_mw': 0,
        'health_score': 100
    }
}

# ============================================================
# SIMULATION LOOPS
# ============================================================

def power_simulation_loop():
    """Power grid simulation with EV load integration"""
    while system_state['running']:
        try:
            # Update hour
            system_state['current_hour'] = datetime.now().hour
            
            # Run power flow every 30 seconds
            if system_state['simulation_time'] % 30 == 0:
                result = power_grid.run_power_flow("dc")
                if result:
                    system_state['power_metrics']['total_load_mw'] = result.total_loss_mw
                    system_state['power_metrics']['health_score'] = 100 - len(result.voltage_violations) * 5
            
            # Update traffic light phases every 2 seconds
            if system_state['simulation_time'] % 2 == 0:
                integrated_system.update_traffic_light_phases()
            
            # Calculate EV charging load
            if sumo_sim and sumo_sim.running:
                ev_load = 0
                for station_id, station in sumo_sim.charging_stations.items():
                    ev_load += station.get('power_consumption', 0) / 1000  # Convert to MW
                system_state['power_metrics']['ev_load_mw'] = ev_load
            
            time.sleep(1)
            system_state['simulation_time'] += 1
            
        except Exception as e:
            print(f"Power loop error: {e}")
            time.sleep(1)

def traffic_simulation_loop():
    """Ultimate traffic simulation loop with vehicle tracking"""
    if not SUMO_AVAILABLE or not sumo_sim:
        return
    
    while system_state['running'] and sumo_sim.running:
        try:
            # Step simulation
            stats = sumo_sim.step()
            
            if stats:
                # Update traffic metrics
                system_state['traffic_metrics'].update(stats)
                
                # Get vehicle positions for map display
                system_state['vehicles'] = sumo_sim.get_vehicle_positions()
                
                # Get charging station status
                system_state['charging_stations'] = sumo_sim.get_charging_stations_status()
                
                # Calculate congestion level (0-1)
                if stats['avg_speed_kmh'] > 0:
                    # Normal speed in Manhattan is ~25 km/h
                    congestion = max(0, 1 - (stats['avg_speed_kmh'] / 25))
                    system_state['traffic_metrics']['congestion_level'] = congestion
                
                # Inject emergency vehicles during incidents
                if len(system_state['failed_substations']) > 0 and random.random() < 0.01:
                    sumo_sim.inject_emergency_vehicle()
            
            time.sleep(0.5)  # 2 Hz update rate
            
        except Exception as e:
            print(f"Traffic loop error: {e}")
            time.sleep(1)

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve ultimate dashboard"""
    return render_template_string(HTML_ULTIMATE_TEMPLATE)

@app.route('/api/system_state')
def get_system_state():
    """Get complete system state with vehicles"""
    network_state = integrated_system.get_network_state()
    
    # Add traffic data
    network_state['traffic'] = system_state['traffic_metrics']
    network_state['traffic']['simulation_active'] = sumo_sim.running if sumo_sim else False
    
    # Add power metrics
    network_state['power'] = system_state['power_metrics']
    
    # Add current time info
    network_state['time'] = {
        'simulation_time': system_state['simulation_time'],
        'current_hour': system_state['current_hour'],
        'rush_hour': (7 <= system_state['current_hour'] <= 9) or (17 <= system_state['current_hour'] <= 19)
    }
    
    return jsonify(network_state)

@app.route('/api/vehicles')
def get_vehicles():
    """Get all vehicle positions for map display"""
    # Convert vehicle dict to list for easier handling
    vehicles_list = list(system_state['vehicles'].values())
    
    # Limit to 500 vehicles for performance
    if len(vehicles_list) > 500:
        # Prioritize EVs, emergency vehicles, and nearby vehicles
        prioritized = []
        
        # Add all emergency vehicles
        prioritized.extend([v for v in vehicles_list if v['type'] == 'emergency'])
        
        # Add EVs
        prioritized.extend([v for v in vehicles_list if v['type'] == 'ev'][:100])
        
        # Add vehicles near Times Square (center of map)
        center_lat, center_lon = 40.758, -73.985
        nearby = sorted(vehicles_list, 
                       key=lambda v: abs(v['lat'] - center_lat) + abs(v['lon'] - center_lon))
        prioritized.extend(nearby[:400])
        
        # Remove duplicates
        seen = set()
        vehicles_list = []
        for v in prioritized:
            if v['id'] not in seen:
                seen.add(v['id'])
                vehicles_list.append(v)
                if len(vehicles_list) >= 500:
                    break
    
    return jsonify({'vehicles': vehicles_list, 'total': len(system_state['vehicles'])})

@app.route('/api/charging_stations')
def get_charging_stations():
    """Get EV charging station status"""
    stations = []
    
    if sumo_sim and sumo_sim.running:
        for station_id, status in system_state['charging_stations'].items():
            station_data = sumo_sim.charging_stations.get(station_id, {})
            stations.append({
                'id': station_id,
                'name': station_id.replace('CS_', '').replace('_', ' '),
                'lat': station_data.get('lat', 40.758),
                'lon': station_data.get('lon', -73.985),
                'occupied': status.get('occupied', 0),
                'capacity': status.get('capacity', 10),
                'queue': status.get('queue_length', 0),
                'operational': status.get('operational', True),
                'power_kw': status.get('power_kw', 0)
            })
    
    return jsonify({'stations': stations})

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Fail a substation with full cascading effects"""
    # Power system failure
    impact = integrated_system.simulate_substation_failure(substation)
    power_grid.trigger_failure('substation', substation)
    
    # Add to failed list
    system_state['failed_substations'].add(substation)
    
    # Traffic system impact
    if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
        affected_lights = sumo_sim.simulate_power_failure(substation)
        impact['traffic_lights_failed'] = affected_lights
        
        # Dispatch emergency vehicles
        for _ in range(2):  # Send 2 emergency vehicles
            sumo_sim.inject_emergency_vehicle()
    
    return jsonify(impact)

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore a substation"""
    success = integrated_system.restore_substation(substation)
    
    if success:
        power_grid.restore_component('substation', substation)
        system_state['failed_substations'].discard(substation)
        
        # Restore traffic systems
        if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
            restored_lights = sumo_sim.restore_power(substation)
            print(f"⚡ Restored {restored_lights} traffic lights")
    
    return jsonify({'success': success})

@app.route('/api/restore_all', methods=['POST'])
def restore_all():
    """Restore all systems"""
    for sub_name in list(system_state['failed_substations']):
        restore_substation(sub_name)
    return jsonify({'success': True, 'message': 'All systems restored'})

@app.route('/api/sumo/start', methods=['POST'])
def start_sumo():
    """Start SUMO simulation"""
    if not SUMO_AVAILABLE:
        return jsonify({'success': False, 'error': 'SUMO not available'})
    
    gui = request.json.get('gui', True) if request.json else True
    
    if sumo_sim and not sumo_sim.running:
        success = sumo_sim.start(gui=gui)
        if success:
            # Start traffic loop
            traffic_thread = threading.Thread(target=traffic_simulation_loop, daemon=True)
            traffic_thread.start()
        return jsonify({'success': success})
    
    return jsonify({'success': False, 'error': 'Already running'})

@app.route('/api/sumo/stop', methods=['POST'])
def stop_sumo():
    """Stop SUMO simulation"""
    if sumo_sim:
        sumo_sim.stop()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/sumo/inject_emergency', methods=['POST'])
def inject_emergency():
    """Inject emergency vehicle"""
    if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
        vehicle_id = sumo_sim.inject_emergency_vehicle()
        return jsonify({'success': True, 'vehicle_id': vehicle_id})
    return jsonify({'success': False, 'error': 'SUMO not running'})

@app.route('/api/sumo/add_traffic', methods=['POST'])
def add_traffic():
    """Add more vehicles dynamically"""
    if not SUMO_AVAILABLE or not sumo_sim or not sumo_sim.running:
        return jsonify({'success': False, 'error': 'SUMO not running'})
    
    try:
        count = request.json.get('count', 50) if request.json else 50
        vehicle_type = request.json.get('type', 'mixed') if request.json else 'mixed'
        
        edges = traci.edge.getIDList()
        added = 0
        
        for i in range(count):
            vid = f"dynamic_{system_state['simulation_time']}_{i}"
            
            # Select vehicle type
            if vehicle_type == 'mixed':
                vtype = random.choice(['car', 'taxi', 'ev', 'delivery', 'bus'])
            else:
                vtype = vehicle_type
            
            # Random route
            from_edge = random.choice(edges)
            to_edge = random.choice(edges)
            
            if from_edge != to_edge:
                route = traci.simulation.findRoute(from_edge, to_edge)
                if route and route.edges:
                    route_id = f"route_{vid}"
                    traci.route.add(route_id, route.edges)
                    traci.vehicle.add(vid, route_id, typeID=vtype)
                    added += 1
        
        return jsonify({'success': True, 'vehicles_added': added})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/traffic/set_rush_hour', methods=['POST'])
def set_rush_hour():
    """Simulate rush hour traffic"""
    if not SUMO_AVAILABLE or not sumo_sim or not sumo_sim.running:
        return jsonify({'success': False, 'error': 'SUMO not running'})
    
    # Add many vehicles to simulate rush hour
    rush_hour_vehicles = 500
    
    try:
        edges = traci.edge.getIDList()
        added = 0
        
        for i in range(rush_hour_vehicles):
            vid = f"rush_{system_state['simulation_time']}_{i}"
            vtype = random.choice(['car', 'car', 'taxi', 'ev'])  # More cars during rush
            
            from_edge = random.choice(edges)
            to_edge = random.choice(edges)
            
            if from_edge != to_edge:
                route = traci.simulation.findRoute(from_edge, to_edge)
                if route and route.edges:
                    route_id = f"route_{vid}"
                    traci.route.add(route_id, route.edges)
                    traci.vehicle.add(vid, route_id, typeID=vtype)
                    added += 1
        
        return jsonify({'success': True, 'message': f'Rush hour started! Added {added} vehicles'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================================
# HTML DASHBOARD WITH VEHICLE VISUALIZATION
# ============================================================

HTML_ULTIMATE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Manhattan Ultimate Infrastructure System</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #fff;
            overflow: hidden;
        }
        
        #map {
            position: absolute;
            width: 100%;
            height: 100%;
        }
        
        .control-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 450px;
            max-height: 90vh;
            background: linear-gradient(135deg, rgba(10,10,20,0.98), rgba(20,20,40,0.95));
            border-radius: 20px;
            padding: 25px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(102,126,234,0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            z-index: 1000;
            overflow-y: auto;
        }
        
        h1 {
            font-size: 26px;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00ff88, #0088ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            background: rgba(255,255,255,0.08);
            transform: translateY(-2px);
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 11px;
            color: rgba(255,255,255,0.6);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .traffic-panel {
            background: rgba(0,255,136,0.1);
            border: 1px solid rgba(0,255,136,0.3);
            border-radius: 12px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .ev-panel {
            background: rgba(0,136,255,0.1);
            border: 1px solid rgba(0,136,255,0.3);
            border-radius: 12px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .panel-title {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .traffic-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .traffic-item {
            font-size: 12px;
        }
        
        .traffic-value {
            font-weight: 600;
        }
        
        .substation-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin: 15px 0;
        }
        
        .sub-btn {
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s;
        }
        
        .sub-btn:hover {
            background: rgba(255,68,68,0.2);
            border-color: rgba(255,68,68,0.5);
        }
        
        .sub-btn.failed {
            background: rgba(255,68,68,0.3);
            border-color: #ff4444;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .action-btn {
            padding: 12px;
            background: linear-gradient(135deg, #00ff88, #00aa44);
            border: none;
            color: #000;
            border-radius: 10px;
            cursor: pointer;
            width: 100%;
            margin: 8px 0;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,255,136,0.4);
        }
        
        .sumo-controls {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin: 10px 0;
        }
        
        .sumo-btn {
            padding: 10px;
            background: linear-gradient(135deg, #0088ff, #0066cc);
            border: none;
            color: #fff;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .sumo-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(0,136,255,0.4);
        }
        
        .emergency-btn {
            background: linear-gradient(135deg, #ff0000, #cc0000);
        }
        
        .rush-btn {
            background: linear-gradient(135deg, #ff6600, #cc4400);
        }
        
        .status-bar {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(10,10,20,0.95);
            padding: 15px 30px;
            border-radius: 30px;
            border: 1px solid rgba(102,126,234,0.3);
            z-index: 1000;
            display: flex;
            gap: 30px;
            align-items: center;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        
        .legend {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(10,10,20,0.95);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid rgba(102,126,234,0.3);
            z-index: 1000;
        }
        
        .legend-title {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 10px;
            color: rgba(255,255,255,0.8);
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 6px 0;
            font-size: 11px;
            color: rgba(255,255,255,0.7);
        }
        
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            border: 1px solid white;
        }
        
        .congestion-bar {
            width: 100%;
            height: 20px;
            background: linear-gradient(90deg, #00ff00, #ffff00, #ff0000);
            border-radius: 10px;
            position: relative;
            margin: 10px 0;
        }
        
        .congestion-indicator {
            position: absolute;
            top: -5px;
            width: 30px;
            height: 30px;
            background: white;
            border-radius: 50%;
            border: 2px solid #000;
            transition: left 0.5s;
        }
        
        .mapboxgl-popup-content {
            background: rgba(20, 20, 30, 0.95) !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            padding: 12px !important;
        }
        
        /* Vehicle info panel */
        .vehicle-info {
            position: absolute;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(10,10,20,0.95);
            padding: 10px 20px;
            border-radius: 20px;
            border: 1px solid rgba(102,126,234,0.3);
            z-index: 999;
            font-size: 12px;
        }
        
        .ev-station-marker {
            width: 24px;
            height: 24px;
            background: linear-gradient(135deg, #00ff00, #00cc00);
            border-radius: 50%;
            border: 2px solid white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="control-panel">
        <h1>Manhattan Ultimate System</h1>
        <div style="font-size: 13px; color: rgba(255,255,255,0.5); margin-bottom: 20px;">
            Power + Traffic + EVs | Real-time Integration
        </div>
        
        <!-- Main Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="traffic-lights" style="color: #ffaa00;">0</div>
                <div class="stat-label">Traffic Lights</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="active-vehicles" style="color: #00ff88;">0</div>
                <div class="stat-label">Vehicles</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="load-mw" style="color: #0088ff;">0</div>
                <div class="stat-label">MW Load</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="substations" style="color: #ff88ff;">0</div>
                <div class="stat-label">Substations</div>
            </div>
        </div>
        
        <!-- Traffic Panel -->
        <div class="traffic-panel">
            <div class="panel-title" style="color: #00ff88;">
                🚗 Traffic Simulation
            </div>
            <div class="traffic-stats">
                <div class="traffic-item">
                    Active: <span class="traffic-value" id="vehicle-count" style="color: #00ff88;">0</span>
                </div>
                <div class="traffic-item">
                    Speed: <span class="traffic-value" id="avg-speed" style="color: #00ff88;">0</span> km/h
                </div>
                <div class="traffic-item">
                    EVs: <span class="traffic-value" id="ev-count" style="color: #00ff88;">0</span>
                </div>
                <div class="traffic-item">
                    CO₂: <span class="traffic-value" id="co2" style="color: #00ff88;">0</span> g/s
                </div>
            </div>
            
            <!-- Congestion Level -->
            <div style="margin-top: 10px;">
                <div style="font-size: 11px; margin-bottom: 5px;">Congestion Level</div>
                <div class="congestion-bar">
                    <div class="congestion-indicator" id="congestion-indicator" style="left: 0%;"></div>
                </div>
            </div>
            
            <div class="sumo-controls">
                <button class="sumo-btn" onclick="startSUMO(true)">Start GUI</button>
                <button class="sumo-btn" onclick="startSUMO(false)">Start Headless</button>
                <button class="sumo-btn" onclick="addTraffic(50)">+50 Cars</button>
                <button class="sumo-btn" onclick="addTraffic(100)">+100 Cars</button>
                <button class="sumo-btn emergency-btn" onclick="injectEmergency()">🚨 Emergency</button>
                <button class="sumo-btn rush-btn" onclick="simulateRushHour()">🚦 Rush Hour</button>
            </div>
        </div>
        
        <!-- EV Charging Panel -->
        <div class="ev-panel">
            <div class="panel-title" style="color: #0088ff;">
                ⚡ EV Charging Stations
            </div>
            <div id="charging-stations" style="font-size: 12px;">
                Loading...
            </div>
        </div>
        
        <!-- Substation Controls -->
        <div style="font-size: 14px; margin: 20px 0 10px; font-weight: 600;">
            Power Grid Control
        </div>
        <div class="substation-grid" id="substation-controls"></div>
        
        <button class="action-btn" onclick="restoreAll()">
            🔧 RESTORE ALL SYSTEMS
        </button>
        
        <button class="action-btn" onclick="stopSUMO()" style="background: linear-gradient(135deg, #ff4444, #cc0000);">
            ⏹ STOP SIMULATION
        </button>
    </div>
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-title">Vehicle Types</div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #FFD700;"></div>
            <span>Taxi</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #6666FF;"></div>
            <span>Car</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #00FF00;"></div>
            <span>Electric Vehicle</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #0066CC;"></div>
            <span>Bus</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #8B4513;"></div>
            <span>Delivery</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: #FF0000;"></div>
            <span>Emergency</span>
        </div>
    </div>
    
    <!-- Status Bar -->
    <div class="status-bar">
        <div class="status-item">
            <span class="status-indicator" id="power-indicator"></span>
            <span id="power-status">Power Grid</span>
        </div>
        <div class="status-item">
            <span class="status-indicator" id="traffic-indicator"></span>
            <span id="traffic-status">Traffic</span>
        </div>
        <div class="status-item">
            <span id="time">00:00:00</span>
        </div>
        <div class="status-item">
            <span id="vehicle-info">Vehicles: 0</span>
        </div>
    </div>
    
    <script>
        // Initialize Mapbox
        mapboxgl.accessToken = 'pk.eyJ1IjoibWFyb25veCIsImEiOiJjbWV1ODE5bHEwNGhoMmlvY2RleW51dWozIn0.FMrYdXLqnOwOEFi8qHSwxg';
        
        const map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/dark-v11',
            center: [-73.980, 40.758],
            zoom: 14,
            pitch: 45,
            bearing: -20
        });
        
        let systemState = null;
        let vehicleMarkers = {};
        let substationMarkers = [];
        let chargingStationMarkers = [];
        let updateInterval = null;
        let vehicleUpdateInterval = null;
        
        async function loadSystemState() {
            try {
                const response = await fetch('/api/system_state');
                systemState = await response.json();
                updateUI();
                renderInfrastructure();
            } catch (error) {
                console.error('Error loading system state:', error);
            }
        }
        
        async function loadVehicles() {
            try {
                const response = await fetch('/api/vehicles');
                const data = await response.json();
                updateVehicles(data.vehicles);
                document.getElementById('vehicle-info').textContent = `Vehicles: ${data.total}`;
            } catch (error) {
                console.error('Error loading vehicles:', error);
            }
        }
        
        async function loadChargingStations() {
            try {
                const response = await fetch('/api/charging_stations');
                const data = await response.json();
                updateChargingStations(data.stations);
            } catch (error) {
                console.error('Error loading charging stations:', error);
            }
        }
        
        function updateUI() {
            if (!systemState) return;
            
            const stats = systemState.statistics;
            const traffic = systemState.traffic || {};
            
            // Update main stats
            document.getElementById('traffic-lights').textContent = stats.total_traffic_lights;
            document.getElementById('active-vehicles').textContent = traffic.active_vehicles || 0;
            document.getElementById('load-mw').textContent = 
                Math.round((systemState.power?.total_load_mw || 0) + (systemState.power?.ev_load_mw || 0));
            document.getElementById('substations').textContent = 
                `${stats.operational_substations}/${stats.total_substations}`;
            
            // Update traffic stats
            document.getElementById('vehicle-count').textContent = traffic.active_vehicles || 0;
            document.getElementById('avg-speed').textContent = Math.round(traffic.avg_speed_kmh || 0);
            document.getElementById('ev-count').textContent = traffic.evs_active || 0;
            document.getElementById('co2').textContent = Math.round(traffic.co2_emissions || 0);
            
            // Update congestion indicator
            const congestion = (traffic.congestion_level || 0) * 100;
            document.getElementById('congestion-indicator').style.left = `${congestion}%`;
            
            // Update substations
            const controls = document.getElementById('substation-controls');
            controls.innerHTML = '';
            
            systemState.substations.forEach(sub => {
                const btn = document.createElement('button');
                btn.className = 'sub-btn';
                if (!sub.operational) {
                    btn.classList.add('failed');
                }
                btn.textContent = sub.name.replace(/_/g, ' ');
                btn.onclick = () => toggleSubstation(sub.name);
                controls.appendChild(btn);
            });
            
            // Update status indicators
            const failures = stats.total_substations - stats.operational_substations;
            const powerIndicator = document.getElementById('power-indicator');
            const trafficIndicator = document.getElementById('traffic-indicator');
            
            if (failures === 0) {
                powerIndicator.style.background = '#00ff88';
                document.getElementById('power-status').textContent = 'Power: Online';
            } else {
                powerIndicator.style.background = '#ff0000';
                document.getElementById('power-status').textContent = `Power: ${failures} Failures`;
            }
            
            if (traffic.simulation_active) {
                trafficIndicator.style.background = '#00ff88';
                document.getElementById('traffic-status').textContent = 
                    `Traffic: ${traffic.active_vehicles || 0} vehicles`;
            } else {
                trafficIndicator.style.background = '#666';
                document.getElementById('traffic-status').textContent = 'Traffic: Offline';
            }
        }
        
        function renderInfrastructure() {
            if (!systemState) return;
            
            // Clear existing markers
            substationMarkers.forEach(m => m.remove());
            substationMarkers = [];
            
            // Add substations
            systemState.substations.forEach(sub => {
                const el = document.createElement('div');
                el.style.width = '30px';
                el.style.height = '30px';
                el.style.background = sub.operational ? 
                    'radial-gradient(circle, #ff0066, #cc0044)' : 
                    'radial-gradient(circle, #ff0000, #aa0000)';
                el.style.borderRadius = '50%';
                el.style.border = '3px solid white';
                el.style.boxShadow = sub.operational ? 
                    '0 0 30px rgba(255,0,102,0.9)' : 
                    '0 0 30px rgba(255,0,0,0.9)';
                el.style.cursor = 'pointer';
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([sub.lon, sub.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(`
                        <strong>${sub.name}</strong><br>
                        ${sub.capacity_mva} MVA<br>
                        Load: ${sub.load_mw.toFixed(1)} MW<br>
                        Status: ${sub.operational ? '⚡ Online' : '⚠️ FAILED'}
                    `))
                    .addTo(map);
                
                substationMarkers.push(marker);
            });
            
            // Update traffic lights layer
            if (!map.getSource('traffic-lights')) {
                const features = systemState.traffic_lights.map(tl => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [tl.lon, tl.lat]
                    },
                    properties: {
                        powered: tl.powered,
                        color: tl.color || '#ff0000'
                    }
                }));
                
                map.addSource('traffic-lights', {
                    type: 'geojson',
                    data: {
                        type: 'FeatureCollection',
                        features: features
                    }
                });
                
                map.addLayer({
                    id: 'traffic-lights-layer',
                    type: 'circle',
                    source: 'traffic-lights',
                    paint: {
                        'circle-radius': [
                            'interpolate', ['linear'], ['zoom'],
                            13, 2,
                            15, 4,
                            17, 6
                        ],
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 0.9,
                        'circle-stroke-width': 0.5,
                        'circle-stroke-color': '#ffffff'
                    }
                });
            }
        }
        
        function updateVehicles(vehicles) {
            // Remove old vehicle markers
            Object.values(vehicleMarkers).forEach(m => m.remove());
            vehicleMarkers = {};
            
            if (!vehicles || vehicles.length === 0) return;
            
            // Add new vehicle markers
            vehicles.forEach(vehicle => {
                const el = document.createElement('div');
                el.style.borderRadius = '50%';
                el.style.border = '1px solid white';
                
                // Style based on vehicle type
                switch(vehicle.type) {
                    case 'taxi':
                        el.style.width = '8px';
                        el.style.height = '8px';
                        el.style.background = '#FFD700';
                        break;
                    case 'ev':
                        el.style.width = '8px';
                        el.style.height = '8px';
                        el.style.background = '#00FF00';
                        if (vehicle.battery && vehicle.battery < 20) {
                            el.style.background = '#FF8800';  // Orange for low battery
                        }
                        break;
                    case 'emergency':
                        el.style.width = '12px';
                        el.style.height = '12px';
                        el.style.background = '#FF0000';
                        el.style.animation = 'pulse 0.5s infinite';
                        break;
                    case 'bus':
                        el.style.width = '10px';
                        el.style.height = '10px';
                        el.style.background = '#0066CC';
                        break;
                    case 'delivery':
                        el.style.width = '9px';
                        el.style.height = '9px';
                        el.style.background = '#8B4513';
                        break;
                    default:
                        el.style.width = '7px';
                        el.style.height = '7px';
                        el.style.background = '#6666FF';
                }
                
                el.style.boxShadow = '0 0 4px rgba(0,0,0,0.8)';
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([vehicle.lon, vehicle.lat])
                    .addTo(map);
                
                vehicleMarkers[vehicle.id] = marker;
            });
        }
        
        function updateChargingStations(stations) {
            // Clear old markers
            chargingStationMarkers.forEach(m => m.remove());
            chargingStationMarkers = [];
            
            // Update panel
            const panel = document.getElementById('charging-stations');
            let html = '';
            
            stations.forEach(station => {
                // Add marker
                const el = document.createElement('div');
                el.className = 'ev-station-marker';
                el.innerHTML = '⚡';
                
                if (!station.operational) {
                    el.style.background = 'linear-gradient(135deg, #666, #444)';
                } else if (station.occupied >= station.capacity) {
                    el.style.background = 'linear-gradient(135deg, #ff6600, #cc4400)';
                }
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([station.lon, station.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(`
                        <strong>${station.name}</strong><br>
                        Occupied: ${station.occupied}/${station.capacity}<br>
                        Queue: ${station.queue} vehicles<br>
                        Power: ${station.power_kw} kW<br>
                        Status: ${station.operational ? '✅ Online' : '❌ Offline'}
                    `))
                    .addTo(map);
                
                chargingStationMarkers.push(marker);
                
                // Update panel
                const status = station.operational ? 
                    `${station.occupied}/${station.capacity}` : 
                    'OFFLINE';
                const color = station.operational ? 
                    (station.occupied >= station.capacity ? '#ff6600' : '#00ff88') : 
                    '#ff0000';
                
                html += `
                    <div style="margin: 5px 0;">
                        ${station.name}: 
                        <span style="color: ${color}; font-weight: 600;">
                            ${status}
                        </span>
                        ${station.queue > 0 ? ` (${station.queue} waiting)` : ''}
                    </div>
                `;
            });
            
            panel.innerHTML = html || 'No stations available';
        }
        
        async function toggleSubstation(name) {
            const sub = systemState.substations.find(s => s.name === name);
            const endpoint = sub.operational ? `/api/fail/${name}` : `/api/restore/${name}`;
            await fetch(endpoint, { method: 'POST' });
            await loadSystemState();
        }
        
        async function restoreAll() {
            await fetch('/api/restore_all', { method: 'POST' });
            await loadSystemState();
        }
        
        async function startSUMO(gui) {
            const response = await fetch('/api/sumo/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({gui: gui})
            });
            const result = await response.json();
            if (result.success) {
                alert(gui ? 'SUMO GUI started!' : 'SUMO running in background');
                // Start vehicle updates
                vehicleUpdateInterval = setInterval(() => {
                    loadVehicles();
                    loadChargingStations();
                }, 1000);
            } else {
                alert('Failed to start SUMO: ' + (result.error || 'Unknown error'));
            }
        }
        
        async function stopSUMO() {
            await fetch('/api/sumo/stop', { method: 'POST' });
            if (vehicleUpdateInterval) {
                clearInterval(vehicleUpdateInterval);
                vehicleUpdateInterval = null;
            }
            // Clear vehicles from map
            Object.values(vehicleMarkers).forEach(m => m.remove());
            vehicleMarkers = {};
            alert('Simulation stopped');
        }
        
        async function addTraffic(count) {
            const response = await fetch('/api/sumo/add_traffic', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({count: count})
            });
            const result = await response.json();
            if (result.success) {
                console.log(`Added ${result.vehicles_added} vehicles`);
            }
        }
        
        async function injectEmergency() {
            const response = await fetch('/api/sumo/inject_emergency', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                console.log('Emergency vehicle dispatched!');
            }
        }
        
        async function simulateRushHour() {
            const response = await fetch('/api/traffic/set_rush_hour', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                alert(result.message);
            }
        }
        
        function updateTime() {
            const now = new Date();
            document.getElementById('time').textContent = 
                now.toLocaleTimeString('en-US', { hour12: false });
        }
        
        // Initialize
        map.on('load', () => {
            loadSystemState();
            loadChargingStations();
            
            // Update system state every 3 seconds
            updateInterval = setInterval(loadSystemState, 3000);
            
            // Update time every second
            setInterval(updateTime, 1000);
            updateTime();
        });
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (updateInterval) clearInterval(updateInterval);
            if (vehicleUpdateInterval) clearInterval(vehicleUpdateInterval);
        });
    </script>
</body>
</html>
'''

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SYSTEM READY")
    print("="*60)
    print(f"📊 System Components:")
    print(f"   • Substations: {len(integrated_system.substations)}")
    print(f"   • Traffic Lights: {len(integrated_system.traffic_lights)}")
    print(f"   • EV Stations: {len(integrated_system.ev_stations)}")
    print(f"   • SUMO Available: {'✅ Yes' if SUMO_AVAILABLE else '❌ No'}")
    
    if SUMO_AVAILABLE and sumo_sim:
        if os.path.exists(sumo_sim.net_file):
            try:
                net = sumolib.net.readNet(sumo_sim.net_file)
                print(f"   • Streets: {len(net.getEdges())}")
                print(f"   • SUMO Traffic Lights: {len(net.getTrafficLights())}")
                print(f"   • Charging Stations: {len(sumo_sim.charging_stations)}")
            except:
                pass
    
    print("\n💡 Features:")
    print("   • Continuous traffic generation (24-hour patterns)")
    print("   • Real-time vehicle tracking on map")
    print("   • EV charging behavior and queuing")
    print("   • Power failure cascading to traffic")
    print("   • Emergency vehicle dispatch")
    print("   • Rush hour simulation")
    
    print("\n" + "="*60)
    
    # Start simulation threads
    power_thread = threading.Thread(target=power_simulation_loop, daemon=True)
    power_thread.start()
    
    print("\n🌐 Dashboard: http://localhost:5000")
    print("\n📝 Instructions:")
    print("   1. Open dashboard in browser")
    print("   2. Click 'Start GUI' or 'Start Headless' to begin traffic")
    print("   3. Fail substations to see traffic impact")
    print("   4. Watch vehicles navigate and EVs charge")
    print("="*60 + "\n")
    
    app.run(debug=False, port=5000)