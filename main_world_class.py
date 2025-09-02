"""
Manhattan Power Grid - World Class Main Application with SUMO
COMPLETE INTEGRATION: Power + Traffic + EVs + Real-time Visualization
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
import asyncio

# Import our systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from manhattan_sumo_integration import (
    WorldClassTrafficSimulation, 
    integrate_sumo_with_power_grid,
    IntegratedWebSocketServer
)

app = Flask(__name__)
CORS(app)

# Initialize systems
print("=" * 60)
print("MANHATTAN POWER GRID - WORLD CLASS SYSTEM")
print("Professional Integration: Con Edison + NYC DOT + SUMO")
print("=" * 60)

# Initialize power grid
print("Initializing PyPSA power grid...")
power_grid = ManhattanPowerGrid()

# Initialize integrated system
print("Loading integrated distribution network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# Initialize SUMO traffic simulation
print("Initializing SUMO traffic simulation...")
traffic_sim = integrate_sumo_with_power_grid(integrated_system, power_grid)

# System state
system_running = True
current_time = 0

def simulation_loop():
    """Background simulation loop"""
    global current_time
    
    while system_running:
        try:
            # Update traffic light phases every 2 seconds
            if current_time % 2 == 0:
                integrated_system.update_traffic_light_phases()
                
                # Sync with SUMO if available
                if traffic_sim and traffic_sim.running:
                    # Traffic lights are synced inside SUMO loop
                    pass
            
            # Run power flow every 30 seconds
            if current_time % 30 == 0:
                power_grid.run_power_flow("dc")
            
            current_time += 1
            time.sleep(1)
            
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)

# Start simulation thread
sim_thread = threading.Thread(target=simulation_loop, daemon=True)
sim_thread.start()

# Enhanced HTML Template with vehicle visualization
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manhattan Power Grid - World Class System with Traffic</title>
    
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
        
        /* Popup styling */
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
        
        .mapboxgl-popup-tip {
            border-top-color: rgba(20, 20, 30, 0.95) !important;
        }
        
        /* Control Panel */
        .control-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 420px;
            max-height: 90vh;
            overflow-y: auto;
            background: linear-gradient(135deg, rgba(15,15,25,0.98), rgba(25,25,45,0.95));
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(100,200,255,0.2);
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            z-index: 1000;
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
        
        /* Traffic Section */
        .traffic-section {
            background: rgba(0,170,255,0.05);
            border: 1px solid rgba(0,170,255,0.2);
            border-radius: 10px;
            padding: 12px;
            margin: 16px 0;
        }
        
        .traffic-title {
            font-size: 14px;
            font-weight: 600;
            color: #00aaff;
            margin-bottom: 10px;
        }
        
        .traffic-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        
        .traffic-stat {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            font-size: 12px;
        }
        
        .traffic-stat-value {
            font-weight: 600;
            color: #00aaff;
        }
        
        /* Vehicle indicator */
        .vehicle-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 2px;
            margin-right: 4px;
        }
        
        .vehicle-sedan { background: #ffff00; }
        .vehicle-ev { background: #00ff00; }
        .vehicle-bus { background: #ff8800; }
        .vehicle-charging { background: #00ff00; animation: pulse 1s infinite; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Substation Controls */
        .section-title {
            font-size: 14px;
            font-weight: 600;
            margin: 20px 0 12px 0;
            color: rgba(255,255,255,0.8);
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
            font-size: 12px;
            transition: all 0.3s ease;
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
        
        /* Action Buttons */
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
            transition: all 0.3s ease;
        }
        
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,255,136,0.3);
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
            gap: 30px;
            align-items: center;
            z-index: 1000;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }
        
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
        }
        
        .status-indicator.warning {
            background: #ffaa00;
        }
        
        .status-indicator.critical {
            background: #ff0000;
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
        
        /* Connection status */
        .connection-status {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(15,15,25,0.95);
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid rgba(100,200,255,0.2);
            font-size: 12px;
            z-index: 1000;
        }
        
        .connection-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }
        
        .connected { background: #00ff88; }
        .disconnected { background: #ff0000; }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Connection Status -->
    <div class="connection-status">
        <span class="connection-dot disconnected" id="ws-status"></span>
        <span id="ws-text">Connecting...</span>
    </div>
    
    <!-- Control Panel -->
    <div class="control-panel">
        <h1>Manhattan Power Grid</h1>
        <div class="subtitle">Integrated Power + Traffic + EV System</div>
        
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
        
        <!-- Traffic Section -->
        <div class="traffic-section">
            <div class="traffic-title">🚗 Live Traffic</div>
            <div class="traffic-stats">
                <div class="traffic-stat">
                    <span><span class="vehicle-indicator vehicle-sedan"></span>Vehicles</span>
                    <span class="traffic-stat-value" id="active-vehicles">0</span>
                </div>
                <div class="traffic-stat">
                    <span><span class="vehicle-indicator vehicle-ev"></span>EVs</span>
                    <span class="traffic-stat-value" id="active-evs">0</span>
                </div>
                <div class="traffic-stat">
                    <span><span class="vehicle-indicator vehicle-charging"></span>Charging</span>
                    <span class="traffic-stat-value" id="evs-charging">0</span>
                </div>
                <div class="traffic-stat">
                    <span>Avg Speed</span>
                    <span class="traffic-stat-value" id="avg-speed">0 mph</span>
                </div>
            </div>
        </div>
        
        <!-- Substation Controls -->
        <div class="section-title">Substation Control</div>
        <div class="substation-grid" id="substation-controls"></div>
        
        <!-- Action Buttons -->
        <button class="action-btn" onclick="restoreAll()">
            🔧 Restore All Systems
        </button>
        
        <button class="action-btn" style="background: linear-gradient(135deg, #00aaff, #0088dd);" onclick="toggleTraffic()">
            🚦 Toggle Traffic Simulation
        </button>
        
        <!-- Layer Controls -->
        <div class="layer-controls">
            <div class="section-title">Visualization Layers</div>
            
            <div class="layer-item">
                <span>🚗 Vehicles</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-vehicles" onchange="toggleLayer('vehicles')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>🚦 Traffic Lights</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-lights" onchange="toggleLayer('lights')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>⚡ EV Stations</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-ev" onchange="toggleLayer('ev')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>🔌 Power Cables</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-cables" onchange="toggleLayer('cables')">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>🏭 Substations</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-substations" onchange="toggleLayer('substations')">
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
            <span id="total-load">0</span> MW
        </div>
        <div class="status-item">
            <span id="failures">0</span> Failures
        </div>
        <div class="status-item">
            <span id="co2">0</span> kg CO₂/h
        </div>
        <div class="status-item">
            <span id="time">00:00</span>
        </div>
    </div>
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-title">System Components</div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ffff00;"></div>
            <span>Regular Vehicles</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00ff00;"></div>
            <span>Electric Vehicles</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff8800;"></div>
            <span>Buses</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00ff00; animation: pulse 1s infinite;"></div>
            <span>Charging EVs</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff0066;"></div>
            <span>Substations</span>
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
        let vehicles = {};
        let vehicleMarkers = {};
        let markers = [];
        let layers = {
            vehicles: true,
            lights: true,
            ev: true,
            cables: true,
            substations: true
        };
        let ws = null;
        let wsConnected = false;
        let trafficEnabled = true;
        
        // WebSocket connection for real-time vehicle updates
        function connectWebSocket() {
            ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                wsConnected = true;
                document.getElementById('ws-status').className = 'connection-dot connected';
                document.getElementById('ws-text').textContent = 'SUMO Connected';
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'traffic_update') {
                    updateVehicles(data.vehicles);
                    updateTrafficStats(data.statistics);
                }
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                wsConnected = false;
                document.getElementById('ws-status').className = 'connection-dot disconnected';
                document.getElementById('ws-text').textContent = 'SUMO Offline';
                
                // Retry connection after 5 seconds
                setTimeout(connectWebSocket, 5000);
            };
        }
        
        // Update vehicles on map
        function updateVehicles(vehicleData) {
            if (!layers.vehicles) return;
            
            const currentVehicles = new Set();
            
            vehicleData.forEach(vehicle => {
                currentVehicles.add(vehicle.id);
                
                if (!vehicleMarkers[vehicle.id]) {
                    // Create new vehicle marker
                    const el = document.createElement('div');
                    el.style.width = '8px';
                    el.style.height = '8px';
                    el.style.borderRadius = '2px';
                    el.style.border = '1px solid rgba(255,255,255,0.5)';
                    
                    // Set color based on vehicle type and state
                    if (vehicle.charging) {
                        el.style.background = '#00ff00';
                        el.style.animation = 'pulse 1s infinite';
                        el.style.boxShadow = '0 0 10px rgba(0,255,0,0.8)';
                    } else if (vehicle.is_ev) {
                        if (vehicle.battery_soc < 0.2) {
                            el.style.background = '#ff8800';  // Orange for low battery
                        } else {
                            el.style.background = '#00cccc';  // Cyan for EV
                        }
                    } else if (vehicle.type === 'bus') {
                        el.style.background = '#ff8800';
                        el.style.width = '12px';
                        el.style.height = '6px';
                    } else if (vehicle.type === 'taxi') {
                        el.style.background = '#ffff00';
                    } else {
                        el.style.background = '#ffffff';
                    }
                    
                    const marker = new mapboxgl.Marker(el)
                        .setLngLat([vehicle.lon, vehicle.lat])
                        .addTo(map);
                    
                    vehicleMarkers[vehicle.id] = marker;
                } else {
                    // Update existing marker position
                    vehicleMarkers[vehicle.id].setLngLat([vehicle.lon, vehicle.lat]);
                    
                    // Update appearance if charging status changed
                    const el = vehicleMarkers[vehicle.id].getElement();
                    if (vehicle.charging) {
                        el.style.background = '#00ff00';
                        el.style.animation = 'pulse 1s infinite';
                    } else if (vehicle.is_ev && vehicle.battery_soc < 0.2) {
                        el.style.background = '#ff8800';
                        el.style.animation = '';
                    }
                }
            });
            
            // Remove vehicles that left
            Object.keys(vehicleMarkers).forEach(id => {
                if (!currentVehicles.has(id)) {
                    vehicleMarkers[id].remove();
                    delete vehicleMarkers[id];
                }
            });
        }
        
        // Update traffic statistics
        function updateTrafficStats(stats) {
            document.getElementById('active-vehicles').textContent = stats.active_vehicles || 0;
            document.getElementById('active-evs').textContent = 
                Math.floor((stats.active_vehicles || 0) * 0.3);  // 30% EVs
            document.getElementById('evs-charging').textContent = stats.evs_charging || 0;
            document.getElementById('avg-speed').textContent = 
                Math.round(stats.avg_speed_mph || 0) + ' mph';
            document.getElementById('co2').textContent = 
                Math.round(stats.co2_emissions_kg || 0);
        }
        
        // Load network state
        async function loadNetworkState(forceRedraw = false) {
            try {
                const response = await fetch('/api/network_state');
                networkState = await response.json();
                updateUI();
                
                if (forceRedraw) {
                    renderNetwork();
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
            
            // Update substation controls
            const controls = document.getElementById('substation-controls');
            controls.innerHTML = '';
            
            networkState.substations.forEach(sub => {
                const btn = document.createElement('button');
                btn.className = 'sub-btn';
                if (!sub.operational) {
                    btn.classList.add('failed');
                }
                btn.textContent = sub.name.replace(/_/g, ' ');
                btn.onclick = () => toggleSubstation(sub.name);
                controls.appendChild(btn);
            });
            
            // Update status
            const failures = stats.total_substations - stats.operational_substations;
            document.getElementById('failures').textContent = failures;
            
            const indicator = document.getElementById('system-indicator');
            const status = document.getElementById('system-status');
            
            if (failures === 0) {
                indicator.className = 'status-indicator';
                status.textContent = 'System Online';
            } else if (failures <= 2) {
                indicator.className = 'status-indicator warning';
                status.textContent = `${failures} Substation${failures > 1 ? 's' : ''} Failed`;
            } else {
                indicator.className = 'status-indicator critical';
                status.textContent = 'Critical Failures';
            }
            
            document.getElementById('total-load').textContent = Math.round(stats.total_load_mw);
        }
        
        // Render network on map
        function renderNetwork() {
            if (!networkState) return;
            
            // Clear existing markers
            markers.forEach(m => m.remove());
            markers = [];
            
            // Add substations
            if (layers.substations) {
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
                    el.style.zIndex = '100';
                    
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
            }
            
            // Add cables
            if (layers.cables && networkState.cables) {
                // Remove old cable layers
                ['primary-cables', 'secondary-cables'].forEach(layerId => {
                    if (map.getLayer(layerId)) map.removeLayer(layerId);
                    if (map.getSource(layerId)) map.removeSource(layerId);
                });
                
                // Add primary cables
                if (networkState.cables.primary) {
                    const features = networkState.cables.primary
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
                    
                    if (features.length > 0) {
                        map.addSource('primary-cables', {
                            type: 'geojson',
                            data: {
                                type: 'FeatureCollection',
                                features: features
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
                
                // Add secondary cables (limited for performance)
                if (networkState.cables.secondary) {
                    const features = networkState.cables.secondary
                        .slice(0, 100)  // Limit to first 100
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
                    
                    if (features.length > 0) {
                        map.addSource('secondary-cables', {
                            type: 'geojson',
                            data: {
                                type: 'FeatureCollection',
                                features: features
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
                                'line-opacity': 0.3
                            }
                        });
                    }
                }
            }
            
            // Add traffic lights
            if (layers.lights && networkState.traffic_lights) {
                if (map.getLayer('traffic-lights')) map.removeLayer('traffic-lights');
                if (map.getSource('traffic-lights')) map.removeSource('traffic-lights');
                
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
                            16, 4
                        ],
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 0.9,
                        'circle-stroke-width': 0.5,
                        'circle-stroke-color': '#ffffff',
                        'circle-stroke-opacity': 0.3
                    }
                });
            }
            
            // Add EV stations
            if (layers.ev && networkState.ev_stations) {
                networkState.ev_stations.forEach(ev => {
                    const el = document.createElement('div');
                    el.style.width = '24px';
                    el.style.height = '24px';
                    el.style.background = ev.operational ? 
                        'linear-gradient(135deg, #00aaff 0%, #0088dd 100%)' : 
                        '#666';
                    el.style.borderRadius = '6px';
                    el.style.border = '2px solid #fff';
                    el.style.display = 'flex';
                    el.style.alignItems = 'center';
                    el.style.justifyContent = 'center';
                    el.style.fontSize = '14px';
                    el.style.fontWeight = 'bold';
                    el.style.color = '#fff';
                    el.style.boxShadow = ev.operational ? 
                        '0 2px 10px rgba(0,170,255,0.5)' : 
                        '0 2px 5px rgba(0,0,0,0.3)';
                    el.innerHTML = '⚡';
                    
                    const marker = new mapboxgl.Marker(el)
                        .setLngLat([ev.lon, ev.lat])
                        .setPopup(new mapboxgl.Popup({offset: 25}).setHTML(`
                            <strong>${ev.name}</strong><br>
                            Chargers: ${ev.chargers}<br>
                            Substation: ${ev.substation}<br>
                            Status: <span style="color: ${ev.operational ? '#00ff88' : '#ff0000'}">
                                ${ev.operational ? '✅ Online' : '❌ Offline'}
                            </span>
                        `))
                        .addTo(map);
                    
                    markers.push(marker);
                });
            }
        }
        
        // Toggle substation
        async function toggleSubstation(name) {
            const sub = networkState.substations.find(s => s.name === name);
            
            if (sub.operational) {
                await fetch(`/api/fail/${name}`, { method: 'POST' });
            } else {
                await fetch(`/api/restore/${name}`, { method: 'POST' });
            }
            
            await loadNetworkState(true);
        }
        
        // Restore all
        async function restoreAll() {
            await fetch('/api/restore_all', { method: 'POST' });
            await loadNetworkState(true);
        }
        
        // Toggle traffic simulation
        async function toggleTraffic() {
            trafficEnabled = !trafficEnabled;
            if (trafficEnabled) {
                await fetch('/api/start_traffic', { method: 'POST' });
            } else {
                await fetch('/api/stop_traffic', { method: 'POST' });
            }
        }
        
        // Toggle layer
        function toggleLayer(layer) {
            layers[layer] = !layers[layer];
            
            if (layer === 'vehicles') {
                // Show/hide vehicle markers
                Object.values(vehicleMarkers).forEach(marker => {
                    marker.getElement().style.display = layers[layer] ? 'block' : 'none';
                });
            } else if (layer === 'lights' && map.getLayer('traffic-lights')) {
                map.setLayoutProperty('traffic-lights', 'visibility', layers[layer] ? 'visible' : 'none');
            } else if (layer === 'cables') {
                ['primary-cables', 'secondary-cables'].forEach(layerId => {
                    if (map.getLayer(layerId)) {
                        map.setLayoutProperty(layerId, 'visibility', layers[layer] ? 'visible' : 'none');
                    }
                });
            } else {
                renderNetwork();
            }
        }
        
        // Update time
        function updateTime() {
            const now = new Date();
            document.getElementById('time').textContent = 
                now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }
        
        // Initialize
        map.on('load', () => {
            loadNetworkState(true);
            connectWebSocket();
            
            // Update network state periodically
            setInterval(() => loadNetworkState(false), 5000);
            
            setInterval(updateTime, 1000);
            updateTime();
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/network_state')
def get_network_state():
    """Get complete network state"""
    return jsonify(integrated_system.get_network_state())

@app.route('/api/traffic_state')
def get_traffic_state():
    """Get traffic simulation state"""
    if traffic_sim and traffic_sim.running:
        return jsonify({
            'vehicles': traffic_sim.get_vehicle_states(),
            'statistics': traffic_sim.get_statistics()
        })
    return jsonify({'vehicles': [], 'statistics': {}})

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Trigger substation failure - affects both power and traffic"""
    
    # Fail in integrated system
    impact = integrated_system.simulate_substation_failure(substation)
    
    # Fail in power grid
    power_grid.trigger_failure('substation', substation)
    
    # Impact traffic if SUMO is running
    if traffic_sim and traffic_sim.running:
        # Traffic lights will be synced automatically in SUMO loop
        pass
    
    return jsonify(impact)

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore substation"""
    success = integrated_system.restore_substation(substation)
    if success:
        power_grid.restore_component('substation', substation)
    return jsonify({'success': success})

@app.route('/api/restore_all', methods=['POST'])
def restore_all():
    """Restore all substations"""
    for sub_name in integrated_system.substations.keys():
        integrated_system.restore_substation(sub_name)
        power_grid.restore_component('substation', sub_name)
    return jsonify({'success': True, 'message': 'All systems restored'})

@app.route('/api/start_traffic', methods=['POST'])
def start_traffic():
    """Start traffic simulation"""
    global traffic_sim
    if not traffic_sim or not traffic_sim.running:
        traffic_sim = integrate_sumo_with_power_grid(integrated_system, power_grid)
    return jsonify({'success': True})

@app.route('/api/stop_traffic', methods=['POST'])
def stop_traffic():
    """Stop traffic simulation"""
    if traffic_sim:
        traffic_sim.stop_simulation()
    return jsonify({'success': True})

@app.route('/api/status')
def get_status():
    """Get system status"""
    power_status = power_grid.get_system_status()
    
    # Add traffic stats if available
    if traffic_sim and traffic_sim.running:
        power_status['traffic'] = traffic_sim.get_statistics()
    
    return jsonify(power_status)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("WORLD CLASS INTEGRATED SYSTEM READY")
    print("=" * 60)
    print("System Components:")
    print(f"  ⚡ Substations: {len(integrated_system.substations)}")
    print(f"  🔌 Distribution Transformers: {len(integrated_system.distribution_transformers)}")
    print(f"  🚦 Traffic Lights: {len(integrated_system.traffic_lights)}")
    print(f"  ⚡ EV Stations: {len(integrated_system.ev_stations)}")
    print(f"  🔋 EV Penetration: 30%")
    
    if traffic_sim and traffic_sim.running:
        print("\nTraffic Simulation:")
        print("  🚗 SUMO: ACTIVE")
        print("  📡 WebSocket: ws://localhost:8765")
        print("  🔄 Real-time sync: ENABLED")
    else:
        print("\nTraffic Simulation:")
        print("  ⚠️  SUMO not available")
        print("  💡 Install: apt-get install sumo sumo-tools")
    
    print("=" * 60)
    print("\n🚀 Starting server at http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, port=5000)