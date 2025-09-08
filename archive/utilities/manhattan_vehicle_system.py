"""
Manhattan Vehicle System - World Class Implementation
Realistic vehicle behavior, EV charging, traffic patterns
Professional-grade SUMO integration
"""

import os
import json
import random
import numpy as np
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import traci
import time
from datetime import datetime

class TimeOfDay(Enum):
    """Time periods with different traffic patterns"""
    NIGHT = "night"           # 12am-6am: Light traffic
    MORNING_RUSH = "morning"  # 6am-10am: Heavy traffic
    MIDDAY = "midday"         # 10am-3pm: Moderate traffic  
    EVENING_RUSH = "evening"  # 3pm-8pm: Heavy traffic
    EVENING = "evening_late"  # 8pm-12am: Moderate to light

@dataclass
class Vehicle:
    """Individual vehicle with properties"""
    id: str
    vtype: str
    origin: str
    destination: str
    depart_time: float
    battery_level: float = 100.0  # For EVs
    needs_charging: bool = False
    charging_station: Optional[str] = None
    route: List[str] = None

@dataclass
class ChargingStation:
    """EV charging station matching your power grid"""
    id: str
    name: str
    edge_id: str  # SUMO edge where station is located
    lat: float
    lon: float
    capacity: int  # Number of chargers
    power_kw: float
    vehicles_charging: List[str] = None
    
    def __post_init__(self):
        if self.vehicles_charging is None:
            self.vehicles_charging = []

