"""
Fixed Manhattan Integrated Simulation System
Properly handles SUMO network structure and edge parsing
"""

import os
import json
import threading
import queue
import time
import random
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET
from datetime import datetime

# SUMO imports
import traci
import sumolib

# Your existing imports
from core.power_system import ManhattanPowerGrid
from integrated_backend import ManhattanIntegratedSystem

class VehicleState(Enum):
    """Vehicle operational states"""
    NORMAL = "normal"
    REROUTING = "rerouting"
    CHARGING = "charging"
    STUCK = "stuck"
    EMERGENCY = "emergency"

@dataclass
class SmartVehicle:
    """Intelligent vehicle with decision-making capabilities"""
    id: str
    vtype: str
    is_ev: bool
    battery_level: float = 100.0
    battery_capacity: float = 75.0
    consumption_rate: float = 0.2
    state: VehicleState = VehicleState.NORMAL
    origin: str = ""
    destination: str = ""
    current_edge: str = ""
    target_charging_station: Optional[str] = None
    route_history: List[str] = field(default_factory=list)
    waiting_time: float = 0
    total_distance: float = 0
    power_grid_affected: bool = False

@dataclass
class SmartChargingStation:
    """Intelligent charging station with grid awareness"""
    id: str
    name: str
    edge_id: str
    junction_id: str
    lat: float
    lon: float
    substation: str
    capacity: int
    available_slots: int
    power_kw: float
    operational: bool = True
    vehicles_charging: List[str] = field(default_factory=list)
    vehicles_queued: List[str] = field(default_factory=list)
    grid_load_mw: float = 0

@dataclass
class TrafficLightState:
    """Traffic light with power dependency"""
    id: str
    junction_id: str
    substation: str
    powered: bool = True
    normal_program: str = "0"
    emergency_program: str = "emergency"
    affected_vehicles: List[str] = field(default_factory=list)

