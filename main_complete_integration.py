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
import os

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

# Import our systems
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem
from core.sumo_manager import ManhattanSUMOManager, SimulationScenario
from ml_engine import MLPowerGridEngine
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()
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

# ADD THIS: Initialize loads with realistic values
print("Setting initial load values...")
# Around line 45 - REDUCE all loads to prevent overload
initial_loads = {
    "Commercial_Hell's_Kitchen": 24,      # was 120
    "Commercial_Times_Square": 56,        # was 280
    "Commercial_Penn_Station": 44,        # was 220
    "Commercial_Grand_Central": 50,       # was 250
    "Commercial_Murray_Hill": 18,         # was 90
    "Commercial_Turtle_Bay": 22,          # was 110
    "Commercial_Chelsea": 17,             # was 85
    "Commercial_Midtown_East": 34,        # was 170
    "Industrial_Hell's_Kitchen": 9,       # was 45
    "Industrial_Times_Square": 6,         # was 30
    "Industrial_Penn_Station": 14,        # was 70
    "Industrial_Grand_Central": 10,       # was 50
    "Industrial_Murray_Hill": 8,          # was 40
    "Industrial_Turtle_Bay": 10,          # was 50
    "Industrial_Chelsea": 14,             # was 70
    "Industrial_Midtown_East": 10         # was 50
}
for load_name, load_mw in initial_loads.items():
    # Fix the name format to match PyPSA (underscores instead of apostrophes)
    fixed_load_name = load_name.replace("'", "")
    if fixed_load_name in power_grid.network.loads.index:
        power_grid.network.loads.at[fixed_load_name, 'p_set'] = load_mw
        print(f"  Set {fixed_load_name}: {load_mw} MW")
    elif load_name in power_grid.network.loads.index:
        power_grid.network.loads.at[load_name, 'p_set'] = load_mw
        print(f"  Set {load_name}: {load_mw} MW")

print(f"Total initial load: {sum(initial_loads.values())} MW")


# Initialize integrated system
print("Loading integrated distribution network...")
integrated_system = ManhattanIntegratedSystem(power_grid)

# Initialize SUMO manager
print("Initializing SUMO vehicle manager...")
sumo_manager = ManhattanSUMOManager(integrated_system)

# Initialize ML Engine
ml_engine = MLPowerGridEngine(integrated_system=integrated_system, power_grid=power_grid)

# Initialize OpenAI client (optional if key provided)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# Optional: cache of SUMO edge shapes (lon/lat) for road-locked rendering
EDGE_SHAPES: dict = {}

def preload_edge_shapes(max_edges: int | None = None) -> int:
    """Preload and cache SUMO edge shapes into EDGE_SHAPES using traci.
    Returns number of edges cached. Requires SUMO to be running.
    """
    try:
        import traci
    except Exception:
        return 0
    if not (system_state.get('sumo_running') and getattr(sumo_manager, 'running', False)):
        return 0
    count = 0
    try:
        edge_ids = [e for e in traci.edge.getIDList() if not e.startswith(':')]
        if max_edges is not None:
            edge_ids = edge_ids[:max_edges]
        for edge_id in edge_ids:
            if edge_id in EDGE_SHAPES:
                continue
            try:
                shape_xy = traci.edge.getShape(edge_id)
                edge_shape = []
                for sx, sy in shape_xy:
                    slon, slat = traci.simulation.convertGeo(sx, sy)
                    edge_shape.append([slon, slat])
                EDGE_SHAPES[edge_id] = {'xy': shape_xy, 'lonlat': edge_shape}
                count += 1
            except Exception:
                # Skip edges that fail shape retrieval
                continue
    except Exception:
        return count
    return count

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
            if system_state['current_time'] % 50 == 0:
                power_grid.run_power_flow("dc")
            
            system_state['current_time'] += 1
            time.sleep(0.01 / system_state['simulation_speed'])
            
        except Exception as e:
            print(f"Simulation error: {e}")
            traceback.print_exc()
            time.sleep(1)

