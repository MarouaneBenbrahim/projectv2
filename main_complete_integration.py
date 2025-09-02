"""
Manhattan Power Grid - COMPLETE World-Class Integration
All features from main_world_class.py PLUS advanced SUMO vehicle simulation
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
import traceback
import random

# Import our systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from core.sumo_manager import ManhattanSUMOManager, SimulationScenario

app = Flask(__name__)
CORS(app)

# Initialize systems
print("=" * 60)
print("MANHATTAN POWER GRID - COMPLETE INTEGRATION")
print("Power + Traffic + Vehicles - World Class System")
print("=" * 60)

# Initialize power grid
print("Initializing PyPSA power grid...")
power_grid = ManhattanPowerGrid()

# Initialize integrated system
print("Loading integrated distribution network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# Initialize SUMO manager
print("Initializing SUMO vehicle manager...")
sumo_manager = ManhattanSUMOManager(integrated_system)

# System state
system_state = {
    'running': True,
    'sumo_running': False,
    'simulation_speed': 1.0,
    'current_time': 0,
    'scenario': SimulationScenario.MIDDAY
}

def simulation_loop():
    """Main simulation loop integrating power, traffic lights, and vehicles"""
    global system_state
    
    while system_state['running']:
        try:
            # Update traffic light phases every 2 seconds
            if system_state['current_time'] % 20 == 0:  # Every 2 seconds at 0.1s steps
                integrated_system.update_traffic_light_phases()
            
            # Run SUMO step if active
            if system_state['sumo_running'] and sumo_manager.running:
                # Sync traffic lights to SUMO
                sumo_manager.update_traffic_lights()
                
                # Step SUMO simulation
                sumo_manager.step()
                
                # Update power grid with EV charging loads
                update_ev_power_loads()
            
            # Run power flow every 30 seconds
            if system_state['current_time'] % 300 == 0:
                power_grid.run_power_flow("dc")
            
            system_state['current_time'] += 1
            time.sleep(0.1 / system_state['simulation_speed'])
            
        except Exception as e:
            print(f"Simulation error: {e}")
            traceback.print_exc()
            time.sleep(1)

def update_ev_power_loads():
    """Update power grid loads based on EV charging"""
    
    # Get current charging statistics from SUMO
    if not sumo_manager.running:
        return
        
    stats = sumo_manager.get_statistics()
    
    # Track charging by station
    charging_by_station = {}
    for vehicle in sumo_manager.vehicles.values():
        if vehicle.is_charging and vehicle.assigned_ev_station:
            if vehicle.assigned_ev_station not in charging_by_station:
                charging_by_station[vehicle.assigned_ev_station] = 0
            charging_by_station[vehicle.assigned_ev_station] += 1
    
    # Update each EV station's load
    for ev_id, ev_station in integrated_system.ev_stations.items():
        chargers_in_use = charging_by_station.get(ev_id, 0)
        charging_power_kw = chargers_in_use * 7.2  # 7.2kW per Level 2 charger
        
        # Update the integrated system
        ev_station['vehicles_charging'] = chargers_in_use
        ev_station['current_load_kw'] = charging_power_kw

# Start simulation thread
sim_thread = threading.Thread(target=simulation_loop, daemon=True)
sim_thread.start()

# API Routes

@app.route('/')
def index():
    """Serve complete dashboard with all features"""
    return render_template_string(HTML_COMPLETE_TEMPLATE)

@app.route('/api/network_state')
def get_network_state():
    """Get complete network state including vehicles"""
    state = integrated_system.get_network_state()
    
    # Add vehicle data if SUMO is running
    if system_state['sumo_running'] and sumo_manager.running:
        # Get vehicle positions with more detail
        vehicles = []
        for vehicle in sumo_manager.vehicles.values():
            try:
                # Get position from SUMO
                import traci
                if vehicle.id in traci.vehicle.getIDList():
                    x, y = traci.vehicle.getPosition(vehicle.id)
                    lon, lat = traci.simulation.convertGeo(x, y)
                    
                    vehicles.append({
                        'id': vehicle.id,
                        'lat': lat,
                        'lon': lon,
                        'type': vehicle.config.vtype.value,
                        'speed': vehicle.speed,
                        'speed_kmh': round(vehicle.speed * 3.6, 1),
                        'soc': vehicle.config.current_soc if vehicle.config.is_ev else 1.0,
                        'battery_percent': round(vehicle.config.current_soc * 100) if vehicle.config.is_ev else 100,
                        'is_charging': vehicle.is_charging,
                        'is_ev': vehicle.config.is_ev,
                        'distance_traveled': round(vehicle.distance_traveled, 1),
                        'waiting_time': round(vehicle.waiting_time, 1),
                        'destination': vehicle.destination,
                        'assigned_station': vehicle.assigned_ev_station
                    })
            except:
                pass
        
        state['vehicles'] = vehicles
        state['vehicle_stats'] = sumo_manager.get_statistics()
    else:
        state['vehicles'] = []
        state['vehicle_stats'] = {}
    
    return jsonify(state)

@app.route('/api/sumo/start', methods=['POST'])
def start_sumo():
    """Start SUMO simulation"""
    global system_state
    
    if system_state['sumo_running']:
        return jsonify({'success': False, 'message': 'SUMO already running'})
    
    try:
        # Start SUMO (headless for web interface)
        success = sumo_manager.start_sumo(gui=False, seed=42)
        
        if success:
            system_state['sumo_running'] = True
            
            # Spawn initial vehicles
            data = request.json or {}
            count = data.get('vehicle_count', 10)
            ev_percentage = data.get('ev_percentage', 0.7)
            
            spawned = sumo_manager.spawn_vehicles(count, ev_percentage)
            
            return jsonify({
                'success': True,
                'message': f'SUMO started with {spawned} vehicles',
                'vehicles_spawned': spawned
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to start SUMO'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/sumo/spawn', methods=['POST'])
def spawn_vehicles():
    """Spawn additional vehicles"""
    if not system_state['sumo_running']:
        return jsonify({'success': False, 'message': 'SUMO not running'})
    
    data = request.json or {}
    count = data.get('count', 5)
    ev_percentage = data.get('ev_percentage', 0.7)
    
    spawned = sumo_manager.spawn_vehicles(count, ev_percentage)
    
    return jsonify({
        'success': True,
        'spawned': spawned,
        'total_vehicles': sumo_manager.stats['total_vehicles']
    })

@app.route('/api/sumo/stop', methods=['POST'])
def stop_sumo():
    """Stop SUMO simulation"""
    global system_state
    
    if system_state['sumo_running']:
        sumo_manager.stop()
        system_state['sumo_running'] = False
        return jsonify({'success': True, 'message': 'SUMO stopped'})
    
    return jsonify({'success': False, 'message': 'SUMO not running'})

@app.route('/api/sumo/scenario', methods=['POST'])
def set_scenario():
    """Change simulation scenario (rush hour, night, etc.)"""
    data = request.json or {}
    scenario_name = data.get('scenario', 'MIDDAY')
    
    try:
        scenario = SimulationScenario[scenario_name]
        system_state['scenario'] = scenario
        sumo_manager.current_scenario = scenario
        
        # Adjust spawning patterns based on scenario
        if system_state['sumo_running']:
            if scenario == SimulationScenario.MORNING_RUSH:
                # Heavy traffic, more vehicles
                sumo_manager.spawn_vehicles(20, 0.6)
            elif scenario == SimulationScenario.EVENING_RUSH:
                # Heavy traffic, EVs need charging
                sumo_manager.spawn_vehicles(25, 0.7)
            elif scenario == SimulationScenario.NIGHT:
                # Light traffic
                sumo_manager.spawn_vehicles(5, 0.8)
        
        return jsonify({'success': True, 'scenario': scenario_name})
        
    except KeyError:
        return jsonify({'success': False, 'message': 'Invalid scenario'})

@app.route('/api/simulation/speed', methods=['POST'])
def set_simulation_speed():
    """Set simulation speed"""
    data = request.json or {}
    speed = data.get('speed', 1.0)
    
    system_state['simulation_speed'] = max(0.1, min(10.0, speed))
    
    return jsonify({'success': True, 'speed': system_state['simulation_speed']})

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Trigger substation failure affecting traffic lights and EV stations"""
    impact = integrated_system.simulate_substation_failure(substation)
    power_grid.trigger_failure('substation', substation)
    
    # Update SUMO traffic lights if running
    if system_state['sumo_running'] and sumo_manager.running:
        sumo_manager.update_traffic_lights()
        
        # Also update EV station availability
        for ev_id, ev_station in integrated_system.ev_stations.items():
            if ev_station['substation'] == substation:
                if ev_id in sumo_manager.ev_stations_sumo:
                    sumo_manager.ev_stations_sumo[ev_id]['available'] = 0
    
    return jsonify(impact)

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore substation"""
    success = integrated_system.restore_substation(substation)
    if success:
        power_grid.restore_component('substation', substation)
        
        # Update SUMO traffic lights if running
        if system_state['sumo_running'] and sumo_manager.running:
            sumo_manager.update_traffic_lights()
            
            # Restore EV station availability
            for ev_id, ev_station in integrated_system.ev_stations.items():
                if ev_station['substation'] == substation:
                    if ev_id in sumo_manager.ev_stations_sumo:
                        sumo_manager.ev_stations_sumo[ev_id]['available'] = ev_station['chargers']
    
    return jsonify({'success': success})

@app.route('/api/restore_all', methods=['POST'])
def restore_all():
    """Restore all substations"""
    for sub_name in integrated_system.substations.keys():
        integrated_system.restore_substation(sub_name)
        power_grid.restore_component('substation', sub_name)
    
    # Update SUMO if running
    if system_state['sumo_running'] and sumo_manager.running:
        sumo_manager.update_traffic_lights()
        
        # Restore all EV stations
        for ev_id, ev_station in integrated_system.ev_stations.items():
            if ev_id in sumo_manager.ev_stations_sumo:
                sumo_manager.ev_stations_sumo[ev_id]['available'] = ev_station['chargers']
    
    return jsonify({'success': True, 'message': 'All systems restored'})

@app.route('/api/status')
def get_status():
    """Get complete system status"""
    power_status = power_grid.get_system_status()
    
    # Add vehicle statistics
    if system_state['sumo_running'] and sumo_manager.running:
        vehicle_stats = sumo_manager.get_statistics()
        power_status['vehicles'] = {
            'total': vehicle_stats['total_vehicles'],
            'active': len(sumo_manager.vehicles),
            'evs': vehicle_stats['ev_vehicles'],
            'charging': vehicle_stats['vehicles_charging'],
            'avg_speed_kmh': round(vehicle_stats['avg_speed_mps'] * 3.6, 1),
            'energy_consumed_kwh': round(vehicle_stats['total_energy_consumed_kwh'], 2)
        }
    else:
        power_status['vehicles'] = {
            'total': 0,
            'active': 0,
            'evs': 0,
            'charging': 0,
            'avg_speed_kmh': 0,
            'energy_consumed_kwh': 0
        }
    
    power_status['simulation'] = {
        'sumo_running': system_state['sumo_running'],
        'speed': system_state['simulation_speed'],
        'scenario': system_state['scenario'].value
    }
    
    return jsonify(power_status)

# HTML Template - Complete with all features
HTML_COMPLETE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manhattan Power Grid - Complete Integration</title>
    
    <!-- Mapbox GL JS -->
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #fff;
            overflow: hidden;
        }
        
        #map {
            position: absolute;
            width: 100%;
            height: 100%;
            background: #000;
        }
        
        /* Popup Styling */
        .mapboxgl-popup-content {
            background: rgba(20, 20, 30, 0.95) !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-size: 13px !important;
            border: 1px solid rgba(100, 200, 255, 0.3) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.8) !important;
        }
        
        .mapboxgl-popup-content strong {
            color: #00ff88 !important;
            font-size: 14px !important;
        }
        
        /* Control Panel */
        .control-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 440px;
            background: linear-gradient(135deg, rgba(15,15,25,0.98), rgba(25,25,45,0.95));
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(100,200,255,0.2);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            z-index: 1000;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        h1 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #00ff88, #00aaff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            font-size: 13px;
            color: rgba(255,255,255,0.5);
            margin-bottom: 20px;
        }
        
        /* Statistics Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            background: rgba(255,255,255,0.06);
            transform: translateY(-2px);
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        
        .stat-label {
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Traffic Light Stats */
        .light-stats {
            display: flex;
            gap: 10px;
            margin-top: 10px;
            font-size: 11px;
        }
        
        .light-stat {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .light-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        /* Vehicle Control Section */
        .vehicle-control {
            margin: 20px 0;
            padding: 16px;
            background: rgba(0,170,255,0.1);
            border-radius: 12px;
            border: 1px solid rgba(0,170,255,0.3);
        }
        
        .vehicle-control h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: #00aaff;
        }
        
        .vehicle-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .vehicle-stat {
            text-align: center;
            padding: 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
        }
        
        .vehicle-stat-value {
            font-size: 20px;
            font-weight: bold;
            color: #00ff88;
        }
        
        .vehicle-stat-label {
            font-size: 10px;
            color: rgba(255,255,255,0.5);
        }
        
        /* Buttons */
        .btn-group {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin: 12px 0;
        }
        
        .btn {
            padding: 10px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #00ff88, #00cc66);
            color: #000;
        }
        
        .btn-secondary {
            background: rgba(255,255,255,0.1);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            color: #fff;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,255,136,0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Substation Controls */
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
            background: rgba(255,50,50,0.2);
            border-color: rgba(255,50,50,0.5);
        }
        
        .sub-btn.failed {
            background: rgba(255,0,0,0.3);
            border-color: #ff0000;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        /* Scenario Selector */
        .scenario-selector {
            margin: 16px 0;
        }
        
        .scenario-buttons {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 6px;
        }
        
        .scenario-btn {
            padding: 8px;
            font-size: 11px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .scenario-btn.active {
            background: rgba(0,255,136,0.2);
            border-color: #00ff88;
        }
        
        /* Speed Control */
        .speed-control {
            margin: 16px 0;
        }
        
        .speed-slider {
            width: 100%;
            margin: 10px 0;
        }
        
        /* Layer Controls */
        .layer-controls {
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        
        .layer-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
        }
        
        .toggle {
            position: relative;
            width: 44px;
            height: 22px;
        }
        
        .toggle input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.2);
            transition: .3s;
            border-radius: 22px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 16px;
            width: 16px;
            left: 3px;
            bottom: 3px;
            background: white;
            transition: .3s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background: linear-gradient(90deg, #00ff88, #00aaff);
        }
        
        input:checked + .slider:before {
            transform: translateX(22px);
        }
        
        /* Status Bar */
        .status-bar {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(15,15,25,0.95);
            padding: 12px 24px;
            border-radius: 30px;
            border: 1px solid rgba(100,200,255,0.2);
            display: flex;
            gap: 20px;
            align-items: center;
            z-index: 1000;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }
        
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
        }
        
        /* Legend */
        .legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(15,15,25,0.95);
            padding: 16px;
            border-radius: 12px;
            border: 1px solid rgba(100,200,255,0.2);
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
            font-size: 12px;
            color: rgba(255,255,255,0.7);
        }
        
        .legend-color {
            width: 24px;
            height: 3px;
            border-radius: 2px;
        }
        
        .legend-vehicle {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        
        /* Vehicle Icon */
        .vehicle-icon {
            width: 20px;
            height: 10px;
            background: #00ff00;
            border: 2px solid #fff;
            border-radius: 3px;
            position: relative;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .vehicle-icon::before {
            content: '';
            position: absolute;
            top: -3px;
            left: 2px;
            right: 2px;
            height: 4px;
            background: rgba(255,255,255,0.3);
            border-radius: 2px;
        }
        
        .vehicle-icon.ev {
            background: #00ff00;
        }
        
        .vehicle-icon.gas {
            background: #6464ff;
        }
        
        .vehicle-icon.charging {
            background: #ffa500;
            animation: pulse 1s infinite;
        }
        
        .vehicle-icon:hover {
            transform: scale(1.5);
            z-index: 1000;
        }
        
        .section-title {
            font-size: 14px;
            font-weight: 600;
            margin: 20px 0 12px 0;
            color: rgba(255,255,255,0.8);
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Control Panel -->
    <div class="control-panel">
        <h1>Manhattan Power Grid</h1>
        <div class="subtitle">Complete Integration: Power + Traffic + Vehicles</div>
        
        <!-- Main Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="traffic-lights" style="color: #ffaa00;">0</div>
                <div class="stat-label">Traffic Lights</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="powered-lights" style="color: #00ff88;">0</div>
                <div class="stat-label">Powered</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="load-mw" style="color: #00aaff;">0</div>
                <div class="stat-label">MW Load</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="substations-online" style="color: #ff88ff;">0</div>
                <div class="stat-label">Substations</div>
            </div>
        </div>
        
        <!-- Traffic Light Color Distribution -->
        <div class="light-stats">
            <div class="light-stat">
                <div class="light-dot" style="background: #00ff00;"></div>
                <span id="green-count">0</span> Green
            </div>
            <div class="light-stat">
                <div class="light-dot" style="background: #ffff00;"></div>
                <span id="yellow-count">0</span> Yellow
            </div>
            <div class="light-stat">
                <div class="light-dot" style="background: #ff0000;"></div>
                <span id="red-count">0</span> Red
            </div>
            <div class="light-stat">
                <div class="light-dot" style="background: #000000; border: 1px solid #666;"></div>
                <span id="black-count">0</span> Off
            </div>
        </div>
        
        <!-- Vehicle Control -->
        <div class="vehicle-control">
            <h3>🚗 Vehicle Simulation Control</h3>
            
            <div class="vehicle-stats">
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="active-vehicles">0</div>
                    <div class="vehicle-stat-label">Active</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="ev-count">0</div>
                    <div class="vehicle-stat-label">EVs</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="charging-count">0</div>
                    <div class="vehicle-stat-label">Charging</div>
                </div>
            </div>
            
            <div class="vehicle-stats">
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="avg-speed">0</div>
                    <div class="vehicle-stat-label">km/h</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="energy-consumed">0</div>
                    <div class="vehicle-stat-label">kWh Used</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="wait-time">0</div>
                    <div class="vehicle-stat-label">Wait (s)</div>
                </div>
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" onclick="startSUMO()" id="start-sumo-btn">
                    ▶️ Start Vehicles
                </button>
                <button class="btn btn-danger" onclick="stopSUMO()" id="stop-sumo-btn" disabled>
                    ⏹️ Stop Vehicles
                </button>
                <button class="btn btn-secondary" onclick="spawnVehicles(5)" id="spawn-btn" disabled>
                    ➕ Add 5 Cars
                </button>
                <button class="btn btn-secondary" onclick="spawnVehicles(10)" id="spawn10-btn" disabled>
                    ➕ Add 10 Cars
                </button>
            </div>
        </div>
        
        <!-- Scenario Selector -->
        <div class="scenario-selector">
            <div class="section-title">📅 Traffic Scenario</div>
            <div class="scenario-buttons">
                <button class="scenario-btn" onclick="setScenario('NIGHT')">🌙 Night</button>
                <button class="scenario-btn" onclick="setScenario('MORNING_RUSH')">🌅 Rush AM</button>
                <button class="scenario-btn active" onclick="setScenario('MIDDAY')">☀️ Midday</button>
                <button class="scenario-btn" onclick="setScenario('EVENING_RUSH')">🌇 Rush PM</button>
            </div>
        </div>
        
        <!-- Speed Control -->
        <div class="speed-control">
            <div class="section-title">⚡ Simulation Speed: <span id="speed-value">1.0x</span></div>
            <input type="range" class="speed-slider" id="speed-slider" 
                   min="0.1" max="5" step="0.1" value="1.0" 
                   onchange="setSimulationSpeed(this.value)">
        </div>
        
        <!-- Substation Controls -->
        <div class="section-title">🏭 Substation Control</div>
        <div class="substation-grid" id="substation-controls"></div>
        
        <!-- Action Buttons -->
        <button class="btn btn-primary" style="width: 100%; margin-top: 16px;" onclick="restoreAll()">
            🔧 Restore All Systems
        </button>
        
        <!-- Layer Controls -->
        <div class="layer-controls">
            <div class="section-title">👁️ Visualization Layers</div>
            
            <div class="layer-item">
                <span>Traffic Lights</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-lights" onchange="toggleLayer('lights')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>Vehicles</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-vehicles" onchange="toggleLayer('vehicles')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>13.8kV Cables</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-primary" onchange="toggleLayer('primary')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>480V Cables</span>
                <label class="toggle">
                    <input type="checkbox" id="layer-secondary" onchange="toggleLayer('secondary')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>EV Stations</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-ev" onchange="toggleLayer('ev')">
                    <span class="slider"></span>
                </label>
            </div>
        </div>
    </div>
    
    <!-- Status Bar -->
    <div class="status-bar">
        <div class="status-item">
            <span class="status-indicator" id="system-indicator"></span>
            <span id="system-status">System Online</span>
        </div>
        <div class="status-item">
            🚗 <span id="vehicle-count">0</span> vehicles
        </div>
        <div class="status-item">
            ⚡ <span id="charging-stations">0</span> charging
        </div>
        <div class="status-item">
            📊 <span id="total-load">0</span> MW
        </div>
        <div class="status-item">
            🕐 <span id="time">00:00</span>
        </div>
    </div>
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-title">System Components</div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff0066; height: 8px;"></div>
            <span>Substations (138kV)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00ff88;"></div>
            <span>Primary (13.8kV)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ffaa00;"></div>
            <span>Service (480V)</span>
        </div>
        <div class="legend-item">
            <div class="legend-vehicle" style="background: #00ff00; border: 2px solid #fff;"></div>
            <span>Electric Vehicle</span>
        </div>
        <div class="legend-item">
            <div class="legend-vehicle" style="background: #6464ff; border: 2px solid #fff;"></div>
            <span>Gas Vehicle</span>
        </div>
        <div class="legend-item">
            <div class="legend-vehicle" style="background: #ffa500; border: 2px solid #fff;"></div>
            <span>Charging EV</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00aaff; height: 8px;"></div>
            <span>EV Stations</span>
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
        
        // State
        let networkState = null;
        let markers = [];
        let vehicleMarkers = {};
        let layers = {
            lights: true,
            vehicles: true,
            primary: true,
            secondary: false,  // Off by default for performance
            ev: true
        };
        let sumoRunning = false;
        
        // Load network state
        async function loadNetworkState() {
            try {
                const response = await fetch('/api/network_state');
                networkState = await response.json();
                updateUI();
                renderNetwork();
                if (layers.vehicles) {
                    renderVehicles();
                }
            } catch (error) {
                console.error('Error loading network state:', error);
            }
        }
        
        // Update UI
        function updateUI() {
            if (!networkState) return;
            
            const stats = networkState.statistics;
            
            // Update main stats
            document.getElementById('traffic-lights').textContent = stats.total_traffic_lights;
            document.getElementById('powered-lights').textContent = stats.powered_traffic_lights;
            document.getElementById('load-mw').textContent = Math.round(stats.total_load_mw);
            document.getElementById('substations-online').textContent = 
                `${stats.operational_substations}/${stats.total_substations}`;
            
            // Update traffic light color counts
            document.getElementById('green-count').textContent = stats.green_lights || 0;
            document.getElementById('yellow-count').textContent = stats.yellow_lights || 0;
            document.getElementById('red-count').textContent = stats.red_lights || 0;
            document.getElementById('black-count').textContent = stats.black_lights || 0;
            
            // Vehicle stats
            if (networkState.vehicle_stats) {
                document.getElementById('active-vehicles').textContent = (networkState.vehicles || []).length;
                document.getElementById('ev-count').textContent = networkState.vehicle_stats.ev_vehicles || 0;
                document.getElementById('charging-count').textContent = networkState.vehicle_stats.vehicles_charging || 0;
                document.getElementById('avg-speed').textContent = 
                    Math.round((networkState.vehicle_stats.avg_speed_mps || 0) * 3.6);
                document.getElementById('energy-consumed').textContent = 
                    Math.round(networkState.vehicle_stats.total_energy_consumed_kwh || 0);
                document.getElementById('wait-time').textContent = 
                    Math.round(networkState.vehicle_stats.total_wait_time || 0);
                
                document.getElementById('vehicle-count').textContent = (networkState.vehicles || []).length;
                document.getElementById('charging-stations').textContent = networkState.vehicle_stats.vehicles_charging || 0;
            }
            
            document.getElementById('total-load').textContent = Math.round(stats.total_load_mw);
            
            // Create substation buttons if not exists
            const controls = document.getElementById('substation-controls');
            if (controls.children.length === 0) {
                networkState.substations.forEach(sub => {
                    const btn = document.createElement('button');
                    btn.className = 'sub-btn';
                    btn.id = `sub-btn-${sub.name}`;
                    btn.textContent = sub.name.replace(/_/g, ' ');
                    btn.onclick = () => toggleSubstation(sub.name);
                    controls.appendChild(btn);
                });
            }
            
            // Update substation button states
            networkState.substations.forEach(sub => {
                const btn = document.getElementById(`sub-btn-${sub.name}`);
                if (btn) {
                    if (sub.operational) {
                        btn.classList.remove('failed');
                    } else {
                        btn.classList.add('failed');
                    }
                }
            });
            
            // Update system status
            const failures = stats.total_substations - stats.operational_substations;
            const indicator = document.getElementById('system-indicator');
            const status = document.getElementById('system-status');
            
            if (failures === 0) {
                indicator.style.background = '#00ff88';
                status.textContent = 'System Online';
            } else if (failures <= 2) {
                indicator.style.background = '#ffaa00';
                status.textContent = `${failures} Substation${failures > 1 ? 's' : ''} Failed`;
            } else {
                indicator.style.background = '#ff0000';
                status.textContent = 'Critical Failures';
            }
        }
        
        // Render network
        function renderNetwork() {
            if (!networkState) return;
            
            // Clear existing non-vehicle markers
            markers.forEach(m => m.remove());
            markers = [];
            
            // Remove existing layers
            ['primary-cables', 'secondary-cables', 'traffic-lights'].forEach(layerId => {
                if (map.getLayer(layerId)) map.removeLayer(layerId);
                if (map.getSource(layerId)) map.removeSource(layerId);
            });
            
            // Add substations
            networkState.substations.forEach(sub => {
                const el = document.createElement('div');
                el.style.width = '30px';
                el.style.height = '30px';
                el.style.background = sub.operational ? 
                    'radial-gradient(circle, #ff0066 40%, #cc0052 100%)' : 
                    'radial-gradient(circle, #ff0000 40%, #aa0000 100%)';
                el.style.borderRadius = '50%';
                el.style.border = '3px solid #fff';
                el.style.boxShadow = sub.operational ? 
                    '0 0 25px rgba(255,0,102,0.9)' :
                    '0 0 25px rgba(255,0,0,0.9)';
                el.style.cursor = 'pointer';
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([sub.lon, sub.lat])
                    .setPopup(new mapboxgl.Popup({offset: 25}).setHTML(`
                        <strong>${sub.name}</strong><br>
                        Capacity: ${sub.capacity_mva} MVA<br>
                        Load: ${sub.load_mw.toFixed(1)} MW<br>
                        Status: <span style="color: ${sub.operational ? '#00ff88' : '#ff0000'}">
                            ${sub.operational ? '⚡ ONLINE' : '⚠️ FAILED'}
                        </span><br>
                        Coverage: ${sub.coverage_area}
                    `))
                    .addTo(map);
                
                markers.push(marker);
            });
            
            // Add EV stations if layer is enabled
            if (layers.ev) {
                networkState.ev_stations.forEach(ev => {
                    const el = document.createElement('div');
                    el.style.width = '28px';
                    el.style.height = '28px';
                    el.style.background = ev.operational ? 
                        'linear-gradient(135deg, #00aaff 0%, #0088dd 100%)' : '#666';
                    el.style.borderRadius = '6px';
                    el.style.border = '2px solid #fff';
                    el.style.display = 'flex';
                    el.style.alignItems = 'center';
                    el.style.justifyContent = 'center';
                    el.style.fontSize = '16px';
                    el.style.fontWeight = 'bold';
                    el.style.color = '#fff';
                    el.style.boxShadow = ev.operational ? 
                        '0 2px 10px rgba(0,170,255,0.5)' : 
                        '0 2px 5px rgba(0,0,0,0.3)';
                    el.innerHTML = '⚡';
                    
                    const charging = ev.vehicles_charging || 0;
                    const marker = new mapboxgl.Marker(el)
                        .setLngLat([ev.lon, ev.lat])
                        .setPopup(new mapboxgl.Popup({offset: 25}).setHTML(`
                            <strong>${ev.name}</strong><br>
                            Chargers: ${ev.chargers}<br>
                            Charging: ${charging}/${ev.chargers}<br>
                            Substation: ${ev.substation}<br>
                            Status: <span style="color: ${ev.operational ? '#00ff88' : '#ff0000'}">
                                ${ev.operational ? '✅ Online' : '❌ Offline'}
                            </span>
                        `))
                        .addTo(map);
                    
                    markers.push(marker);
                });
            }
            
            // Add cables
            if (networkState.cables) {
                // Primary cables (13.8kV)
                if (layers.primary && networkState.cables.primary) {
                    const primaryFeatures = networkState.cables.primary
                        .filter(cable => cable.path && cable.path.length > 1)
                        .map(cable => ({
                            type: 'Feature',
                            geometry: {
                                type: 'LineString',
                                coordinates: cable.path
                            },
                            properties: {
                                operational: cable.operational
                            }
                        }));
                    
                    if (primaryFeatures.length > 0) {
                        map.addSource('primary-cables', {
                            type: 'geojson',
                            data: {
                                type: 'FeatureCollection',
                                features: primaryFeatures
                            }
                        });
                        
                        map.addLayer({
                            id: 'primary-cables',
                            type: 'line',
                            source: 'primary-cables',
                            paint: {
                                'line-color': ['case',
                                    ['get', 'operational'], '#00ff88',
                                    '#ff0000'
                                ],
                                'line-width': 3,
                                'line-opacity': 0.7
                            }
                        });
                    }
                }
                
                // Secondary cables (480V) - only if enabled
                if (layers.secondary && networkState.cables.secondary) {
                    const secondaryFeatures = networkState.cables.secondary
                        .filter(cable => cable.path && cable.path.length > 1)
                        .slice(0, 100)  // Limit for performance
                        .map(cable => ({
                            type: 'Feature',
                            geometry: {
                                type: 'LineString',
                                coordinates: cable.path
                            },
                            properties: {
                                operational: cable.operational
                            }
                        }));
                    
                    if (secondaryFeatures.length > 0) {
                        map.addSource('secondary-cables', {
                            type: 'geojson',
                            data: {
                                type: 'FeatureCollection',
                                features: secondaryFeatures
                            }
                        });
                        
                        map.addLayer({
                            id: 'secondary-cables',
                            type: 'line',
                            source: 'secondary-cables',
                            paint: {
                                'line-color': ['case',
                                    ['get', 'operational'], '#ffaa00',
                                    '#ff0000'
                                ],
                                'line-width': 1,
                                'line-opacity': 0.4
                            }
                        });
                    }
                }
            }
            
            // Add traffic lights
            if (layers.lights && networkState.traffic_lights) {
                const features = networkState.traffic_lights.map(tl => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [tl.lon, tl.lat]
                    },
                    properties: {
                        powered: tl.powered,
                        color: tl.color || '#ff0000',
                        phase: tl.phase,
                        intersection: tl.intersection
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
                    id: 'traffic-lights',
                    type: 'circle',
                    source: 'traffic-lights',
                    paint: {
                        'circle-radius': [
                            'interpolate', ['linear'], ['zoom'],
                            12, 2,
                            14, 3,
                            16, 5
                        ],
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 0.9,
                        'circle-stroke-width': 0.5,
                        'circle-stroke-color': '#ffffff',
                        'circle-stroke-opacity': 0.3
                    }
                });
                
                // Add click handler for traffic lights
                map.on('click', 'traffic-lights', (e) => {
                    const props = e.features[0].properties;
                    let status = '🟢 Green';
                    if (props.color === '#ffff00') status = '🟡 Yellow';
                    else if (props.color === '#ff0000') status = '🔴 Red';
                    else if (props.color === '#000000') status = '⚫ No Power';
                    
                    new mapboxgl.Popup()
                        .setLngLat(e.lngLat)
                        .setHTML(`
                            <strong>Traffic Light</strong><br>
                            ${props.intersection}<br>
                            Status: ${status}
                        `)
                        .addTo(map);
                });
            }
        }
        
        // Render vehicles with better icons
        function renderVehicles() {
            if (!networkState || !networkState.vehicles) return;
            
            networkState.vehicles.forEach(vehicle => {
                let marker = vehicleMarkers[vehicle.id];
                
                if (!marker) {
                    // Create new vehicle marker with better icon
                    const el = document.createElement('div');
                    el.className = 'vehicle-icon';
                    
                    // Set color based on vehicle state
                    if (vehicle.is_charging) {
                        el.classList.add('charging');
                    } else if (vehicle.is_ev) {
                        el.classList.add('ev');
                    } else {
                        el.classList.add('gas');
                    }
                    
                    // Add direction indicator
                    if (vehicle.speed > 0) {
                        el.style.transform = `rotate(${Math.random() * 360}deg)`;
                    }
                    
                    marker = new mapboxgl.Marker(el)
                        .setLngLat([vehicle.lon, vehicle.lat])
                        .setPopup(new mapboxgl.Popup({offset: 25}).setHTML(`
                            <strong>Vehicle ${vehicle.id}</strong><br>
                            Type: ${vehicle.type}<br>
                            Speed: ${vehicle.speed_kmh} km/h<br>
                            ${vehicle.is_ev ? `Battery: ${vehicle.battery_percent}%` : 'Gas Vehicle'}<br>
                            ${vehicle.is_charging ? '🔌 Charging at ' + vehicle.assigned_station : ''}<br>
                            Distance: ${vehicle.distance_traveled} m<br>
                            Wait time: ${vehicle.waiting_time}s
                        `))
                        .addTo(map);
                    
                    vehicleMarkers[vehicle.id] = marker;
                } else {
                    // Update existing marker position smoothly
                    marker.setLngLat([vehicle.lon, vehicle.lat]);
                    
                    // Update color based on state
                    const el = marker.getElement();
                    el.className = 'vehicle-icon';
                    if (vehicle.is_charging) {
                        el.classList.add('charging');
                    } else if (vehicle.is_ev) {
                        el.classList.add('ev');
                    } else {
                        el.classList.add('gas');
                    }
                }
            });
            
            // Remove markers for vehicles that no longer exist
            const currentVehicleIds = new Set(networkState.vehicles.map(v => v.id));
            for (const [id, marker] of Object.entries(vehicleMarkers)) {
                if (!currentVehicleIds.has(id)) {
                    marker.remove();
                    delete vehicleMarkers[id];
                }
            }
        }
        
        // Toggle layer visibility
        function toggleLayer(layer) {
            layers[layer] = !layers[layer];
            
            if (layer === 'lights') {
                if (map.getLayer('traffic-lights')) {
                    map.setLayoutProperty('traffic-lights', 'visibility', layers[layer] ? 'visible' : 'none');
                }
            } else if (layer === 'primary') {
                if (map.getLayer('primary-cables')) {
                    map.setLayoutProperty('primary-cables', 'visibility', layers[layer] ? 'visible' : 'none');
                }
            } else if (layer === 'secondary') {
                if (map.getLayer('secondary-cables')) {
                    map.setLayoutProperty('secondary-cables', 'visibility', layers[layer] ? 'visible' : 'none');
                }
            } else if (layer === 'vehicles') {
                if (!layers[layer]) {
                    // Hide all vehicle markers
                    for (const marker of Object.values(vehicleMarkers)) {
                        marker.remove();
                    }
                    vehicleMarkers = {};
                }
            } else {
                renderNetwork();
            }
        }
        
        // SUMO Control Functions
        async function startSUMO() {
            const response = await fetch('/api/sumo/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    vehicle_count: 10,
                    ev_percentage: 0.7
                })
            });
            
            const result = await response.json();
            if (result.success) {
                sumoRunning = true;
                document.getElementById('start-sumo-btn').disabled = true;
                document.getElementById('stop-sumo-btn').disabled = false;
                document.getElementById('spawn-btn').disabled = false;
                document.getElementById('spawn10-btn').disabled = false;
                alert(result.message);
            } else {
                alert('Failed to start SUMO: ' + result.message);
            }
        }
        
        async function stopSUMO() {
            const response = await fetch('/api/sumo/stop', {method: 'POST'});
            const result = await response.json();
            
            if (result.success) {
                sumoRunning = false;
                document.getElementById('start-sumo-btn').disabled = false;
                document.getElementById('stop-sumo-btn').disabled = true;
                document.getElementById('spawn-btn').disabled = true;
                document.getElementById('spawn10-btn').disabled = true;
                
                // Clear vehicle markers
                for (const marker of Object.values(vehicleMarkers)) {
                    marker.remove();
                }
                vehicleMarkers = {};
            }
        }
        
        async function spawnVehicles(count) {
            const response = await fetch('/api/sumo/spawn', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    count: count,
                    ev_percentage: 0.7
                })
            });
            
            const result = await response.json();
            if (result.success) {
                console.log(`Spawned ${result.spawned} vehicles`);
            }
        }
        
        async function setScenario(scenario) {
            const response = await fetch('/api/sumo/scenario', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({scenario: scenario})
            });
            
            const result = await response.json();
            if (result.success) {
                // Update button states
                document.querySelectorAll('.scenario-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                event.target.classList.add('active');
            }
        }
        
        async function setSimulationSpeed(speed) {
            document.getElementById('speed-value').textContent = `${speed}x`;
            
            await fetch('/api/simulation/speed', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({speed: parseFloat(speed)})
            });
        }
        
        async function toggleSubstation(name) {
            const sub = networkState.substations.find(s => s.name === name);
            
            if (sub.operational) {
                await fetch(`/api/fail/${name}`, { method: 'POST' });
            } else {
                await fetch(`/api/restore/${name}`, { method: 'POST' });
            }
            
            await loadNetworkState();
        }
        
        async function restoreAll() {
            await fetch('/api/restore_all', { method: 'POST' });
            await loadNetworkState();
        }
        
        // Update time
        function updateTime() {
            const now = new Date();
            document.getElementById('time').textContent = 
                now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }
        
        // Initialize
        map.on('load', () => {
            loadNetworkState();
            
            // Update every 500ms for smooth vehicle movement
            setInterval(loadNetworkState, 500);
            setInterval(updateTime, 1000);
            updateTime();
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("COMPLETE SYSTEM INFORMATION:")
    print(f"  - Substations: {len(integrated_system.substations)}")
    print(f"  - Distribution Transformers: {len(integrated_system.distribution_transformers)}")
    print(f"  - Traffic Lights: {len(integrated_system.traffic_lights)}")
    print(f"  - EV Stations: {len(integrated_system.ev_stations)}")
    print(f"  - Primary Cables (13.8kV): {len(integrated_system.primary_cables)}")
    print(f"  - Secondary Cables (480V): {len(integrated_system.secondary_cables)}")
    print("=" * 60)
    print("\n🚀 Starting Complete System at http://localhost:5000")
    print("\n📋 INSTRUCTIONS:")
    print("  1. Open http://localhost:5000 in your browser")
    print("  2. All your original features are preserved:")
    print("     - Toggle traffic lights, cables, EV stations layers")
    print("     - Fail/restore substations")
    print("     - See traffic light phase changes")
    print("  3. NEW Vehicle Features:")
    print("     - Click 'Start Vehicles' to begin SUMO simulation")
    print("     - Watch EVs route to charging stations when battery < 20%")
    print("     - Orange vehicles = actively charging")
    print("     - Try different scenarios (Rush Hour spawns more vehicles)")
    print("     - Fail substations to see EV stations go offline")
    print("=" * 60)
    
    app.run(debug=False, port=5000)