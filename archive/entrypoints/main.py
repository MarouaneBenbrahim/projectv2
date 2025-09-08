"""
Manhattan Power Grid - World Class Integrated System
Complete backend-driven power and traffic management
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import threading
import time
import json

# Core imports
from config.settings import settings
from config.database import db_manager
from core.power_system import ManhattanPowerGrid
from core.world_class_system import WorldClassIntegratedSystem

app = Flask(__name__)
CORS(app)

# Initialize systems
print("=" * 60)
print("INITIALIZING MANHATTAN POWER GRID")
print("=" * 60)

db_manager.initialize()
power_grid = ManhattanPowerGrid()

print("Loading World-Class Integrated System...")
integrated_system = WorldClassIntegratedSystem(power_grid)

# Global state
system_state = {
    'running': True,
    'simulation_speed': 1.0,
    'current_time': 0
}

def simulation_loop():
    """Main simulation loop"""
    while system_state['running']:
        try:
            # Run power flow
            power_grid.run_power_flow("dc")
            
            # Update traffic light phases
            for tl in integrated_system.distribution.traffic_lights.values():
                if tl.powered:
                    tl.phase_timer += 1
                    if tl.phase_timer >= 30:  # Simple phase change every 30 seconds
                        tl.phase_timer = 0
            
            system_state['current_time'] += 1
            time.sleep(1.0 / system_state['simulation_speed'])
            
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)

# Start simulation thread
sim_thread = threading.Thread(target=simulation_loop, daemon=True)
sim_thread.start()

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/complete_state')
def get_complete_state():
    """Get complete system state"""
    return jsonify(integrated_system.get_complete_state())

@app.route('/api/fail/<substation>', methods=['POST'])
def fail_substation(substation):
    """Fail a substation with cascading effects"""
    # Fail in power grid
    power_grid.trigger_failure('substation', substation)
    
    # Fail in distribution network
    impact = integrated_system.distribution.simulate_failure(substation)
    
    # Update SUMO if running
    if integrated_system.sumo.running:
        for tl_id, tl in integrated_system.distribution.traffic_lights.items():
            if tl.substation == substation:
                integrated_system.sumo.update_traffic_light(tl_id, False)
    
    return jsonify(impact)

@app.route('/api/restore/<substation>', methods=['POST'])
def restore_substation(substation):
    """Restore a substation"""
    # Restore in power grid
    power_grid.restore_component('substation', substation)
    
    # Restore in distribution network
    if substation in integrated_system.distribution.substations:
        integrated_system.distribution.substations[substation]['operational'] = True
        
        # Restore all connected components
        for dt_name, dt in integrated_system.distribution.distribution_transformers.items():
            if dt['substation'] == substation:
                dt['operational'] = True
                
                # Restore traffic lights
                for tl in integrated_system.distribution.traffic_lights.values():
                    if tl.feeder == dt_name:
                        tl.powered = True
                        if integrated_system.sumo.running:
                            integrated_system.sumo.update_traffic_light(tl.id, True)
                
                # Restore EV stations
                for ev in integrated_system.distribution.ev_stations.values():
                    if ev.feeder == dt_name:
                        ev.operational = True
    
    return jsonify({'success': True, 'substation': substation})

@app.route('/api/status')
def get_status():
    """Get system status"""
    try:
        status = power_grid.get_system_status()
    except:
        status = {
            'total_load_mw': sum(s['load_mw'] for s in integrated_system.distribution.substations.values()),
            'total_generation_mw': sum(s['load_mw'] for s in integrated_system.distribution.substations.values()),
            'frequency_hz': 60.0,
            'health_score': 100
        }
    
    # Add traffic metrics if SUMO is running
    if integrated_system.sumo.running:
        status['traffic_metrics'] = integrated_system.sumo.get_traffic_metrics()
    
    return jsonify(status)

@app.route('/api/restore_all', methods=['POST'])
def restore_all():
    """Restore all substations"""
    for sub_name in integrated_system.distribution.substations.keys():
        restore_substation(sub_name)
    return jsonify({'success': True, 'message': 'All systems restored'})

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Manhattan Power Grid - World Class System</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #000;
            color: #fff;
            overflow: hidden;
        }
        
        #map { 
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
        }
        
        .control-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 420px;
            max-height: 90vh;
            background: linear-gradient(135deg, rgba(10,10,20,0.98), rgba(20,20,40,0.95));
            border-radius: 20px;
            padding: 25px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(102,126,234,0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            z-index: 1000;
            overflow-y: auto;
        }
        
        h1 {
            font-size: 28px;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00ff88, #0088ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        
        .subtitle {
            color: rgba(255,255,255,0.6);
            margin-bottom: 20px;
            font-size: 14px;
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
        
        .substation-controls {
            margin: 20px 0;
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
        }
        
        .btn-primary {
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
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,255,136,0.4);
        }
        
        .layer-controls {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        
        .layer-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
        }
        
        .toggle {
            position: relative;
            width: 48px;
            height: 24px;
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
            border-radius: 24px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background: white;
            transition: .3s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background: linear-gradient(90deg, #00ff88, #0088ff);
        }
        
        input:checked + .slider:before {
            transform: translateX(24px);
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
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(10,10,20,0.95);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid rgba(102,126,234,0.3);
            z-index: 1000;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 5px 0;
            font-size: 12px;
        }
        
        .legend-color {
            width: 20px;
            height: 3px;
            border-radius: 2px;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="control-panel">
        <h1>Manhattan Power Grid</h1>
        <div class="subtitle">World-Class Integrated System</div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="total-lights" style="color: #ffaa00;">0</div>
                <div class="stat-label">Traffic Lights</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="powered-lights" style="color: #00ff88;">0</div>
                <div class="stat-label">Powered</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="ev-stations" style="color: #00aaff;">0</div>
                <div class="stat-label">EV Stations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="substations" style="color: #ff88ff;">0</div>
                <div class="stat-label">Substations</div>
            </div>
        </div>
        
        <div class="substation-controls">
            <h3 style="font-size: 14px; margin-bottom: 10px; color: rgba(255,255,255,0.8);">
                Substation Control
            </h3>
            <div class="substation-grid" id="substation-buttons"></div>
        </div>
        
        <button class="btn-primary" onclick="restoreAll()">
            🔧 RESTORE ALL SYSTEMS
        </button>
        
        <div class="layer-controls">
            <h3 style="font-size: 14px; margin-bottom: 10px; color: rgba(255,255,255,0.8);">
                Layer Visibility
            </h3>
            
            <div class="layer-item">
                <span>Traffic Lights</span>
                <label class="toggle">
                    <input type="checkbox" checked onchange="toggleLayer('traffic_lights', this.checked)">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>13.8kV Feeders</span>
                <label class="toggle">
                    <input type="checkbox" checked onchange="toggleLayer('primary_cables', this.checked)">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>480V Service</span>
                <label class="toggle">
                    <input type="checkbox" checked onchange="toggleLayer('service_cables', this.checked)">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="layer-item">
                <span>EV Stations</span>
                <label class="toggle">
                    <input type="checkbox" checked onchange="toggleLayer('ev_stations', this.checked)">
                    <span class="slider"></span>
                </label>
            </div>
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <span class="status-indicator"></span>
            <span id="system-status">System Operational</span>
        </div>
        <div class="status-item">
            <span id="load-mw">0</span> MW Load
        </div>
        <div class="status-item">
            <span id="failures">0</span> Failures
        </div>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #ff0088;"></div>
            <span>Substations (138kV)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00ff88;"></div>
            <span>Primary Feeders (13.8kV)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ffaa00;"></div>
            <span>Service Cables (480V)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00aaff;"></div>
            <span>EV Charging Stations</span>
        </div>
    </div>
    
    <script>
        // Initialize Mapbox
        mapboxgl.accessToken = 'pk.eyJ1IjoibWFyb25veCIsImEiOiJjbWV1ODE5bHEwNGhoMmlvY2RleW51dWozIn0.FMrYdXLqnOwOEFi8qHSwxg';
        
        const map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/dark-v11',
            center: [-73.98, 40.757],
            zoom: 13,
            pitch: 45
        });
        
        let systemState = null;
        let failedSubstations = new Set();
        let layers = {
            traffic_lights: true,
            primary_cables: true,
            service_cables: true,
            ev_stations: true
        };
        
        async function loadSystemState() {
            try {
                const response = await fetch('/api/complete_state');
                systemState = await response.json();
                updateDisplay();
                drawNetwork();
            } catch (error) {
                console.error('Error loading system state:', error);
            }
        }
        
        function updateDisplay() {
            if (!systemState) return;
            
            // Update statistics
            document.getElementById('total-lights').textContent = 
                systemState.traffic_lights.length;
            document.getElementById('powered-lights').textContent = 
                systemState.traffic_lights.filter(tl => tl.powered).length;
            document.getElementById('ev-stations').textContent = 
                systemState.ev_stations.length;
            document.getElementById('substations').textContent = 
                systemState.substations.length;
            
            // Create substation buttons
            const container = document.getElementById('substation-buttons');
            container.innerHTML = '';
            
            systemState.substations.forEach(sub => {
                const btn = document.createElement('button');
                btn.className = 'sub-btn';
                if (!sub.operational) {
                    btn.classList.add('failed');
                }
                btn.textContent = sub.name.replace('_', ' ');
                btn.onclick = () => failSubstation(sub.name);
                container.appendChild(btn);
            });
            
            // Update status bar
            const failures = systemState.substations.filter(s => !s.operational).length;
            document.getElementById('failures').textContent = failures;
            
            if (failures > 0) {
                document.getElementById('system-status').textContent = 
                    `${failures} Substation${failures > 1 ? 's' : ''} Failed`;
                document.querySelector('.status-indicator').style.background = '#ff4444';
            } else {
                document.getElementById('system-status').textContent = 'System Operational';
                document.querySelector('.status-indicator').style.background = '#00ff88';
            }
        }
        
        function drawNetwork() {
            if (!systemState) return;
            
            // Clear existing layers
            const layersToRemove = map.getStyle().layers.filter(l => 
                l.id.startsWith('cable-') || 
                l.id.startsWith('lights-') || 
                l.id.startsWith('ev-')
            );
            layersToRemove.forEach(l => {
                if (map.getLayer(l.id)) map.removeLayer(l.id);
                if (map.getSource(l.id)) map.removeSource(l.id);
            });
            
            // Clear markers
            document.querySelectorAll('.mapboxgl-marker').forEach(el => el.remove());
            
            // Draw substations
            systemState.substations.forEach(sub => {
                const el = document.createElement('div');
                el.style.width = '30px';
                el.style.height = '30px';
                el.style.background = sub.operational ? '#ff0088' : '#ff0000';
                el.style.borderRadius = '50%';
                el.style.border = '3px solid #fff';
                el.style.boxShadow = `0 0 20px ${sub.operational ? 'rgba(255,0,136,0.8)' : 'rgba(255,0,0,0.8)'}`;
                
                new mapboxgl.Marker(el)
                    .setLngLat([sub.lon, sub.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(
                        `<b>${sub.name}</b><br>
                        Capacity: ${sub.capacity_mva} MVA<br>
                        Load: ${sub.load_mw.toFixed(1)} MW<br>
                        Status: ${sub.operational ? 'Online' : 'FAILED'}`
                    ))
                    .addTo(map);
            });
            
            // Draw cables
            if (systemState.cables) {
                // Primary feeders (13.8kV)
                const primaryCables = systemState.cables.filter(c => c.type === 'primary');
                if (layers.primary_cables) {
                    primaryCables.forEach((cable, idx) => {
                        if (cable.path && cable.path.length > 1) {
                            const id = `cable-primary-${idx}`;
                            
                            map.addSource(id, {
                                type: 'geojson',
                                data: {
                                    type: 'Feature',
                                    geometry: {
                                        type: 'LineString',
                                        coordinates: cable.path
                                    }
                                }
                            });
                            
                            map.addLayer({
                                id: id,
                                type: 'line',
                                source: id,
                                paint: {
                                    'line-color': cable.operational ? '#00ff88' : '#ff0000',
                                    'line-width': 3,
                                    'line-opacity': 0.7
                                }
                            });
                        }
                    });
                }
                
                // Service cables (480V)
                const serviceCables = systemState.cables.filter(c => c.type === 'service');
                if (layers.service_cables) {
                    serviceCables.forEach((cable, idx) => {
                        if (cable.path && cable.path.length > 1) {
                            const id = `cable-service-${idx}`;
                            
                            map.addSource(id, {
                                type: 'geojson',
                                data: {
                                    type: 'Feature',
                                    geometry: {
                                        type: 'LineString',
                                        coordinates: cable.path
                                    }
                                }
                            });
                            
                            map.addLayer({
                                id: id,
                                type: 'line',
                                source: id,
                                paint: {
                                    'line-color': cable.operational ? '#ffaa00' : '#ff0000',
                                    'line-width': 1,
                                    'line-opacity': 0.4
                                }
                            });
                        }
                    });
                }
            }
            
            // Draw traffic lights
            if (layers.traffic_lights && systemState.traffic_lights) {
                const geojson = {
                    type: 'FeatureCollection',
                    features: systemState.traffic_lights.map(tl => ({
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [tl.lon, tl.lat]
                        },
                        properties: {
                            powered: tl.powered,
                            substation: tl.substation
                        }
                    }))
                };
                
                map.addSource('lights-source', {
                    type: 'geojson',
                    data: geojson
                });
                
                map.addLayer({
                    id: 'lights-layer',
                    type: 'circle',
                    source: 'lights-source',
                    paint: {
                        'circle-radius': 3,
                        'circle-color': [
                            'case',
                            ['get', 'powered'],
                            '#00ff00',
                            '#ff0000'
                        ],
                        'circle-opacity': 0.8
                    }
                });
            }
            
            // Draw EV stations
            if (layers.ev_stations && systemState.ev_stations) {
                systemState.ev_stations.forEach(ev => {
                    const el = document.createElement('div');
                    el.style.width = '24px';
                    el.style.height = '24px';
                    el.style.background = ev.operational ? '#00aaff' : '#666';
                    el.style.borderRadius = '4px';
                    el.style.border = '2px solid #fff';
                    el.style.display = 'flex';
                    el.style.alignItems = 'center';
                    el.style.justifyContent = 'center';
                    el.style.fontSize = '14px';
                    el.innerHTML = '⚡';
                    
                    new mapboxgl.Marker(el)
                        .setLngLat([ev.lon, ev.lat])
                        .setPopup(new mapboxgl.Popup().setHTML(
                            `<b>${ev.name}</b><br>
                            Chargers: ${ev.chargers}<br>
                            Status: ${ev.operational ? 'Online' : 'Offline'}`
                        ))
                        .addTo(map);
                });
            }
        }
        
        function toggleLayer(layer, visible) {
            layers[layer] = visible;
            drawNetwork();
        }
        
        async function failSubstation(name) {
            await fetch(`/api/fail/${name}`, { method: 'POST' });
            await loadSystemState();
        }
        
        async function restoreAll() {
            await fetch('/api/restore_all', { method: 'POST' });
            await loadSystemState();
        }
        
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                document.getElementById('load-mw').textContent = Math.round(data.total_load_mw);
            } catch (error) {
                console.error('Error updating status:', error);
            }
        }
        
        // Initialize
        map.on('load', () => {
            loadSystemState();
            setInterval(loadSystemState, 5000);
            setInterval(updateStatus, 2000);
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print("=" * 60)
    print("MANHATTAN POWER GRID - WORLD CLASS SYSTEM")
    print("=" * 60)
    print(f"Version: {settings.version}")
    print(f"Substations: 12")
    print(f"Traffic Lights: 657 (real positions)")
    print(f"EV Stations: 8")
    print(f"Distribution Transformers: 60")
    print("=" * 60)
    print("Starting at http://127.0.0.1:5000")
    print("=" * 60)
    
    app.run(debug=False, port=5000)