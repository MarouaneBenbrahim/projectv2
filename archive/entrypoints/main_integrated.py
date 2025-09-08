"""
Manhattan Complete Integrated Application
World-Class Power Grid + Traffic + Vehicle Simulation
Real-time web interface with live vehicle tracking
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import threading
import time
import json
from datetime import datetime

# Import all systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from integrated_simulation_fixed import FixedIntegratedSimulation

app = Flask(__name__)
CORS(app)

# Global systems
power_grid = None
integrated_backend = None
simulation_system = None
simulation_thread = None
simulation_running = False

# Initialize everything
def initialize_systems():
    """Initialize all systems"""
    global power_grid, integrated_backend, simulation_system
    
    print("\n" + "=" * 60)
    print("INITIALIZING MANHATTAN INTEGRATED SYSTEM")
    print("=" * 60)
    
    # Power grid
    print("Starting PyPSA power grid...")
    power_grid = ManhattanPowerGrid()
    
    # Integrated backend
    print("Loading integrated infrastructure...")
    integrated_backend = ManhattanIntegratedSystem(power_grid)
    
    # Vehicle simulation - USING FIXED VERSION
    print("Initializing vehicle simulation...")
    simulation_system = FixedIntegratedSimulation(power_grid, integrated_backend)
    
    print("✓ All systems initialized")
    print("=" * 60)

# Run simulation in background
def run_vehicle_simulation():
    """Background thread for vehicle simulation"""
    global simulation_running
    
    simulation_running = True
    simulation_system.start_integrated_simulation(num_vehicles=10)
    simulation_running = False

# Initialize on startup
initialize_systems()

# Start vehicle simulation
simulation_thread = threading.Thread(target=run_vehicle_simulation, daemon=True)
simulation_thread.start()

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Manhattan Integrated Power & Traffic System</title>
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
            border: 1px solid rgba(100,200,255,0.2);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            z-index: 1000;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(90deg, #00ff88, #00aaff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        
        .subtitle {
            font-size: 12px;
            color: rgba(255,255,255,0.5);
            margin-bottom: 20px;
        }
        
        .section {
            margin: 20px 0;
            padding: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .section-title {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #00ff88;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .stat-box {
            background: rgba(255,255,255,0.05);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .stat-label {
            font-size: 10px;
            color: rgba(255,255,255,0.5);
            text-transform: uppercase;
        }
        
        .vehicle-list {
            max-height: 200px;
            overflow-y: auto;
            font-size: 12px;
        }
        
        .vehicle-item {
            display: flex;
            justify-content: space-between;
            padding: 5px;
            margin: 2px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
        }
        
        .vehicle-ev {
            background: rgba(0,255,0,0.1);
        }
        
        .substation-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        
        .sub-btn {
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            border-radius: 8px;
            cursor: pointer;
            font-size: 11px;
            transition: all 0.3s;
            text-align: center;
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
        
        .action-btn {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            background: linear-gradient(135deg, #00ff88, #00cc66);
            border: none;
            border-radius: 10px;
            color: #000;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,255,136,0.3);
        }
        
        .alert {
            padding: 10px;
            margin: 10px 0;
            border-radius: 8px;
            font-size: 12px;
        }
        
        .alert-warning {
            background: rgba(255,170,0,0.2);
            border: 1px solid rgba(255,170,0,0.5);
        }
        
        .alert-danger {
            background: rgba(255,0,0,0.2);
            border: 1px solid rgba(255,0,0,0.5);
        }
        
        .status-bar {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(10,10,20,0.95);
            padding: 15px 30px;
            border-radius: 30px;
            border: 1px solid rgba(100,200,255,0.2);
            display: flex;
            gap: 30px;
            align-items: center;
            z-index: 1000;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
        }
        
        .status-dot.warning {
            background: #ffaa00;
        }
        
        .status-dot.danger {
            background: #ff0000;
        }
        
        /* Vehicle markers on map */
        .vehicle-marker {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 2px solid #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: bold;
            color: #fff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }
        
        .vehicle-marker.ev {
            background: #00ff00;
        }
        
        .vehicle-marker.car {
            background: #888888;
        }
        
        .vehicle-marker.taxi {
            background: #ffff00;
            color: #000;
        }
        
        .charging-station-marker {
            width: 30px;
            height: 30px;
            background: #00aaff;
            border-radius: 6px;
            border: 2px solid #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            color: #fff;
            box-shadow: 0 4px 12px rgba(0,170,255,0.5);
        }
        
        .charging-station-marker.offline {
            background: #666;
            box-shadow: none;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="control-panel">
        <h1>Manhattan Integrated System</h1>
        <div class="subtitle">Power Grid + Traffic + Vehicles | Real-time Simulation</div>
        
        <!-- System Status -->
        <div class="section">
            <div class="section-title">System Status</div>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value" id="total-vehicles">0</div>
                    <div class="stat-label">Vehicles</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="evs-charging">0</div>
                    <div class="stat-label">EVs Charging</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="traffic-lights">0</div>
                    <div class="stat-label">Traffic Lights</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="grid-load">0</div>
                    <div class="stat-label">MW Load</div>
                </div>
            </div>
        </div>
        
        <!-- Vehicle Status -->
        <div class="section">
            <div class="section-title">Active Vehicles</div>
            <div class="vehicle-list" id="vehicle-list">
                <!-- Populated by JavaScript -->
            </div>
        </div>
        
        <!-- Substation Control -->
        <div class="section">
            <div class="section-title">Substation Control</div>
            <div class="substation-grid" id="substation-controls">
                <!-- Populated by JavaScript -->
            </div>
        </div>
        
        <!-- Actions -->
        <button class="action-btn" onclick="testFailure()">
            ⚡ Test Times Square Failure
        </button>
        <button class="action-btn" onclick="restoreAll()">
            🔧 Restore All Systems
        </button>
        
        <!-- Alerts -->
        <div id="alerts"></div>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <span class="status-dot" id="system-status"></span>
            <span id="status-text">System Online</span>
        </div>
        <div class="status-item">
            <span id="sim-step">0</span> steps
        </div>
        <div class="status-item">
            <span id="avg-wait">0</span>s avg wait
        </div>
        <div class="status-item">
            <span id="reroutes">0</span> reroutes
        </div>
    </div>
    
    <script>
        // Initialize map
        mapboxgl.accessToken = 'pk.eyJ1IjoibWFyb25veCIsImEiOiJjbWV1ODE5bHEwNGhoMmlvY2RleW51dWozIn0.FMrYdXLqnOwOEFi8qHSwxg';
        
        const map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/dark-v11',
            center: [-73.980, 40.758],
            zoom: 13.5,
            pitch: 30
        });
        
        // State
        let systemState = null;
        let vehicleMarkers = {};
        let stationMarkers = {};
        
        // Load initial state
        async function loadState() {
            try {
                // Get infrastructure state
                const infraResponse = await fetch('/api/network_state');
                const infraState = await infraResponse.json();
                
                // Get simulation state
                const simResponse = await fetch('/api/simulation_state');
                const simState = await simResponse.json();
                
                // Update UI
                updateInfrastructure(infraState);
                updateVehicles(simState);
                updateMetrics(simState);
                
            } catch (error) {
                console.error('Error loading state:', error);
            }
        }
        
        function updateInfrastructure(state) {
            // Update substations
            const controls = document.getElementById('substation-controls');
            controls.innerHTML = '';
            
            state.substations.forEach(sub => {
                const btn = document.createElement('button');
                btn.className = 'sub-btn';
                if (!sub.operational) {
                    btn.classList.add('failed');
                }
                btn.textContent = sub.name.replace(/_/g, ' ');
                btn.onclick = () => toggleSubstation(sub.name);
                controls.appendChild(btn);
            });
            
            // Draw traffic lights
            if (state.traffic_lights && state.traffic_lights.length > 0) {
                const features = state.traffic_lights.map(tl => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [tl.lon, tl.lat]
                    },
                    properties: {
                        powered: tl.powered,
                        color: tl.color || (tl.powered ? '#00ff00' : '#000000')
                    }
                }));
                
                // Add/update source
                if (map.getSource('traffic-lights')) {
                    map.getSource('traffic-lights').setData({
                        type: 'FeatureCollection',
                        features: features
                    });
                } else {
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
                            'circle-radius': 3,
                            'circle-color': ['get', 'color'],
                            'circle-opacity': 0.8
                        }
                    });
                }
            }
            
            // Update stats
            document.getElementById('traffic-lights').textContent = 
                state.statistics.powered_traffic_lights + '/' + state.statistics.total_traffic_lights;
        }
        
        function updateVehicles(state) {
            // Clear old markers
            Object.values(vehicleMarkers).forEach(m => m.remove());
            vehicleMarkers = {};
            
            // Update vehicle list
            const list = document.getElementById('vehicle-list');
            list.innerHTML = '';
            
            // Add vehicles to map and list
            state.vehicles.forEach(vehicle => {
                // Create marker
                const el = document.createElement('div');
                el.className = 'vehicle-marker';
                
                if (vehicle.type.includes('ev')) {
                    el.classList.add('ev');
                    el.innerHTML = '⚡';
                } else if (vehicle.type === 'taxi') {
                    el.classList.add('taxi');
                    el.innerHTML = 'T';
                } else {
                    el.classList.add('car');
                    el.innerHTML = 'C';
                }
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([vehicle.lon, vehicle.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(
                        `<b>${vehicle.id}</b><br>
                        Type: ${vehicle.type}<br>
                        Speed: ${vehicle.speed.toFixed(1)} km/h<br>
                        ${vehicle.battery !== null ? `Battery: ${vehicle.battery.toFixed(1)}%` : ''}
                        State: ${vehicle.state}`
                    ))
                    .addTo(map);
                
                vehicleMarkers[vehicle.id] = marker;
                
                // Add to list
                const item = document.createElement('div');
                item.className = 'vehicle-item';
                if (vehicle.type.includes('ev')) {
                    item.classList.add('vehicle-ev');
                }
                item.innerHTML = `
                    <span>${vehicle.id}</span>
                    <span>${vehicle.speed.toFixed(0)} km/h</span>
                    ${vehicle.battery !== null ? `<span>${vehicle.battery.toFixed(0)}%</span>` : ''}
                `;
                list.appendChild(item);
            });
            
            // Update charging stations
            Object.values(stationMarkers).forEach(m => m.remove());
            stationMarkers = {};
            
            state.charging_stations.forEach(station => {
                const el = document.createElement('div');
                el.className = 'charging-station-marker';
                if (!station.operational) {
                    el.classList.add('offline');
                }
                el.innerHTML = '⚡';
                
                const marker = new mapboxgl.Marker(el)
                    .setLngLat([station.lon, station.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(
                        `<b>${station.name}</b><br>
                        Status: ${station.operational ? 'Online' : 'OFFLINE'}<br>
                        Charging: ${station.vehicles_charging}/${station.capacity}<br>
                        Load: ${station.grid_load_mw.toFixed(2)} MW`
                    ))
                    .addTo(map);
                
                stationMarkers[station.id] = marker;
            });
            
            // Update stats
            document.getElementById('total-vehicles').textContent = state.vehicles.length;
            const evs_charging = state.charging_stations.reduce((sum, s) => sum + s.vehicles_charging, 0);
            document.getElementById('evs-charging').textContent = evs_charging;
        }
        
        function updateMetrics(state) {
            document.getElementById('sim-step').textContent = state.simulation_step;
            document.getElementById('avg-wait').textContent = state.metrics.avg_waiting_time.toFixed(1);
            document.getElementById('reroutes').textContent = state.metrics.reroutes_performed;
            document.getElementById('grid-load').textContent = state.metrics.grid_load_mw.toFixed(1);
            
            // Update status
            if (state.failed_substations.length > 0) {
                document.getElementById('system-status').className = 'status-dot danger';
                document.getElementById('status-text').textContent = 
                    `${state.failed_substations.length} Failures`;
                
                // Show alert
                const alerts = document.getElementById('alerts');
                alerts.innerHTML = `
                    <div class="alert alert-danger">
                        ⚠️ Failed: ${state.failed_substations.join(', ')}
                    </div>
                `;
            } else {
                document.getElementById('system-status').className = 'status-dot';
                document.getElementById('status-text').textContent = 'System Online';
                document.getElementById('alerts').innerHTML = '';
            }
        }
        
        async function toggleSubstation(name) {
            const response = await fetch(`/api/fail/${name}`, { method: 'POST' });
            const result = await response.json();
            console.log('Substation toggle:', result);
        }
        
        async function testFailure() {
            const response = await fetch('/api/test_failure', { method: 'POST' });
            const result = await response.json();
            
            // Show alert
            const alerts = document.getElementById('alerts');
            alerts.innerHTML = `
                <div class="alert alert-warning">
                    ⚡ Triggered Times Square failure - watch vehicles reroute!
                </div>
            `;
        }
        
        async function restoreAll() {
            const response = await fetch('/api/restore_all', { method: 'POST' });
            const result = await response.json();
            
            const alerts = document.getElementById('alerts');
            alerts.innerHTML = `
                <div class="alert alert-success">
                    ✅ All systems restored
                </div>
            `;
        }
        
        // Initialize map
        map.on('load', () => {
            loadState();
            
            // Update every 2 seconds
            setInterval(loadState, 2000);
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/network_state')
def get_network_state():
    """Get infrastructure state"""
    return jsonify(integrated_backend.get_network_state())

@app.route('/api/simulation_state')
def get_simulation_state():
    """Get vehicle simulation state"""
    if simulation_system:
        return jsonify(simulation_system.get_real_time_state())
    return jsonify({
        'simulation_step': 0,
        'vehicles': [],
        'charging_stations': [],
        'metrics': {},
        'failed_substations': []
    })

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Trigger substation failure"""
    # Fail in all systems
    integrated_backend.simulate_substation_failure(substation)
    power_grid.trigger_failure('substation', substation)
    
    if simulation_system:
        simulation_system.trigger_substation_failure(substation)
    
    return jsonify({
        'success': True,
        'substation': substation,
        'message': f'Failed {substation} - vehicles rerouting'
    })

