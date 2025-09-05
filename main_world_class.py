"""
Manhattan Power Grid - World Class Main Application
COMPLETE INTEGRATION: Power + Traffic + EVs + Real-time Visualization
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
import os
import sys

# Add SUMO tools to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)

# Import your actual systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from manhattan_simulation_runner import ManhattanSimulation

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

# Initialize vehicle simulation
print("Initializing vehicle simulation...")
vehicle_simulation = None
try:
    vehicle_simulation = ManhattanSimulation()
    if vehicle_simulation.network_data:
        print("✅ Vehicle simulation ready")
    else:
        print("⚠️ Vehicle simulation disabled - run manhattan_network_analyzer.py first")
        vehicle_simulation = None
except Exception as e:
    print(f"⚠️ Could not initialize vehicle simulation: {e}")
    vehicle_simulation = None

# System state
system_running = True
current_time = 0

def vehicle_simulation_thread():
    """Run vehicle simulation in background"""
    global vehicle_simulation
    
    if not vehicle_simulation or not vehicle_simulation.network_data:
        print("Vehicle simulation not available")
        return
    
    # Configure for headless operation
    vehicle_simulation.config['gui'] = False
    vehicle_simulation.config['spawn_rate'] = 2.0
    vehicle_simulation.config['total_vehicles'] = 100
    vehicle_simulation.config['ev_percentage'] = 70
    
    # Start simulation
    if vehicle_simulation.start_simulation(gui=False):
        print("✅ Vehicle simulation started in background")
        vehicle_simulation.run()
    else:
        print("❌ Failed to start vehicle simulation")

def simulation_loop():
    """Background simulation loop for power and traffic lights"""
    global current_time
    
    while system_running:
        try:
            # Update traffic light phases every 2 seconds
            if current_time % 2 == 0:
                integrated_system.update_traffic_light_phases()
            
            # Run power flow every 30 seconds
            if current_time % 30 == 0:
                power_grid.run_power_flow("dc")
            
            current_time += 1
            time.sleep(1)
            
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)

# Start background threads
sim_thread = threading.Thread(target=simulation_loop, daemon=True)
sim_thread.start()

if vehicle_simulation:
    vehicle_thread = threading.Thread(target=vehicle_simulation_thread, daemon=True)
    vehicle_thread.start()

# Your existing HTML template (keep as is)
HTML_TEMPLATE = '''
[Your existing HTML template - keep exactly as is]
'''

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/network_state')
def get_network_state():
    """Get complete network state"""
    state = integrated_system.get_network_state()
    
    # Add vehicle data if available
    if vehicle_simulation:
        telemetry = vehicle_simulation.get_telemetry()
        state['vehicles'] = telemetry.get('vehicles', [])
        state['vehicle_stats'] = telemetry.get('statistics', {})
    
    return jsonify(state)

@app.route('/api/traffic_state')
def get_traffic_state():
    """Get traffic simulation state"""
    if vehicle_simulation:
        telemetry = vehicle_simulation.get_telemetry()
        return jsonify({
            'vehicles': telemetry.get('vehicles', []),
            'statistics': telemetry.get('statistics', {})
        })
    return jsonify({'vehicles': [], 'statistics': {}})

@app.route('/api/vehicles/list')
def get_vehicles():
    """Get vehicle positions for map"""
    if vehicle_simulation:
        telemetry = vehicle_simulation.get_telemetry()
        return jsonify(telemetry.get('vehicles', []))
    return jsonify([])

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
    
    # Add vehicle stats if available
    if vehicle_simulation:
        telemetry = vehicle_simulation.get_telemetry()
        power_status['vehicles'] = telemetry.get('statistics', {})
    
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
    
    if vehicle_simulation:
        print("\nVehicle Simulation:")
        print("  🚗 SUMO: RUNNING (headless)")
        print("  📊 Vehicles will appear on map")
        print("  🔄 Real-time updates: ENABLED")
    else:
        print("\nVehicle Simulation:")
        print("  ⚠️ Not available - run manhattan_network_analyzer.py first")
    
    print("=" * 60)
    print("\n🚀 Starting server at http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, port=5000)