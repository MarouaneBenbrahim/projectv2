"""
Manhattan Integrated Simulation System - World Class Implementation
Complete integration: Power Grid (PyPSA) + Traffic Lights + Vehicles (SUMO)
Real-time cascading effects and intelligent rerouting
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
    STUCK = "stuck"  # At failed traffic light
    EMERGENCY = "emergency"  # Finding alternate charging

@dataclass
class SmartVehicle:
    """Intelligent vehicle with decision-making capabilities"""
    id: str
    vtype: str
    is_ev: bool
    battery_level: float = 100.0
    battery_capacity: float = 75.0  # kWh
    consumption_rate: float = 0.2  # kWh/km
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

class IntegratedSimulationSystem:
    """
    World-class integrated system orchestrating:
    - Power Grid (PyPSA)
    - Traffic Infrastructure
    - Vehicle Behavior (SUMO)
    """
    
    def __init__(self, power_grid: ManhattanPowerGrid, integrated_system: ManhattanIntegratedSystem):
        # Core systems
        self.power_grid = power_grid
        self.integrated_system = integrated_system
        
        # SUMO configuration
        self.sumo_running = False
        self.sumo_port = 8813
        self.data_dir = 'data/sumo'
        self.network_file = os.path.join(self.data_dir, 'manhattan.net.xml')
        
        # Load network
        self.net = sumolib.net.readNet(self.network_file)
        
        # Smart components
        self.vehicles: Dict[str, SmartVehicle] = {}
        self.charging_stations: Dict[str, SmartChargingStation] = {}
        self.traffic_lights: Dict[str, TrafficLightState] = {}
        
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
        
        # Initialize components
        self._initialize_infrastructure()
        
        print("=" * 60)
        print("INTEGRATED SIMULATION SYSTEM INITIALIZED")
        print(f"  Power Grid: {len(self.integrated_system.substations)} substations")
        print(f"  Traffic Lights: {len(self.traffic_lights)} intersections")
        print(f"  Charging Stations: {len(self.charging_stations)} locations")
        print("=" * 60)
    
    def _initialize_infrastructure(self):
        """Initialize all infrastructure components with grid mapping"""
        
        # Initialize charging stations from power grid
        self._init_charging_stations()
        
        # Initialize traffic lights with power dependencies
        self._init_traffic_lights()
        
        # Map infrastructure to edges for routing
        self._map_infrastructure_to_network()
    
    def _init_charging_stations(self):
        """Create charging stations matching power grid"""
        
        # Map your EV stations to SUMO network
        ev_station_mappings = [
            ('CS_TimesSquare', 'Times Square Garage', 40.758, -73.985, 'Times Square'),
            ('CS_BryantPark', 'Bryant Park Station', 40.754, -73.984, 'Times Square'),
            ('CS_PennStation', 'Penn Station Hub', 40.750, -73.993, 'Penn Station'),
            ('CS_GrandCentral', 'Grand Central Charging', 40.752, -73.977, 'Grand Central'),
            ('CS_ColumbusCircle', 'Columbus Circle EV', 40.768, -73.982, 'Columbus Circle'),
            ('CS_MurrayHill', 'Murray Hill Garage', 40.748, -73.978, 'Murray Hill'),
        ]
        
        for cs_id, name, lat, lon, substation in ev_station_mappings:
            # Find nearest edge and junction
            x, y = self.net.convertLonLat2XY(lon, lat)
            edges = self.net.getNeighboringEdges(x, y, r=200)
            
            if edges:
                closest_edge, dist = edges[0]
                edge_id = closest_edge.getID()
                
                # Get junction
                to_node = closest_edge.getToNode()
                junction_id = to_node.getID() if to_node else ""
                
                station = SmartChargingStation(
                    id=cs_id,
                    name=name,
                    edge_id=edge_id,
                    junction_id=junction_id,
                    lat=lat,
                    lon=lon,
                    substation=substation,
                    capacity=30,  # 30 charging slots
                    available_slots=30,
                    power_kw=30 * 7.2,  # 7.2kW per charger
                    operational=True
                )
                
                self.charging_stations[cs_id] = station
    
    def _init_traffic_lights(self):
        """Initialize traffic lights with substation dependencies"""
        
        # Get all traffic lights from network
        tls_ids = self.net.getTrafficLights()
        
        for tl in tls_ids:
            tl_id = tl.getID()
            
            # Find location
            connections = tl.getConnections()
            if connections:
                edge = connections[0][0]  # Get first connection's edge
                coord = edge.getShape()[0]
                lon, lat = self.net.convertXY2LonLat(coord[0], coord[1])
                
                # Assign to nearest substation
                min_dist = float('inf')
                assigned_substation = 'Times Square'  # Default
                
                for sub_name, sub_data in self.integrated_system.substations.items():
                    dist = np.sqrt((lat - sub_data['lat'])**2 + (lon - sub_data['lon'])**2)
                    if dist < min_dist:
                        min_dist = dist
                        assigned_substation = sub_name
                
                self.traffic_lights[tl_id] = TrafficLightState(
                    id=tl_id,
                    junction_id=tl_id,
                    substation=assigned_substation,
                    powered=True
                )
    
    def _map_infrastructure_to_network(self):
        """Create mapping of infrastructure to network edges"""
        
        self.substation_edges = {}
        
        # Map each substation to affected edges
        for sub_name in self.integrated_system.substations:
            affected_edges = set()
            
            # Get edges near traffic lights of this substation
            for tl in self.traffic_lights.values():
                if tl.substation == sub_name:
                    # Get edges connected to this junction
                    node = self.net.getNode(tl.junction_id)
                    if node:
                        for edge in node.getIncoming():
                            affected_edges.add(edge.getID())
                        for edge in node.getOutgoing():
                            affected_edges.add(edge.getID())
            
            self.substation_edges[sub_name] = affected_edges
    
    def generate_smart_vehicles(self, num_vehicles: int = 10) -> str:
        """Generate intelligent vehicles with realistic patterns"""
        
        print(f"\nGenerating {num_vehicles} smart vehicles...")
        
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
                # Add battery device
                param = ET.SubElement(vt, 'param')
                param.set('key', 'has.battery.device')
                param.set('value', 'true')
        
        # Get all normal edges (not internal)
        edges = [e for e in self.net.getEdges() if not e.getID().startswith(':')]
        valid_edges = [e.getID() for e in edges if e.allows('passenger')]
        
        if len(valid_edges) < 2:
            print("Warning: Not enough valid edges for routing")
            return routes_file
        
        # Generate vehicles
        for i in range(num_vehicles):
            # 40% EVs, 40% cars, 20% taxis
            rand = random.random()
            if rand < 0.4:
                vtype = 'ev_sedan' if random.random() < 0.7 else 'ev_suv'
                is_ev = True
                battery = random.uniform(30, 90)  # 30-90% charge
            elif rand < 0.8:
                vtype = 'car'
                is_ev = False
                battery = 100
            else:
                vtype = 'taxi'
                is_ev = False
                battery = 100
            
            # Select origin and destination
            origin = random.choice(valid_edges)
            destination = random.choice(valid_edges)
            while destination == origin:
                destination = random.choice(valid_edges)
            
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
            trip.set('depart', str(i * 3.0))  # Stagger departures
            trip.set('from', origin)
            trip.set('to', destination)
        
        # Write routes file
        tree = ET.ElementTree(root)
        tree.write(routes_file, encoding='utf-8', xml_declaration=True)
        
        print(f"✓ Generated {num_vehicles} vehicles")
        print(f"  - EVs: {sum(1 for v in self.vehicles.values() if v.is_ev)}")
        print(f"  - Regular: {sum(1 for v in self.vehicles.values() if not v.is_ev)}")
        
        return routes_file
    
    def start_integrated_simulation(self, num_vehicles: int = 10):
        """Start the complete integrated simulation"""
        
        print("\n" + "=" * 60)
        print("STARTING INTEGRATED SIMULATION")
        print("Mode: Headless (no GUI)")
        print("Vehicles: " + str(num_vehicles))
        print("=" * 60)
        
        # Generate vehicles
        routes_file = self.generate_smart_vehicles(num_vehicles)
        
        # Start SUMO
        sumo_cmd = [
            'sumo',  # Headless
            '-n', self.network_file,
            '-r', routes_file,
            '--step-length', '1.0',
            '--no-step-log',
            '--no-warnings',
            '--duration-log.disable',
            '--device.emissions.probability', '1.0',
            '--device.battery.probability', '1.0',
            '--collision.action', 'warn',
            '--routing-algorithm', 'dijkstra',
            '--device.rerouting.probability', '1.0',
            '--device.rerouting.period', '60',
            '--time-to-teleport', '300'
        ]
        
        try:
            traci.start(sumo_cmd, port=self.sumo_port)
            self.sumo_running = True
            print("✓ SUMO started successfully")
            
            # Run simulation
            self._run_simulation()
            
        except Exception as e:
            print(f"✗ Error: {e}")
        finally:
            if self.sumo_running:
                traci.close()
                self.sumo_running = False
    
    def _run_simulation(self):
        """Main simulation loop"""
        
        print("\nSimulation running...")
        print("-" * 40)
        
        while self.sumo_running and traci.simulation.getMinExpectedNumber() > 0:
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
            
            # Stop after 600 steps (10 minutes)
            if self.simulation_step >= 600:
                break
        
        print("\n" + "=" * 60)
        print("SIMULATION COMPLETE")
        self._print_final_metrics()
        print("=" * 60)
    
    def _update_vehicles(self):
        """Update all vehicle states"""
        
        vehicle_ids = traci.vehicle.getIDList()
        
        for veh_id in vehicle_ids:
            if veh_id in self.vehicles:
                vehicle = self.vehicles[veh_id]
                
                # Update position
                try:
                    vehicle.current_edge = traci.vehicle.getRoadID(veh_id)
                    vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                    vehicle.total_distance = traci.vehicle.getDistance(veh_id)
                    
                    # Update battery for EVs
                    if vehicle.is_ev:
                        # Decrease battery based on distance
                        distance_km = vehicle.total_distance / 1000
                        battery_used = distance_km * vehicle.consumption_rate
                        vehicle.battery_level = max(0, vehicle.battery_level - battery_used)
                        
                        # Check if needs charging
                        if vehicle.battery_level < 20 and vehicle.state != VehicleState.CHARGING:
                            self._route_to_charging(vehicle)
                    
                    # Check if stuck at failed traffic light
                    if vehicle.waiting_time > 120:  # Stuck for 2 minutes
                        vehicle.state = VehicleState.STUCK
                        self._handle_stuck_vehicle(vehicle)
                        
                except traci.TraCIException:
                    pass
    
    def _manage_ev_charging(self):
        """Manage EV charging at stations"""
        
        for station in self.charging_stations.values():
            if not station.operational:
                continue
            
            # Check for EVs at station
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
                                    traci.vehicle.setStop(
                                        veh_id, 
                                        station.edge_id,
                                        pos=10.0,
                                        duration=60  # 60 second charge
                                    )
                                else:
                                    # Queue if station full
                                    if veh_id not in station.vehicles_queued:
                                        station.vehicles_queued.append(veh_id)
                        
                        # Simulate charging
                        if veh_id in station.vehicles_charging:
                            vehicle.battery_level = min(100, vehicle.battery_level + 2)  # 2% per step
                            
                            if vehicle.battery_level >= 80:
                                # Charging complete
                                station.vehicles_charging.remove(veh_id)
                                vehicle.state = VehicleState.NORMAL
                                
                                # Resume journey
                                traci.vehicle.resume(veh_id)
                                
                                # Update station availability
                                station.available_slots = station.capacity - len(station.vehicles_charging)
                                
                                # Process queue
                                if station.vehicles_queued:
                                    next_veh = station.vehicles_queued.pop(0)
                                    station.vehicles_charging.append(next_veh)
                                    
            except traci.TraCIException:
                pass
            
            # Update power grid load
            station.grid_load_mw = len(station.vehicles_charging) * 0.0072  # 7.2kW per vehicle
    
    def _route_to_charging(self, vehicle: SmartVehicle):
        """Route EV to nearest operational charging station"""
        
        # Find nearest operational station
        best_station = None
        min_distance = float('inf')
        
        try:
            veh_pos = traci.vehicle.getPosition(vehicle.id)
            
            for station in self.charging_stations.values():
                if station.operational and station.available_slots > 0:
                    # Get station position
                    edge = self.net.getEdge(station.edge_id)
                    if edge:
                        station_pos = edge.getShape()[0]
                        dist = np.sqrt((veh_pos[0] - station_pos[0])**2 + 
                                     (veh_pos[1] - station_pos[1])**2)
                        
                        if dist < min_distance:
                            min_distance = dist
                            best_station = station
            
            if best_station:
                # Reroute to charging station
                traci.vehicle.changeTarget(vehicle.id, best_station.edge_id)
                vehicle.state = VehicleState.REROUTING
                vehicle.target_charging_station = best_station.id
                self.metrics['charging_redirects'] += 1
                
                print(f"  EV {vehicle.id}: Battery {vehicle.battery_level:.1f}% -> {best_station.name}")
            else:
                vehicle.state = VehicleState.EMERGENCY
                print(f"  WARNING: EV {vehicle.id} low battery, no stations available!")
                
        except traci.TraCIException:
            pass
    
    def _handle_stuck_vehicle(self, vehicle: SmartVehicle):
        """Handle vehicle stuck at failed infrastructure"""
        
        try:
            # Find alternative route avoiding failed areas
            current_edge = vehicle.current_edge
            destination = traci.vehicle.getRoute(vehicle.id)[-1]
            
            # Get edges to avoid (those affected by power failure)
            avoid_edges = list(self.affected_edges)
            
            # Calculate new route
            if avoid_edges:
                # Use SUMO's routing with forbidden edges
                try:
                    route = traci.simulation.findRoute(
                        current_edge, 
                        destination,
                        vType=vehicle.vtype,
                        routingMode=0
                    )
                    
                    if route and route.edges:
                        traci.vehicle.setRoute(vehicle.id, route.edges)
                        vehicle.state = VehicleState.REROUTING
                        self.metrics['reroutes_performed'] += 1
                except:
                    pass
                    
        except traci.TraCIException:
            pass
    
    def trigger_substation_failure(self, substation_name: str):
        """Trigger cascading failure from substation outage"""
        
        print(f"\n⚡ SUBSTATION FAILURE: {substation_name}")
        print("-" * 40)
        
        if substation_name not in self.integrated_system.substations:
            print(f"Unknown substation: {substation_name}")
            return
        
        # Mark substation as failed
        self.failed_substations.add(substation_name)
        
        # Fail in power grid
        self.integrated_system.simulate_substation_failure(substation_name)
        
        # 1. Fail traffic lights
        affected_tls = []
        for tl in self.traffic_lights.values():
            if tl.substation == substation_name:
                tl.powered = False
                affected_tls.append(tl.id)
                
                # Set to flashing red or off
                try:
                    if self.sumo_running:
                        # Set all phases to red
                        traci.trafficlight.setRedYellowGreenState(
                            tl.id, 
                            'r' * 16  # All red
                        )
                        traci.trafficlight.setPhaseDuration(tl.id, 1000)
                except:
                    pass
        
        print(f"  ✗ {len(affected_tls)} traffic lights failed")
        
        # 2. Fail charging stations
        affected_stations = []
        for station in self.charging_stations.values():
            if station.substation == substation_name:
                station.operational = False
                station.available_slots = 0
                affected_stations.append(station.id)
                
                # Kick out charging vehicles
                for veh_id in station.vehicles_charging:
                    if veh_id in self.vehicles:
                        self.vehicles[veh_id].state = VehicleState.EMERGENCY
                        try:
                            if self.sumo_running:
                                traci.vehicle.resume(veh_id)
                                # Find alternative charging
                                self._route_to_charging(self.vehicles[veh_id])
                        except:
                            pass
                
                station.vehicles_charging.clear()
                station.vehicles_queued.clear()
        
        print(f"  ✗ {len(affected_stations)} charging stations offline")
        
        # 3. Mark affected edges
        if substation_name in self.substation_edges:
            self.affected_edges.update(self.substation_edges[substation_name])
            print(f"  ✗ {len(self.substation_edges[substation_name])} road segments affected")
        
        # 4. Reroute affected vehicles
        if self.sumo_running:
            affected_vehicles = self._get_affected_vehicles(substation_name)
            print(f"  ⚠ {len(affected_vehicles)} vehicles need rerouting")
            
            for veh_id in affected_vehicles:
                if veh_id in self.vehicles:
                    self.rerouting_queue.put(veh_id)
                    self.metrics['vehicles_affected'] += 1
        
        print("-" * 40)
    
    def restore_substation(self, substation_name: str):
        """Restore failed substation"""
        
        print(f"\n✓ RESTORING SUBSTATION: {substation_name}")
        
        if substation_name in self.failed_substations:
            self.failed_substations.remove(substation_name)
        
        # Restore in power grid
        self.integrated_system.restore_substation(substation_name)
        
        # Restore traffic lights
        for tl in self.traffic_lights.values():
            if tl.substation == substation_name:
                tl.powered = True
                try:
                    if self.sumo_running:
                        # Restore normal program
                        traci.trafficlight.setProgram(tl.id, tl.normal_program)
                except:
                    pass
        
        # Restore charging stations
        for station in self.charging_stations.values():
            if station.substation == substation_name:
                station.operational = True
                station.available_slots = station.capacity
        
        # Clear affected edges
        if substation_name in self.substation_edges:
            self.affected_edges.difference_update(self.substation_edges[substation_name])
        
        print(f"✓ Substation {substation_name} restored")
    
    def _get_affected_vehicles(self, substation_name: str) -> List[str]:
        """Get vehicles affected by substation failure"""
        
        affected = []
        
        if not self.sumo_running:
            return affected
        
        try:
            # Get all vehicles
            for veh_id in traci.vehicle.getIDList():
                # Check if on affected edge
                edge_id = traci.vehicle.getRoadID(veh_id)
                if edge_id in self.affected_edges:
                    affected.append(veh_id)
                    continue
                
                # Check if heading to failed charging station
                if veh_id in self.vehicles:
                    vehicle = self.vehicles[veh_id]
                    if vehicle.target_charging_station:
                        station = self.charging_stations.get(vehicle.target_charging_station)
                        if station and not station.operational:
                            affected.append(veh_id)
                            
        except traci.TraCIException:
            pass
        
        return affected
    
    def _process_rerouting_queue(self):
        """Process vehicles that need rerouting"""
        
        while not self.rerouting_queue.empty():
            try:
                veh_id = self.rerouting_queue.get_nowait()
                if veh_id in self.vehicles:
                    vehicle = self.vehicles[veh_id]
                    
                    if vehicle.is_ev and vehicle.battery_level < 30:
                        self._route_to_charging(vehicle)
                    else:
                        self._handle_stuck_vehicle(vehicle)
                        
            except queue.Empty:
                break
    
    def _update_metrics(self):
        """Update simulation metrics"""
        
        if not self.sumo_running:
            return
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            if vehicle_ids:
                # Average waiting time
                total_waiting = sum(traci.vehicle.getWaitingTime(v) for v in vehicle_ids)
                self.metrics['avg_waiting_time'] = total_waiting / len(vehicle_ids)
                
                # Total delay
                self.metrics['total_delay'] = sum(
                    traci.vehicle.getAccumulatedWaitingTime(v) for v in vehicle_ids
                )
                
                # Grid load from charging
                self.metrics['grid_load_mw'] = sum(
                    s.grid_load_mw for s in self.charging_stations.values()
                )
                
        except traci.TraCIException:
            pass
    
    def _print_status(self):
        """Print current simulation status"""
        
        try:
            num_vehicles = traci.simulation.getVehicleNumber()
            
            if num_vehicles > 0:
                # Count EVs charging
                evs_charging = sum(
                    len(s.vehicles_charging) for s in self.charging_stations.values()
                )
                
                # Count vehicles at failed lights
                stuck = sum(1 for v in self.vehicles.values() if v.state == VehicleState.STUCK)
                
                print(f"Step {self.simulation_step}: {num_vehicles} vehicles | "
                      f"EVs charging: {evs_charging} | "
                      f"Stuck: {stuck} | "
                      f"Avg wait: {self.metrics['avg_waiting_time']:.1f}s | "
                      f"Grid: {self.metrics['grid_load_mw']:.2f}MW")
                
                # Show failed infrastructure
                if self.failed_substations:
                    print(f"  ⚠ Failed substations: {', '.join(self.failed_substations)}")
                    
        except traci.TraCIException:
            pass
    
    def _print_final_metrics(self):
        """Print final simulation metrics"""
        
        print("\nFINAL METRICS:")
        print(f"  Vehicles affected by failures: {self.metrics['vehicles_affected']}")
        print(f"  Reroutes performed: {self.metrics['reroutes_performed']}")
        print(f"  EV charging redirects: {self.metrics['charging_redirects']}")
        print(f"  Total accumulated delay: {self.metrics['total_delay']:.1f}s")
        print(f"  Peak grid load: {self.metrics['grid_load_mw']:.2f}MW")
        
        # Vehicle statistics
        if self.vehicles:
            ev_count = sum(1 for v in self.vehicles.values() if v.is_ev)
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
        
        # Get vehicle positions
        if self.sumo_running:
            try:
                for veh_id in traci.vehicle.getIDList():
                    if veh_id in self.vehicles:
                        vehicle = self.vehicles[veh_id]
                        pos = traci.vehicle.getPosition(veh_id)
                        lon, lat = self.net.convertXY2LonLat(pos[0], pos[1])
                        
                        state['vehicles'].append({
                            'id': veh_id,
                            'type': vehicle.vtype,
                            'lat': lat,
                            'lon': lon,
                            'battery': vehicle.battery_level if vehicle.is_ev else None,
                            'state': vehicle.state.value,
                            'speed': traci.vehicle.getSpeed(veh_id) * 3.6  # km/h
                        })
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


def test_integrated_system():
    """Test the integrated simulation system"""
    
    print("\n" + "=" * 60)
    print("WORLD-CLASS INTEGRATED SIMULATION TEST")
    print("=" * 60)
    
    # Initialize your existing systems
    print("\nInitializing power grid...")
    power_grid = ManhattanPowerGrid()
    
    print("Initializing integrated backend...")
    integrated_system = ManhattanIntegratedSystem(power_grid)
    
    # Create the integrated simulation
    print("Creating integrated simulation system...")
    sim = IntegratedSimulationSystem(power_grid, integrated_system)
    
    # Start simulation in separate thread
    def run_simulation():
        sim.start_integrated_simulation(num_vehicles=10)
    
    sim_thread = threading.Thread(target=run_simulation)
    sim_thread.start()
    
    # Wait a bit for simulation to start
    time.sleep(5)
    
    # Test substation failure after 30 seconds
    print("\nWaiting 30 seconds before triggering failure...")
    time.sleep(30)
    
    print("\n" + "!" * 60)
    print("TRIGGERING SUBSTATION FAILURE: Times Square")
    print("!" * 60)
    sim.trigger_substation_failure('Times Square')
    
    # Let it run with failure for 60 seconds
    time.sleep(60)
    
    # Restore
    print("\n" + "!" * 60)
    print("RESTORING SUBSTATION: Times Square")
    print("!" * 60)
    sim.restore_substation('Times Square')
    
    # Wait for simulation to complete
    sim_thread.join()
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_integrated_system()