@app.route('/api/test_failure', methods=['POST'])
def test_failure():
    """Test Times Square failure"""
    return fail_substation('Times Square')

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore substation"""
    integrated_backend.restore_substation(substation)
    power_grid.restore_component('substation', substation)
    
    if simulation_system:
        simulation_system.restore_substation(substation)
    
    return jsonify({
        'success': True,
        'substation': substation
    })

@app.route('/api/restore_all', methods=['POST'])
def restore_all():
    """Restore all systems"""
    for sub_name in integrated_backend.substations.keys():
        integrated_backend.restore_substation(sub_name)
        power_grid.restore_component('substation', sub_name)
        
        if simulation_system:
            simulation_system.restore_substation(sub_name)
    
    return jsonify({
        'success': True,
        'message': 'All systems restored'
    })

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("MANHATTAN INTEGRATED SYSTEM - WORLD CLASS")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ PyPSA Power Grid")
    print("  ✓ Traffic Light Control")
    print("  ✓ EV Charging Stations")
    print("  ✓ SUMO Vehicle Simulation (Headless)")
    print("  ✓ Real-time Web Interface")
    print("  ✓ Cascading Failure Simulation")
    print("  ✓ Intelligent Vehicle Rerouting")
    print("\n" + "=" * 60)
    print("Starting server at http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, port=5000)