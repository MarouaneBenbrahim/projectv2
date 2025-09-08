"""
Manhattan Power Grid + SUMO Traffic
COMPLETE WORLD-CLASS INTEGRATED SYSTEM
Con Edison Power + NYC DOT Traffic + EV Charging
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
import os
import sys

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
from manhattan_sumo_fixed import ManhattanTrafficSimulation

app = Flask(__name__)
CORS(app)

# ============================================================
# SYSTEM INITIALIZATION
# ============================================================

print("\n" + "="*60)
print("MANHATTAN INTEGRATED POWER & TRAFFIC SYSTEM")
print("World-Class Infrastructure Simulation")
print("="*60)

# Initialize power grid
print("\n⚡ Initializing Power Grid (PyPSA)...")
power_grid = ManhattanPowerGrid()

# Initialize distribution network
print("🔌 Loading Distribution Network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# Initialize SUMO if available
sumo_sim = None
if SUMO_AVAILABLE:
    print("🚦 Initializing SUMO Traffic Simulation...")
    sumo_sim = ManhattanTrafficSimulation(integrated_system)
    
    # Check if SUMO files exist
    if not os.path.exists(sumo_sim.net_file):
        print("   Setting up SUMO network...")
        sumo_sim.setup_complete()

# ============================================================
# GLOBAL STATE
# ============================================================

system_state = {
    'running': True,
    'simulation_time': 0,
    'power_ok': True,
    'traffic_ok': SUMO_AVAILABLE,
    'failed_substations': set(),
    'traffic_metrics': {},
    'power_metrics': {}
}

# ============================================================
# SIMULATION LOOPS
# ============================================================

def power_simulation_loop():
    """Power grid simulation loop"""
    while system_state['running']:
        try:
            # Run power flow every 30 seconds
            if system_state['simulation_time'] % 30 == 0:
                result = power_grid.run_power_flow("dc")
                if result:
                    system_state['power_metrics'] = {
                        'total_load_mw': result.total_loss_mw,
                        'health_score': 100 - len(result.voltage_violations) * 5
                    }
            
            # Update traffic light phases
            if system_state['simulation_time'] % 2 == 0:
                integrated_system.update_traffic_light_phases()
            
            time.sleep(1)
            system_state['simulation_time'] += 1
            
        except Exception as e:
            print(f"Power loop error: {e}")
            time.sleep(1)

def traffic_simulation_loop():
    """SUMO traffic simulation loop"""
    if not SUMO_AVAILABLE or not sumo_sim:
        return
    
    # Start SUMO headless
    if not sumo_sim.running:
        print("🚗 Starting SUMO traffic simulation (headless)...")
        sumo_sim.start(gui=False)
    
    while system_state['running'] and sumo_sim.running:
        try:
            metrics = sumo_sim.step()
            if metrics:
                system_state['traffic_metrics'] = metrics
                
                # Update EV charging loads
                if metrics['vehicles'] > 0:
                    ev_count = int(metrics['vehicles'] * 0.15)  # 15% EVs
                    _update_ev_charging(ev_count)
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Traffic loop error: {e}")
            time.sleep(1)

def _update_ev_charging(ev_count):
    """Update EV charging station loads"""
    for ev_station in integrated_system.ev_stations.values():
        if ev_station['operational']:
            # Simulate 20% of EVs are charging
            charging = min(int(ev_count * 0.2), ev_station['chargers'])
            ev_station['vehicles_charging'] = charging

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/system_state')
def get_system_state():
    """Get complete system state"""
    network_state = integrated_system.get_network_state()
    
    # Add SUMO metrics if available
    if SUMO_AVAILABLE and system_state['traffic_metrics']:
        network_state['traffic'] = {
            'vehicles': system_state['traffic_metrics'].get('vehicles', 0),
            'avg_speed_kmh': system_state['traffic_metrics'].get('avg_speed', 0) * 3.6,
            'waiting_time': system_state['traffic_metrics'].get('waiting_time', 0),
            'co2_emissions': system_state['traffic_metrics'].get('co2_emissions', 0),
            'simulation_active': sumo_sim.running if sumo_sim else False
        }
    else:
        network_state['traffic'] = {
            'vehicles': 0,
            'avg_speed_kmh': 0,
            'simulation_active': False
        }
    
    # Add power metrics
    network_state['power'] = system_state['power_metrics']
    
    return jsonify(network_state)

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Fail a substation with cascading effects"""
    # Power system failure
    impact = integrated_system.simulate_substation_failure(substation)
    power_grid.trigger_failure('substation', substation)
    
    # Add to failed list
    system_state['failed_substations'].add(substation)
    
    # Traffic system impact
    if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
        affected_lights = 0
        for tl_id, tl in integrated_system.traffic_lights.items():
            if tl['substation'] == substation:
                sumo_sim.update_traffic_light_power(tl_id, False)
                affected_lights += 1
        
        impact['traffic_lights_failed'] = affected_lights
        print(f"⚡ Power failure: {affected_lights} traffic lights affected")
    
    return jsonify(impact)

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore a substation"""
    # Restore power
    success = integrated_system.restore_substation(substation)
    if success:
        power_grid.restore_component('substation', substation)
        system_state['failed_substations'].discard(substation)
        
        # Restore traffic lights in SUMO
        if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
            restored_lights = 0
            for tl_id, tl in integrated_system.traffic_lights.items():
                if tl['substation'] == substation:
                    sumo_sim.update_traffic_light_power(tl_id, True)
                    restored_lights += 1
            
            print(f"⚡ Power restored: {restored_lights} traffic lights back online")
    
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
        if success and not gui:
            # Start background loop for headless mode
            traffic_thread = threading.Thread(target=traffic_simulation_loop, daemon=True)
            traffic_thread.start()
        return jsonify({'success': success})
    
    return jsonify({'success': False, 'error': 'Already running or not initialized'})

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
        try:
            # Get edges and create emergency vehicle
            edges = traci.edge.getIDList()
            if len(edges) >= 2:
                import random
                veh_id = f"emergency_{system_state['simulation_time']}"
                route_id = f"emergency_route_{system_state['simulation_time']}"
                
                from_edge = random.choice(edges[:50])
                to_edge = random.choice(edges[-50:])
                
                traci.route.add(route_id, [from_edge, to_edge])
                traci.vehicle.add(veh_id, route_id, typeID='taxi')  # Use taxi as emergency
                traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
                traci.vehicle.setSpeedMode(veh_id, 0)
                
                return jsonify({'success': True, 'vehicle_id': veh_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'SUMO not running'})

@app.route('/api/sumo/add_traffic', methods=['POST'])
def add_traffic():
    """Add more vehicles to simulation"""
    if SUMO_AVAILABLE and sumo_sim and sumo_sim.running:
        try:
            num_vehicles = request.json.get('count', 50) if request.json else 50
            edges = traci.edge.getIDList()
            
            added = 0
            for i in range(num_vehicles):
                if len(edges) >= 2:
                    import random
                    veh_id = f"added_{system_state['simulation_time']}_{i}"
                    route_id = f"route_{veh_id}"
                    
                    from_edge = random.choice(edges)
                    to_edge = random.choice(edges)
                    
                    if from_edge != to_edge:
                        traci.route.add(route_id, [from_edge, to_edge])
                        vtype = random.choice(['car', 'taxi', 'bus', 'delivery'])
                        traci.vehicle.add(veh_id, route_id)
                        added += 1
            
            return jsonify({'success': True, 'vehicles_added': added})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'SUMO not running'})

# ============================================================
# HTML DASHBOARD
# ============================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Manhattan Power & Traffic - World Class System</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
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
            width: 420px;
            background: linear-gradient(135deg, rgba(10,10,20,0.98), rgba(20,20,40,0.95));
            border-radius: 20px;
            padding: 25px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(102,126,234,0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            z-index: 1000;
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
            font-size: 32px;
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
        
        .traffic-title {
            font-size: 14px;
            font-weight: 600;
            color: #00ff88;
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
            color: #00ff88;
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
            padding: 15px;
            background: linear-gradient(135deg, #00ff88, #00aa44);
            border: none;
            color: #000;
            border-radius: 12px;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
            font-size: 16px;
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
            gap: 10px;
            margin: 15px 0;
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
        
        .sumo-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
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
        
        .status-indicator.warning {
            background: #ffaa00;
        }
        
        .status-indicator.critical {
            background: #ff0000;
        }
        
        .mapboxgl-popup-content {
            background: rgba(20, 20, 30, 0.95) !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-size: 13px !important;
        }
        
        .mapboxgl-popup-content strong {
            color: #00ff88 !important;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="control-panel">
        <h1>Manhattan Power & Traffic</h1>
        <div style="font-size: 13px; color: rgba(255,255,255,0.5); margin-bottom: 20px;">
            Con Edison + NYC DOT + SUMO Integration
        </div>
        
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
                <div class="stat-value" id="load-mw" style="color: #0088ff;">0</div>
                <div class="stat-label">MW Load</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="substations" style="color: #ff88ff;">0</div>
                <div class="stat-label">Substations</div>
            </div>
        </div>
        
        <!-- SUMO Traffic Panel -->
        <div class="traffic-panel">
            <div class="traffic-title">🚗 SUMO Traffic Simulation</div>
            <div class="traffic-stats">
                <div class="traffic-item">
                    Vehicles: <span class="traffic-value" id="vehicle-count">0</span>
                </div>
                <div class="traffic-item">
                    Avg Speed: <span class="traffic-value" id="avg-speed">0</span> km/h
                </div>
                <div class="traffic-item">
                    CO₂: <span class="traffic-value" id="co2">0</span> g/s
                </div>
                <div class="traffic-item">
                    Status: <span class="traffic-value" id="sumo-status">Offline</span>
                </div>
            </div>
            
            <div class="sumo-controls">
                <button class="sumo-btn" onclick="startSUMO(true)">Start GUI</button>
                <button class="sumo-btn" onclick="startSUMO(false)">Start Headless</button>
                <button class="sumo-btn" onclick="stopSUMO()">Stop SUMO</button>
                <button class="sumo-btn" onclick="addTraffic()">Add Traffic</button>
                <button class="sumo-btn" onclick="injectEmergency()" style="background: linear-gradient(135deg, #ff0000, #cc0000);">
                    🚨 Emergency
                </button>
                <button class="sumo-btn" onclick="addTraffic(100)">+100 Cars</button>
            </div>
        </div>
        
        <!-- Substation Controls -->
        <div style="font-size: 14px; margin: 20px 0 10px; font-weight: 600;">
            Substation Control
        </div>
        <div class="substation-grid" id="substation-controls"></div>
        
        <button class="action-btn" onclick="restoreAll()">
            🔧 RESTORE ALL SYSTEMS
        </button>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <span class="status-indicator" id="power-indicator"></span>
            <span id="power-status">Power Grid Online</span>
        </div>
        <div class="status-item">
            <span class="status-indicator" id="traffic-indicator"></span>
            <span id="traffic-status">Traffic System</span>
        </div>
        <div class="status-item">
            <span id="time">00:00:00</span>
        </div>
    </div>
    
    <script>
        // Initialize Mapbox
        mapboxgl.accessToken = 'pk.eyJ1IjoibWFyb25veCIsImEiOiJjbWV1ODE5bHEwNGhoMmlvY2RleW51dWozIn0.FMrYdXLqnOwOEFi8qHSwxg';
        
        const map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/dark-v11',
            center: [-73.980, 40.758],
            zoom: 13.5,
            pitch: 45,
            bearing: -20
        });
        
        let systemState = null;
        let markers = [];
        let updateInterval = null;
        
        async function loadSystemState() {
            try {
                const response = await fetch('/api/system_state');
                systemState = await response.json();
                updateUI();
                renderMap();
            } catch (error) {
                console.error('Error loading system state:', error);
            }
        }
        
        function updateUI() {
            if (!systemState) return;
            
            const stats = systemState.statistics;
            document.getElementById('traffic-lights').textContent = stats.total_traffic_lights;
            document.getElementById('powered-lights').textContent = stats.powered_traffic_lights;
            document.getElementById('load-mw').textContent = Math.round(stats.total_load_mw);
            document.getElementById('substations').textContent = 
                `${stats.operational_substations}/${stats.total_substations}`;
            
            // Update SUMO stats
            if (systemState.traffic) {
                document.getElementById('vehicle-count').textContent = systemState.traffic.vehicles;
                document.getElementById('avg-speed').textContent = 
                    Math.round(systemState.traffic.avg_speed_kmh);
                document.getElementById('co2').textContent = 
                    Math.round(systemState.traffic.co2_emissions);
                document.getElementById('sumo-status').textContent = 
                    systemState.traffic.simulation_active ? 'Running' : 'Offline';
                
                const trafficIndicator = document.getElementById('traffic-indicator');
                if (systemState.traffic.simulation_active) {
                    trafficIndicator.style.background = '#00ff88';
                    document.getElementById('traffic-status').textContent = 
                        `Traffic: ${systemState.traffic.vehicles} vehicles`;
                } else {
                    trafficIndicator.style.background = '#666';
                    document.getElementById('traffic-status').textContent = 'Traffic: Offline';
                }
            }
            
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
            
            // Update power status
            const failures = stats.total_substations - stats.operational_substations;
            const powerIndicator = document.getElementById('power-indicator');
            if (failures === 0) {
                powerIndicator.className = 'status-indicator';
                document.getElementById('power-status').textContent = 'Power Grid Online';
            } else {
                powerIndicator.className = 'status-indicator critical';
                document.getElementById('power-status').textContent = 
                    `Power: ${failures} Failure${failures > 1 ? 's' : ''}`;
            }
        }
        
        function renderMap() {
            if (!systemState) return;
            
            // Clear existing markers
            markers.forEach(m => m.remove());
            markers = [];
            
            // Add substations
            systemState.substations.forEach(sub => {
                const el = document.createElement('div');
                el.style.width = '30px';
                el.style.height = '30px';
                el.style.background = sub.operational ? '#ff0066' : '#ff0000';
                el.style.borderRadius = '50%';
                el.style.border = '3px solid #fff';
                el.style.boxShadow = sub.operational ? 
                    '0 0 25px rgba(255,0,102,0.9)' : '0 0 25px rgba(255,0,0,0.9)';
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([sub.lon, sub.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(`
                        <strong>${sub.name}</strong><br>
                        ${sub.capacity_mva} MVA<br>
                        Load: ${sub.load_mw.toFixed(1)} MW<br>
                        Status: ${sub.operational ? '⚡ Online' : '⚠️ FAILED'}
                    `))
                    .addTo(map);
                
                markers.push(marker);
            });
            
            // Add traffic lights layer
            if (!map.getSource('traffic-lights')) {
                const features = systemState.traffic_lights.map(tl => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [tl.lon, tl.lat]
                    },
                    properties: {
                        powered: tl.powered,
                        color: tl.color
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
                        'circle-radius': 3,
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 0.9
                    }
                });
            }
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
            } else {
                alert('Failed to start SUMO: ' + (result.error || 'Unknown error'));
            }
        }
        
        async function stopSUMO() {
            await fetch('/api/sumo/stop', { method: 'POST' });
            alert('SUMO stopped');
        }
        
        async function addTraffic(count = 50) {
            const response = await fetch('/api/sumo/add_traffic', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({count: count})
            });
            const result = await response.json();
            if (result.success) {
                alert(`Added ${result.vehicles_added} vehicles`);
            }
        }
        
        async function injectEmergency() {
            const response = await fetch('/api/sumo/inject_emergency', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                alert('Emergency vehicle dispatched!');
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
            updateInterval = setInterval(loadSystemState, 3000);
            setInterval(updateTime, 1000);
            updateTime();
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
    print(f"Substations: {len(integrated_system.substations)}")
    print(f"Traffic Lights: {len(integrated_system.traffic_lights)}")
    print(f"EV Stations: {len(integrated_system.ev_stations)}")
    print(f"SUMO Available: {'✅ Yes' if SUMO_AVAILABLE else '❌ No'}")
    
    if SUMO_AVAILABLE and sumo_sim:
        if os.path.exists(sumo_sim.net_file):
            try:
                net = sumolib.net.readNet(sumo_sim.net_file)
                print(f"SUMO Network: {len(net.getEdges())} streets, {len(net.getTrafficLights())} traffic lights")
            except:
                pass
    
    print("="*60)
    
    # Start simulation threads
    power_thread = threading.Thread(target=power_simulation_loop, daemon=True)
    power_thread.start()
    
    if SUMO_AVAILABLE and sumo_sim:
        print("\n💡 TIP: Click 'Start GUI' or 'Start Headless' in the dashboard to begin traffic simulation")
    
    print(f"\n🌐 Dashboard: http://localhost:5000")
    print("="*60 + "\n")
    
    app.run(debug=False, port=5000)