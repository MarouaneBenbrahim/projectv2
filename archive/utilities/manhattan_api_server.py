"""
API Server to connect SUMO simulation with Mapbox frontend
"""

from flask import Flask, jsonify
from flask_cors import CORS
import threading
from manhattan_simulation_runner import ManhattanSimulation

app = Flask(__name__)
CORS(app)

# Global simulation instance
sim = None

@app.route('/api/vehicles')
def get_vehicles():
    """Get real-time vehicle positions for Mapbox"""
    if sim:
        telemetry = sim.get_telemetry()
        return jsonify(telemetry['vehicles'])
    return jsonify([])

@app.route('/api/charging')
def get_charging():
    """Get charging station status"""
    if sim:
        telemetry = sim.get_telemetry()
        return jsonify(telemetry['charging_stations'])
    return jsonify([])

@app.route('/api/stats')
def get_stats():
    """Get simulation statistics"""
    if sim:
        telemetry = sim.get_telemetry()
        return jsonify(telemetry['statistics'])
    return jsonify({})

def run_simulation():
    """Run SUMO in background thread"""
    global sim
    sim = ManhattanSimulation()
    sim.config['gui'] = False  # Run headless for API
    sim.config['total_vehicles'] = 200
    if sim.start_simulation(gui=False):
        sim.run()

if __name__ == '__main__':
    # Start simulation in background
    sim_thread = threading.Thread(target=run_simulation)
    sim_thread.daemon = True
    sim_thread.start()
    
    # Run API server
    app.run(port=5001, debug=False)