def update_ev_power_loads():
    """Update power grid loads based on EV charging - COMPLETE FIXED VERSION"""
    
    global power_grid  # Use the global instance
    global previous_ev_load_mw  # Track previous load
    
    print(f"[DEBUG] update_ev_power_loads called at time {system_state['current_time']}")
    
    # Initialize previous load tracking
    if 'previous_ev_load_mw' not in globals():
        previous_ev_load_mw = 0
    
    # Verify power_grid exists
    if not power_grid:
        print("[ERROR] power_grid not initialized!")
        return
    
    # Check if SUMO is running
    if not sumo_manager.running:
        print(f"[DEBUG] SUMO not running, skipping EV load update")
        return
    
    # Get SUMO statistics
    stats = sumo_manager.get_statistics()
    print(f"[DEBUG] Stats - Vehicles charging: {stats.get('vehicles_charging', 0)}")
    
    # Track detailed charging information
    charging_by_station = {}
    charging_details = {
        'total_vehicles_charging': 0,
        'total_power_kw': 0,
        'stations_active': 0,
        'critical_stations': []
    }
    
    # Count charging vehicles properly
    for vehicle in sumo_manager.vehicles.values():
        if vehicle.config.is_ev:
            # Check multiple charging indicators
            has_is_charging = hasattr(vehicle, 'is_charging')
            is_charging_val = has_is_charging and vehicle.is_charging
            
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
    
    # Update each EV station's load and PyPSA
    total_charging_kw = 0
    substation_loads = {}  # Track load per substation
    
    for ev_id, ev_station in integrated_system.ev_stations.items():
        chargers_in_use = charging_counts.get(ev_id, 0)
        
        # Calculate realistic charging power based on number of vehicles
        if chargers_in_use > 0:
            # Variable charging rate based on station load
            if chargers_in_use <= 5:
                power_per_vehicle = 150  # 150kW DC fast charging when not crowded
            elif chargers_in_use <= 10:
                power_per_vehicle = 100  # 100kW when moderately busy
            elif chargers_in_use <= 15:
                power_per_vehicle = 50   # 50kW when busy
            else:
                power_per_vehicle = 22   # 22kW when very crowded
            
            charging_power_kw = chargers_in_use * power_per_vehicle
        else:
            charging_power_kw = 0
        
        total_charging_kw += charging_power_kw
        
        # Update the integrated system
        ev_station['vehicles_charging'] = chargers_in_use
        ev_station['current_load_kw'] = charging_power_kw
        
        # Track load by substation
        substation_name = ev_station['substation']
        if substation_name not in substation_loads:
            substation_loads[substation_name] = 0
        substation_loads[substation_name] += charging_power_kw
        
        # Update station statistics
        if chargers_in_use > 0:
            charging_details['stations_active'] += 1
            charging_details['total_vehicles_charging'] += chargers_in_use
            print(f"[DEBUG] {ev_station['name']}: {chargers_in_use} vehicles = {charging_power_kw} kW")
            
            # Check if station is critical (>80% capacity)
            if chargers_in_use >= 16:  # 80% of 20 ports
                charging_details['critical_stations'].append(ev_station['name'])
    
    charging_details['total_power_kw'] = total_charging_kw
    
    # UPDATE PYPSA NETWORK - Key part
    print(f"[DEBUG] Total EV charging load: {total_charging_kw/1000:.2f} MW")
    
    # COMPLETE FIX: Map ALL substations correctly
    bus_name_mapping = {
        "Hell's Kitchen": "Hell's Kitchen_13.8kV",  # Note the apostrophe in PyPSA!
        "Times Square": "Times Square_13.8kV",
        "Penn Station": "Penn Station_13.8kV", 
        "Grand Central": "Grand Central_13.8kV",
        "Murray Hill": "Murray Hill_13.8kV",
        "Turtle Bay": "Turtle Bay_13.8kV",
        "Columbus Circle": "Chelsea_13.8kV",  # Columbus Circle maps to Chelsea bus
        "Midtown East": "Midtown East_13.8kV"
    }
    
    # Update PyPSA loads for each substation
    for substation_name, load_kw in substation_loads.items():
        load_mw = load_kw / 1000
        
        # Get correct bus name from mapping
        bus_name = bus_name_mapping.get(substation_name)
        if not bus_name:
            print(f"[ERROR] No mapping for substation: {substation_name}")
            continue
        
        # Check if bus exists in network (handling apostrophes)
        bus_name_in_pypsa = None
        if bus_name in power_grid.network.buses.index:
            bus_name_in_pypsa = bus_name
        elif bus_name.replace("'", "") in power_grid.network.buses.index:
            bus_name_in_pypsa = bus_name.replace("'", "")
        elif bus_name.replace(" ", "_") in power_grid.network.buses.index:
            bus_name_in_pypsa = bus_name.replace(" ", "_")
        
        if not bus_name_in_pypsa:
            print(f"[WARNING] Bus {bus_name} not found in network")
            if system_state['current_time'] % 1000 == 0:  # Every 100 seconds
                available_buses = [b for b in power_grid.network.buses.index if "13.8kV" in b]
                print(f"[DEBUG] Available 13.8kV buses: {available_buses}")
            continue
        
        # Create EV load name
        clean_name = substation_name.replace(' ', '_').replace("'", '')
        ev_load_name = f"EV_{clean_name}"
        
        # Update integrated system
        if substation_name in integrated_system.substations:
            old_ev_load = integrated_system.substations[substation_name].get('ev_load_mw', 0)
            integrated_system.substations[substation_name]['ev_load_mw'] = load_mw
            
            if abs(old_ev_load - load_mw) > 0.01:
                print(f"[DEBUG] {substation_name} EV load: {old_ev_load:.2f} → {load_mw:.2f} MW")
        
        # Update PyPSA bus load
        try:
            if ev_load_name not in power_grid.network.loads.index:
                # Create new load
                power_grid.network.add(
                    "Load",
                    ev_load_name,
                    bus=bus_name_in_pypsa,
                    p_set=load_mw
                )
                print(f"[DEBUG] Created new EV load at {bus_name_in_pypsa}: {load_mw:.2f} MW")
            else:
                # Update existing load
                old_value = power_grid.network.loads.at[ev_load_name, 'p_set']
                power_grid.network.loads.at[ev_load_name, 'p_set'] = load_mw
                
                if abs(old_value - load_mw) > 0.01:  # Only log significant changes
                    print(f"[DEBUG] Updated {ev_load_name}: {old_value:.2f} → {load_mw:.2f} MW")
                    
        except Exception as e:
            print(f"[ERROR] Failed to update PyPSA load for {substation_name}: {e}")
    
    # Clean up zero loads
    for substation_name in bus_name_mapping.keys():
        if substation_name not in substation_loads:
            clean_name = substation_name.replace(' ', '_').replace("'", '')
            ev_load_name = f"EV_{clean_name}"
            if ev_load_name in power_grid.network.loads.index:
                old_val = power_grid.network.loads.at[ev_load_name, 'p_set']
                if old_val > 0:
                    power_grid.network.loads.at[ev_load_name, 'p_set'] = 0
                    print(f"[DEBUG] Cleared {ev_load_name}: {old_val:.2f} → 0.00 MW")
    
    # TRIGGER POWER FLOW - COMPLETE FIXED VERSION
    total_ev_load_mw = total_charging_kw / 1000
    
    # Ensure previous_ev_load_mw exists before using it
    if 'previous_ev_load_mw' not in globals():
        previous_ev_load_mw = 0.0
        print(f"[DEBUG] Initialized previous_ev_load_mw to 0.0")
    
    # Calculate conditions
    load_change = abs(total_ev_load_mw - previous_ev_load_mw)
    time_for_periodic = (system_state['current_time'] % 50 == 0)
    first_charging = (previous_ev_load_mw == 0 and total_ev_load_mw > 0)
    
    # Debug output
    print(f"[DEBUG] Power flow check: current={total_ev_load_mw:.3f} MW, previous={previous_ev_load_mw:.3f} MW, diff={load_change:.3f} MW")
    print(f"[DEBUG] Time check: timestep={system_state['current_time']}, periodic={time_for_periodic}")
    
    # Determine if power flow should run
    should_run_power_flow = False
    reason = ""
    
    if load_change > 0.05:
        should_run_power_flow = True
        reason = f"load change {load_change:.3f} MW"
    elif system_state['current_time'] % 50 == 0 and total_ev_load_mw > 0:
        should_run_power_flow = True
        reason = f"forced periodic at timestep {system_state['current_time']}"
        # Force update to trigger next time by setting an impossible previous value
        previous_ev_load_mw = -999
    elif first_charging:
        should_run_power_flow = True
        reason = "first EV started charging"
    elif system_state['current_time'] % 500 == 0:  # Force every 50 seconds regardless
        should_run_power_flow = True
        reason = "forced periodic check"
    
    if should_run_power_flow:
        print(f"[DEBUG] ⚡ TRIGGERING POWER FLOW: {reason}")
        print(f"[DEBUG] Running power flow: EV load {previous_ev_load_mw:.2f} → {total_ev_load_mw:.2f} MW")
        
        try:
            # Calculate total system load INCLUDING base load
            base_load = sum(integrated_system.substations[s]['load_mw'] 
                           for s in integrated_system.substations)
            total_system_load = base_load + total_ev_load_mw
            
            print(f"[DEBUG] System loads: Base={base_load:.2f} MW, EV={total_ev_load_mw:.2f} MW, Total={total_system_load:.2f} MW")
            
            # Verify PyPSA network state
            pypsa_total = sum(power_grid.network.loads.at[load, 'p_set'] 
                             for load in power_grid.network.loads.index)
            print(f"[DEBUG] PyPSA network total load: {pypsa_total:.2f} MW")
            
            # Run power flow
            print(f"[DEBUG] Executing power flow calculation...")
            result = power_grid.run_power_flow("dc")
            
            if result.converged:
                print(f"[DEBUG] ✅ POWER FLOW CONVERGED")
                print(f"[DEBUG]    Max line loading: {result.max_line_loading:.1%}")
                # Line 430 - just comment it out or remove it
                # print(f"[DEBUG]    Total losses: {result.total_losses_mw:.2f} MW")
                
                # Get actual values if available
                if hasattr(result, 'total_generation'):
                    print(f"[DEBUG]    Total generation: {result.total_generation:.2f} MW")
                if hasattr(result, 'total_load'):
                    print(f"[DEBUG]    Total load: {result.total_load:.2f} MW")
                
                # Detailed line analysis
                if hasattr(result, 'critical_lines') and result.critical_lines:
                    print(f"[DEBUG]    Critical lines (>80% loaded):")
                    for line in result.critical_lines[:3]:
                        print(f"[DEBUG]      - {line}")
                
                # CHECK FOR GRID STRESS
                if result.max_line_loading > 0.9:
                    print("⚠️ WARNING: TRANSMISSION LINE APPROACHING LIMIT!")
                    print(f"   Line loading: {result.max_line_loading:.1%}")
                    
                    # Check which substations are most loaded
                    for name, substation in integrated_system.substations.items():
                        total_substation_load = substation['load_mw'] + substation.get('ev_load_mw', 0)
                        capacity = substation['capacity_mva'] * 0.9  # Power factor
                        loading_percent = (total_substation_load / capacity) * 100
                        
                        if loading_percent > 85:
                            print(f"   ⚡ {name}: {loading_percent:.1f}% loaded")
                    
                    # Implement demand response if critical
                    if charging_details['total_vehicles_charging'] > 10:
                        print(f"   📉 Would implement demand response for {charging_details['total_vehicles_charging']} EVs")
                        for station_name in charging_details['critical_stations']:
                            print(f"    Would reduce charging at {station_name} by 50%")
                            
                elif result.max_line_loading > 0.8:
                    print("📊 NOTICE: Line loading above 80% - monitoring required")
                
                # CHECK FOR VOLTAGE VIOLATIONS
                if hasattr(result, 'voltage_violations') and result.voltage_violations:
                    print(f"⚡ VOLTAGE ISSUES: {len(result.voltage_violations)} buses outside limits")
                    for i, violation in enumerate(result.voltage_violations):
                        if i < 3:  # Show first 3
                            print(f"   Bus {violation.get('bus', 'unknown')}: {violation.get('voltage', 0):.3f} pu")
                
                # CHECK FOR SUBSTATION OVERLOADS
                overloaded_substations = []
                for name, substation in integrated_system.substations.items():
                    total_substation_load = substation['load_mw'] + substation.get('ev_load_mw', 0)
                    capacity = substation['capacity_mva'] * 0.9  # Power factor
                    loading_percent = (total_substation_load / capacity) * 100
                    
                    if loading_percent > 90:
                        overloaded_substations.append((name, loading_percent))
                        print(f"🔥 SUBSTATION OVERLOAD: {name} at {loading_percent:.1f}% capacity!")
                        print(f"   Load: {total_substation_load:.1f} MW / {capacity:.1f} MW")
                        
                        if loading_percent > 100:
                            print(f"   💥 {name} WOULD TRIP! Initiating load shedding...")
                            system_state['emergency'] = True
                
                # Summary
                if not overloaded_substations and result.max_line_loading < 0.8:
                    print(f"[DEBUG] ✅ Grid stable with {total_ev_load_mw:.2f} MW EV load")
                
            else:
                print(f"[DEBUG] ❌ POWER FLOW DIVERGED - SYSTEM UNSTABLE!")
                print(f"[DEBUG]    This indicates severe grid stress")
                print(f"[DEBUG]    System cannot handle {total_ev_load_mw:.2f} MW additional EV load")
                
                # Emergency response
                if charging_details['total_vehicles_charging'] > 5:
                    print("   🚨 EMERGENCY: Stopping all new EV charging")
                    print(f"   🚨 Must reduce load by {total_ev_load_mw * 0.5:.2f} MW")
                    system_state['emergency'] = True
                    
        except Exception as e:
            print(f"[ERROR] Power flow calculation failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Update previous load after power flow
        print(f"[DEBUG] Updating previous_ev_load_mw after power flow: {previous_ev_load_mw:.3f} → {total_ev_load_mw:.3f} MW")
        previous_ev_load_mw = total_ev_load_mw
        
    else:
        # No power flow needed
        if load_change > 0.001:
            print(f"[DEBUG] Minor load change ({load_change:.3f} MW), no power flow needed")
            
    # ALWAYS update previous load at the end to track changes
    if total_ev_load_mw != previous_ev_load_mw:
        print(f"[DEBUG] Final update previous_ev_load_mw: {previous_ev_load_mw:.3f} → {total_ev_load_mw:.3f} MW")
        previous_ev_load_mw = total_ev_load_mw
    
    # Periodic summary (every 30 seconds at 0.1s timestep = 300 steps)
    if system_state['current_time'] % 300 == 0 and charging_details['total_vehicles_charging'] > 0:
        print(f"\n📊 EV CHARGING SUMMARY:")
        print(f"  Total Load: {total_charging_kw/1000:.2f} MW")
        print(f"  Vehicles Charging: {charging_details['total_vehicles_charging']}")
        print(f"  Active Stations: {charging_details['stations_active']}/8")
        if charging_details['critical_stations']:
            print(f"  ⚠️ Critical Stations: {', '.join(charging_details['critical_stations'])}")
        
        # Show load distribution
        print(f"  Load by Substation:")
        for sub_name, load_kw in sorted(substation_loads.items(), key=lambda x: x[1], reverse=True):
            print(f"    {sub_name}: {load_kw/1000:.2f} MW")
def check_n_minus_1_contingency():
    """Check if system can survive any single component failure"""
    critical_components = []
    for line in power_grid.network.lines.index:
        # Temporarily fail this line
        original_capacity = power_grid.network.lines.at[line, 's_nom']
        power_grid.network.lines.at[line, 's_nom'] = 0
        
        # Run power flow
        result = power_grid.run_power_flow("dc")
        
        # Check if system survives
        if not result.converged or result.max_line_loading > 1.0:
            critical_components.append(line)
        
        # Restore
        power_grid.network.lines.at[line, 's_nom'] = original_capacity
    
    return critical_components
def calculate_dynamic_charging_power(soc):
    """Calculate realistic charging power based on battery SOC"""
    if soc < 0.2:
        return 150  # 150kW DC fast charging for low battery
    elif soc < 0.5:
        return 100  # 100kW moderate fast charging
    elif soc < 0.8:
        return 50   # 50kW standard charging
    else:
        return 22   # 22kW trickle charging above 80%

def handle_grid_stress(power_flow_result, charging_details):
    """Handle grid stress conditions - WORLD CLASS"""
    
    print("\n🚨 GRID STRESS DETECTED - INITIATING RESPONSE")
    
    # Identify critical lines
    critical_lines = []
    for line_name, line_data in power_grid.network.lines.iterrows():
        loading = abs(line_data.p0 / line_data.s_nom) if line_data.s_nom > 0 else 0
        if loading > 0.85:
            critical_lines.append((line_name, loading))
    
    critical_lines.sort(key=lambda x: x[1], reverse=True)
    
    # Implement demand response
    if charging_details['total_vehicles_charging'] > 20:
        print(f"  📉 Implementing demand response for {charging_details['total_vehicles_charging']} EVs")
        
        # Reduce charging rate at critical stations
        for station_name in charging_details['critical_stations']:
            # Find station and reduce power
            for ev_id, ev_station in integrated_system.ev_stations.items():
                if ev_station['name'] == station_name:
                    # Signal SUMO to reduce charging rate
                    if hasattr(sumo_manager, 'reduce_charging_rate'):
                        sumo_manager.reduce_charging_rate(ev_id, 0.5)  # 50% reduction
                    print(f"    Reduced charging at {station_name} by 50%")
    
    # Log critical lines
    for line, loading in critical_lines[:3]:
        print(f"  ⚡ Line {line}: {loading:.1%} loaded")

def handle_voltage_issues(violations):
    """Handle voltage violations - WORLD CLASS"""
    
    print("\n⚡ VOLTAGE CONTROL ACTIVATED")
    
    # Group violations by severity
    critical = [v for v in violations if abs(v['deviation']) > 0.1]
    warning = [v for v in violations if 0.05 < abs(v['deviation']) <= 0.1]
    
    if critical:
        print(f"  🔴 CRITICAL: {len(critical)} buses with >10% deviation")
        # Implement voltage control actions
        for violation in critical[:3]:  # Show top 3
            print(f"    Bus {violation.get('bus', 'unknown')}: {violation.get('voltage', 0):.3f} pu")
    
    if warning:
        print(f"  🟡 WARNING: {len(warning)} buses with 5-10% deviation")

def check_substation_overloads(substation_loads):
    """Check for substation overloads - WORLD CLASS"""
    
    for substation_name, ev_load_kw in substation_loads.items():
        if substation_name in integrated_system.substations:
            substation = integrated_system.substations[substation_name]
            
            # Total load including base + EV
            total_load_mw = substation['load_mw'] + (ev_load_kw / 1000)
            capacity_mva = substation['capacity_mva']
            
            # Assume 0.9 power factor
            capacity_mw = capacity_mva * 0.9
            loading_percent = (total_load_mw / capacity_mw) * 100
            
            if loading_percent > 90:
                print(f"🔥 SUBSTATION OVERLOAD: {substation_name}")
                print(f"   Load: {total_load_mw:.1f} MW / {capacity_mw:.1f} MW ({loading_percent:.1f}%)")
                
                if loading_percent > 100:
                    print(f"   💥 {substation_name} WOULD TRIP - INITIATING LOAD SHED")
                    initiate_load_shedding(substation_name, total_load_mw - capacity_mw)

def initiate_emergency_response(charging_details):
    """Emergency response when power flow diverges"""
    
    print("\n🚨🚨 EMERGENCY RESPONSE ACTIVATED 🚨🚨")
    print(f"  System cannot support {charging_details['total_power_kw']/1000:.1f} MW EV load")
    
    # Stop all new charging
    if hasattr(sumo_manager, 'stop_new_charging'):
        sumo_manager.stop_new_charging()
    
    # Reduce existing charging
    print("  Reducing all charging rates to 25%")
    
    # Signal critical state to dashboard
    system_state['emergency'] = True

def initiate_load_shedding(substation_name, excess_mw):
    """Implement load shedding to prevent cascade"""
    
    print(f"\n⚡ LOAD SHEDDING at {substation_name}: {excess_mw:.1f} MW")
    
    # Priority order for shedding
    # 1. Reduce EV charging
    # 2. Turn off non-critical loads
    # 3. Rolling blackouts if necessary
    
    # This would interface with your actual control system
    pass
# Start simulation thread
sim_thread = threading.Thread(target=simulation_loop, daemon=True)
sim_thread.start()

# API Routes
@app.route('/api/debug/buses')
def debug_buses():
    """Show all bus names in PyPSA"""
    buses_13kv = [b for b in power_grid.network.buses.index if '13.8kV' in b]
    
    # Also show substation names from integrated system
    substations = list(integrated_system.substations.keys())
    
    return jsonify({
        'pypsa_buses_13kv': buses_13kv,
        'integrated_substations': substations,
        'mapping_check': {
            sub: f"{sub.replace(' ', '_')}_13.8kV" in power_grid.network.buses.index
            for sub in substations
        }
    })
@app.route('/')
def index():
    """Serve complete dashboard with all features"""
    return render_template_string(HTML_COMPLETE_TEMPLATE)
@app.route('/api/debug/pypsa')
def debug_pypsa():
    """Debug PyPSA network state"""
    
    debug_info = {
        'buses': list(power_grid.network.buses.index),
        'loads': {},
        'generators': {},
        'total_load': 0,
        'total_generation': 0
    }
    
    # Check all loads
    for load_name in power_grid.network.loads.index:
        load_value = power_grid.network.loads.at[load_name, 'p_set']
        debug_info['loads'][load_name] = float(load_value)
        debug_info['total_load'] += float(load_value)
    
    # Check generators
    for gen_name in power_grid.network.generators.index:
        gen_p = power_grid.network.generators.at[gen_name, 'p_nom']
        debug_info['generators'][gen_name] = float(gen_p)
        debug_info['total_generation'] += float(gen_p)
    
    # Check if loads_t exists and has wrong values
    if hasattr(power_grid.network, 'loads_t') and hasattr(power_grid.network.loads_t, 'p'):
        debug_info['loads_t_sum'] = float(power_grid.network.loads_t.p.sum().sum())
        debug_info['loads_t_shape'] = power_grid.network.loads_t.p.shape
    
    return jsonify(debug_info)
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
                    # Extended kinematics and path info
                    edge_id = None
                    lane_id = None
                    lane_pos = None
                    lane_len = None
                    edge_shape = None
                    try:
                        edge_id = traci.vehicle.getRoadID(vehicle.id)
                        lane_id = traci.vehicle.getLaneID(vehicle.id)
                        lane_pos = traci.vehicle.getLanePosition(vehicle.id)
                        if lane_id:
                            lane_len = traci.lane.getLength(lane_id)
                        if edge_id and not edge_id.startswith(':'):
                            # Use cached shapes if available
                            try:
                                from __main__ import EDGE_SHAPES
                            except:
                                EDGE_SHAPES = {}
                            if edge_id in EDGE_SHAPES:
                                shape_xy = EDGE_SHAPES[edge_id]['xy']
                                edge_shape = EDGE_SHAPES[edge_id]['lonlat']
                            else:
                                shape_xy = traci.edge.getShape(edge_id)
                                edge_shape = []
                                for sx, sy in shape_xy:
                                    slon, slat = traci.simulation.convertGeo(sx, sy)
                                    edge_shape.append([slon, slat])
                                EDGE_SHAPES[edge_id] = {'xy': shape_xy, 'lonlat': edge_shape}
                            # Nearest point on XY polyline to (x,y)
                            best_d = 1e18
                            snap_x = x
                            snap_y = y
                            for i in range(len(shape_xy)-1):
                                x1, y1 = shape_xy[i]
                                x2, y2 = shape_xy[i+1]
                                dx = x2 - x1
                                dy = y2 - y1
                                L2 = dx*dx + dy*dy if dx*dx + dy*dy != 0 else 1e-9
                                t = ((x - x1)*dx + (y - y1)*dy) / L2
                                if t < 0:
                                    px, py = x1, y1
                                elif t > 1:
                                    px, py = x2, y2
                                else:
                                    px, py = x1 + dx*t, y1 + dy*t
                                d = ((x - px)**2 + (y - py)**2) ** 0.5
                                if d < best_d:
                                    best_d = d
                                    snap_x, snap_y = px, py
                            snap_lon, snap_lat = traci.simulation.convertGeo(snap_x, snap_y)
                    except:
                        pass
                    
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
                        'assigned_station': vehicle.assigned_ev_station,
                        'edge_id': edge_id,
                        'lane_id': lane_id,
                        'lane_pos': lane_pos,
                        'lane_len': lane_len,
                        'edge_shape': edge_shape,
                        'snap_lon': locals().get('snap_lon'),
                        'snap_lat': locals().get('snap_lat')
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
            
            # Preload edge shapes for road snapping (limit for faster start if needed)
            try:
                cached = preload_edge_shapes()
                print(f"Preloaded {cached} SUMO edge shapes")
            except Exception as e:
                print(f"Edge preload skipped: {e}")
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
    """Scenario control minimized per request. Only EV rush supported."""
    data = request.json or {}
    scenario_name = data.get('scenario', 'EV_RUSH')
    
    if not system_state['sumo_running']:
        return jsonify({'success': False, 'message': 'SUMO not running'})
    
    if scenario_name == 'EV_RUSH':
        spawned = sumo_manager.spawn_vehicles(30, 0.9)
        return jsonify({'success': True, 'scenario': 'EV_RUSH', 'spawned': spawned})
    
    return jsonify({'success': False, 'message': 'Only EV_RUSH is supported now'})

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
        # Update traffic lights - they go to YELLOW during blackout, not RED
        sumo_manager.update_traffic_lights()
        
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

# ==========================
# ML API ENDPOINTS
# ==========================

@app.route('/api/ml/dashboard')
def ml_dashboard():
    try:
        data = ml_engine.get_ml_dashboard_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/predict/demand')
def ml_predict_demand():
    try:
        hours = int(request.args.get('hours', 6))
        preds = ml_engine.predict_power_demand(next_hours=hours)
        return jsonify(preds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/optimize')
def ml_optimize():
    try:
        result = ml_engine.optimize_power_distribution()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/baselines')
def ml_baselines():
    try:
        baseline = {}
        if hasattr(ml_engine, 'compare_with_baselines'):
            baseline = ml_engine.compare_with_baselines()
        return jsonify(baseline)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/feature_importance')
def ml_feature_importance():
    try:
        demand_labels = ['hour', 'day_of_week', 'temperature', 'total_evs', 'current_load']
        charging_labels = ['hour', 'station_id', 'queue_length', 'avg_soc']
        imp = {
            'demand': {
                'labels': demand_labels,
                'importances': []
            },
            'charging': {
                'labels': charging_labels,
                'importances': []
            }
        }
        if hasattr(ml_engine.demand_predictor, 'feature_importances_'):
            imp['demand']['importances'] = [float(x) for x in ml_engine.demand_predictor.feature_importances_]
        if hasattr(ml_engine.charging_predictor, 'feature_importances_'):
            imp['charging']['importances'] = [float(x) for x in ml_engine.charging_predictor.feature_importances_]
        return jsonify(imp)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/advice', methods=['GET', 'POST'])
def ai_advice():
    """Generate AI advice that explains ML insights and next actions."""
    if not openai_client:
        return jsonify({'error': 'OPENAI_API_KEY not configured'}), 400
    try:
        data = ml_engine.get_ml_dashboard_data()
        # Optional custom question
        q = request.args.get('q')
        if request.method == 'POST':
            body = request.get_json(silent=True) or {}
            q = q or body.get('question')
        # Build concise context for the model
        context = {
            'time': data.get('timestamp'),
            'metrics': data.get('metrics', {}),
            'top_patterns': data.get('patterns', {}).get('top_patterns', []),
            'anomalies': data.get('anomalies', []),
            'optimization': data.get('optimization', {}),
        }
        if q:
            prompt = (
                "You are a Manhattan power grid assistant. Answer the operator's question "
                "specifically and concisely, then list 2-3 actionable steps. "
                "Context (JSON) is provided.\n"
                f"Question: {q}\n"
                f"Context: {json.dumps(context, default=str)}"
            )
        else:
            prompt = (
                "You are a Manhattan power grid assistant. Summarize the current situation "
                "in 3 bullet points, then list 3 prioritized operator actions with reasons. "
                "Be concise and specific. Context (JSON):\n" + json.dumps(context, default=str)
            )
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful power grid assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=350,
        )
        content = resp.choices[0].message.content
        return jsonify({'advice': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/report')
def ai_report():
    if not openai_client:
        return jsonify({'error': 'OPENAI_API_KEY not configured'}), 400
    try:
        data = ml_engine.get_ml_dashboard_data()
        # Gather quick grid snapshot
        snapshot = {
            'time': data.get('timestamp'),
            'metrics': data.get('metrics', {}),
            'anomalies': data.get('anomalies', []),
            'optimization': data.get('optimization', {}),
            'substations': [
                {
                    'name': sname,
                    'operational': sdata.get('operational', True),
                    'load_mw': sdata.get('load_mw')
                } for sname, sdata in getattr(ml_engine.integrated_system, 'substations', {}).items()
            ]
        }
        prompt = (
            "Create a concise executive report in markdown with sections: "
            "1) Summary (3-5 bullets), 2) Current Risks, 3) ML Insights (accuracy, patterns, anomalies), "
            "4) Optimization Recommendations, 5) Next Steps. Keep under 350 words. Context JSON follows.\n" +
            json.dumps(snapshot, default=str)
        )
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise executive assistant for power grid ops."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500,
        )
        content = resp.choices[0].message.content
        return jsonify({'report': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    <!-- Chatbot launcher -->
    <div id="chatbot-launcher" class="chatbot-launcher" title="Ask AI" onclick="toggleChatbot()">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 5.58 2 10c0 2.39 1.31 4.53 3.4 6.01-.14.52-.51 1.89-.59 2.24-.09.37.13.73.5.82.26.06.52-.03.7-.21.28-.27 1.25-1.2 1.77-1.7.79.22 1.63.34 2.52.34 5.52 0 10-3.58 10-8s-4.48-8-10-8Z" fill="#ffffff"/>
        </svg>
    </div>
    <!-- Chatbot window -->
    <div id="chatbot-window" class="chatbot-window">
        <div class="chat-header">
            <div class="chat-title"><span class="chat-avatar"></span> Manhattan AI Assistant</div>
            <button class="chat-close" onclick="toggleChatbot()">Close</button>
        </div>
        <div id="chat-messages" class="chat-messages"></div>
        <div class="chat-input">
            <input id="chat-input" placeholder="Ask about outages, demand, EVs, traffic…"/>
            <button class="btn btn-secondary chat-send" onclick="sendChatMessage()">Send</button>
        </div>
    </div>
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
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" onclick="startSUMO()" id="start-sumo-btn">
                    ▶️ Start Vehicles
                </button>
                <button class="btn btn-danger" onclick="stopSUMO()" id="stop-sumo-btn" disabled>
                    ⏹️ Stop Vehicles
                </button>
                <button class="btn btn-secondary" onclick="spawnVehicles(10)" id="spawn10-btn" disabled>
                    ➕ Add Cars
                </button>
            </div>
        </div>
        
        <!-- Scenario Selector removed per request -->
        
        <!-- Speed Control -->
        <div class="speed-control">
            <div class="section-title">⚡ Simulation Speed: <span id="speed-value">1.0x</span></div>
            <input type="range" class="speed-slider" id="speed-slider" 
                   min="0.1" max="5" step="0.1" value="1.0" 
                   onchange="setSimulationSpeed(this.value)">
        </div>
        
        <!-- Machine Learning Analytics -->
        <div class="ml-dashboard" style="margin: 20px 0; padding: 18px; background: linear-gradient(145deg, rgba(30, 20, 50, 0.95), rgba(20, 15, 35, 0.95)); border-radius: 16px; border: 1px solid rgba(138, 43, 226, 0.35); box-shadow: 0 18px 50px rgba(0,0,0,0.6);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <h3 style="font-size: 16px; color: #c8a2ff; letter-spacing: .2px;">🧠 Machine Learning Analytics</h3>
                <div style="font-size:11px;color:rgba(255,255,255,0.6);">Updated <span id="ml-updated">–</span></div>
            </div>
            <div class="ml-metrics" style="display:grid;grid-template-columns: repeat(4, 1fr);gap:10px;margin-bottom:12px;">
                <div class="ml-stat" style="padding:10px;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(255,255,255,0.04);">
                    <div style="font-size: 22px; font-weight: 800; color: #c8a2ff;" id="ml-accuracy">–</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.6);">Prediction Accuracy</div>
                </div>
                <div class="ml-stat" style="padding:10px;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(255,255,255,0.04);">
                    <div style="font-size: 22px; font-weight: 800; color: #00ff88;" id="ml-patterns">0</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.6);">Patterns Found</div>
                </div>
                <div class="ml-stat" style="padding:10px;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(255,255,255,0.04);">
                    <div style="font-size: 22px; font-weight: 800; color: #ff6b6b;" id="ml-anomalies">0</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.6);">Anomalies</div>
                </div>
                <div class="ml-stat" style="padding:10px;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(255,255,255,0.04);">
                    <div style="font-size: 22px; font-weight: 800; color: #4ecdc4;" id="ml-savings">0%</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.6);">Cost Savings</div>
                </div>
            </div>
            <div class="btn-group" style="display:flex;gap:8px;flex-wrap:wrap;">
                <button class="btn btn-secondary" onclick="showMLPredictions()">📈 Show Predictions</button>
                <button class="btn btn-secondary" onclick="runMLOptimization()">⚡ Optimize Grid</button>
                <button class="btn btn-secondary" onclick="askAIAdvice()">🤖 Ask AI</button>
                <button class="btn btn-secondary" onclick="showBaselines()">📐 Baselines</button>
                <button class="btn btn-secondary" onclick="downloadExecutiveReport()">📄 Executive Report</button>
            </div>
            <div id="ml-results" style="margin-top: 12px; padding: 10px; background: rgba(0,0,0,0.35); border-radius: 10px; font-size: 12px; display: none; border:1px solid rgba(255,255,255,0.06);"></div>
        </div>
        
        <!-- Substation Controls -->
        <div class="section-title">🏭 Substation Control</div>
        <div class="substation-grid" id="substation-controls"></div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
            <button class="btn btn-danger" onclick="triggerBlackout()">⚠️ BLACKOUT</button>
            <button class="btn btn-primary" onclick="restoreAll()">🔧 Restore All</button>
        </div>
        
        <!-- Action Buttons -->
        
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
    
    <!-- Global Red Alert Overlay -->
    <div id="blackout-alert" style="position: fixed; inset: 0; background: rgba(120,0,0,0.92); color: #fff; display: none; align-items: center; justify-content: center; z-index: 2000;">
        <div style="text-align: center; max-width: 700px; padding: 24px; border: 2px solid rgba(255,255,255,0.3); border-radius: 12px;">
            <div style="font-size: 38px; font-weight: 800; letter-spacing: 1px; margin-bottom: 8px;">🚨 CITYWIDE BLACKOUT</div>
            <div id="blackout-message" style="font-size: 22px; margin-bottom: 16px;">7 substations down • 1 operational (Midtown East)</div>
            <button onclick="dismissBlackoutAlert()" class="btn btn-primary" style="font-size: 16px; padding: 10px 18px;">Dismiss</button>
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
    