class FixedIntegratedSimulation:
    """Fixed integrated simulation that properly handles SUMO network"""
    
    def __init__(self, power_grid: ManhattanPowerGrid, integrated_system: ManhattanIntegratedSystem):
        # Core systems
        self.power_grid = power_grid
        self.integrated_system = integrated_system
        
        # SUMO configuration
        self.sumo_running = False
        self.sumo_port = 8813
        self.data_dir = 'data/sumo'
        self.network_file = os.path.join(self.data_dir, 'manhattan.net.xml')
        
        # Smart components
        self.vehicles: Dict[str, SmartVehicle] = {}
        self.charging_stations: Dict[str, SmartChargingStation] = {}
        self.traffic_lights: Dict[str, TrafficLightState] = {}
        
        # Valid edges for routing
        self.valid_edges = []
        self.major_edges = []
        self.all_junctions = []
        
        # System state
        self.simulation_step = 0
        self.failed_substations: set = set()
        self.affected_edges: set = set()
        self.rerouting_queue: queue.Queue = queue.Queue()
        
        # Metrics
        self.metrics = {
            'vehicles_affected': 0,
            'avg_waiting_time': 0,
            'reroutes_performed': 0,
            'charging_redirects': 0,
            'total_delay': 0,
            'grid_load_mw': 0
        }
        
        # Parse network first
        print("Parsing SUMO network...")
        self._parse_network_properly()
        
        # Then initialize infrastructure
        print("Initializing infrastructure...")
        self._initialize_infrastructure()
        
        print("=" * 60)
        print("FIXED INTEGRATED SIMULATION SYSTEM READY")
        print(f"  Valid edges: {len(self.valid_edges)}")
        print(f"  Major edges: {len(self.major_edges)}")
        print(f"  Traffic lights: {len(self.traffic_lights)}")
        print(f"  Charging stations: {len(self.charging_stations)}")
        print("=" * 60)
    
    def _parse_network_properly(self):
        """Properly parse SUMO network to get valid edges"""
        
        # Parse XML directly for better control
        tree = ET.parse(self.network_file)
        root = tree.getroot()
        
        # Get all edges
        edges = root.findall('.//edge')
        
        # Track edge categories
        major_streets = ['broadway', '5th', '7th', 'park', 'madison', 'lexington',
                        '42nd', '34th', '57th', 'times square', '8th', '6th']
        
        for edge in edges:
            edge_id = edge.get('id', '')
            
            # Skip internal edges (junction connectors)
            if edge_id.startswith(':'):
                continue
            
            # Check if edge allows passenger vehicles
            lanes = edge.findall('.//lane')
            allows_passenger = False
            
            for lane in lanes:
                allow = lane.get('allow', '')
                disallow = lane.get('disallow', '')
                
                # Check if passenger vehicles are allowed
                if not disallow or 'passenger' not in disallow:
                    if not allow or 'passenger' in allow or allow == 'all':
                        allows_passenger = True
                        break
            
            if allows_passenger and edge_id:
                self.valid_edges.append(edge_id)
                
                # Check if it's a major street
                edge_name = edge.get('name', '').lower()
                if edge_name and any(major in edge_name for major in major_streets):
                    self.major_edges.append(edge_id)
        
        # Get all junctions
        junctions = root.findall('.//junction')
        for junction in junctions:
            junction_id = junction.get('id', '')
            if junction_id and not junction_id.startswith(':'):
                self.all_junctions.append(junction_id)
        
        # If no major edges found, use some valid edges as major
        if not self.major_edges and self.valid_edges:
            self.major_edges = self.valid_edges[:min(20, len(self.valid_edges))]
        
        print(f"Found {len(self.valid_edges)} valid edges, {len(self.major_edges)} major edges")
    
    def _initialize_infrastructure(self):
        """Initialize infrastructure with fixed junction handling"""
        
        # Initialize charging stations
        self._init_charging_stations()
        
        # Initialize traffic lights (fixed)
        self._init_traffic_lights_fixed()
    
    def _init_charging_stations(self):
        """Create charging stations at valid locations"""
        
        ev_station_mappings = [
            ('CS_TimesSquare', 'Times Square Garage', 40.758, -73.985, 'Times Square'),
            ('CS_BryantPark', 'Bryant Park Station', 40.754, -73.984, 'Times Square'),
            ('CS_PennStation', 'Penn Station Hub', 40.750, -73.993, 'Penn Station'),
            ('CS_GrandCentral', 'Grand Central Charging', 40.752, -73.977, 'Grand Central'),
            ('CS_ColumbusCircle', 'Columbus Circle EV', 40.768, -73.982, 'Columbus Circle'),
            ('CS_MurrayHill', 'Murray Hill Garage', 40.748, -73.978, 'Murray Hill'),
        ]
        
        for i, (cs_id, name, lat, lon, substation) in enumerate(ev_station_mappings):
            # Assign to valid edges
            if i < len(self.valid_edges):
                edge_id = self.valid_edges[i * (len(self.valid_edges) // 6)]
            else:
                edge_id = random.choice(self.valid_edges) if self.valid_edges else "unknown"
            
            junction_id = self.all_junctions[i] if i < len(self.all_junctions) else "unknown"
            
            station = SmartChargingStation(
                id=cs_id,
                name=name,
                edge_id=edge_id,
                junction_id=junction_id,
                lat=lat,
                lon=lon,
                substation=substation,
                capacity=30,
                available_slots=30,
                power_kw=30 * 7.2,
                operational=True
            )
            
            self.charging_stations[cs_id] = station
    
    def _init_traffic_lights_fixed(self):
        """Initialize traffic lights with proper junction IDs"""
        
        # Parse network to get actual traffic light IDs
        tree = ET.parse(self.network_file)
        root = tree.getroot()
        
        # Get traffic light junctions
        tls_junctions = root.findall(".//junction[@type='traffic_light']")
        
        substations = list(self.integrated_system.substations.keys())
        
        for i, junction in enumerate(tls_junctions):
            junction_id = junction.get('id', '')
            
            if junction_id:
                # Assign to nearest substation (round-robin for simplicity)
                assigned_substation = substations[i % len(substations)]
                
                self.traffic_lights[junction_id] = TrafficLightState(
                    id=junction_id,
                    junction_id=junction_id,
                    substation=assigned_substation,
                    powered=True
                )
        
        print(f"Initialized {len(self.traffic_lights)} traffic lights")
    
    def generate_smart_vehicles(self, num_vehicles: int = 10) -> str:
        """Generate vehicles with proper edge selection"""
        
        print(f"\nGenerating {num_vehicles} smart vehicles...")
        
        if not self.valid_edges:
            print("ERROR: No valid edges found!")
            return None
        
        routes_file = os.path.join(self.data_dir, 'smart_routes.rou.xml')
        root = ET.Element('routes')
        
        # Vehicle type definitions
        vtypes = [
            {'id': 'car', 'color': '0.8,0.8,0.8', 'length': '4.5', 'battery': False},
            {'id': 'taxi', 'color': '1,1,0', 'length': '4.5', 'battery': False},
            {'id': 'ev_sedan', 'color': '0,1,0', 'length': '4.8', 'battery': True},
            {'id': 'ev_suv', 'color': '0,0.8,0.2', 'length': '5.2', 'battery': True},
        ]
        
        for vtype in vtypes:
            vt = ET.SubElement(root, 'vType')
            vt.set('id', vtype['id'])
            vt.set('color', vtype['color'])
            vt.set('length', vtype['length'])
            vt.set('accel', '2.6')
            vt.set('decel', '4.5')
            vt.set('sigma', '0.5')
            
            if vtype['battery']:
                param = ET.SubElement(vt, 'param')
                param.set('key', 'has.battery.device')
                param.set('value', 'true')
        
        # Generate vehicles using valid edges
        edges_to_use = self.major_edges if self.major_edges else self.valid_edges
        
        for i in range(num_vehicles):
            # 40% EVs, 40% cars, 20% taxis
            rand = random.random()
            if rand < 0.4:
                vtype = 'ev_sedan' if random.random() < 0.7 else 'ev_suv'
                is_ev = True
                battery = random.uniform(30, 90)
            elif rand < 0.8:
                vtype = 'car'
                is_ev = False
                battery = 100
            else:
                vtype = 'taxi'
                is_ev = False
                battery = 100
            
            # Select different origin and destination
            origin = random.choice(edges_to_use)
            destination = random.choice(edges_to_use)
            
            # Ensure they're different
            attempts = 0
            while destination == origin and attempts < 10:
                destination = random.choice(edges_to_use)
                attempts += 1
            
            # Create vehicle
            vehicle = SmartVehicle(
                id=f'veh_{i}',
                vtype=vtype,
                is_ev=is_ev,
                battery_level=battery,
                battery_capacity=75.0 if vtype == 'ev_sedan' else 100.0,
                origin=origin,
                destination=destination
            )
            
            self.vehicles[vehicle.id] = vehicle
            
            # Add to routes file
            trip = ET.SubElement(root, 'trip')
            trip.set('id', vehicle.id)
            trip.set('type', vtype)
            trip.set('depart', str(i * 3.0))
            trip.set('from', origin)
            trip.set('to', destination)
        
        # Write routes file
        tree = ET.ElementTree(root)
        tree.write(routes_file, encoding='utf-8', xml_declaration=True)
        
        print(f"✓ Generated {num_vehicles} vehicles")
        print(f"  - EVs: {sum(1 for v in self.vehicles.values() if v.is_ev)}")
        print(f"  - Regular: {sum(1 for v in self.vehicles.values() if not v.is_ev)}")
        print(f"  - Routes file: {routes_file}")
        
        return routes_file
    
    def start_integrated_simulation(self, num_vehicles: int = 10):
        """Start the simulation with proper error handling"""
        
        print("\n" + "=" * 60)
        print("STARTING FIXED INTEGRATED SIMULATION")
        print("Mode: Headless (no GUI)")
        print("Vehicles: " + str(num_vehicles))
        print("=" * 60)
        
        # Generate vehicles
        routes_file = self.generate_smart_vehicles(num_vehicles)
        
        if not routes_file:
            print("ERROR: Could not generate routes!")
            return
        
        # Additional files that exist
        add_files = []
        traffic_lights_file = os.path.join(self.data_dir, 'traffic_lights.add.xml')
        types_file = os.path.join(self.data_dir, 'types.add.xml')
        
        if os.path.exists(traffic_lights_file):
            add_files.append(traffic_lights_file)
        if os.path.exists(types_file):
            add_files.append(types_file)
        
        # Start SUMO
        sumo_cmd = [
            'sumo',  # Headless
            '-n', self.network_file,
            '-r', routes_file,
            '--step-length', '1.0',
            '--no-step-log',
            '--no-warnings',
            '--duration-log.disable',
            '--collision.action', 'warn',
            '--routing-algorithm', 'dijkstra',
            '--device.rerouting.probability', '1.0',
            '--device.rerouting.period', '60',
            '--time-to-teleport', '300',
            '--no-internal-links',  # Simplify network
            '--ignore-junction-blocker', '1'  # Prevent deadlocks
        ]
        
        # Add additional files
        for add_file in add_files:
            sumo_cmd.extend(['-a', add_file])
        
        try:
            print("Starting SUMO...")
            traci.start(sumo_cmd, port=self.sumo_port)
            self.sumo_running = True
            print("✓ SUMO started successfully")
            
            # Run simulation
            self._run_simulation()
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.sumo_running:
                traci.close()
                self.sumo_running = False
    
    def _run_simulation(self):
        """Main simulation loop with better error handling"""
        
        print("\nSimulation running...")
        print("-" * 40)
        
        max_steps = 600  # 10 minutes
        
        try:
            while self.sumo_running and self.simulation_step < max_steps:
                # Check if simulation should continue
                if traci.simulation.getMinExpectedNumber() <= 0:
                    print("All vehicles completed their routes")
                    break
                
                # Step simulation
                traci.simulationStep()
                self.simulation_step += 1
                
                # Update vehicle states
                self._update_vehicles()
                
                # Handle EV charging
                self._manage_ev_charging()
                
                # Update metrics
                self._update_metrics()
                
                # Status update every 30 steps
                if self.simulation_step % 30 == 0:
                    self._print_status()
                
                # Process any pending reroutes
                self._process_rerouting_queue()
                
        except Exception as e:
            print(f"Simulation error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("SIMULATION COMPLETE")
        self._print_final_metrics()
        print("=" * 60)
    
    def _update_vehicles(self):
        """Update vehicle states with error handling"""
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for veh_id in vehicle_ids:
                if veh_id in self.vehicles:
                    vehicle = self.vehicles[veh_id]
                    
                    try:
                        vehicle.current_edge = traci.vehicle.getRoadID(veh_id)
                        vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                        vehicle.total_distance = traci.vehicle.getDistance(veh_id)
                        
                        # Update battery for EVs
                        if vehicle.is_ev:
                            distance_km = vehicle.total_distance / 1000
                            battery_used = distance_km * vehicle.consumption_rate
                            vehicle.battery_level = max(0, vehicle.battery_level - battery_used)
                            
                            # Check if needs charging
                            if vehicle.battery_level < 20 and vehicle.state != VehicleState.CHARGING:
                                self._route_to_charging(vehicle)
                        
                        # Check if stuck
                        if vehicle.waiting_time > 120:
                            vehicle.state = VehicleState.STUCK
                            
                    except traci.TraCIException:
                        pass
        except Exception as e:
            pass
    
    def _manage_ev_charging(self):
        """Manage EV charging with error handling"""
        
        for station in self.charging_stations.values():
            if not station.operational:
                continue
            
            try:
                vehicles_on_edge = traci.edge.getLastStepVehicleIDs(station.edge_id)
                
                for veh_id in vehicles_on_edge:
                    if veh_id in self.vehicles:
                        vehicle = self.vehicles[veh_id]
                        
                        if vehicle.is_ev and vehicle.battery_level < 80:
                            # Start charging
                            if veh_id not in station.vehicles_charging:
                                if len(station.vehicles_charging) < station.capacity:
                                    station.vehicles_charging.append(veh_id)
                                    vehicle.state = VehicleState.CHARGING
                                    
                                    # Stop vehicle for charging
                                    try:
                                        traci.vehicle.setStop(
                                            veh_id, 
                                            station.edge_id,
                                            pos=10.0,
                                            duration=60
                                        )
                                    except:
                                        pass
                        
                        # Simulate charging
                        if veh_id in station.vehicles_charging:
                            vehicle.battery_level = min(100, vehicle.battery_level + 2)
                            
                            if vehicle.battery_level >= 80:
                                station.vehicles_charging.remove(veh_id)
                                vehicle.state = VehicleState.NORMAL
                                
                                try:
                                    traci.vehicle.resume(veh_id)
                                except:
                                    pass
                                
            except Exception:
                pass
            
            # Update power grid load
            station.grid_load_mw = len(station.vehicles_charging) * 0.0072
    
    def _route_to_charging(self, vehicle: SmartVehicle):
        """Route EV to charging with error handling"""
        
        # Find operational station
        operational_stations = [s for s in self.charging_stations.values() if s.operational]
        
        if operational_stations:
            station = random.choice(operational_stations)
            
            try:
                traci.vehicle.changeTarget(vehicle.id, station.edge_id)
                vehicle.state = VehicleState.REROUTING
                vehicle.target_charging_station = station.id
                self.metrics['charging_redirects'] += 1
                
                print(f"  EV {vehicle.id}: Battery {vehicle.battery_level:.1f}% -> {station.name}")
            except:
                pass
    
    def trigger_substation_failure(self, substation_name: str):
        """Trigger substation failure with proper handling"""
        
        print(f"\n⚡ SUBSTATION FAILURE: {substation_name}")
        print("-" * 40)
        
        self.failed_substations.add(substation_name)
        
        # Fail traffic lights
        affected_tls = 0
        for tl in self.traffic_lights.values():
            if tl.substation == substation_name:
                tl.powered = False
                affected_tls += 1
                
                # Try to set traffic light to red
                if self.sumo_running:
                    try:
                        traci.trafficlight.setRedYellowGreenState(tl.id, 'rrrrrrrrrrrrrrrr')
                    except:
                        pass
        
        print(f"  ✗ {affected_tls} traffic lights failed")
        
        # Fail charging stations
        affected_stations = 0
        for station in self.charging_stations.values():
            if station.substation == substation_name:
                station.operational = False
                station.available_slots = 0
                affected_stations += 1
                
                # Clear charging vehicles
                for veh_id in station.vehicles_charging[:]:
                    if veh_id in self.vehicles:
                        self.vehicles[veh_id].state = VehicleState.EMERGENCY
                        try:
                            if self.sumo_running:
                                traci.vehicle.resume(veh_id)
                        except:
                            pass
                
                station.vehicles_charging.clear()
        
        print(f"  ✗ {affected_stations} charging stations offline")
        
        # Count affected vehicles
        if self.sumo_running:
            try:
                vehicle_ids = traci.vehicle.getIDList()
                self.metrics['vehicles_affected'] = len(vehicle_ids)
                print(f"  ⚠ {len(vehicle_ids)} vehicles potentially affected")
            except:
                pass
        
        print("-" * 40)
    
    def restore_substation(self, substation_name: str):
        """Restore substation"""
        
        print(f"\n✓ RESTORING SUBSTATION: {substation_name}")
        
        if substation_name in self.failed_substations:
            self.failed_substations.remove(substation_name)
        
        # Restore traffic lights
        for tl in self.traffic_lights.values():
            if tl.substation == substation_name:
                tl.powered = True
                if self.sumo_running:
                    try:
                        traci.trafficlight.setProgram(tl.id, tl.normal_program)
                    except:
                        pass
        
        # Restore charging stations
        for station in self.charging_stations.values():
            if station.substation == substation_name:
                station.operational = True
                station.available_slots = station.capacity
        
        print(f"✓ Substation {substation_name} restored")
    
    def _process_rerouting_queue(self):
        """Process rerouting queue"""
        
        while not self.rerouting_queue.empty():
            try:
                veh_id = self.rerouting_queue.get_nowait()
                if veh_id in self.vehicles:
                    vehicle = self.vehicles[veh_id]
                    
                    if vehicle.is_ev and vehicle.battery_level < 30:
                        self._route_to_charging(vehicle)
                        
            except queue.Empty:
                break
    
    def _update_metrics(self):
        """Update metrics with error handling"""
        
        if not self.sumo_running:
            return
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            if vehicle_ids:
                total_waiting = sum(traci.vehicle.getWaitingTime(v) for v in vehicle_ids)
                self.metrics['avg_waiting_time'] = total_waiting / len(vehicle_ids)
                
                self.metrics['total_delay'] = sum(
                    traci.vehicle.getAccumulatedWaitingTime(v) for v in vehicle_ids
                )
                
                self.metrics['grid_load_mw'] = sum(
                    s.grid_load_mw for s in self.charging_stations.values()
                )
                
        except:
            pass
    
    def _print_status(self):
        """Print status with error handling"""
        
        try:
            num_vehicles = traci.simulation.getVehicleNumber()
            
            if num_vehicles > 0:
                evs_charging = sum(
                    len(s.vehicles_charging) for s in self.charging_stations.values()
                )
                
                stuck = sum(1 for v in self.vehicles.values() if v.state == VehicleState.STUCK)
                
                print(f"Step {self.simulation_step}: {num_vehicles} vehicles | "
                      f"EVs charging: {evs_charging} | "
                      f"Stuck: {stuck} | "
                      f"Avg wait: {self.metrics['avg_waiting_time']:.1f}s | "
                      f"Grid: {self.metrics['grid_load_mw']:.2f}MW")
                
                if self.failed_substations:
                    print(f"  ⚠ Failed: {', '.join(self.failed_substations)}")
                    
        except:
            pass
    
    def _print_final_metrics(self):
        """Print final metrics"""
        
        print("\nFINAL METRICS:")
        print(f"  Vehicles affected: {self.metrics['vehicles_affected']}")
        print(f"  Reroutes: {self.metrics['reroutes_performed']}")
        print(f"  EV charging redirects: {self.metrics['charging_redirects']}")
        print(f"  Total delay: {self.metrics['total_delay']:.1f}s")
        print(f"  Peak grid load: {self.metrics['grid_load_mw']:.2f}MW")
        
        if self.vehicles:
            ev_count = sum(1 for v in self.vehicles.values() if v.is_ev)
            if ev_count > 0:
                avg_battery = np.mean([v.battery_level for v in self.vehicles.values() if v.is_ev])
                print(f"\nVEHICLE STATISTICS:")
                print(f"  Total vehicles: {len(self.vehicles)}")
                print(f"  EVs: {ev_count}")
                print(f"  Average EV battery: {avg_battery:.1f}%")
    
    def get_real_time_state(self) -> Dict[str, Any]:
        """Get current state for web interface"""
        
        state = {
            'simulation_step': self.simulation_step,
            'vehicles': [],
            'charging_stations': [],
            'traffic_lights': [],
            'metrics': self.metrics,
            'failed_substations': list(self.failed_substations)
        }
        
        # Get vehicle data
        if self.sumo_running:
            try:
                for veh_id in traci.vehicle.getIDList():
                    if veh_id in self.vehicles:
                        vehicle = self.vehicles[veh_id]
                        
                        try:
                            pos = traci.vehicle.getPosition(veh_id)
                            # Simple conversion (you'd use proper projection in production)
                            lon = -73.98 + (pos[0] / 10000)
                            lat = 40.75 + (pos[1] / 10000)
                            
                            state['vehicles'].append({
                                'id': veh_id,
                                'type': vehicle.vtype,
                                'lat': lat,
                                'lon': lon,
                                'battery': vehicle.battery_level if vehicle.is_ev else None,
                                'state': vehicle.state.value,
                                'speed': traci.vehicle.getSpeed(veh_id) * 3.6
                            })
                        except:
                            pass
            except:
                pass
        
        # Charging station status
        for station in self.charging_stations.values():
            state['charging_stations'].append({
                'id': station.id,
                'name': station.name,
                'lat': station.lat,
                'lon': station.lon,
                'operational': station.operational,
                'vehicles_charging': len(station.vehicles_charging),
                'capacity': station.capacity,
                'grid_load_mw': station.grid_load_mw
            })
        
        return state


def test_fixed_system():
    """Test the fixed simulation system"""
    
    print("\n" + "=" * 60)
    print("TESTING FIXED INTEGRATED SIMULATION")
    print("=" * 60)
    
    # Initialize systems
    print("\nInitializing power grid...")
    power_grid = ManhattanPowerGrid()
    
    print("Initializing integrated backend...")
    integrated_system = ManhattanIntegratedSystem(power_grid)
    
    # Create fixed simulation
    print("Creating fixed simulation system...")
    sim = FixedIntegratedSimulation(power_grid, integrated_system)
    
    # Start simulation in thread
    def run_simulation():
        sim.start_integrated_simulation(num_vehicles=10)
    
    sim_thread = threading.Thread(target=run_simulation)
    sim_thread.start()
    
    # Wait for simulation to start
    time.sleep(5)
    
    # Test substation failure after 30 seconds
    print("\nWaiting 30 seconds before testing failure...")
    time.sleep(30)
    
    print("\n" + "!" * 60)
    print("TRIGGERING TEST: Times Square Failure")
    print("!" * 60)
    sim.trigger_substation_failure('Times Square')
    
    # Let it run with failure
    time.sleep(60)
    
    # Restore
    print("\n" + "!" * 60)
    print("RESTORING: Times Square")
    print("!" * 60)
    sim.restore_substation('Times Square')
    
    # Wait for completion
    sim_thread.join()
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_fixed_system()