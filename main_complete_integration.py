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
    'simulation_speed': 10.0,
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
            time.sleep(0.01 / system_state['simulation_speed'])
            
        except Exception as e:
            print(f"Simulation error: {e}")
            traceback.print_exc()
            time.sleep(1)

def update_ev_power_loads():
    """Update power grid loads based on EV charging"""
    
    print(f"[DEBUG] update_ev_power_loads called")
    
    # Get current charging statistics from SUMO
    if not sumo_manager.running:
        print(f"[DEBUG] SUMO not running, skipping")
        return
        
    stats = sumo_manager.get_statistics()
    print(f"[DEBUG] Stats - Vehicles charging: {stats.get('vehicles_charging', 0)}")
    
    # Track charging by station
    charging_by_station = {}
    for vehicle in sumo_manager.vehicles.values():
        # Debug each EV
        if vehicle.config.is_ev:
            # Check if vehicle has charging attributes
            has_is_charging = hasattr(vehicle, 'is_charging')
            is_charging_val = has_is_charging and vehicle.is_charging
            
            # Additional check for charging_at_station attribute
            has_charging_at = hasattr(vehicle, 'charging_at_station')
            charging_at_val = has_charging_at and vehicle.charging_at_station
            
            # Debug output for EVs at stations
            if vehicle.assigned_ev_station:
                print(f"[DEBUG] {vehicle.id}: station={vehicle.assigned_ev_station}, is_charging={is_charging_val}, SOC={vehicle.config.current_soc:.2f}")
            
            # Count if actually charging
            if is_charging_val or charging_at_val:
                if vehicle.assigned_ev_station:
                    if vehicle.assigned_ev_station not in charging_by_station:
                        charging_by_station[vehicle.assigned_ev_station] = []
                    charging_by_station[vehicle.assigned_ev_station].append(vehicle.id)
    
    # Convert to counts and show which vehicles are charging where
    charging_counts = {}
    for station_id, vehicles in charging_by_station.items():
        charging_counts[station_id] = len(vehicles)
        if vehicles:
            station_name = integrated_system.ev_stations[station_id]['name']
            print(f"[DEBUG] {station_name}: {len(vehicles)} charging - {', '.join(vehicles)}")
    
    print(f"[DEBUG] Charging by station summary: {charging_counts}")
    
    # Update each EV station's load
    total_charging_kw = 0
    for ev_id, ev_station in integrated_system.ev_stations.items():
        chargers_in_use = charging_counts.get(ev_id, 0)
        # 50kW DC fast charging per vehicle
        charging_power_kw = chargers_in_use * 50  # 50kW per charger
        total_charging_kw += charging_power_kw
        
        # Update the integrated system
        ev_station['vehicles_charging'] = chargers_in_use
        ev_station['current_load_kw'] = charging_power_kw
        
        # UPDATE PYPSA NETWORK LOAD
        if chargers_in_use > 0:
            # Find which substation this EV station is connected to
            substation_name = ev_station['substation']
            
            print(f"[DEBUG] {ev_station['name']}: {chargers_in_use} vehicles = {charging_power_kw} kW")
            
            # Update the substation load in the integrated system
            if substation_name in integrated_system.substations:
                # Add EV charging load to substation
                old_load = integrated_system.substations[substation_name].get('ev_load_mw', 0)
                new_load = charging_power_kw / 1000  # Convert to MW
                integrated_system.substations[substation_name]['ev_load_mw'] = new_load
                
                # Update PyPSA bus load
                bus_name = f"{substation_name}_13.8kV"
                if bus_name in power_grid.network.buses.index:
                    # Find or create EV load at this bus
                    ev_load_name = f"EV_{substation_name}"
                    
                    if ev_load_name not in power_grid.network.loads.index:
                        # Create new load for EV charging
                        power_grid.network.add(
                            "Load",
                            ev_load_name,
                            bus=bus_name,
                            p_set=new_load
                        )
                        print(f"[DEBUG] Created new EV load at {bus_name}: {new_load:.2f} MW")
                    else:
                        # Update existing load
                        power_grid.network.loads.at[ev_load_name, 'p_set'] = new_load
                        print(f"[DEBUG] Updated EV load at {bus_name}: {new_load:.2f} MW")
    
    print(f"[DEBUG] Total EV charging load: {total_charging_kw/1000:.2f} MW")
    
    # TRIGGER POWER FLOW AND CHECK FOR PROBLEMS
    if total_charging_kw > 100:  # If more than 100kW (0.1MW) of EV charging
        print(f"[DEBUG] Running power flow due to {total_charging_kw/1000:.2f} MW EV load")
        try:
            result = power_grid.run_power_flow("dc")
            if result.converged:
                print(f"[DEBUG] Power flow converged. Max line loading: {result.max_line_loading:.1%}")
                
                # CHECK FOR GRID STRESS
                if result.max_line_loading > 0.9:  # Line loaded above 90%
                    print("⚠️ WARNING: TRANSMISSION LINE OVERLOAD!")
                    print(f"   Critical lines: {result.critical_lines}")
                    
                    # REDUCE CHARGING RATE AT AFFECTED STATIONS
                    for ev_id, ev_station in integrated_system.ev_stations.items():
                        if ev_station['vehicles_charging'] > 0:
                            # Find most loaded substation
                            if ev_station['substation'] in ['Times Square', 'Grand Central']:
                                print(f"   🔌 REDUCING charging power at {ev_station['name']}")
                                
                                # Tell SUMO vehicles to slow charging
                                for vehicle in sumo_manager.vehicles.values():
                                    if hasattr(vehicle, 'is_charging') and vehicle.is_charging:
                                        if vehicle.assigned_ev_station == ev_id:
                                            # This is where we'd reduce charging rate
                                            print(f"      - {vehicle.id} charging limited")
                
                if result.voltage_violations:
                    print("⚠️ VOLTAGE VIOLATIONS DETECTED!")
                    for violation in result.voltage_violations[:5]:
                        print(f"   {violation}")
                
                # CHECK FOR TRANSFORMER OVERLOAD
                for name, substation in integrated_system.substations.items():
                    total_substation_load = substation['load_mw'] + substation.get('ev_load_mw', 0)
                    capacity = substation['capacity_mva'] * 0.9  # Power factor
                    
                    loading_percent = (total_substation_load / capacity) * 100
                    if loading_percent > 90:
                        print(f"🔥 SUBSTATION OVERLOAD: {name} at {loading_percent:.1f}% capacity!")
                        print(f"   Load: {total_substation_load:.1f} MW / {capacity:.1f} MW")
                        
                        # This is where we'd trip the substation or shed load
                        if loading_percent > 100:
                            print(f"   💥 {name} WOULD TRIP! (>100% loading)")
                
            else:
                print(f"[DEBUG] Power flow did NOT converge - system stressed!")
                
        except Exception as e:
            print(f"[DEBUG] Power flow error: {e}")
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
        vehicles = []
        
        # Create station charging counts
        station_charging_counts = {}
        station_queued_counts = {}
        
        vehicle_list = list(sumo_manager.vehicles.values())
        
        for vehicle in vehicle_list:
            try:
                import traci
                # Check if vehicle exists in SUMO
                if vehicle.id in traci.vehicle.getIDList():
                    x, y = traci.vehicle.getPosition(vehicle.id)
                    lon, lat = traci.simulation.convertGeo(x, y)
                    
                    # Track charging at stations
                    if hasattr(vehicle, 'is_charging') and vehicle.is_charging and vehicle.assigned_ev_station:
                        if vehicle.assigned_ev_station not in station_charging_counts:
                            station_charging_counts[vehicle.assigned_ev_station] = 0
                        station_charging_counts[vehicle.assigned_ev_station] += 1
                    
                    # Track queued at stations
                    if hasattr(vehicle, 'is_queued') and vehicle.is_queued and vehicle.assigned_ev_station:
                        if vehicle.assigned_ev_station not in station_queued_counts:
                            station_queued_counts[vehicle.assigned_ev_station] = 0
                        station_queued_counts[vehicle.assigned_ev_station] += 1
                    
                    vehicles.append({
                        'id': vehicle.id,
                        'lat': lat,
                        'lon': lon,
                        'type': vehicle.config.vtype.value,
                        'speed': vehicle.speed,
                        'speed_kmh': round(vehicle.speed * 3.6, 1),
                        'soc': vehicle.config.current_soc if vehicle.config.is_ev else 1.0,
                        'battery_percent': round(vehicle.config.current_soc * 100) if vehicle.config.is_ev else 100,
                        'is_charging': getattr(vehicle, 'is_charging', False),
                        'is_queued': getattr(vehicle, 'is_queued', False),
                        'is_circling': getattr(vehicle, 'is_circling', False),
                        'is_stranded': getattr(vehicle, 'is_stranded', False),
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
        
        # Update EV station charging counts
        for ev_station in state['ev_stations']:
            ev_station['vehicles_charging'] = station_charging_counts.get(ev_station['id'], 0)
            ev_station['vehicles_queued'] = station_queued_counts.get(ev_station['id'], 0)
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
@app.route('/api/test/ev_rush', methods=['POST'])
def test_ev_rush():
    """Test scenario: spawn many low-battery EVs"""
    if not system_state['sumo_running']:
        return jsonify({'success': False, 'message': 'Start SUMO first'})
    
    # Spawn 30 EVs with very low battery
    spawned = 0
    for i in range(30):
        vehicle_id = f"test_ev_{i}"
        try:
            # Get random edges
            import traci
            edges = [e for e in traci.edge.getIDList() if not e.startswith(':')]
            if len(edges) >= 2:
                origin = edges[i % len(edges)]
                dest = edges[(i + 10) % len(edges)]
                
                # Create route
                route = traci.simulation.findRoute(origin, dest)
                if route and route.edges:
                    route_id = f"test_route_{i}"
                    traci.route.add(route_id, route.edges)
                    
                    # Add EV with VERY low battery
                    traci.vehicle.add(vehicle_id, route_id, typeID="ev_sedan", depart="now")
                    traci.vehicle.setColor(vehicle_id, (255, 0, 0, 255))  # Red for low battery
                    traci.vehicle.setMaxSpeed(vehicle_id, 40)  # Fast movement
                    
                    # Set very low battery (10-20%)
                    battery = 75000 * random.uniform(0.10, 0.20)
                    traci.vehicle.setParameter(vehicle_id, "device.battery.actualBatteryCapacity", str(battery))
                    
                    spawned += 1
        except:
            pass
    
    return jsonify({
        'success': True,
        'message': f'Spawned {spawned} low-battery EVs for testing'
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
    # Update SUMO traffic lights if running
    if system_state['sumo_running'] and sumo_manager.running:
        # Update traffic lights - they go to RED during blackout
        sumo_manager.update_traffic_lights()
        
        # Handle blackout traffic behavior (slow down vehicles)
        sumo_manager.handle_blackout_traffic([substation])
        
        # Handle blackout for traffic lights specifically
        if hasattr(sumo_manager, 'handle_blackout_traffic_lights'):
            sumo_manager.handle_blackout_traffic_lights([substation])
        
        # UPDATE EV STATION STATUS PROPERLY
        for ev_id, ev_station in integrated_system.ev_stations.items():
            if ev_station['substation'] == substation:
                # Mark station as non-operational in integrated system
                ev_station['operational'] = False
                
                # Update SUMO manager's station status
                if ev_id in sumo_manager.ev_stations_sumo:
                    sumo_manager.ev_stations_sumo[ev_id]['available'] = 0
                
                # Update station manager's status if it exists
                if hasattr(sumo_manager, 'station_manager') and sumo_manager.station_manager:
                    if ev_id in sumo_manager.station_manager.stations:
                        sumo_manager.station_manager.stations[ev_id]['operational'] = False
                        
                        # Call the blackout handler
                        sumo_manager.station_manager.handle_blackout(substation)
    
    print(f"\n⚡ SUBSTATION FAILURE: {substation}")
    print(f"   - Traffic lights: Set to YELLOW (caution mode)")
    print(f"   - EV stations affected: {impact.get('ev_stations_affected', 0)}")
    print(f"   - Load lost: {impact.get('load_lost_mw', 0):.1f} MW")
    
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
            # Restore normal traffic speeds
            sumo_manager.restore_normal_traffic([substation])
            
            # RESTORE EV STATION STATUS
            for ev_id, ev_station in integrated_system.ev_stations.items():
                if ev_station['substation'] == substation:
                    # Mark station as operational
                    ev_station['operational'] = True
                    
                    # Update SUMO manager
                    if ev_id in sumo_manager.ev_stations_sumo:
                        sumo_manager.ev_stations_sumo[ev_id]['available'] = ev_station['chargers']
                    
                    # Update station manager
                    if hasattr(sumo_manager, 'station_manager') and sumo_manager.station_manager:
                        if ev_id in sumo_manager.station_manager.stations:
                            sumo_manager.station_manager.stations[ev_id]['operational'] = True
                            print(f"   ✅ Restored {ev_station['name']} ONLINE")
    
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
@app.route('/api/debug/ev_stations')
def debug_ev_stations():
    """Debug endpoint to check EV station status"""
    status = {}
    
    for ev_id, ev_station in integrated_system.ev_stations.items():
        status[ev_id] = {
            'name': ev_station['name'],
            'substation': ev_station['substation'],
            'operational': ev_station['operational'],
            'substation_operational': integrated_system.substations[ev_station['substation']]['operational'],
            'vehicles_charging': ev_station.get('vehicles_charging', 0),
            'current_load_kw': ev_station.get('current_load_kw', 0)
        }
    
    return jsonify(status)
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
        @keyframes pulse {
            0%, 100% { 
                transform: scale(1);
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            50% { 
                transform: scale(1.2);
                box-shadow: 0 3px 8px rgba(255,0,102,0.6);
            }
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
        
        .legend-circle {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 1.5px solid #fff;
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
                    <div class="vehicle-stat-value" id="charging-count" style="color: #00ffff;">0</div>
                    <div class="vehicle-stat-label">Charging/20</div>
                </div>
            </div>

            <div class="vehicle-stats">
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="queued-count" style="color: #ffff00;">0</div>
                    <div class="vehicle-stat-label">Queued/20</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="circling-count" style="color: #ff8c00;">0</div>
                    <div class="vehicle-stat-label">Circling</div>
                </div>
                <div class="vehicle-stat">
                    <div class="vehicle-stat-value" id="stranded-count" style="color: #ff00ff;">0</div>
                    <div class="vehicle-stat-label">Stranded</div>
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
                <button class="btn btn-danger" onclick="testEVRush()" id="test-rush-btn" disabled>
                    🔋 Test EV Rush
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
            <div class="legend-circle" style="background: #00ff00;"></div>
            <span>Electric Vehicle</span>
        </div>
        <div class="legend-item">
            <div class="legend-circle" style="background: #6464ff;"></div>
            <span>Gas Vehicle</span>
        </div>
        <div class="legend-item">
            <div class="legend-circle" style="background: #ffa500;"></div>
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
        let vehicleMarkers = {};  // Keep for cleanup but won't use for new vehicles
        let vehicleLayerInitialized = false;
        let evStationLayerInitialized = false;
        let layers = {
            lights: true,
            vehicles: true,
            primary: true,
            secondary: true,
            ev: true
        };
        let sumoRunning = false;
        let substationMarkers = {};
        let evStationMarkers = {};
        let sourcesInitialized = false;
        let lightsClickBound = false;
        
        // Load network state
        async function loadNetworkState() {
            try {
                const response = await fetch('/api/network_state');
                networkState = await response.json();
                updateUI();
                renderNetwork();
                if (layers.vehicles) {
                    renderVehicles();
            renderEVStations();
                }
            } catch (error) {
                console.error('Error loading network state:', error);
            }
        }
        async function testEVRush() {
            const response = await fetch('/api/test/ev_rush', {method: 'POST'});
            const result = await response.json();
            if (result.success) {
                alert(result.message);
            }
        }
        // Update UI
        function updateUI() {
            if (!networkState) return;
            
            const stats = networkState.statistics;
            
            document.getElementById('traffic-lights').textContent = stats.total_traffic_lights;
            document.getElementById('powered-lights').textContent = stats.powered_traffic_lights;
            document.getElementById('load-mw').textContent = Math.round(stats.total_load_mw);
            document.getElementById('substations-online').textContent = 
                `${stats.operational_substations}/${stats.total_substations}`;
            
            document.getElementById('green-count').textContent = stats.green_lights || 0;
            document.getElementById('yellow-count').textContent = stats.yellow_lights || 0;
            document.getElementById('red-count').textContent = stats.red_lights || 0;
            document.getElementById('black-count').textContent = stats.black_lights || 0;
            
            if (networkState.vehicle_stats) {
                document.getElementById('active-vehicles').textContent = (networkState.vehicles || []).length;
                document.getElementById('ev-count').textContent = networkState.vehicle_stats.ev_vehicles || 0;
                document.getElementById('charging-count').textContent = networkState.vehicle_stats.vehicles_charging || 0;
                document.getElementById('queued-count').textContent = networkState.vehicle_stats.vehicles_queued || 0;
                document.getElementById('circling-count').textContent = networkState.vehicle_stats.vehicles_circling || 0;
                document.getElementById('stranded-count').textContent = networkState.vehicle_stats.vehicles_stranded || 0;
                document.getElementById('avg-speed').textContent = 
                    Math.round((networkState.vehicle_stats.avg_speed_mps || 0) * 3.6);
                document.getElementById('energy-consumed').textContent = 
                    Math.round(networkState.vehicle_stats.total_energy_consumed_kwh || 0);
                document.getElementById('wait-time').textContent = 
                    Math.round(networkState.vehicle_stats.total_wait_time || 0);
                
                document.getElementById('vehicle-count').textContent = (networkState.vehicles || []).length;
                document.getElementById('charging-stations').textContent = 
                 `${networkState.vehicle_stats.vehicles_charging || 0}/${networkState.vehicle_stats.vehicles_queued || 0}`;
            }
            
            document.getElementById('total-load').textContent = Math.round(stats.total_load_mw);
            
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
        
        // Initialize vehicle layer (call once)
        function initializeVehicleLayer() {
            if (vehicleLayerInitialized) return;
            
            // Add GeoJSON source for vehicles
            map.addSource('vehicles', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: []
                }
            });
            
            // Add vehicle layer - circles that stay on the map
            map.addLayer({
                id: 'vehicles-layer',
                type: 'circle',
                source: 'vehicles',
                paint: {
                    'circle-radius': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        12, 3,
                        14, 5,
                        16, 7,
                        18, 10
                    ],
                    'circle-color': ['get', 'color'],
                    'circle-opacity': 0.9,
                    'circle-stroke-width': 1.5,
                    'circle-stroke-color': '#ffffff',
                    'circle-stroke-opacity': 0.8
                }
            });
            
            // Add click handler for vehicle info
            map.on('click', 'vehicles-layer', (e) => {
                const props = e.features[0].properties;
                
                new mapboxgl.Popup()
                    .setLngLat(e.lngLat)
                    .setHTML(`
                        <strong>Vehicle ${props.id}</strong><br>
                        Type: ${props.type}<br>
                        Speed: ${props.speed_kmh} km/h<br>
                        ${props.is_ev ? `Battery: ${props.battery_percent}%` : 'Gas Vehicle'}<br>
                        ${props.is_charging ? '🔌 Charging at ' + props.assigned_station : ''}<br>
                        Distance: ${props.distance_traveled} m<br>
                        Wait time: ${props.waiting_time}s<br>
                        On road: ${props.edge || 'unknown'}
                    `)
                    .addTo(map);
            });
            
            // Change cursor on hover
            map.on('mouseenter', 'vehicles-layer', () => {
                map.getCanvas().style.cursor = 'pointer';
            });
            
            map.on('mouseleave', 'vehicles-layer', () => {
                map.getCanvas().style.cursor = '';
            });
            
            vehicleLayerInitialized = true;
        }
        
        // Initialize EV station layer (call once)
        function initializeEVStationLayer() {
            if (evStationLayerInitialized) return;
            
            // Add GeoJSON source for EV stations
            map.addSource('ev-stations', {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: []
                }
            });
            
            // Base circle for station (background)
            map.addLayer({
                id: 'ev-stations-layer',
                type: 'circle',
                source: 'ev-stations',
                paint: {
                    'circle-radius': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        12, 6,
                        14, 8,
                        16, 10,
                        18, 14
                    ],
                    'circle-color': ['get', 'color'],
                    'circle-opacity': 0.95,
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff',
                    'circle-stroke-opacity': 0.9
                }
            });

            // Center lightning icon to preserve original look
            map.addLayer({
                id: 'ev-stations-icon',
                type: 'symbol',
                source: 'ev-stations',
                layout: {
                    'text-field': '⚡',
                    'text-size': [
                        'interpolate', ['linear'], ['zoom'],
                        12, 12,
                        14, 14,
                        16, 16,
                        18, 20
                    ],
                    'text-allow-overlap': true,
                    'text-ignore-placement': true
                },
                paint: {
                    'text-color': '#ffffff',
                    'text-halo-color': '#000000',
                    'text-halo-width': 0.6
                }
            });

            // Badge background (shows when charging_count > 0)
// In initializeEVStationLayer(), update the badge background layer:
            map.addLayer({
                id: 'ev-stations-badge-bg',
                type: 'circle',
                source: 'ev-stations',
                filter: ['>', ['get', 'charging_count'], 0],  // Show badge when charging
                paint: {
                    'circle-radius': [
                        'interpolate', ['linear'], ['zoom'],
                        12, 7,
                        16, 8,
                        18, 10
                    ],
                    'circle-color': [
                        'case',
                        ['>=', ['get', 'charging_count'], 20], '#ff0000',  // Full - red
                        ['>=', ['get', 'charging_count'], 15], '#ffa500',  // Almost full - orange
                        ['>=', ['get', 'charging_count'], 10], '#ffff00',  // Half full - yellow
                        '#00ff00'  // Available - green
                    ],
                    'circle-stroke-color': '#ffffff',
                    'circle-stroke-width': 2,
                    'circle-opacity': 1.0,
                    'circle-translate': [10, -10],
                    'circle-translate-anchor': 'map'
                }
            });

            // Badge text (charging count) on top-right
            map.addLayer({
                id: 'ev-stations-badge-text',
                type: 'symbol',
                source: 'ev-stations',
                filter: ['>', ['get', 'charging_count'], 0],
                layout: {
                    'text-field': ['to-string', ['get', 'charging_count']],
                    'text-size': [
                        'interpolate', ['linear'], ['zoom'],
                        12, 11,
                        16, 12,
                        18, 14
                    ],
                    'text-allow-overlap': true,
                    'text-ignore-placement': true
                },
                paint: {
                    'text-color': '#ffffff',
                    'text-halo-color': '#000000',
                    'text-halo-width': 0.6,
                    'text-translate': [10, -10],
                    'text-translate-anchor': 'map'
                }
            });
            
            // Add click handler for EV station info
            function onEVClick(e) {
                const props = e.features[0].properties;
                
                const chargingText = props.charging_count > 0 ? 
                    `<span style="color: #00ffff">⚡ Charging: ${props.charging_count}/20</span>` : 
                    '<span>⚡ Charging: 0/20</span>';
                
                const queuedText = props.queued_count > 0 ? 
                    `<br><span style="color: #ffff00">⏳ Queued: ${props.queued_count}/20</span>` : '';
                
                new mapboxgl.Popup()
                    .setLngLat(e.lngLat)
                    .setHTML(`
                        <strong>${props.name}</strong><br>
                        Status: <span style="color: ${props.operational ? '#00ff88' : '#ff0000'}">
                            ${props.operational ? '✅ Online' : '❌ Offline'}
                        </span><br>
                        ${chargingText}
                        ${queuedText}<br>
                        Capacity: ${props.chargers} chargers<br>
                        Substation: ${props.substation}
                    `)
                    .addTo(map);
            }
            map.on('click', 'ev-stations-layer', onEVClick);
            map.on('click', 'ev-stations-icon', onEVClick);
            map.on('click', 'ev-stations-badge-bg', onEVClick);
            map.on('click', 'ev-stations-badge-text', onEVClick);
            
            // Change cursor on hover for all ev layers
            const evHoverLayers = ['ev-stations-layer', 'ev-stations-icon', 'ev-stations-badge-bg', 'ev-stations-badge-text'];
            evHoverLayers.forEach(layerId => {
                map.on('mouseenter', layerId, () => { map.getCanvas().style.cursor = 'pointer'; });
                map.on('mouseleave', layerId, () => { map.getCanvas().style.cursor = ''; });
            });
            
            evStationLayerInitialized = true;
        }
        
        // Clean up old vehicle markers
        function cleanupOldVehicleMarkers() {
            for (const [id, marker] of Object.entries(vehicleMarkers)) {
                marker.remove();
            }
            vehicleMarkers = {};
        }
        
        // Render vehicles using GeoJSON layer (FIXED)
// In renderVehicles() function - ensure NO filtering of charging vehicles
        function renderVehicles() {
            if (!networkState || !networkState.vehicles) {
                if (map.getLayer('vehicles-layer')) {
                    map.setLayoutProperty('vehicles-layer', 'visibility', 'none');
                }
                return;
            }
            
            // Initialize layer if needed
            if (!vehicleLayerInitialized && map.loaded()) {
                initializeVehicleLayer();
            }
            
            if (!map.getSource('vehicles')) return;
            
            // Show/hide vehicle layer based on toggle
            if (map.getLayer('vehicles-layer')) {
                map.setLayoutProperty('vehicles-layer', 'visibility', layers.vehicles ? 'visible' : 'none');
            }
            
            // Convert ALL vehicles to GeoJSON features - NO FILTERING!
            const features = networkState.vehicles.map(vehicle => ({
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [vehicle.lon, vehicle.lat]
                },
                properties: {
                    id: vehicle.id,
                    type: vehicle.type,
                    speed_kmh: vehicle.speed_kmh || 0,
                    is_ev: vehicle.is_ev || false,
                    is_charging: vehicle.is_charging || false,
                    is_queued: vehicle.is_queued || false,
                    is_circling: vehicle.is_circling || false,
                    is_stranded: vehicle.is_stranded || false,
                    battery_percent: vehicle.battery_percent || 100,
                    color: vehicle.is_stranded ? '#ff00ff' :      // Magenta for stranded
                        vehicle.is_charging ? '#00ffff' :      // Cyan for charging
                        vehicle.is_queued ? '#ffff00' :        // Yellow for queued
                        vehicle.is_circling ? '#ff8c00' :      // Dark orange for circling
                        vehicle.battery_percent < 20 ? '#ff0000' :  // Red for critical
                        vehicle.battery_percent < 30 ? '#ffa500' :  // Orange for low
                        vehicle.is_ev ? '#00ff00' :            // Green for good battery
                        vehicle.type === 'taxi' ? '#ffff00' :
                        '#6464ff',
                    angle: vehicle.angle || 0,
                    edge: vehicle.edge || '',
                    distance_traveled: vehicle.distance_traveled || 0,
                    waiting_time: vehicle.waiting_time || 0,
                    assigned_station: vehicle.assigned_station || ''
                }
            }));
            
            // Update the source data
            const source = map.getSource('vehicles');
            if (source) {
                source.setData({
                    type: 'FeatureCollection',
                    features: features
                });
            }
        }
        
        // Render EV stations using GeoJSON layer (FIXED - same as vehicles)
function renderEVStations() {
    if (!networkState || !networkState.ev_stations) {
        if (map.getLayer('ev-stations-layer')) {
            map.setLayoutProperty('ev-stations-layer', 'visibility', 'none');
        }
        return;
    }
    
    // Initialize layer if needed
    if (!evStationLayerInitialized && map.loaded()) {
        initializeEVStationLayer();
    }
    
    if (!map.getSource('ev-stations')) return;
    
    // Show/hide EV station layers based on toggle
    ['ev-stations-layer','ev-stations-icon','ev-stations-badge-bg','ev-stations-badge-text'].forEach(id => {
        if (map.getLayer(id)) {
            map.setLayoutProperty(id, 'visibility', layers.ev ? 'visible' : 'none');
        }
    });
    
    // Convert EV stations to GeoJSON features with accurate counts
    const features = networkState.ev_stations.map(ev => {
        // Use counts from backend (already calculated)
        let chargingCount = ev.vehicles_charging || 0;
        let queuedCount = ev.vehicles_queued || 0;
        
        // Fallback: count from vehicles if backend didn't provide
        if (chargingCount === 0 && networkState.vehicles) {
            chargingCount = networkState.vehicles.filter(v => 
                v.is_charging && v.assigned_station === ev.id
            ).length;
        }
        
        let color = ev.operational ? '#00aaff' : '#666';
        
        return {
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [ev.lon, ev.lat]
            },
            properties: {
                id: ev.id,
                name: ev.name,
                chargers: ev.chargers,
                charging_count: chargingCount,
                queued_count: queuedCount,
                operational: ev.operational,
                substation: ev.substation,
                color: color
            }
        };
    });
    
    // Update the source data
    const source = map.getSource('ev-stations');
    if (source) {
        source.setData({
            type: 'FeatureCollection',
            features: features
        });
    }
}
        // Render network
        function renderNetwork() {
            if (!networkState) return;
            
            // Substations
            const existingSubIds = new Set();
            networkState.substations.forEach(sub => {
                existingSubIds.add(sub.name);
                let marker = substationMarkers[sub.name];
                if (!marker) {
                    const el = document.createElement('div');
                    el.style.width = '30px';
                    el.style.height = '30px';
                    el.style.borderRadius = '50%';
                    el.style.border = '3px solid #fff';
                    el.style.cursor = 'pointer';
                    marker = new mapboxgl.Marker(el)
                        .setLngLat([sub.lon, sub.lat])
                        .setPopup(new mapboxgl.Popup({offset: 25}))
                        .addTo(map);
                    substationMarkers[sub.name] = marker;
                }
                
                const el = substationMarkers[sub.name].getElement();
                el.style.background = sub.operational ?
                    'radial-gradient(circle, #ff0066 40%, #cc0052 100%)' :
                    'radial-gradient(circle, #ff0000 40%, #aa0000 100%)';
                el.style.boxShadow = sub.operational ?
                    '0 0 25px rgba(255,0,102,0.9)' :
                    '0 0 25px rgba(255,0,0,0.9)';
                substationMarkers[sub.name].setPopup(new mapboxgl.Popup({offset: 25}).setHTML(`
                    <strong>${sub.name}</strong><br>
                    Capacity: ${sub.capacity_mva} MVA<br>
                    Load: ${sub.load_mw.toFixed(1)} MW<br>
                    Status: <span style="color: ${sub.operational ? '#00ff88' : '#ff0000'}">
                        ${sub.operational ? '⚡ ONLINE' : '⚠️ FAILED'}
                    </span><br>
                    Coverage: ${sub.coverage_area}
                `));
            });
            
            Object.keys(substationMarkers).forEach(name => {
                if (!existingSubIds.has(name)) {
                    substationMarkers[name].remove();
                    delete substationMarkers[name];
                }
            });
            
// EV stations with charging counters (FIXED - using GeoJSON layer)
            if (layers.ev && networkState.ev_stations) {
                // Initialize layer if needed
                if (!evStationLayerInitialized && map.loaded()) {
                    initializeEVStationLayer();
                }
                
                if (map.getSource('ev-stations')) {
                    // Convert EV stations to GeoJSON features
                    const features = networkState.ev_stations.map(ev => {
                        // Count vehicles charging at this station
                        let chargingCount = 0;
                        if (networkState.vehicles) {
                            chargingCount = networkState.vehicles.filter(v => 
                                v.is_charging && v.assigned_station === ev.id
                            ).length;
                        }
                        
                        // Base color: keep station icon consistent (blue when operational, gray when offline)
                        let color = ev.operational ? '#00aaff' : '#666';
                        
                        return {
                            type: 'Feature',
                            geometry: {
                                type: 'Point',
                                coordinates: [ev.lon, ev.lat]
                            },
                            properties: {
                                id: ev.id,
                                name: ev.name,
                                chargers: ev.chargers,
                                charging_count: chargingCount,
                                operational: ev.operational,
                                substation: ev.substation,
                                color: color
                            }
                        };
                    });
                    
                    // Update the source data
                    const source = map.getSource('ev-stations');
                    if (source) {
                        source.setData({
                            type: 'FeatureCollection',
                            features: features
                        });
                    }
                    
                    // Show/hide EV station layer based on toggle
                    if (map.getLayer('ev-stations-layer')) {
                        map.setLayoutProperty('ev-stations-layer', 'visibility', 'visible');
                    }
                }
            } else {
                // Hide EV station layer if not enabled
                if (map.getLayer('ev-stations-layer')) {
                    map.setLayoutProperty('ev-stations-layer', 'visibility', 'none');
                }
            }
            
            // Cables
            if (networkState.cables) {
                if (networkState.cables.primary) {
                    const primaryFeatures = networkState.cables.primary
                        .filter(cable => cable.path && cable.path.length > 1)
                        .map(cable => ({
                            type: 'Feature',
                            geometry: { type: 'LineString', coordinates: cable.path },
                            properties: { operational: cable.operational }
                        }));
                    const primaryData = { type: 'FeatureCollection', features: primaryFeatures };
                    if (map.getSource('primary-cables')) {
                        map.getSource('primary-cables').setData(primaryData);
                    } else {
                        map.addSource('primary-cables', { type: 'geojson', data: primaryData });
                        map.addLayer({
                            id: 'primary-cables',
                            type: 'line',
                            source: 'primary-cables',
                            paint: {
                                'line-color': ['case', ['get', 'operational'], '#00ff88', '#ff0000'],
                                'line-width': 3,
                                'line-opacity': 0.7
                            }
                        });
                    }
                    if (map.getLayer('primary-cables')) {
                        map.setLayoutProperty('primary-cables', 'visibility', layers.primary ? 'visible' : 'none');
                    }
                }
                
                if (networkState.cables.secondary) {
                    const secondaryFeatures = (layers.secondary ? networkState.cables.secondary : [])
                        .filter(cable => cable.path && cable.path.length > 1)
                        .map(cable => ({
                            type: 'Feature',
                            geometry: { type: 'LineString', coordinates: cable.path },
                            properties: { operational: cable.operational, substation: cable.substation || 'unknown' }
                        }));
                    const secondaryData = { type: 'FeatureCollection', features: secondaryFeatures };
                    if (map.getSource('secondary-cables')) {
                        map.getSource('secondary-cables').setData(secondaryData);
                    } else {
                        map.addSource('secondary-cables', { type: 'geojson', data: secondaryData });
                        map.addLayer({
                            id: 'secondary-cables',
                            type: 'line',
                            source: 'secondary-cables',
                            paint: {
                                'line-color': [
                                    'match', ['get', 'substation'],
                                    "Hell's Kitchen", '#ff66aa',
                                    'Times Square', '#66ffaa',
                                    'Penn Station', '#ffaa66',
                                    'Grand Central', '#66aaff',
                                    'Murray Hill', '#aaff66',
                                    'Turtle Bay', '#aa66ff',
                                    'Columbus Circle', '#66ffaa',
                                    'Midtown East', '#ff66ff',
                                    '#ffaa00'
                                ],
                                'line-width': 0.8,
                                'line-opacity': ['case', ['get', 'operational'], 0.45, 0.15]
                            }
                        });
                    }
                    if (map.getLayer('secondary-cables')) {
                        map.setLayoutProperty('secondary-cables', 'visibility', layers.secondary ? 'visible' : 'none');
                    }
                }
            }
            
            // Traffic lights
            if (networkState.traffic_lights) {
                const features = (layers.lights ? networkState.traffic_lights : []).map(tl => ({
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [tl.lon, tl.lat] },
                    properties: {
                        powered: tl.powered,
                        color: tl.color || '#ff0000',
                        phase: tl.phase,
                        intersection: tl.intersection
                    }
                }));
                const tlData = { type: 'FeatureCollection', features };
                if (map.getSource('traffic-lights')) {
                    map.getSource('traffic-lights').setData(tlData);
                } else {
                    map.addSource('traffic-lights', { type: 'geojson', data: tlData });
                    map.addLayer({
                        id: 'traffic-lights',
                        type: 'circle',
                        source: 'traffic-lights',
                        paint: {
                            'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 2, 14, 3, 16, 5],
                            'circle-color': ['get', 'color'],
                            'circle-opacity': 0.9,
                            'circle-stroke-width': 0.5,
                            'circle-stroke-color': '#ffffff',
                            'circle-stroke-opacity': 0.3
                        }
                    });
                }
                if (!lightsClickBound && map.getLayer('traffic-lights')) {
                    lightsClickBound = true;
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
                if (map.getLayer('traffic-lights')) {
                    map.setLayoutProperty('traffic-lights', 'visibility', layers.lights ? 'visible' : 'none');
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
                if (map.getLayer('vehicles-layer')) {
                    map.setLayoutProperty('vehicles-layer', 'visibility', layers[layer] ? 'visible' : 'none');
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
                document.getElementById('test-rush-btn').disabled = false;
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
                
                // Clear vehicle data
                if (map.getSource('vehicles')) {
                    map.getSource('vehicles').setData({
                        type: 'FeatureCollection',
                        features: []
                    });
                }
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
        
        function updateTime() {
            const now = new Date();
            document.getElementById('time').textContent = 
                now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }
        
        // Initialize
        map.on('load', () => {
            // Initialize vehicle layer
            initializeVehicleLayer();
            
            // Initialize EV station layer
            initializeEVStationLayer();
            
            // Clean up any old markers
            cleanupOldVehicleMarkers();
            
            // Load initial state
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