<!-- MANHATTAN POWER GRID - COMPLETE ULTRA SMOOTH SCRIPT -->
<!-- Copy and paste this entire script to replace your existing one -->

    <script>
    // ==========================================
    // PERFORMANCE CONFIGURATION FOR HIGH-END HARDWARE
    // ==========================================
    const PERFORMANCE_CONFIG = {
        renderMode: 'webgl',
        targetFPS: 144,
        dataUpdateRate: 60,  // Slightly slower update rate for smoother interpolation
        interpolationSteps: 1,
        useWebWorkers: false,
        useGPUAcceleration: true,
        vehiclePoolSize: 1000,
        enableAdvancedEffects: false,
        enablePrediction: false,
        smoothingFactor: 1,
        enableDebugMode: window.location.hash === '#debug'
    };

    // ==========================================
    // MAPBOX INITIALIZATION
    // ==========================================
    mapboxgl.accessToken = 'pk.eyJ1IjoibWFyb25veCIsImEiOiJjbWV1ODE5bHEwNGhoMmlvY2RleW51dWozIn0.FMrYdXLqnOwOEFi8qHSwxg';

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v11',
        center: [-73.980, 40.758],
        zoom: 14,
        pitch: 45,
        bearing: -20,
        antialias: true,
        preserveDrawingBuffer: PERFORMANCE_CONFIG.enableDebugMode,
        refreshExpiredTiles: false,
        fadeDuration: 0
    });

    // ==========================================
    // WEBGL VEHICLE RENDERER (GPU ACCELERATED)
    // ==========================================
    class WebGLVehicleRenderer {
        constructor(map) {
            this.map = map;
            this.vehicles = new Map();
            this.animationFrame = null;
            this.lastFrameTime = performance.now();
            this.frameCount = 0;
            this.fps = 0;
            
            this.gl = null;
            this.program = null;
            this.buffers = {};
            
            this.stats = {
                fps: 0,
                vehicles: 0,
                drawCalls: 0,
                updateTime: 0,
                renderTime: 0
            };
            
            this.initWebGL();
            this.initWorker();
        }
        
        initWebGL() {
            this.customLayer = {
                id: 'vehicle-webgl-layer',
                type: 'custom',
                
                onAdd: (map, gl) => {
                    this.gl = gl;
                    
                    const vertexShader = `
                        attribute vec2 a_position;
                        attribute vec3 a_color;
                        attribute float a_size;
                        
                        uniform mat4 u_matrix;
                        uniform float u_zoom;
                        
                        varying vec3 v_color;
                        
                        void main() {
                            float size = a_size * pow(2.0, u_zoom - 14.0);
                            gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);
                            gl_PointSize = size;
                            v_color = a_color;
                        }
                    `;
                    
                    const fragmentShader = `
                        precision mediump float;
                        varying vec3 v_color;
                        
                        void main() {
                            vec2 coord = 2.0 * gl_PointCoord - 1.0;
                            float dist = length(coord);
                            
                            if (dist > 1.0) {
                                discard;
                            }
                            
                            float alpha = 1.0 - smoothstep(0.5, 1.0, dist);
                            vec3 color = v_color;
                            
                            if (dist < 0.7) {
                                color = mix(color, vec3(1.0), 0.3 * (1.0 - dist));
                            }
                            
                            gl_FragColor = vec4(color, alpha);
                        }
                    `;
                    
                    const vs = this.compileShader(gl, vertexShader, gl.VERTEX_SHADER);
                    const fs = this.compileShader(gl, fragmentShader, gl.FRAGMENT_SHADER);
                    
                    this.program = gl.createProgram();
                    gl.attachShader(this.program, vs);
                    gl.attachShader(this.program, fs);
                    gl.linkProgram(this.program);
                    
                    this.attributes = {
                        position: gl.getAttribLocation(this.program, 'a_position'),
                        color: gl.getAttribLocation(this.program, 'a_color'),
                        size: gl.getAttribLocation(this.program, 'a_size')
                    };
                    
                    this.uniforms = {
                        matrix: gl.getUniformLocation(this.program, 'u_matrix'),
                        zoom: gl.getUniformLocation(this.program, 'u_zoom')
                    };
                    
                    this.buffers = {
                        position: gl.createBuffer(),
                        color: gl.createBuffer(),
                        size: gl.createBuffer()
                    };
                    
                    this.arrays = {
                        positions: new Float32Array(PERFORMANCE_CONFIG.vehiclePoolSize * 2),
                        colors: new Float32Array(PERFORMANCE_CONFIG.vehiclePoolSize * 3),
                        sizes: new Float32Array(PERFORMANCE_CONFIG.vehiclePoolSize)
                    };
                },
                
                render: (gl, matrix) => {
                    if (!this.program || this.vehicles.size === 0) return;
                    
                    const startTime = performance.now();
                    
                    gl.useProgram(this.program);
                    gl.uniformMatrix4fv(this.uniforms.matrix, false, matrix);
                    gl.uniform1f(this.uniforms.zoom, this.map.getZoom());
                    
                    let index = 0;
                    for (const [id, vehicle] of this.vehicles) {
                        const pos = this.getInterpolatedPosition(vehicle);
                        const projected = mapboxgl.MercatorCoordinate.fromLngLat([pos.lon, pos.lat]);
                        
                        this.arrays.positions[index * 2] = projected.x;
                        this.arrays.positions[index * 2 + 1] = projected.y;
                        
                        const color = this.getVehicleColor(vehicle.data);
                        this.arrays.colors[index * 3] = color.r;
                        this.arrays.colors[index * 3 + 1] = color.g;
                        this.arrays.colors[index * 3 + 2] = color.b;
                        
                        this.arrays.sizes[index] = vehicle.scale * 20;
                        index++;
                    }
                    
                    this.updateBuffer(gl, this.buffers.position, this.arrays.positions, this.attributes.position, 2, index);
                    this.updateBuffer(gl, this.buffers.color, this.arrays.colors, this.attributes.color, 3, index);
                    this.updateBuffer(gl, this.buffers.size, this.arrays.sizes, this.attributes.size, 1, index);
                    
                    gl.enable(gl.BLEND);
                    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
                    gl.drawArrays(gl.POINTS, 0, index);
                    gl.disable(gl.BLEND);
                    
                    this.stats.renderTime = performance.now() - startTime;
                    this.stats.drawCalls++;
                }
            };
            
            if (PERFORMANCE_CONFIG.renderMode === 'webgl') {
                this.map.addLayer(this.customLayer);
            }
        }
        
        initWorker() {
            // Disable worker for now - handle interpolation in main thread for better control
            this.worker = null;
            return;
        }
        compileShader(gl, source, type) {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            
            if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
                console.error('Shader compilation error:', gl.getShaderInfoLog(shader));
                gl.deleteShader(shader);
                return null;
            }
            
            return shader;
        }
        
        updateBuffer(gl, buffer, data, attribute, size, count) {
            gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
            gl.bufferData(gl.ARRAY_BUFFER, data.subarray(0, count * size), gl.DYNAMIC_DRAW);
            gl.enableVertexAttribArray(attribute);
            gl.vertexAttribPointer(attribute, size, gl.FLOAT, false, 0, 0);
        }
        getInterpolatedPosition(vehicle) {
            // Return the smoothly interpolated position
            return {
                lon: vehicle.currentLon || vehicle.targetLon || 0,
                lat: vehicle.currentLat || vehicle.targetLat || 0
            };
        } 
        updateVehicles(vehicleData) {
            const updateStartTime = performance.now();
            const currentTime = performance.now();
            
            vehicleData.forEach(data => {
                if (!this.vehicles.has(data.id)) {
                    // Initialize with all positions aligned - critical for smooth start
                    this.vehicles.set(data.id, {
                        id: data.id,
                        previousLon: data.lon,
                        previousLat: data.lat,
                        currentLon: data.lon,  // Important: start at actual position
                        currentLat: data.lat,   // Important: start at actual position
                        targetLon: data.lon,
                        targetLat: data.lat,
                        lastUpdateTime: currentTime,
                        interpolationProgress: 0,
                        velocityLon: 0,
                        velocityLat: 0,
                        angle: 0,
                        scale: 0,
                        targetScale: 1,
                        opacity: 0,
                        targetOpacity: 1,
                        data: data,
                        trail: []
                    });
                } else {
                    const vehicle = this.vehicles.get(data.id);
                    
                    // Only update if position actually changed (prevents micro-jitter)
                    const distanceMoved = Math.sqrt(
                        Math.pow(data.lon - vehicle.targetLon, 2) + 
                        Math.pow(data.lat - vehicle.targetLat, 2)
                    );
                    
                    if (distanceMoved > 0.000001) { // Tiny threshold
                        // Store current interpolated position as previous
                        vehicle.previousLon = vehicle.currentLon;
                        vehicle.previousLat = vehicle.currentLat;
                        
                        // Set new target
                        vehicle.targetLon = data.lon;
                        vehicle.targetLat = data.lat;
                        
                        // Reset interpolation
                        vehicle.interpolationProgress = 0;
                        vehicle.lastUpdateTime = currentTime;
                        
                        // Update angle
                        const dx = vehicle.targetLon - vehicle.previousLon;
                        const dy = vehicle.targetLat - vehicle.previousLat;
                        if (Math.abs(dx) > 0.00001 || Math.abs(dy) > 0.00001) {
                            vehicle.angle = Math.atan2(dy, dx);
                        }
                    }
                    
                    vehicle.data = data;
                }
            });
            
            // Handle removals
            const currentIds = new Set(vehicleData.map(v => v.id));
            for (const [id, vehicle] of this.vehicles) {
                if (!currentIds.has(id)) {
                    vehicle.targetOpacity = 0;
                    vehicle.targetScale = 0;
                    if (vehicle.opacity < 0.01) {
                        this.vehicles.delete(id);
                    }
                }
            }
            
            this.stats.updateTime = performance.now() - updateStartTime;
            this.stats.vehicles = this.vehicles.size;
        }
                
        // Replace the current interpolate method with this improved version
        interpolate(deltaTime) {
            const now = performance.now();
            
            for (const [id, vehicle] of this.vehicles) {
                // Calculate time since last server update
                const timeSinceUpdate = now - vehicle.lastUpdateTime;
                
                // Use actual update interval with small buffer
                const expectedUpdateInterval = PERFORMANCE_CONFIG.dataUpdateRate * 1.2; // 20% buffer
                vehicle.interpolationProgress = Math.min(1, timeSinceUpdate / expectedUpdateInterval);
                
                // Smoother easing function - sine wave for perfect smoothness
                const easeInOutSine = (t) => {
                    return -(Math.cos(Math.PI * t) - 1) / 2;
                };
                
                // Apply smooth easing
                const easedProgress = easeInOutSine(vehicle.interpolationProgress);
                
                // Add micro-smoothing for the last bit of movement
                const microSmooth = 0.02; // Tiny smoothing factor
                const targetLon = vehicle.previousLon + (vehicle.targetLon - vehicle.previousLon) * easedProgress;
                const targetLat = vehicle.previousLat + (vehicle.targetLat - vehicle.previousLat) * easedProgress;
                
                // Apply micro-smoothing to eliminate any remaining micro-stutters
                vehicle.currentLon = vehicle.currentLon * (1 - microSmooth) + targetLon * microSmooth;
                vehicle.currentLat = vehicle.currentLat * (1 - microSmooth) + targetLat * microSmooth;
                
                // Smooth scale animation
                const scaleSpeed = 0.08; // Slower for smoother appearance
                if (Math.abs(vehicle.targetScale - vehicle.scale) > 0.001) {
                    vehicle.scale += (vehicle.targetScale - vehicle.scale) * scaleSpeed;
                }
                
                // Smooth opacity animation
                const opacitySpeed = 0.08; // Slower for smoother fade
                if (Math.abs(vehicle.targetOpacity - vehicle.opacity) > 0.001) {
                    vehicle.opacity += (vehicle.targetOpacity - vehicle.opacity) * opacitySpeed;
                }
            }
            
            if (PERFORMANCE_CONFIG.renderMode === 'webgl') {
                this.map.triggerRepaint();
            }
        }
        
        updateFromWorker(positions) {
            positions.forEach(pos => {
                const vehicle = this.vehicles.get(pos.id);
                if (vehicle) {
                    vehicle.currentLon = pos.lon;
                    vehicle.currentLat = pos.lat;
                }
            });
        }
        
        getInterpolatedPosition(vehicle) {
            // Return the smoothly interpolated position
            return {
                lon: vehicle.currentLon || vehicle.targetLon || 0,
                lat: vehicle.currentLat || vehicle.targetLat || 0
            };
        }
        
        getVehicleColor(data) {
            let r, g, b;
            
            if (data.is_stranded) {
                const flash = Math.sin(performance.now() * 0.01) > 0;
                r = 1; g = 0; b = flash ? 1 : 0.5;
            } else if (data.is_charging) {
                r = 0; g = 1; b = 1;
            } else if (data.is_queued) {
                r = 1; g = 1; b = 0;
            } else if (data.is_circling) {
                r = 1; g = 0.55; b = 0;
            } else if (data.is_ev) {
                const battery = data.battery_percent || 100;
                if (battery < 20) {
                    r = 1; g = 0; b = 0;
                } else if (battery < 50) {
                    r = 1; g = 0.65; b = 0;
                } else {
                    r = 0; g = 1; b = 0;
                }
            } else {
                r = 0.4; g = 0.4; b = 1;
            }
            
            return { r, g, b };
        }
        
        getStats() {
            return this.stats;
        }
        
        clear() {
            this.vehicles.clear();
            if (this.worker) {
                this.worker.postMessage({ type: 'clear' });
            }
        }
    }

    // ==========================================
    // HYBRID DOM RENDERER (FALLBACK)
    // ==========================================
    class HybridVehicleRenderer {
        constructor(map) {
            this.map = map;
            this.vehicles = new Map();
            this.markerPool = [];
            this.activeMarkers = new Map();
            this.stats = { vehicles: 0, updateTime: 0, renderTime: 0 };
        }
        
        createMarker(data) {
            let el;
            if (this.markerPool.length > 0) {
                el = this.markerPool.pop();
                el.style.display = 'block';
            } else {
                el = document.createElement('div');
                el.className = 'vehicle-marker-ultra';
                el.style.cssText = `
                    position: absolute;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    border: 2px solid rgba(255,255,255,0.9);
                    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
                    will-change: transform;
                    transform: translate(-50%, -50%);
                    transition: transform 0.05s linear;
                    pointer-events: auto;
                    cursor: pointer;
                `;
            }
            
            el.style.background = this.getColor(data);
            
            const marker = new mapboxgl.Marker({
                element: el,
                anchor: 'center'
            }).setLngLat([data.lon, data.lat]).addTo(this.map);
            
            return marker;
        }
        
        updateVehicles(vehicleData) {
            const updateStartTime = performance.now();
            const currentTime = performance.now();
            
            vehicleData.forEach(data => {
                if (!this.vehicles.has(data.id)) {
                    // Initialize with all positions aligned - critical for smooth start
                    this.vehicles.set(data.id, {
                        id: data.id,
                        previousLon: data.lon,
                        previousLat: data.lat,
                        currentLon: data.lon,  // Important: start at actual position
                        currentLat: data.lat,   // Important: start at actual position
                        targetLon: data.lon,
                        targetLat: data.lat,
                        lastUpdateTime: currentTime,
                        interpolationProgress: 0,
                        velocityLon: 0,
                        velocityLat: 0,
                        angle: 0,
                        scale: 0,
                        targetScale: 1,
                        opacity: 0,
                        targetOpacity: 1,
                        data: data,
                        trail: []
                    });
                } else {
                    const vehicle = this.vehicles.get(data.id);
                    
                    // Only update if position actually changed (prevents micro-jitter)
                    const distanceMoved = Math.sqrt(
                        Math.pow(data.lon - vehicle.targetLon, 2) + 
                        Math.pow(data.lat - vehicle.targetLat, 2)
                    );
                    
                    if (distanceMoved > 0.000001) { // Tiny threshold
                        // Store current interpolated position as previous
                        vehicle.previousLon = vehicle.currentLon;
                        vehicle.previousLat = vehicle.currentLat;
                        
                        // Set new target
                        vehicle.targetLon = data.lon;
                        vehicle.targetLat = data.lat;
                        
                        // Reset interpolation
                        vehicle.interpolationProgress = 0;
                        vehicle.lastUpdateTime = currentTime;
                        
                        // Update angle
                        const dx = vehicle.targetLon - vehicle.previousLon;
                        const dy = vehicle.targetLat - vehicle.previousLat;
                        if (Math.abs(dx) > 0.00001 || Math.abs(dy) > 0.00001) {
                            vehicle.angle = Math.atan2(dy, dx);
                        }
                    }
                    
                    vehicle.data = data;
                }
            });
            
            // Handle removals
            const currentIds = new Set(vehicleData.map(v => v.id));
            for (const [id, vehicle] of this.vehicles) {
                if (!currentIds.has(id)) {
                    vehicle.targetOpacity = 0;
                    vehicle.targetScale = 0;
                    if (vehicle.opacity < 0.01) {
                        this.vehicles.delete(id);
                    }
                }
            }
            
            this.stats.updateTime = performance.now() - updateStartTime;
            this.stats.vehicles = this.vehicles.size;
        }
        
        interpolate(deltaTime) {
            const now = performance.now();
            
            for (const [id, vehicle] of this.vehicles) {
                // Calculate time since last server update
                const timeSinceUpdate = now - vehicle.lastUpdateTime;
                
                // Calculate interpolation progress (0 to 1)
                // Use a slightly longer interval to ensure smooth transition to next update
                const expectedUpdateInterval = PERFORMANCE_CONFIG.dataUpdateRate * 1.1;
                vehicle.interpolationProgress = Math.min(1, timeSinceUpdate / expectedUpdateInterval);
                
                // Smooth ease-in-out interpolation function
                const easeInOutCubic = (t) => {
                    return t < 0.5 
                        ? 4 * t * t * t 
                        : 1 - Math.pow(-2 * t + 2, 3) / 2;
                };
                
                // Apply easing to interpolation progress
                const easedProgress = easeInOutCubic(vehicle.interpolationProgress);
                
                // Interpolate position with easing
                vehicle.currentLon = vehicle.previousLon + 
                    (vehicle.targetLon - vehicle.previousLon) * easedProgress;
                vehicle.currentLat = vehicle.previousLat + 
                    (vehicle.targetLat - vehicle.previousLat) * easedProgress;
                
                // Smooth scale animation
                if (vehicle.scale !== vehicle.targetScale) {
                    const scaleDelta = vehicle.targetScale - vehicle.scale;
                    vehicle.scale += scaleDelta * 0.15;
                    if (Math.abs(scaleDelta) < 0.001) {
                        vehicle.scale = vehicle.targetScale;
                    }
                }
                
                // Smooth opacity animation
                if (vehicle.opacity !== vehicle.targetOpacity) {
                    const opacityDelta = vehicle.targetOpacity - vehicle.opacity;
                    vehicle.opacity += opacityDelta * 0.15;
                    if (Math.abs(opacityDelta) < 0.001) {
                        vehicle.opacity = vehicle.targetOpacity;
                    }
                }
            }
            
            // Trigger map repaint for WebGL rendering
            if (PERFORMANCE_CONFIG.renderMode === 'webgl') {
                this.map.triggerRepaint();
            }
        }
        
        getColor(data) {
            if (data.is_stranded) return '#ff00ff';
            if (data.is_charging) return '#00ffff';
            if (data.is_queued) return '#ffff00';
            if (data.is_circling) return '#ff8c00';
            if (data.is_ev) {
                const battery = data.battery_percent || 100;
                if (battery < 20) return '#ff0000';
                if (battery < 50) return '#ffa500';
                return '#00ff00';
            }
            return '#6464ff';
        }
        
        getStats() {
            return this.stats;
        }
        
        clear() {
            for (const [id, marker] of this.activeMarkers) {
                marker.remove();
            }
            this.activeMarkers.clear();
            this.vehicles.clear();
        }
    }

    // ==========================================
    // GLOBAL STATE
    // ==========================================
    let networkState = null;
    let vehicleRenderer = null;
    let substationMarkers = {};
    let evStationLayerInitialized = false;
    let lightsClickBound = false;
    let layers = {
        lights: true,
        vehicles: true,
        primary: true,
        secondary: true,
        ev: true
    };
    let sumoRunning = false;

    // ==========================================
    // PERFORMANCE MONITORING
    // ==========================================
    const performanceMonitor = {
        frameCount: 0,
        lastTime: performance.now(),
        fps: 0,
        
        update() {
            this.frameCount++;
            const now = performance.now();
            if (now - this.lastTime >= 1000) {
                this.fps = this.frameCount;
                this.frameCount = 0;
                this.lastTime = now;
                
                if (PERFORMANCE_CONFIG.enableDebugMode) {
                    this.updateDebugDisplay();
                }
            }
        },
        
        updateDebugDisplay() {
            let debugEl = document.getElementById('debug-overlay');
            if (!debugEl) {
                debugEl = document.createElement('div');
                debugEl.id = 'debug-overlay';
                debugEl.style.cssText = `
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: rgba(0,0,0,0.8);
                    color: #00ff00;
                    padding: 10px;
                    font-family: monospace;
                    font-size: 12px;
                    z-index: 9999;
                    border: 1px solid #00ff00;
                `;
                document.body.appendChild(debugEl);
            }
            
            const stats = vehicleRenderer ? vehicleRenderer.getStats() : {};
            debugEl.innerHTML = `
                <div>FPS: ${this.fps}</div>
                <div>Vehicles: ${stats.vehicles || 0}</div>
                <div>Update: ${(stats.updateTime || 0).toFixed(2)}ms</div>
                <div>Render: ${(stats.renderTime || 0).toFixed(2)}ms</div>
                <div>Mode: ${PERFORMANCE_CONFIG.renderMode}</div>
            `;
        }
    };

    // ==========================================
    // DATA MANAGEMENT
    // ==========================================
    const dataManager = {
        lastFetch: 0,
        cache: null,
        fetching: false,
        
        async fetchData() {
            if (this.fetching) return this.cache;
            
            const now = performance.now();
            if (this.cache && now - this.lastFetch < PERFORMANCE_CONFIG.dataUpdateRate) {
                return this.cache;
            }
            
            this.fetching = true;
            try {
                const response = await fetch('/api/network_state');
                const data = await response.json();
                this.cache = data;
                this.lastFetch = now;
                return data;
            } catch (error) {
                console.error('Error fetching data:', error);
                return this.cache;
            } finally {
                this.fetching = false;
            }
        }
    };

    // ==========================================
    // MAIN LOOPS
    // ==========================================
    async function updateLoop() {
        try {
            const response = await fetch('/api/network_state');
            const data = await response.json();
            
            if (data) {
                networkState = data;
                updateUI();
                
                // Update vehicles with new positions
                if (data.vehicles && layers.vehicles && vehicleRenderer) {
                    vehicleRenderer.updateVehicles(data.vehicles);
                }
                
                renderNetwork();
                renderEVStations();
            }
        } catch (error) {
            console.error('Error fetching data:', error);
        }
        
        // Consistent update interval
        setTimeout(updateLoop, PERFORMANCE_CONFIG.dataUpdateRate);
    }

    let lastAnimationTime = performance.now();
    let animationFrameId = null;

    function animationLoop(currentTime) {
        // Calculate delta time
        const deltaTime = currentTime - lastAnimationTime;
        lastAnimationTime = currentTime;
        
        // Cap delta time to prevent large jumps
        const cappedDeltaTime = Math.min(deltaTime, 50);
        
        // Always interpolate vehicles every frame
        if (vehicleRenderer && layers.vehicles) {
            vehicleRenderer.interpolate(cappedDeltaTime);
        }
        
        // Update performance monitor
        performanceMonitor.update();
        
        // Schedule next frame
        animationFrameId = requestAnimationFrame(animationLoop);
    }

    // ==========================================
    // UI UPDATES
    // ==========================================
    function updateUI() {
        if (!networkState) return;
        
        requestAnimationFrame(() => {
            const stats = networkState.statistics;
            
            const updates = {
                'traffic-lights': stats.total_traffic_lights,
                'powered-lights': stats.powered_traffic_lights,
                'load-mw': Math.round(stats.total_load_mw),
                'substations-online': `${stats.operational_substations}/${stats.total_substations}`,
                'green-count': stats.green_lights || 0,
                'yellow-count': stats.yellow_lights || 0,
                'red-count': stats.red_lights || 0,
                'black-count': stats.black_lights || 0,
                'total-load': Math.round(stats.total_load_mw)
            };
            
            Object.entries(updates).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value;
            });
            
            if (networkState.vehicle_stats) {
                const active = (networkState.vehicles || []).length;
                document.getElementById('active-vehicles').textContent = active;
                document.getElementById('ev-count').textContent = networkState.vehicle_stats.ev_vehicles || 0;
                document.getElementById('vehicle-count').textContent = active;
                document.getElementById('charging-stations').textContent = 
                    `${networkState.vehicle_stats.vehicles_charging || 0}/${networkState.vehicle_stats.vehicles_queued || 0}`;
            }
            
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
        });
    }

    // ==========================================
    // RENDERING FUNCTIONS
    // ==========================================
    function initializeRenderers() {
        if (PERFORMANCE_CONFIG.renderMode === 'webgl') {
            vehicleRenderer = new WebGLVehicleRenderer(map);
        } else {
            vehicleRenderer = new HybridVehicleRenderer(map);
        }
    }

    function initializeEVStationLayer() {
        if (evStationLayerInitialized) return;
        
        map.addSource('ev-stations', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });
        
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

        map.addLayer({
            id: 'ev-stations-badge-bg',
            type: 'circle',
            source: 'ev-stations',
            filter: ['>', ['get', 'charging_count'], 0],
            paint: {
                'circle-radius': [
                    'interpolate', ['linear'], ['zoom'],
                    12, 7,
                    16, 8,
                    18, 10
                ],
                'circle-color': [
                    'case',
                    ['>=', ['get', 'charging_count'], 20], '#ff0000',
                    ['>=', ['get', 'charging_count'], 15], '#ffa500',
                    ['>=', ['get', 'charging_count'], 10], '#ffff00',
                    '#00ff00'
                ],
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 2,
                'circle-opacity': 1.0,
                'circle-translate': [10, -10],
                'circle-translate-anchor': 'map'
            }
        });

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
        
        function onEVClick(e) {
            const props = e.features[0].properties;
            
            new mapboxgl.Popup()
                .setLngLat(e.lngLat)
                .setHTML(`
                    <strong>${props.name}</strong><br>
                    Status: <span style="color: ${props.operational ? '#00ff88' : '#ff0000'}">
                        ${props.operational ? '✅ Online' : '❌ Offline'}
                    </span><br>
                    ⚡ Charging: ${props.charging_count}/20<br>
                    Capacity: ${props.chargers} chargers<br>
                    Substation: ${props.substation}
                `)
                .addTo(map);
        }
        
        map.on('click', 'ev-stations-layer', onEVClick);
        map.on('click', 'ev-stations-icon', onEVClick);
        
        evStationLayerInitialized = true;
    }

    function renderNetwork() {
        if (!networkState) return;
        
        networkState.substations.forEach(sub => {
            if (!substationMarkers[sub.name]) {
                const el = document.createElement('div');
                el.className = 'substation-marker';
                el.style.cssText = `
                    width: 30px;
                    height: 30px;
                    border-radius: 50%;
                    border: 3px solid white;
                    cursor: pointer;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                `;
                
                const marker = new mapboxgl.Marker(el)
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
                '0 0 30px rgba(255,0,102,0.9)' :
                '0 0 30px rgba(255,0,0,0.9)';
                
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
                            'line-color': '#ffaa00',
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

    function renderEVStations() {
        if (!networkState || !networkState.ev_stations) {
            if (map.getLayer('ev-stations-layer')) {
                map.setLayoutProperty('ev-stations-layer', 'visibility', 'none');
            }
            return;
        }
        
        if (!evStationLayerInitialized && map.loaded()) {
            initializeEVStationLayer();
        }
        
        if (!map.getSource('ev-stations')) return;
        
        ['ev-stations-layer','ev-stations-icon','ev-stations-badge-bg','ev-stations-badge-text'].forEach(id => {
            if (map.getLayer(id)) {
                map.setLayoutProperty(id, 'visibility', layers.ev ? 'visible' : 'none');
            }
        });
        
        const features = networkState.ev_stations.map(ev => {
            let chargingCount = ev.vehicles_charging || 0;
            let queuedCount = ev.vehicles_queued || 0;
            
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
        
        const source = map.getSource('ev-stations');
        if (source) {
            source.setData({
                type: 'FeatureCollection',
                features: features
            });
        }
    }

    // ==========================================
    // CONTROL FUNCTIONS
    // ==========================================
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
            document.getElementById('spawn10-btn').disabled = true;
            
            if (vehicleRenderer) {
                vehicleRenderer.clear();
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

    async function triggerBlackout() {
        try {
            const subs = (networkState?.substations || []).map(s => s.name);
            const total = subs.length;
            showBlackoutAlert(total - 1, 1);
            for (const s of subs) {
                if (s !== 'Midtown East') {
                    await fetch(`/api/fail/${encodeURIComponent(s)}`, {method: 'POST'});
                }
            }
            await loadNetworkState();
        } catch (e) {
            console.error('Blackout error', e);
        }
    }

    async function testEVRush() {
        const response = await fetch('/api/test/ev_rush', {method: 'POST'});
        const result = await response.json();
        if (result.success) {
            alert(result.message);
        }
    }

    async function loadNetworkState() {
        try {
            const response = await fetch('/api/network_state');
            networkState = await response.json();
            updateUI();
            renderNetwork();
            if (layers.vehicles && vehicleRenderer && networkState.vehicles) {
                vehicleRenderer.updateVehicles(networkState.vehicles);
            }
            renderEVStations();
        } catch (error) {
            console.error('Error loading network state:', error);
        }
    }

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
            if (PERFORMANCE_CONFIG.renderMode === 'webgl' && map.getLayer('vehicle-webgl-layer')) {
                map.setLayoutProperty('vehicle-webgl-layer', 'visibility', layers[layer] ? 'visible' : 'none');
            }
            if (!layers[layer] && vehicleRenderer) {
                vehicleRenderer.clear();
            }
        } else if (layer === 'ev') {
            renderNetwork();
        }
    }

    function updateTime() {
        const now = new Date();
        document.getElementById('time').textContent = 
            now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }

    function showBlackoutAlert(failedCount, operationalCount) {
        const alertEl = document.getElementById('blackout-alert');
        const msg = document.getElementById('blackout-message');
        let onlineName = 'Midtown East';
        if (networkState && networkState.substations) {
            const online = networkState.substations.find(s => s.operational);
            if (online) onlineName = online.name;
        }
        msg.textContent = `${failedCount} stations down • ${operationalCount} on (${onlineName})`;
        alertEl.style.display = 'flex';
    }

    function dismissBlackoutAlert() {
        document.getElementById('blackout-alert').style.display = 'none';
    }

    // ==========================================
    // ML DASHBOARD FUNCTIONS
    // ==========================================
    async function updateMLDashboard() {
        try {
            const response = await fetch('/api/ml/dashboard');
            const data = await response.json();
            const accEl = document.getElementById('ml-accuracy');
            if (!accEl) return;
            accEl.textContent = `${100 - (data.metrics.demand_mape || 5)}%`;
            document.getElementById('ml-patterns').textContent = data.metrics.patterns_found || 0;
            document.getElementById('ml-anomalies').textContent = data.anomalies ? data.anomalies.length : 0;
            document.getElementById('ml-savings').textContent = `${data.metrics.optimization_savings || 0}%`;
            document.getElementById('ml-updated').textContent = new Date(data.timestamp).toLocaleTimeString('en-US', {hour12:false});
            if (data.anomalies && data.anomalies.length > 0) {
                const resultsDiv = document.getElementById('ml-results');
                if (resultsDiv) {
                    resultsDiv.style.display = 'block';
                    resultsDiv.innerHTML = '<strong>⚠️ Anomalies Detected:</strong><br>' +
                        data.anomalies.map(a => `${a.type}: ${a.description}`).join('<br>');
                }
            }
        } catch (e) {
            console.error('ML Dashboard error:', e);
        }
    }

    async function showMLPredictions() {
        const response = await fetch('/api/ml/predict/demand?hours=6');
        const predictions = await response.json();
        const resultsDiv = document.getElementById('ml-results');
        if (!resultsDiv) return;
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = '<strong>📊 Power Demand Predictions (Next 6 Hours):</strong><br>' +
            predictions.map(p => `Hour +${p.hour}: ${p.predicted_mw} MW (±${(p.confidence_upper - p.predicted_mw).toFixed(1)} MW)`).join('<br>');
    }

    async function runMLOptimization() {
        const response = await fetch('/api/ml/optimize');
        const optimization = await response.json();
        const resultsDiv = document.getElementById('ml-results');
        if (!resultsDiv) return;
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = '<strong>⚡ Optimization Recommendations:</strong><br>' +
            optimization.recommendations.map(r => `${r.type}: ${r.action} (Priority: ${r.priority})`).join('<br>') +
            `<br><strong>Total Savings: ${optimization.total_savings_mw} MW (${optimization.savings_percentage}%)</strong>`;
    }

    async function askAIAdvice() {
        let chat = document.getElementById('ai-chat');
        if (!chat) {
            chat = document.createElement('div');
            chat.id = 'ai-chat';
            chat.style.cssText = 'position:fixed;right:20px;bottom:20px;width:360px;max-height:60vh;background:rgba(20,20,30,0.98);border:1px solid rgba(138,43,226,0.4);border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.6);display:flex;flex-direction:column;z-index:1200;overflow:hidden;';
            chat.innerHTML = `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.1);">
                    <div style="font-weight:700;color:#8a2be2;">🤖 AI Assistant</div>
                    <button id="ai-close" class="btn btn-secondary" style="padding:6px 10px;font-size:12px;">Close</button>
                </div>
                <div id="ai-messages" style="padding:10px 12px;font-size:12px;line-height:1.4;overflow:auto;max-height:40vh;flex:1;"></div>
                <div style="display:flex;gap:6px;padding:10px 12px;border-top:1px solid rgba(255,255,255,0.1);">
                    <input id="ai-input" placeholder="Ask about grid status, ML, optimization…" style="flex:1;padding:8px 10px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(0,0,0,0.4);color:#fff;"/>
                    <button id="ai-send" class="btn btn-secondary">Send</button>
                </div>
            `;
            document.body.appendChild(chat);
            document.getElementById('ai-close').onclick = () => { chat.style.display = 'none'; };
            document.getElementById('ai-send').onclick = async () => {
                const box = document.getElementById('ai-messages');
                const input = document.getElementById('ai-input');
                const q = input.value.trim();
                if (!q) return;
                box.innerHTML += `<div><strong>You</strong>: ${q}</div>`;
                input.value = '';
                box.innerHTML += `<div>AI is typing…</div>`;
                box.scrollTop = box.scrollHeight;
                try {
                    const resp = await fetch('/api/ai/advice', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:q})});
                    const data = await resp.json();
                    if (data.advice) {
                        box.innerHTML += `<div style="margin-top:6px;color:#ddd;"><strong>AI</strong>: ${data.advice.replace(/\\n/g,'<br>')}</div>`;
                    } else {
                        box.innerHTML += `<div style="color:#f66;">Error: ${data.error||'Unknown'}</div>`;
                    }
                } catch(e) {
                    box.innerHTML += `<div style="color:#f66;">Request failed</div>`;
                }
                box.scrollTop = box.scrollHeight;
            };
        }
        chat.style.display = 'flex';
        const box = document.getElementById('ai-messages');
        box.innerHTML = 'Loading latest summary…';
        try {
            const resp = await fetch('/api/ai/advice');
            const data = await resp.json();
            if (data.advice) {
                box.innerHTML = `<div style="color:#ddd;">${data.advice.replace(/\\n/g,'<br>')}</div>`;
            } else {
                box.innerHTML = `<div style="color:#f66;">${data.error||'No response'}</div>`;
            }
        } catch(e) {
            box.innerHTML = '<div style="color:#f66;">AI request failed.</div>'
        }
    }

    async function showBaselines() {
        const r = await fetch('/api/ml/baselines');
        const data = await r.json();
        const resultsDiv = document.getElementById('ml-results');
        if (!resultsDiv) return;
        resultsDiv.style.display = 'block';
        if (data.method_comparison) {
            const rows = Object.entries(data.method_comparison)
            .map(([k,v]) => `${k}: MAPE ${v.MAPE}%, Runtime ${v.Runtime_ms}ms, Savings ${v.Cost_Savings}%`)
            .join('<br>');
            resultsDiv.innerHTML = '<strong>📐 Baselines:</strong><br>' + rows;
        } else {
            resultsDiv.textContent = 'No baseline data available.';
        }
    }

    async function downloadExecutiveReport() {
        try {
            const r = await fetch('/api/ai/report');
            const data = await r.json();
            if (!data.report) return alert(data.error || 'Report failed');
            const blob = new Blob([data.report], {type: 'text/markdown'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Executive_Report_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'_')}.md`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            alert('Report generation failed');
        }
    }

    // ==========================================
    // CHATBOT FUNCTIONS
    // ==========================================
    function toggleChatbot() {
        const launcher = document.getElementById('chatbot-launcher');
        const win = document.getElementById('chatbot-window');
        if (win.style.display === 'flex') {
            win.style.display = 'none';
            launcher.style.display = 'flex';
        } else {
            win.style.display = 'flex';
            launcher.style.display = 'none';
            const box = document.getElementById('chat-messages');
            box.innerHTML = '<div class="msg ai">Loading summary…</div>';
            fetch('/api/ai/advice').then(r=>r.json()).then(data=>{
                if (data.advice) {
                    box.innerHTML = `<div class=\"msg ai\">${data.advice.replace(/\\n/g,'<br>')}</div>`;
                } else {
                    box.innerHTML = `<div class=\"msg ai\" style=\"color:#f66;\">${data.error||'No response'}</div>`;
                }
            }).catch(()=>{
                box.innerHTML = '<div class="msg ai" style="color:#f66;">AI request failed.</div>';
            });
        }
    }

    function sendChatMessage() {
        const input = document.getElementById('chat-input');
        const text = (input.value||'').trim();
        if (!text) return;
        const box = document.getElementById('chat-messages');
        box.innerHTML += `<div class=\"msg user\"><strong>You:</strong> ${text}</div>`;
        box.innerHTML += `<div class=\"typing\">AI is typing…</div>`;
        const typingRef = box.querySelector('.typing');
        input.value = '';
        fetch('/api/ai/advice', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:text})})
        .then(r=>r.json()).then(data=>{
            if (typingRef) typingRef.remove();
            if (data.advice) {
                box.innerHTML += `<div class=\"msg ai\"><strong>AI:</strong> ${data.advice.replace(/\\n/g,'<br>')}</div>`;
            } else {
                box.innerHTML += `<div class=\"msg ai\" style=\"color:#f66;\"><strong>AI:</strong> ${data.error||'No response'}</div>`;
            }
            box.scrollTop = box.scrollHeight;
        }).catch(()=>{
            if (typingRef) typingRef.remove();
            box.innerHTML += '<div class="msg ai" style="color:#f66;"><strong>AI:</strong> Request failed</div>';
        });
    }

    // ==========================================
    // INITIALIZATION
    // ==========================================
    map.on('load', () => {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0%, 100% { transform: scale(1); opacity: 0.9; }
                50% { transform: scale(1.2); opacity: 1; }
            }
            
            .vehicle-marker-ultra {
                will-change: transform;
                backface-visibility: hidden;
                -webkit-backface-visibility: hidden;
                transform: translateZ(0);
                -webkit-transform: translateZ(0);
            }
            
            .mapboxgl-canvas {
                image-rendering: optimizeSpeed;
                image-rendering: -webkit-optimize-contrast;
            }
            
            * {
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
            }
        `;
        document.head.appendChild(style);
        
        initializeRenderers();
        initializeEVStationLayer();
        
        // Initialize vehicle renderer
        vehicleRenderer = new WebGLVehicleRenderer(map);
        
        // Start update loop
        updateLoop();
        
        // Start animation loop
        requestAnimationFrame(animationLoop);
        animationFrameId = requestAnimationFrame(animationLoop);
        setInterval(updateTime, 1000);
        updateTime();
        
        setInterval(updateMLDashboard, 5000);
        updateMLDashboard();
        
        console.log('🚀 Ultra-smooth vehicle system initialized!');
        console.log('Performance mode:', PERFORMANCE_CONFIG.renderMode);
        console.log('Target FPS:', PERFORMANCE_CONFIG.targetFPS);
    });

    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            map.resize();
        }, 100);
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