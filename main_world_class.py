"""
Manhattan Power Grid - World Class Main Application
FIXED: Traffic light colors, popup styling, refresh issues
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime

# Import our systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem

app = Flask(__name__)
CORS(app)

# Initialize systems
print("=" * 60)
print("MANHATTAN POWER GRID - WORLD CLASS SYSTEM")
print("Professional Integration for Con Edison & NYC DOT")
print("=" * 60)

# Initialize power grid
print("Initializing PyPSA power grid...")
power_grid = ManhattanPowerGrid()

# Initialize integrated system
print("Loading integrated distribution network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# System state
system_running = True
current_time = 0

def simulation_loop():
    """Background simulation loop for realistic traffic light phases"""
    global current_time
    
    while system_running:
        try:
            # Update traffic light phases every 2 seconds
            if current_time % 2 == 0:
                integrated_system.update_traffic_light_phases()
            
            # Run power flow every 30 seconds (less frequent)
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

# HTML Template with fixes
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manhattan Power Grid - World Class System</title>
    
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
        
        /* FIX FOR POPUP STYLING - Dark background with white text */
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
        
        .mapboxgl-popup-content div {
            color: #ffffff !important;
        }
        
        .mapboxgl-popup-tip {
            border-top-color: rgba(20, 20, 30, 0.95) !important;
        }
        
        .mapboxgl-popup-close-button {
            color: #ffffff !important;
            font-size: 18px !important;
        }
        
        .mapboxgl-popup-close-button:hover {
            background: rgba(255, 255, 255, 0.1) !important;
        }
        
        /* Control Panel */
        .control-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 380px;
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
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
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
        
        /* Traffic light stats */
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
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Control Panel -->
    <div class="control-panel">
        <h1>Manhattan Power Grid</h1>
        <div class="subtitle">Con Edison & NYC DOT Integrated System</div>
        
        <!-- Statistics -->
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
        
        <!-- Traffic Light Stats -->
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
        
        <!-- Substation Controls -->
        <div class="section-title">Substation Control</div>
        <div class="substation-grid" id="substation-controls"></div>
        
        <!-- Action Buttons -->
        <button class="action-btn" onclick="restoreAll()">
            🔧 Restore All Systems
        </button>
        
        <!-- Layer Controls -->
        <div class="layer-controls">
            <div class="section-title">Visualization Layers</div>
            
            <div class="layer-item">
                <span>Traffic Lights</span>
                <label class="toggle">
                    <input type="checkbox" checked id="layer-lights" onchange="toggleLayer('lights')">
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
                    <input type="checkbox" checked id="layer-secondary" onchange="toggleLayer('secondary')">
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
            
            <div class="layer-item">
                <span>Substations</span>
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
            <span id="time">00:00</span>
        </div>
    </div>
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-title">Network Components</div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff0066;"></div>
            <span>Substations (138kV)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00ff88;"></div>
            <span>13.8kV Feeders</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ffaa00;"></div>
            <span>480V Service</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00aaff;"></div>
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
            zoom: 13.5,
            pitch: 45,
            bearing: -20
        });
        
        // State
        let networkState = null;
        let markers = [];
        let layers = {
            lights: true,
            primary: true,
            secondary: true,
            ev: true,
            substations: true
        };
        let lastUpdateTime = 0;
        
        // Load network state (optimized to prevent flashing)
        async function loadNetworkState(forceRedraw = false) {
            try {
                const response = await fetch('/api/network_state');
                networkState = await response.json();
                updateUI();
                
                // Only redraw if forced or first time
                const now = Date.now();
                if (forceRedraw || now - lastUpdateTime > 5000) {
                    renderNetwork();
                    lastUpdateTime = now;
                } else {
                    // Just update traffic lights without full redraw
                    updateTrafficLights();
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
        }
        
        // Update only traffic lights (no full redraw)
        function updateTrafficLights() {
            if (!map.getSource('traffic-lights') || !networkState) return;
            
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
            
            map.getSource('traffic-lights').setData({
                type: 'FeatureCollection',
                features: features
            });
        }
        
        // Render network on map
        function renderNetwork() {
            if (!networkState) return;
            
            // Clear existing markers only
            markers.forEach(m => m.remove());
            markers = [];
            
            // Add substations (only if layer enabled)
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
                        '0 0 25px rgba(255,0,102,0.9), 0 0 50px rgba(255,0,102,0.5)' :
                        '0 0 25px rgba(255,0,0,0.9), 0 0 50px rgba(255,0,0,0.5)';
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
            }
            
            // Handle cables (only recreate if needed)
            if (!map.getLayer('primary-cables') && networkState.cables) {
                // Primary cables
                if (layers.primary && networkState.cables.primary) {
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
                                'line-width': 3.5,
                                'line-opacity': 0.8
                            }
                        });
                    }
                }
                
                // Secondary cables
                if (layers.secondary && networkState.cables.secondary) {
                    const features = networkState.cables.secondary
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
                                'line-width': 1.2,
                                'line-opacity': 0.5
                            }
                        });
                    }
                }
            }
            
            // Add traffic lights with ACTUAL COLORS
            if (layers.lights && networkState.traffic_lights) {
                const features = networkState.traffic_lights.map(tl => ({
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [tl.lon, tl.lat]
                    },
                    properties: {
                        powered: tl.powered,
                        color: tl.color || '#ff0000',  // Use actual color from backend
                        phase: tl.phase,
                        intersection: tl.intersection
                    }
                }));
                
                // Remove old layer if exists
                if (map.getLayer('traffic-lights')) {
                    map.removeLayer('traffic-lights');
                }
                if (map.getSource('traffic-lights')) {
                    map.removeSource('traffic-lights');
                }
                
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
                            14, 3.5,
                            16, 5
                        ],
                        'circle-color': ['get', 'color'],  // Use the actual color property
                        'circle-opacity': [
                            'interpolate', ['linear'], ['zoom'],
                            12, 0.8,
                            14, 0.9,
                            16, 1
                        ],
                        'circle-stroke-width': 0.5,
                        'circle-stroke-color': '#ffffff',
                        'circle-stroke-opacity': 0.3
                    }
                });
                
                // Add popup on click
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
                
                map.on('mouseenter', 'traffic-lights', () => {
                    map.getCanvas().style.cursor = 'pointer';
                });
                
                map.on('mouseleave', 'traffic-lights', () => {
                    map.getCanvas().style.cursor = '';
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
            
            // Force full redraw after failure/restore
            await loadNetworkState(true);
        }
        
        // Restore all
        async function restoreAll() {
            await fetch('/api/restore_all', { method: 'POST' });
            await loadNetworkState(true);
        }
        
        // Toggle layer
        function toggleLayer(layer) {
            layers[layer] = !layers[layer];
            
            // Handle layer visibility
            if (layer === 'lights' && map.getLayer('traffic-lights')) {
                map.setLayoutProperty('traffic-lights', 'visibility', layers[layer] ? 'visible' : 'none');
            } else if (layer === 'primary' && map.getLayer('primary-cables')) {
                map.setLayoutProperty('primary-cables', 'visibility', layers[layer] ? 'visible' : 'none');
            } else if (layer === 'secondary' && map.getLayer('secondary-cables')) {
                map.setLayoutProperty('secondary-cables', 'visibility', layers[layer] ? 'visible' : 'none');
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
            
            // Update traffic lights every 2 seconds
            setInterval(() => loadNetworkState(false), 2000);
            
            // Full refresh every 30 seconds
            setInterval(() => loadNetworkState(true), 30000);
            
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

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Trigger substation failure"""
    impact = integrated_system.simulate_substation_failure(substation)
    power_grid.trigger_failure('substation', substation)
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

@app.route('/api/status')
def get_status():
    """Get system status"""
    power_status = power_grid.get_system_status()
    return jsonify(power_status)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("System Information:")
    print(f"  - Substations: {len(integrated_system.substations)}")
    print(f"  - Distribution Transformers: {len(integrated_system.distribution_transformers)}")
    print(f"  - Traffic Lights: {len(integrated_system.traffic_lights)}")
    print(f"  - EV Stations: {len(integrated_system.ev_stations)}")
    print(f"  - Primary Cables (13.8kV): {len(integrated_system.primary_cables)}")
    print(f"  - Secondary Cables (480V): {len(integrated_system.secondary_cables)}")
    print("=" * 60)
    print("\n🚀 Starting server at http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, port=5000)