class ManhattanVehicleSystem:
    """World-class vehicle simulation system"""
    
    def __init__(self):
        self.data_dir = 'data/sumo'
        self.network_file = os.path.join(self.data_dir, 'manhattan.net.xml')
        
        # Load network info
        with open(os.path.join(self.data_dir, 'network_info.json'), 'r') as f:
            self.network_info = json.load(f)
        
        # Vehicle fleet
        self.vehicles = {}
        self.active_vehicles = []
        
        # Charging stations (matching your power grid locations)
        self.charging_stations = self._init_charging_stations()
        
        # Traffic patterns
        self.time_of_day = TimeOfDay.MIDDAY
        self.current_time = 0
        
        # SUMO connection
        self.sumo_connected = False
        
        # Important edges (streets) for routing
        self.major_edges = []
        self.residential_edges = []
        self.commercial_edges = []
        
        # Parse network
        self._parse_network()
    
    def _init_charging_stations(self) -> Dict[str, ChargingStation]:
        """Initialize charging stations matching your power grid"""
        
        stations = {
            'CS_TimesSquare': ChargingStation(
                id='CS_TimesSquare',
                name='Times Square Garage',
                edge_id=None,  # Will be found
                lat=40.7580, lon=-73.9855,
                capacity=50, power_kw=50*7.2
            ),
            'CS_BryantPark': ChargingStation(
                id='CS_BryantPark',
                name='Bryant Park Station',
                edge_id=None,
                lat=40.7540, lon=-73.9840,
                capacity=30, power_kw=30*7.2
            ),
            'CS_PennStation': ChargingStation(
                id='CS_PennStation',
                name='Penn Station Hub',
                edge_id=None,
                lat=40.7508, lon=-73.9936,
                capacity=40, power_kw=40*7.2
            ),
            'CS_GrandCentral': ChargingStation(
                id='CS_GrandCentral',
                name='Grand Central Charging',
                edge_id=None,
                lat=40.7525, lon=-73.9774,
                capacity=60, power_kw=60*7.2
            ),
            'CS_ColumbusCircle': ChargingStation(
                id='CS_ColumbusCircle',
                name='Columbus Circle EV',
                edge_id=None,
                lat=40.7685, lon=-73.9815,
                capacity=35, power_kw=35*7.2
            ),
            'CS_MurrayHill': ChargingStation(
                id='CS_MurrayHill',
                name='Murray Hill Garage',
                edge_id=None,
                lat=40.7492, lon=-73.9768,
                capacity=25, power_kw=25*7.2
            ),
        }
        
        return stations
    
    def _parse_network(self):
        """Parse SUMO network to find edges and match charging stations"""
        
        tree = ET.parse(self.network_file)
        root = tree.getroot()
        
        # Get all edges
        edges = root.findall('.//edge[@function="normal"]')
        
        for edge in edges:
            edge_id = edge.get('id')
            if edge_id and not edge_id.startswith(':'):
                # Classify edges by name
                name = edge.get('name', '').lower()
                
                # Major streets
                if any(major in name for major in ['broadway', '5th avenue', '7th avenue', 
                                                    'park avenue', 'madison', 'lexington']):
                    self.major_edges.append(edge_id)
                # Commercial areas
                elif any(com in name for com in ['42nd', '34th', '57th', 'times square']):
                    self.commercial_edges.append(edge_id)
                else:
                    self.residential_edges.append(edge_id)
                
                # Match charging stations to nearest edge
                lanes = edge.findall('.//lane')
                if lanes:
                    lane = lanes[0]
                    shape = lane.get('shape', '')
                    if shape:
                        # Get first coordinate
                        coords = shape.split(' ')[0].split(',')
                        if len(coords) == 2:
                            try:
                                x, y = float(coords[0]), float(coords[1])
                                # Simple matching (you'd use proper projection in production)
                                for station in self.charging_stations.values():
                                    if station.edge_id is None:
                                        # Rough distance check
                                        dist = abs(station.lat - 40.75) * 111000 + abs(station.lon + 73.98) * 85000
                                        if dist < 500:  # Within 500m
                                            station.edge_id = edge_id
                                            break
                            except:
                                pass
        
        # Ensure all stations have edges (fallback to random commercial edge)
        for station in self.charging_stations.values():
            if station.edge_id is None and self.commercial_edges:
                station.edge_id = random.choice(self.commercial_edges)
        
        print(f"Network parsed: {len(self.major_edges)} major, {len(self.commercial_edges)} commercial, "
              f"{len(self.residential_edges)} residential edges")
    
    def generate_routes_file(self, scenario: str = "normal", num_vehicles: int = 10):
        """Generate routes file with intelligent trip patterns"""
        
        print(f"\nGenerating {scenario} scenario with {num_vehicles} vehicles...")
        
        routes_file = os.path.join(self.data_dir, f'manhattan_{scenario}.rou.xml')
        
        root = ET.Element('routes')
        
        # Add vehicle types
        self._add_vehicle_types_to_routes(root)
        
        # Generate vehicles based on scenario
        if scenario == "rush_hour":
            vehicles = self._generate_rush_hour_vehicles(num_vehicles)
        elif scenario == "night":
            vehicles = self._generate_night_vehicles(num_vehicles)
        else:  # normal
            vehicles = self._generate_normal_vehicles(num_vehicles)
        
        # Add vehicles to routes file
        for vehicle in vehicles:
            self._add_vehicle_to_routes(root, vehicle)
        
        # Write routes file
        tree = ET.ElementTree(root)
        tree.write(routes_file, encoding='utf-8', xml_declaration=True)
        
        print(f"✓ Generated {len(vehicles)} vehicles")
        print(f"  - EVs: {sum(1 for v in vehicles if 'ev' in v.vtype)}")
        print(f"  - Regular: {sum(1 for v in vehicles if 'ev' not in v.vtype)}")
        print(f"✓ Routes file: {routes_file}")
        
        return routes_file
    
    def _add_vehicle_types_to_routes(self, root):
        """Add vehicle type references"""
        # Types are defined in types.add.xml, just reference them here
        pass
    
    def _generate_normal_vehicles(self, num: int) -> List[Vehicle]:
        """Generate vehicles for normal traffic"""
        
        vehicles = []
        
        for i in range(num):
            # 30% EVs, 60% cars, 10% taxis
            rand = random.random()
            if rand < 0.3:
                vtype = 'ev_sedan' if random.random() < 0.7 else 'ev_suv'
                battery = random.uniform(20, 90)  # Random battery level
            elif rand < 0.9:
                vtype = 'car'
                battery = 100
            else:
                vtype = 'taxi'
                battery = 100
            
            # Pick origin and destination intelligently
            if vtype == 'taxi':
                # Taxis: commercial to commercial or residential
                origin = random.choice(self.commercial_edges) if self.commercial_edges else random.choice(self.major_edges)
                destination = random.choice(self.commercial_edges + self.residential_edges)
            else:
                # Regular traffic: varied patterns
                origin = random.choice(self.major_edges + self.residential_edges)
                destination = random.choice(self.major_edges + self.commercial_edges + self.residential_edges)
            
            # Ensure different origin and destination
            while destination == origin:
                destination = random.choice(self.major_edges + self.commercial_edges + self.residential_edges)
            
            vehicle = Vehicle(
                id=f"veh_{i}",
                vtype=vtype,
                origin=origin,
                destination=destination,
                depart_time=i * 3.0,  # Stagger departures
                battery_level=battery,
                needs_charging=(battery < 30 and 'ev' in vtype)
            )
            
            vehicles.append(vehicle)
        
        return vehicles
    
    def _generate_rush_hour_vehicles(self, num: int) -> List[Vehicle]:
        """Generate rush hour traffic patterns"""
        
        vehicles = []
        
        for i in range(num):
            # More regular cars during rush hour, fewer EVs
            rand = random.random()
            if rand < 0.2:  # 20% EVs
                vtype = 'ev_sedan' if random.random() < 0.8 else 'ev_suv'
                battery = random.uniform(40, 95)  # Higher battery for commute
            elif rand < 0.85:
                vtype = 'car'
                battery = 100
            elif rand < 0.95:
                vtype = 'taxi'
                battery = 100
            else:
                vtype = 'bus'
                battery = 100
            
            # Rush hour patterns: residential to commercial (morning) or reverse (evening)
            if self.time_of_day == TimeOfDay.MORNING_RUSH:
                # Morning: residential to commercial
                origin = random.choice(self.residential_edges) if self.residential_edges else random.choice(self.major_edges)
                destination = random.choice(self.commercial_edges) if self.commercial_edges else random.choice(self.major_edges)
            else:
                # Evening: commercial to residential
                origin = random.choice(self.commercial_edges) if self.commercial_edges else random.choice(self.major_edges)
                destination = random.choice(self.residential_edges) if self.residential_edges else random.choice(self.major_edges)
            
            vehicle = Vehicle(
                id=f"veh_rush_{i}",
                vtype=vtype,
                origin=origin,
                destination=destination,
                depart_time=i * 1.5,  # Tighter spacing during rush hour
                battery_level=battery,
                needs_charging=(battery < 25 and 'ev' in vtype)
            )
            
            vehicles.append(vehicle)
        
        return vehicles
    
    def _generate_night_vehicles(self, num: int) -> List[Vehicle]:
        """Generate night traffic (fewer vehicles, more taxis)"""
        
        vehicles = []
        actual_num = max(3, num // 3)  # Fewer vehicles at night
        
        for i in range(actual_num):
            # Night: more taxis, some EVs
            rand = random.random()
            if rand < 0.25:  # 25% EVs
                vtype = 'ev_sedan'
                battery = random.uniform(30, 80)
            elif rand < 0.5:
                vtype = 'taxi'
                battery = 100
            else:
                vtype = 'car'
                battery = 100
            
            # Night patterns: mostly major streets
            origin = random.choice(self.major_edges) if self.major_edges else random.choice(self.commercial_edges)
            destination = random.choice(self.major_edges + self.commercial_edges)
            
            vehicle = Vehicle(
                id=f"veh_night_{i}",
                vtype=vtype,
                origin=origin,
                destination=destination,
                depart_time=i * 10.0,  # Sparse traffic
                battery_level=battery,
                needs_charging=(battery < 35 and 'ev' in vtype)
            )
            
            vehicles.append(vehicle)
        
        return vehicles
    
    def _add_vehicle_to_routes(self, root, vehicle: Vehicle):
        """Add vehicle to routes XML"""
        
        # If EV needs charging, create trip with charging stop
        if vehicle.needs_charging and 'ev' in vehicle.vtype:
            # Find nearest charging station
            station = random.choice(list(self.charging_stations.values()))
            
            # Trip 1: Origin to charging station
            trip1 = ET.SubElement(root, 'trip')
            trip1.set('id', f"{vehicle.id}_charge")
            trip1.set('type', vehicle.vtype)
            trip1.set('depart', str(vehicle.depart_time))
            trip1.set('from', vehicle.origin)
            trip1.set('to', station.edge_id if station.edge_id else vehicle.destination)
            
            # Vehicle will continue after charging (handled by TraCI)
        else:
            # Regular trip
            trip = ET.SubElement(root, 'trip')
            trip.set('id', vehicle.id)
            trip.set('type', vehicle.vtype)
            trip.set('depart', str(vehicle.depart_time))
            trip.set('from', vehicle.origin)
            trip.set('to', vehicle.destination)
    
    def start_simulation(self, scenario: str = "normal", num_vehicles: int = 10, gui: bool = True):
        """Start SUMO simulation with TraCI control"""
        
        print("\n" + "=" * 60)
        print("STARTING MANHATTAN TRAFFIC SIMULATION")
        print(f"Scenario: {scenario.upper()}")
        print(f"Vehicles: {num_vehicles}")
        print("=" * 60)
        
        # Generate routes
        routes_file = self.generate_routes_file(scenario, num_vehicles)
        
        # Prepare SUMO command
        sumo_binary = "sumo-gui" if gui else "sumo"
        
        sumo_cmd = [
            sumo_binary,
            '-n', self.network_file,
            '-r', routes_file,
            '-a', os.path.join(self.data_dir, 'traffic_lights.add.xml'),
            '-a', os.path.join(self.data_dir, 'types.add.xml'),
            '--step-length', '0.5',
            '--collision.action', 'warn',
            '--collision.check-junctions', 'true',
            '--device.battery.probability', '1.0',  # All EVs have battery
            '--device.emissions.probability', '1.0',
            '--lateral-resolution', '0.8',
            '--start', 'true',
            '--quit-on-end', 'false' if gui else 'true',
            '--gui-settings-file', os.path.join(self.data_dir, 'gui-settings.xml') if gui else ''
        ]
        
        # Remove empty strings
        sumo_cmd = [s for s in sumo_cmd if s]
        
        # Create GUI settings for better visualization
        if gui:
            self._create_gui_settings()
        
        try:
            # Start SUMO with TraCI
            traci.start(sumo_cmd)
            self.sumo_connected = True
            
            print("✓ SUMO started successfully")
            print("✓ TraCI connected")
            
            # Run simulation
            self._run_simulation_loop(scenario)
            
        except Exception as e:
            print(f"✗ Error starting SUMO: {e}")
            return False
        finally:
            if self.sumo_connected:
                traci.close()
                self.sumo_connected = False
        
        return True
    
    def _create_gui_settings(self):
        """Create GUI settings for better visualization"""
        
        settings = '''<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <scheme name="real world">
        <vehicles vehicleMode="0" vehicleQuality="2" 
                 showBlinker="true" vehicleSize="1.0">
            <colorScheme name="by type" />
        </vehicles>
        <edges edgeMode="0" widthExaggeration="1.0" 
               laneWidthExaggeration="1.0">
            <colorScheme name="by purpose" />
        </edges>
        <junctions junctionMode="0" drawShape="true" 
                  drawCrossings="true" junctionSize="1.0" />
        <additionals additionalMode="0" additionalSize="1.0" />
        <pois poiSize="0.0" poiDetail="4" poiName="false" poiType="false" />
        <polys polySize="0.0" polyName="false" polyType="false" />
        <legend showSizeLegend="true" showColorLegend="true" />
    </scheme>
</viewsettings>'''
        
        with open(os.path.join(self.data_dir, 'gui-settings.xml'), 'w') as f:
            f.write(settings)
    
    def _run_simulation_loop(self, scenario: str):
        """Main simulation loop with TraCI control"""
        
        step = 0
        charging_events = []
        
        print("\nSimulation running... (Press Ctrl+C to stop)")
        print("-" * 40)
        
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            
            # Get all vehicles
            vehicle_ids = traci.vehicle.getIDList()
            
            # Monitor EVs
            for veh_id in vehicle_ids:
                if 'ev' in traci.vehicle.getTypeID(veh_id):
                    # Check battery level (if available)
                    try:
                        if traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity"):
                            battery = float(traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity"))
                            max_battery = float(traci.vehicle.getParameter(veh_id, "device.battery.maximumBatteryCapacity"))
                            battery_percent = (battery / max_battery) * 100
                            
                            # If battery low, reroute to charging station
                            if battery_percent < 20 and veh_id not in charging_events:
                                station = random.choice(list(self.charging_stations.values()))
                                if station.edge_id:
                                    try:
                                        traci.vehicle.changeTarget(veh_id, station.edge_id)
                                        charging_events.append(veh_id)
                                        print(f"  EV {veh_id}: Battery {battery_percent:.1f}% - Routing to {station.name}")
                                    except:
                                        pass
                    except:
                        pass
            
            # Status update every 100 steps (50 seconds)
            if step % 100 == 0 and step > 0:
                num_vehicles = len(vehicle_ids)
                if num_vehicles > 0:
                    avg_speed = sum(traci.vehicle.getSpeed(v) for v in vehicle_ids) / num_vehicles
                    avg_waiting = sum(traci.vehicle.getWaitingTime(v) for v in vehicle_ids) / num_vehicles
                    
                    print(f"Step {step}: {num_vehicles} vehicles | "
                          f"Avg speed: {avg_speed*3.6:.1f} km/h | "
                          f"Avg wait: {avg_waiting:.1f}s")
                    
                    # Count vehicles at traffic lights
                    stopped = sum(1 for v in vehicle_ids if traci.vehicle.getSpeed(v) < 0.1)
                    if stopped > 0:
                        print(f"  {stopped} vehicles stopped (likely at traffic lights)")
            
            step += 1
            
            # Stop after 1000 steps for demo (500 seconds)
            if step >= 1000:
                print("\nSimulation complete!")
                break
        
        print("-" * 40)
        print(f"Total simulation steps: {step}")
        print(f"EVs that needed charging: {len(charging_events)}")

class SUMOIntegration:
    """Integration with your power grid system"""
    
    def __init__(self, power_grid, integrated_system):
        self.power_grid = power_grid
        self.integrated_system = integrated_system
        self.vehicle_system = ManhattanVehicleSystem()
        
        # Map charging stations to power grid
        self._map_charging_to_grid()
    
    def _map_charging_to_grid(self):
        """Map SUMO charging stations to power grid EV stations"""
        
        # Match by location
        for sumo_station in self.vehicle_system.charging_stations.values():
            for grid_station in self.integrated_system.ev_stations.values():
                # Simple name matching
                if sumo_station.name == grid_station['name']:
                    sumo_station.power_grid_id = grid_station['id']
                    break
    
    def update_charging_load(self):
        """Update power grid based on vehicles charging"""
        
        if not self.vehicle_system.sumo_connected:
            return
        
        # Get all vehicles at charging stations
        for station in self.vehicle_system.charging_stations.values():
            if station.edge_id:
                # Count EVs on this edge
                try:
                    vehicles_on_edge = traci.edge.getLastStepVehicleIDs(station.edge_id)
                    ev_count = sum(1 for v in vehicles_on_edge if 'ev' in traci.vehicle.getTypeID(v))
                    
                    # Update power grid
                    if hasattr(station, 'power_grid_id'):
                        grid_station = self.integrated_system.ev_stations.get(station.power_grid_id)
                        if grid_station:
                            grid_station['vehicles_charging'] = ev_count
                            # Update power consumption
                            grid_station['power_kw'] = ev_count * 7.2  # 7.2kW per vehicle
                except:
                    pass

if __name__ == "__main__":
    # Test the system
    system = ManhattanVehicleSystem()
    
    print("\n" + "=" * 60)
    print("MANHATTAN VEHICLE SYSTEM READY")
    print("=" * 60)
    print("\nAvailable scenarios:")
    print("  1. Normal - Mixed traffic, 30% EVs")
    print("  2. Rush Hour - Heavy traffic, work patterns")
    print("  3. Night - Light traffic, more taxis")
    print("\nStarting with 10 vehicles in NORMAL scenario...")
    print("=" * 60)
    
    # Start simulation
    system.start_simulation(scenario="normal", num_vehicles=10, gui=True)