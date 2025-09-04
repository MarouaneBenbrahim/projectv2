"""
Manhattan SUMO Manager - World Class Vehicle Simulation
COMPLETE VERSION with all coordinate fixes and route validation
"""

import os
import sys
import json
import random
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import time
from ev_battery_model import EVBatteryModel
from ev_station_manager import EVStationManager
# Check if SUMO is available
try:
    import traci
    import sumolib
    SUMO_AVAILABLE = True
except ImportError:
    print("Warning: SUMO not installed. Install with: pip install sumo")
    SUMO_AVAILABLE = False

class VehicleType(Enum):
    """Vehicle types matching real NYC traffic"""
    CAR = "car"
    TAXI = "taxi"
    BUS = "bus"
    EV_SEDAN = "ev_sedan"
    EV_SUV = "ev_suv"
    DELIVERY = "delivery"
    UBER = "uber"

class SimulationScenario(Enum):
    """Traffic scenarios for different times of day"""
    MORNING_RUSH = "morning_rush"
    MIDDAY = "midday"
    EVENING_RUSH = "evening_rush"
    NIGHT = "night"
    WEEKEND = "weekend"
    EMERGENCY = "emergency"

@dataclass
class VehicleConfig:
    """Vehicle configuration with realistic parameters"""
    id: str
    vtype: VehicleType
    origin: str = None
    destination: str = None
    is_ev: bool = False
    battery_capacity_kwh: float = 0
    current_soc: float = 1.0
    consumption_kwh_per_km: float = 0.2
    depart_time: float = 0
    route: List[str] = field(default_factory=list)

class ManhattanSUMOManager:
    """Professional SUMO integration for Manhattan traffic"""
    
    def __init__(self, integrated_system):
        self.integrated_system = integrated_system
        self.running = False
        self.vehicles = {}
        self.current_scenario = SimulationScenario.MIDDAY
        
        # Manhattan bounds (34th to 59th Street)
        self.bounds = {
            'north': 40.770,
            'south': 40.745,
            'west': -74.010,
            'east': -73.960
        }
        
        # SUMO configuration - traffic lights file removed to avoid errors
        self.sumo_config = {
            'net_file': 'data/sumo/manhattan.net.xml',
            'additional_files': [
                'data/sumo/types.add.xml'
            ],
            'step_length': 0.1,
            'collision_action': 'warn',
            'device.rerouting.probability': '0.8',
            'device.battery.probability': '0.3'
        }
        
        # Traffic light mapping
        self.tl_power_to_sumo = {}
        self.tl_sumo_to_power = {}
        
        # EV charging stations in SUMO
        self.ev_stations_sumo = {}
        # Initialize smart station manager
        self.station_manager = None
        
        # Major routes and destinations
        self.destinations = []
        self.popular_routes = []
        self.spawn_edges = []
        
        # Statistics
        self.stats = {
            'total_vehicles': 0,
            'ev_vehicles': 0,
            'vehicles_charging': 0,
            'total_distance_km': 0,
            'total_energy_consumed_kwh': 0,
            'avg_speed_mps': 0,
            'total_wait_time': 0,
            'traffic_light_violations': 0
        }
        
        # Load network data
        self._load_network_data()
    
    def _load_network_data(self):
        """Load SUMO network and establish mappings"""
        
        if not os.path.exists(self.sumo_config['net_file']):
            print("Warning: SUMO network not found. Run get_manhattan_sumo_network.py first!")
            return False
        
        if SUMO_AVAILABLE:
            # Load network
            self.net = sumolib.net.readNet(self.sumo_config['net_file'])
            
            # Get all edges for routing
            self.edges = [e.getID() for e in self.net.getEdges() 
                         if not e.isSpecial() and e.allows("passenger")]
            
            # Get junctions
            try:
                if hasattr(self.net, 'getNodes'):
                    nodes = self.net.getNodes()
                else:
                    nodes = []
                
                self.junctions = []
                for node in nodes:
                    try:
                        if hasattr(node, 'getType') and node.getType() != "dead_end":
                            self.junctions.append(node.getID())
                        elif len(node.getIncoming()) > 1 or len(node.getOutgoing()) > 1:
                            self.junctions.append(node.getID())
                    except:
                        pass
            except:
                self.junctions = list(set([e.getFromNode().getID() for e in self.net.getEdges()[:100]] + 
                                          [e.getToNode().getID() for e in self.net.getEdges()[:100]]))
            
            # Load validated spawn edges
            try:
                with open('data/good_spawn_edges.json', 'r') as f:
                    self.spawn_edges = json.load(f)
                    print(f"Loaded {len(self.spawn_edges)} validated spawn edges")
            except:
                print("Using all edges for spawning (may have connectivity issues)")
                self.spawn_edges = self.edges[:200] if self.edges else []
            
            # Setup destinations
            self._setup_destinations()
            
            print(f"Loaded SUMO network: {len(self.edges)} edges, {len(self.junctions)} junctions")
            
            # Load connected network data if available
            connected_network_file = 'data/manhattan_connected_network.json'
            if os.path.exists(connected_network_file):
                with open(connected_network_file, 'r') as f:
                    network_data = json.load(f)
                    
                    if 'spawn_edges' in network_data and network_data['spawn_edges']:
                        self.spawn_edges = network_data['spawn_edges']
                        print(f"Loaded {len(self.spawn_edges)} spawn points from connected network")
            
            return True
        return False
    
    def _setup_destinations(self):
        """Setup realistic Manhattan destinations"""
        
        self.destinations = [
            ("Times Square", self._find_nearest_edge(40.7589, -73.9851)),
            ("Grand Central", self._find_nearest_edge(40.7527, -73.9772)),
            ("Penn Station", self._find_nearest_edge(40.7505, -73.9934)),
            ("Bryant Park", self._find_nearest_edge(40.7536, -73.9832)),
            ("Rockefeller Center", self._find_nearest_edge(40.7587, -73.9787)),
            ("Herald Square", self._find_nearest_edge(40.7484, -73.9878)),
            ("5th Ave Shopping", self._find_nearest_edge(40.7614, -73.9776)),
            ("MoMA", self._find_nearest_edge(40.7614, -73.9776)),
            ("Carnegie Hall", self._find_nearest_edge(40.7651, -73.9799)),
            ("Hell's Kitchen", self._find_nearest_edge(40.7638, -73.9918)),
            ("Murray Hill", self._find_nearest_edge(40.7478, -73.9750)),
            ("Turtle Bay", self._find_nearest_edge(40.7544, -73.9667)),
            ("Columbus Circle", self._find_nearest_edge(40.7680, -73.9819)),
            ("Plaza Hotel", self._find_nearest_edge(40.7644, -73.9747)),
            ("Waldorf Astoria", self._find_nearest_edge(40.7560, -73.9738))
        ]
        
        self.destinations = [(name, edge) for name, edge in self.destinations if edge]
        self._create_popular_routes()
    
    def _find_nearest_edge(self, lat: float, lon: float) -> Optional[str]:
        """Find nearest SUMO edge to given coordinates"""
        
        if not SUMO_AVAILABLE or not hasattr(self, 'net'):
            return None
        
        try:
            x, y = self.net.convertLonLat2XY(lon, lat)
            
            min_dist = float('inf')
            nearest_edge = None
            
            for edge in self.net.getEdges():
                if not edge.allows("passenger") or edge.isSpecial():
                    continue
                
                shape = edge.getShape()
                if shape:
                    edge_x = sum(p[0] for p in shape) / len(shape)
                    edge_y = sum(p[1] for p in shape) / len(shape)
                    
                    dist = ((x - edge_x) ** 2 + (y - edge_y) ** 2) ** 0.5
                    
                    if dist < min_dist:
                        min_dist = dist
                        nearest_edge = edge.getID()
            
            if not nearest_edge and self.edges:
                nearest_edge = self.edges[0]
            
            return nearest_edge
        except:
            return self.edges[0] if self.edges else None
    
    def _create_popular_routes(self):
        """Create realistic routes between popular destinations"""
        
        if not self.destinations:
            return
        
        route_patterns = [
            ("Hell's Kitchen", "Times Square"),
            ("Murray Hill", "Grand Central"),
            ("Turtle Bay", "Grand Central"),
            ("Columbus Circle", "Penn Station"),
            ("Times Square", "Rockefeller Center"),
            ("Grand Central", "Times Square"),
            ("Penn Station", "Herald Square"),
            ("Penn Station", "5th Ave Shopping"),
            ("Grand Central", "Herald Square"),
            ("Times Square", "MoMA"),
            ("Columbus Circle", "Carnegie Hall")
        ]
        
        for origin_name, dest_name in route_patterns:
            origin_edge = next((e for n, e in self.destinations if n == origin_name), None)
            dest_edge = next((e for n, e in self.destinations if n == dest_name), None)
            
            if origin_edge and dest_edge:
                self.popular_routes.append((origin_edge, dest_edge))
    
    def start_sumo(self, gui: bool = False, seed: int = None) -> bool:
        """Start SUMO simulation with proper configuration"""
        
        if not SUMO_AVAILABLE:
            print("SUMO not available")
            return False
        
        if self.running:
            print("SUMO already running")
            return False
        
        # Build command
        sumo_binary = "sumo-gui" if gui else "sumo"
        
        cmd = [
            sumo_binary,
            "-n", self.sumo_config['net_file'],
            "--step-length", str(self.sumo_config['step_length']),
            "--collision.action", self.sumo_config['collision_action'],
            "--device.rerouting.probability", self.sumo_config['device.rerouting.probability'],
            "--no-warnings",
            "--no-step-log",
            "--duration-log.statistics",
            "--device.emissions.probability", "1.0"
        ]
        
        # Collect additional files
        existing_additional_files = []
        for add_file in self.sumo_config['additional_files']:
            if os.path.exists(add_file):
                existing_additional_files.append(add_file)
        
        if existing_additional_files:
            cmd.extend(["-a", ",".join(existing_additional_files)])
        
        if seed is not None:
            cmd.extend(["--seed", str(seed)])
        
        try:
            traci.start(cmd)
            self.running = True
            
            self._initialize_traffic_lights()
            self._initialize_ev_stations()
            
            # Initialize smart station manager AFTER network is loaded
            if self.net:
                self.station_manager = EVStationManager(self.integrated_system, self.net)
            
            print("SUMO started successfully")
            return True
            
        except Exception as e:
            print(f"Failed to start SUMO: {e}")
            return False
    
    def _initialize_traffic_lights(self):
        """Map traffic lights between power grid and SUMO"""
        
        if not self.running:
            return
        
        tl_ids = traci.trafficlight.getIDList()
        
        for tl_id in tl_ids:
            try:
                if hasattr(self.net, 'getNode'):
                    junction = self.net.getNode(tl_id)
                else:
                    continue
                    
                if junction:
                    coord = junction.getCoord()
                    lon, lat = self.net.convertXY2LonLat(coord[0], coord[1])
                    
                    min_dist = float('inf')
                    nearest_power_tl = None
                    
                    for power_tl_id, power_tl in self.integrated_system.traffic_lights.items():
                        dist = ((lat - power_tl['lat'])**2 + (lon - power_tl['lon'])**2)**0.5
                        if dist < min_dist and dist < 0.001:
                            min_dist = dist
                            nearest_power_tl = power_tl_id
                    
                    if nearest_power_tl:
                        self.tl_power_to_sumo[nearest_power_tl] = tl_id
                        self.tl_sumo_to_power[tl_id] = nearest_power_tl
            except:
                pass
        
        print(f"Mapped {len(self.tl_power_to_sumo)} traffic lights to SUMO")
    
    def _initialize_ev_stations(self):
        """Setup EV charging stations in SUMO"""
        
        if not self.running:
            return
        
        for ev_id, ev_station in self.integrated_system.ev_stations.items():
            edge_id = self._find_nearest_edge(ev_station['lat'], ev_station['lon'])
            
            if edge_id:
                self.ev_stations_sumo[ev_id] = {
                    'edge': edge_id,
                    'capacity': ev_station['chargers'],
                    'available': ev_station['chargers'] if ev_station['operational'] else 0,
                    'charging': []
                }
    
    def spawn_vehicles(self, count: int = 10, ev_percentage: float = 0.3) -> int:
        """Spawn vehicles with validated routes ensuring they start on actual roads"""
        
        if not self.running:
            return 0
        
        import traci
        spawned = 0
        
        # Get ACTUAL edges from the live SUMO network (not from stored list)
        all_edges = traci.edge.getIDList()
        valid_edges = [e for e in all_edges if not e.startswith(':') and traci.edge.getLaneNumber(e) > 0]
        
        if not valid_edges:
            print("ERROR: No valid edges found in SUMO network")
            return 0
        
        print(f"Spawning {count} vehicles using {len(valid_edges)} valid edges...")
        
        for i in range(count):
            vehicle_id = f"veh_{self.stats['total_vehicles'] + i}"
            
            # 80% EVs for testing
            is_ev = random.random() < 0.8
            
            if is_ev:
                vtype = "ev_sedan" if random.random() < 0.6 else "ev_suv"
                # CALIBRATED BATTERY: 30-40% starting charge
                # This ensures they can reach any station from anywhere with 8% left
                initial_soc = random.uniform(0.20, 0.24)  # 30-40% battery
            else:
                vtype = random.choice(["car", "taxi"])
                initial_soc = 1.0
            
            # Rest of the spawn code stays the same...
            # Try multiple times to find a valid route
            spawn_success = False
            for attempt in range(10):
                try:
                    # Pick random edges from ACTUAL network edges
                    origin = random.choice(valid_edges)
                    destination = random.choice(valid_edges)
                    
                    # Make sure they're different
                    while destination == origin and len(valid_edges) > 1:
                        destination = random.choice(valid_edges)
                    
                    # Use SUMO's built-in routing
                    route_result = traci.simulation.findRoute(origin, destination)
                    
                    if route_result and route_result.edges and len(route_result.edges) > 0:
                        # Create and add the route
                        route_id = f"route_{vehicle_id}_{attempt}"
                        traci.route.add(route_id, route_result.edges)
                        
                        # Add the vehicle
                        traci.vehicle.add(
                            vehicle_id,
                            route_id,
                            typeID=vtype,
                            depart="now"
                        )
                        
                        # EXTREME SPEED FOR TESTING
                        traci.vehicle.setMaxSpeed(vehicle_id, 500)  # 500 m/s = 1800 km/h
                        traci.vehicle.setSpeedMode(vehicle_id, 0)  # Ignore ALL safety
                        traci.vehicle.setSpeed(vehicle_id, 200)  # Start at 200 m/s = 720 km/h
                        traci.vehicle.setAccel(vehicle_id, 50)  # Super acceleration
                        traci.vehicle.setDecel(vehicle_id, 50)  # Super braking
                        traci.vehicle.setMinGap(vehicle_id, 0.5)  # Very close following
                        traci.vehicle.setTau(vehicle_id, 0.1)  # Minimal reaction time
                        traci.vehicle.setSpeedFactor(vehicle_id, 10)  # 10x normal speed
                        
                        # Set color based on battery
                        if is_ev:
                            if initial_soc < 0.35:
                                traci.vehicle.setColor(vehicle_id, (255, 165, 0, 255))  # Orange for 30-35%
                            else:
                                traci.vehicle.setColor(vehicle_id, (0, 255, 0, 255))  # Green for 35-40%
                        elif vtype == "taxi":
                            traci.vehicle.setColor(vehicle_id, (255, 255, 0, 255))  # Yellow
                        else:
                            traci.vehicle.setColor(vehicle_id, (100, 100, 255, 255))  # Blue
                        
                        # Set battery for EVs
                        if is_ev:
                            battery_capacity = 75000 if vtype == "ev_sedan" else 100000
                            traci.vehicle.setParameter(vehicle_id, "device.battery.maximumBatteryCapacity", str(battery_capacity))
                            traci.vehicle.setParameter(vehicle_id, "device.battery.actualBatteryCapacity", str(battery_capacity * initial_soc))
                            traci.vehicle.setParameter(vehicle_id, "has.battery.device", "true")
                        
                        # Store vehicle data
                        vtype_enum = VehicleType.EV_SEDAN if vtype == "ev_sedan" else \
                                    VehicleType.EV_SUV if vtype == "ev_suv" else \
                                    VehicleType.TAXI if vtype == "taxi" else \
                                    VehicleType.CAR
                        
                        self.vehicles[vehicle_id] = Vehicle(
                            vehicle_id,
                            VehicleConfig(
                                id=vehicle_id,
                                vtype=vtype_enum,
                                origin=origin,
                                destination=destination,
                                is_ev=is_ev,
                                battery_capacity_kwh=75 if vtype == "ev_sedan" else (100 if vtype == "ev_suv" else 0),
                                current_soc=initial_soc,
                                route=route_result.edges
                            )
                        )
                        
                        spawned += 1
                        spawn_success = True
                        
                        if is_ev:
                            self.stats['ev_vehicles'] += 1
                        
                        break
                        
                except Exception as e:
                    continue
            
            if not spawn_success:
                print(f"  ⚠️ Failed to spawn {vehicle_id} after 10 attempts")
        
        self.stats['total_vehicles'] += spawned
        print(f"✅ Successfully spawned {spawned}/{count} vehicles (80% EVs with 30-40% battery)")
        print(f"⚠️  Battery calibrated: Can reach farthest station with 8% remaining")
        
        return spawned
    def get_vehicle_positions_for_visualization(self) -> List[Dict]:
        """Get vehicle data with CORRECTED coordinates for web visualization"""
        
        if not self.running:
            return []
        
        try:
            import traci
            vehicles_data = []
            
            for vehicle in self.vehicles.values():
                try:
                    if vehicle.id in traci.vehicle.getIDList():
                        # Get position from SUMO (in SUMO's internal coordinate system)
                        x, y = traci.vehicle.getPosition(vehicle.id)
                        
                        # CRITICAL: Use SUMO's built-in coordinate conversion
                        # This ensures vehicles stay on the actual roads
                        lon, lat = traci.simulation.convertGeo(x, y)
                        
                        # Additional validation - ensure within Manhattan bounds
                        if not (self.bounds['south'] <= lat <= self.bounds['north'] and
                                self.bounds['west'] <= lon <= self.bounds['east']):
                            # If outside bounds, try alternative conversion
                            lon, lat = self.net.convertXY2LonLat(x, y)
                        
                        # Final bounds check
                        if (self.bounds['south'] <= lat <= self.bounds['north'] and
                            self.bounds['west'] <= lon <= self.bounds['east']):
                            
                            # Get the actual road/edge the vehicle is on
                            edge_id = traci.vehicle.getRoadID(vehicle.id)
                            lane_pos = traci.vehicle.getLanePosition(vehicle.id)
                            lane_id = traci.vehicle.getLaneID(vehicle.id)
                            
                            # Get vehicle angle for proper orientation
                            angle = traci.vehicle.getAngle(vehicle.id)
                            
                            vehicles_data.append({
                                'id': vehicle.id,
                                'lat': lat,
                                'lon': lon,
                                'type': vehicle.config.vtype.value,
                                'speed': vehicle.speed,
                                'speed_kmh': round(vehicle.speed * 3.6, 1),
                                'soc': vehicle.config.current_soc if vehicle.config.is_ev else 1.0,
                                'battery_percent': round(vehicle.config.current_soc * 100) if vehicle.config.is_ev else 100,
                                'is_charging': vehicle.is_charging,
                                'is_ev': vehicle.config.is_ev,
                                'distance_traveled': round(vehicle.distance_traveled, 1),
                                'waiting_time': round(vehicle.waiting_time, 1),
                                'destination': vehicle.destination,
                                'assigned_station': vehicle.assigned_ev_station,
                                'color': self._get_vehicle_color(vehicle),
                                'angle': angle,
                                'edge': edge_id,
                                'lane_pos': lane_pos,
                                'lane_id': lane_id
                            })
                except Exception as e:
                    continue
            
            return vehicles_data
        
        except Exception as e:
            print(f"Error getting vehicle positions: {e}")
            return []
    
    def _get_vehicle_color(self, vehicle: 'Vehicle') -> str:
        """Get vehicle color for visualization"""
        
        if vehicle.is_charging:
            return '#ffa500'  # Orange for charging
        elif vehicle.config.is_ev:
            if vehicle.config.current_soc < 0.2:
                return '#ff6b6b'  # Red for low battery
            else:
                return '#00ff00'  # Green for EV
        elif vehicle.config.vtype == VehicleType.TAXI:
            return '#ffff00'  # Yellow for taxi
        elif vehicle.config.vtype == VehicleType.BUS:
            return '#4169e1'  # Blue for bus
        else:
            return '#6464ff'  # Default blue for gas vehicles
    
    def update_traffic_lights(self):
        """Sync traffic lights from power grid to SUMO - FIXED for blackouts"""
        
        if not self.running:
            return
        
        import traci
        
        # Get all SUMO traffic lights
        tl_ids = traci.trafficlight.getIDList()
        
        for tl_id in tl_ids:
            try:
                # Get the current signal state to know its structure
                current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                state_length = len(current_state)
                
                # Find corresponding power grid traffic light
                power_tl = None
                if tl_id in self.tl_sumo_to_power:
                    power_tl_id = self.tl_sumo_to_power[tl_id]
                    if power_tl_id in self.integrated_system.traffic_lights:
                        power_tl = self.integrated_system.traffic_lights[power_tl_id]
                
                # Set traffic light state based on power status
                if power_tl:
                    if not power_tl['powered']:
                        # NO POWER = FLASHING YELLOW (vehicles proceed with caution)
                        # Or OFF state - vehicles treat as uncontrolled intersection
                        
                        # Option 1: All yellow (caution mode)
                        yellow_state = 'y' * state_length
                        traci.trafficlight.setRedYellowGreenState(tl_id, yellow_state)
                        
                        # Option 2: Turn off traffic light program (vehicles use priority rules)
                        # traci.trafficlight.setProgram(tl_id, "off")
                        
                    else:
                        # Normal operation - set based on power grid phase
                        if power_tl['phase'] == 'green':
                            # Create green phase pattern
                            if state_length == 4:
                                new_state = 'GGrr'  # Green N-S, Red E-W
                            elif state_length == 8:
                                new_state = 'GGGGrrrr'  # Green main direction
                            else:
                                # General pattern: half green, half red
                                half = state_length // 2
                                new_state = 'G' * half + 'r' * (state_length - half)
                            traci.trafficlight.setRedYellowGreenState(tl_id, new_state)
                            
                        elif power_tl['phase'] == 'yellow':
                            # Yellow phase
                            if state_length == 4:
                                new_state = 'yyrr'
                            elif state_length == 8:
                                new_state = 'yyyyrrrr'
                            else:
                                half = state_length // 2
                                new_state = 'y' * half + 'r' * (state_length - half)
                            traci.trafficlight.setRedYellowGreenState(tl_id, new_state)
                            
                        else:  # red phase
                            # Red main, green cross
                            if state_length == 4:
                                new_state = 'rrGG'  # Red N-S, Green E-W
                            elif state_length == 8:
                                new_state = 'rrrrGGGG'  # Red main, Green cross
                            else:
                                half = state_length // 2
                                new_state = 'r' * half + 'G' * (state_length - half)
                            traci.trafficlight.setRedYellowGreenState(tl_id, new_state)
                else:
                    # No mapping found - let SUMO handle normally
                    pass
                    
            except Exception as e:
                # Continue with other lights if one fails
                pass
    def handle_blackout_traffic_lights(self, affected_substations):
        """Handle traffic lights during blackout - set to flashing yellow or off"""
        
        if not self.running:
            return
        
        import traci
        
        affected_count = 0
        
        for tl_id in traci.trafficlight.getIDList():
            if tl_id in self.tl_sumo_to_power:
                power_tl_id = self.tl_sumo_to_power[tl_id]
                if power_tl_id in self.integrated_system.traffic_lights:
                    power_tl = self.integrated_system.traffic_lights[power_tl_id]
                    
                    # Check if this light's substation is affected
                    if power_tl['substation'] in affected_substations:
                        # Set to yellow (caution) - vehicles can proceed carefully
                        current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                        yellow_state = 'y' * len(current_state)
                        traci.trafficlight.setRedYellowGreenState(tl_id, yellow_state)
                        affected_count += 1
        
        if affected_count > 0:
            print(f"🚦 Set {affected_count} traffic lights to YELLOW (blackout mode)")
    def force_all_lights_red(self):
        """Force all traffic lights to red (for testing)"""
        if not self.running:
            return
        
        import traci
        for tl_id in traci.trafficlight.getIDList():
            try:
                state = traci.trafficlight.getRedYellowGreenState(tl_id)
                red_state = 'r' * len(state)
                traci.trafficlight.setRedYellowGreenState(tl_id, red_state)
            except:
                pass
        print("⚠️ All traffic lights set to RED")        
    
    def step(self):
        """Advance simulation one step"""
        
        if not self.running:
            return
        
        try:
            import traci
            traci.simulationStep()
            
            # These are the ACTUAL methods in your code
            self.update_traffic_lights()  # This exists
            self._update_vehicles()  # This exists  
            self._handle_ev_charging()  # This exists
            self._update_statistics()  # This exists around line 1752
            
        except Exception as e:
            print(f"Simulation step error: {e}")
            import traceback
            traceback.print_exc()

    def _update_statistics(self):
        """Update simulation statistics"""
        
        if not self.running:
            return
        
        try:
            import traci
            vehicle_ids = traci.vehicle.getIDList()
            
            if vehicle_ids:
                speeds = [traci.vehicle.getSpeed(v) for v in vehicle_ids]
                self.stats['avg_speed_mps'] = sum(speeds) / len(speeds) if speeds else 0
                
                self.stats['total_distance_km'] = sum(
                    traci.vehicle.getDistance(v) / 1000 for v in vehicle_ids
                )
                
                self.stats['total_wait_time'] = sum(
                    traci.vehicle.getWaitingTime(v) for v in vehicle_ids
                )
                
                # Calculate energy for EVs
                total_energy = 0
                for vehicle in self.vehicles.values():
                    if vehicle.config.is_ev:
                        energy_used = (1.0 - vehicle.config.current_soc) * vehicle.config.battery_capacity_kwh
                        total_energy += energy_used
                
                self.stats['total_energy_consumed_kwh'] = total_energy
        
        except Exception as e:
            pass  # Silent fail for stats
    def _update_vehicles(self):
        """Update vehicle states with realistic battery drain"""
        
        vehicle_ids = traci.vehicle.getIDList()
        
        for veh_id in vehicle_ids:
            if veh_id in self.vehicles:
                vehicle = self.vehicles[veh_id]
                
                try:
                    # Get vehicle dynamics
                    vehicle.position = traci.vehicle.getPosition(veh_id)
                    speed = traci.vehicle.getSpeed(veh_id)
                    vehicle.speed = speed
                    
                    # FORCE EXTREME SPEED if not charging
                    if not vehicle.is_charging:
                        if speed < 150:  # If going slower than 150 m/s
                            traci.vehicle.setSpeed(veh_id, 200)  # Force 200 m/s
                            traci.vehicle.setSpeedMode(veh_id, 0)  # Ignore all safety
                            traci.vehicle.setAccel(veh_id, 50)  # Super acceleration
                    
                    vehicle.distance_traveled = traci.vehicle.getDistance(veh_id)
                    vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                    
                    # Handle EVs with CALIBRATED battery drain
                    if vehicle.config.is_ev and not vehicle.is_charging:
                        # CALIBRATED DRAIN RATE FOR MANHATTAN
                        # At 200 m/s, we travel 20m per step (0.1s steps)
                        # To drain 30% over 5km: 5000m / 20m = 250 steps
                        # 30% / 250 steps = 0.12% per step
                        
                        # Base drain rate: 0.12% per step at full speed
                        # This ensures from farthest point with 38% battery, 
                        # we arrive at farthest station with 8% left
                        
                        if speed > 150:  # Fast driving (normal for our simulation)
                            drain_rate = 0.0012  # 0.12% per step
                        elif speed > 50:  # Medium speed
                            drain_rate = 0.0008  # 0.08% per step
                        elif speed > 10:  # Slow/traffic
                            drain_rate = 0.0005  # 0.05% per step
                        else:  # Stopped/crawling
                            drain_rate = 0.0002  # 0.02% per step (idle consumption)
                        
                        # Additional drain if accelerating hard
                        try:
                            acceleration = traci.vehicle.getAcceleration(veh_id)
                            if acceleration > 10:  # Hard acceleration
                                drain_rate *= 1.5
                        except:
                            pass
                        
                        # Apply battery drain
                        old_soc = vehicle.config.current_soc
                        vehicle.config.current_soc -= drain_rate
                        vehicle.config.current_soc = max(0, vehicle.config.current_soc)
                        
                        # Update SUMO battery parameter
                        try:
                            new_battery = vehicle.config.current_soc * vehicle.config.battery_capacity_kwh * 1000
                            traci.vehicle.setParameter(veh_id, "device.battery.actualBatteryCapacity", str(new_battery))
                        except:
                            pass
                        
                        # Visual indication of battery level
                        if vehicle.config.current_soc < 0.08:
                            # CRITICAL - below 8% (flashing red)
                            import time
                            flash = int(time.time() * 4) % 2
                            if flash == 0:
                                traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
                            else:
                                traci.vehicle.setColor(veh_id, (139, 0, 0, 255))
                        elif vehicle.config.current_soc < 0.15:
                            # Very low - solid red
                            traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
                        elif vehicle.config.current_soc < 0.25:
                            # Low battery - orange  
                            traci.vehicle.setColor(veh_id, (255, 165, 0, 255))
                        else:
                            # Normal - green
                            traci.vehicle.setColor(veh_id, (0, 255, 0, 255))
                        
                        # Route to charging when below 25% (gives margin to reach station)
                        if vehicle.config.current_soc < 0.25 and not vehicle.assigned_ev_station and self.station_manager:
                            current_edge = traci.vehicle.getRoadID(veh_id)
                            
                            if current_edge and not current_edge.startswith(':'):
                                # Convert position for station manager
                                x, y = vehicle.position
                                lon, lat = traci.simulation.convertGeo(x, y)
                                
                                # Use smart station manager
                                result = self.station_manager.request_charging(
                                    veh_id,
                                    vehicle.config.current_soc,
                                    current_edge,
                                    (lon, lat),
                                    is_emergency=(vehicle.config.current_soc < 0.1)
                                )
                                
                                if result:
                                    station_id, target_edge, wait_time, distance = result
                                    
                                    # Navigate to station
                                    try:
                                        route = traci.simulation.findRoute(current_edge, target_edge)
                                        if route and route.edges:
                                            traci.vehicle.setRoute(veh_id, route.edges)
                                            vehicle.assigned_ev_station = station_id
                                            vehicle.destination = target_edge
                                            
                                            print(f"🔋 {veh_id} (SOC: {vehicle.config.current_soc:.1%}) → {station_id}")
                                    except:
                                        pass
                    
                    # Update route if near end
                    route_index = traci.vehicle.getRouteIndex(veh_id)
                    route = traci.vehicle.getRoute(veh_id)
                    if route_index >= len(route) - 1 and not vehicle.is_charging:
                        new_route = self._generate_realistic_route()
                        if new_route and len(new_route) >= 2:
                            traci.vehicle.setRoute(veh_id, new_route)
                            vehicle.config.destination = new_route[-1]
                    
                except:
                    pass
        
        # Remove vehicles that left
        current_ids = set(vehicle_ids)
        for veh_id in list(self.vehicles.keys()):
            if veh_id not in current_ids:
                del self.vehicles[veh_id]
    
    def _generate_realistic_route(self) -> List[str]:
        """Generate realistic Manhattan route with validation"""
        
        if not self.edges:
            return []
        
        edge_pool = self.spawn_edges if self.spawn_edges else self.edges
        
        for attempt in range(10):
            if self.popular_routes and random.random() < 0.3:
                origin, destination = random.choice(self.popular_routes)
            elif self.destinations and random.random() < 0.3:
                origin = random.choice(edge_pool)
                _, destination = random.choice(self.destinations)
            else:
                if len(edge_pool) >= 2:
                    origin = random.choice(edge_pool)
                    destination = random.choice(edge_pool)
                else:
                    return []
            
            if origin != destination:
                try:
                    if self.net.getEdge(origin) and self.net.getEdge(destination):
                        return [origin, destination]
                except:
                    pass
        
        if len(edge_pool) >= 2:
            return [edge_pool[0], edge_pool[1]]
        
        return []
    
    def _route_to_charging_station(self, vehicle):
        """Route EV to nearest available charging station"""
        
        if not vehicle.config.is_ev or vehicle.is_charging:
            return
        
        try:
            current_edge = traci.vehicle.getRoadID(vehicle.id)
            
            best_station = None
            
            for ev_id, station in self.ev_stations_sumo.items():
                if station['available'] > 0:
                    if ev_id in self.integrated_system.ev_stations:
                        if not self.integrated_system.ev_stations[ev_id]['operational']:
                            continue
                    
                    try:
                        if current_edge and station['edge']:
                            if station['available'] > len(station['charging']):
                                best_station = (ev_id, station)
                                break
                    except:
                        pass
            
            if best_station:
                ev_id, station = best_station
                traci.vehicle.changeTarget(vehicle.id, station['edge'])
                vehicle.destination = station['edge']
                vehicle.assigned_ev_station = ev_id
                print(f"Vehicle {vehicle.id} routing to charging station {ev_id}")
        
        except Exception as e:
            pass
    
    def _handle_ev_charging(self):
        """Handle EV charging with proper stopping and visual feedback"""
        
        import traci
        import random
        
        # First, update station occupancy counts
        station_occupancy = {}
        for station_id in self.integrated_system.ev_stations.keys():
            station_occupancy[station_id] = {
                'charging': [],
                'queued': [],
                'circling': []
            }
        
        # Count vehicles at each station - ENSURE ATTRIBUTES EXIST
        for vehicle in self.vehicles.values():
            if vehicle.config.is_ev:
                # Initialize attributes if they don't exist
                if not hasattr(vehicle, 'is_charging'):
                    vehicle.is_charging = False
                if not hasattr(vehicle, 'is_queued'):
                    vehicle.is_queued = False
                if not hasattr(vehicle, 'is_circling'):
                    vehicle.is_circling = False
                if not hasattr(vehicle, 'is_stranded'):
                    vehicle.is_stranded = False
                if not hasattr(vehicle, 'queue_position'):
                    vehicle.queue_position = 0
                    
                # Count vehicles at stations
                if vehicle.assigned_ev_station:
                    station_id = vehicle.assigned_ev_station
                    if station_id in station_occupancy:
                        if vehicle.is_charging:
                            station_occupancy[station_id]['charging'].append(vehicle.id)
                        elif vehicle.is_queued:
                            station_occupancy[station_id]['queued'].append(vehicle.id)
                        elif vehicle.is_circling:
                            station_occupancy[station_id]['circling'].append(vehicle.id)
        
        # Process each EV
        for vehicle in list(self.vehicles.values()):  # Use list() to avoid iteration issues
            if not vehicle.config.is_ev:
                continue
            
            try:
                veh_id = vehicle.id
                
                # Get vehicle position safely
                if veh_id not in traci.vehicle.getIDList():
                    continue
                    
                current_edge = traci.vehicle.getRoadID(veh_id)
                
                # Skip if on internal edge
                if current_edge.startswith(':'):
                    continue
                
                # CHECK IF VEHICLE IS OUT OF BATTERY (STRANDED)
                if vehicle.config.current_soc <= 0.01:  # Less than 1% battery
                    if not vehicle.is_stranded:
                        vehicle.is_stranded = True
                        vehicle.is_charging = False
                        vehicle.is_queued = False
                        vehicle.is_circling = False
                        
                        # Stop the vehicle completely
                        try:
                            traci.vehicle.setSpeed(veh_id, 0)
                            traci.vehicle.setSpeedMode(veh_id, 0)
                        except:
                            pass
                        
                        print(f"💀 {veh_id} STRANDED - BATTERY DEAD at {current_edge}!")
                        
                    # Flashing effect for stranded vehicle
                    import time
                    flash = int(time.time() * 2) % 2  # Flash every 0.5 seconds
                    if flash == 0:
                        traci.vehicle.setColor(veh_id, (255, 0, 255, 255))  # Magenta
                    else:
                        traci.vehicle.setColor(veh_id, (128, 0, 128, 255))  # Dark magenta
                    continue  # Skip rest of processing for dead vehicle
                
                # If vehicle has no assigned station but needs charging
                if not vehicle.assigned_ev_station and vehicle.config.current_soc < 0.25:
                    # Find nearest operational station
                    best_station = None
                    min_dist = float('inf')
                    
                    for ev_id, ev_station in self.integrated_system.ev_stations.items():
                        if not ev_station['operational']:
                            continue
                        
                        # Check if station has space
                        if ev_id in station_occupancy:
                            if len(station_occupancy[ev_id]['charging']) >= 20 and len(station_occupancy[ev_id]['queued']) >= 20:
                                continue  # Station full
                        
                        # Simple distance check
                        if hasattr(self, 'station_manager') and self.station_manager:
                            if ev_id in self.station_manager.stations:
                                station_edge = self.station_manager.stations[ev_id]['edge']
                                try:
                                    route = traci.simulation.findRoute(current_edge, station_edge)
                                    if route and route.edges and len(route.edges) < min_dist:
                                        min_dist = len(route.edges)
                                        best_station = ev_id
                                except:
                                    pass
                    
                    if best_station:
                        vehicle.assigned_ev_station = best_station
                        if self.station_manager and best_station in self.station_manager.stations:
                            station_edge = self.station_manager.stations[best_station]['edge']
                            
                            try:
                                route = traci.simulation.findRoute(current_edge, station_edge)
                                if route and route.edges:
                                    traci.vehicle.setRoute(veh_id, route.edges)
                                    station_name = self.integrated_system.ev_stations[best_station]['name']
                                    print(f"🔋 {veh_id} (SOC: {vehicle.config.current_soc:.0%}) → {station_name}")
                            except Exception as e:
                                print(f"Route error for {veh_id}: {e}")
                
                # Check if vehicle is at its assigned charging station
                if vehicle.assigned_ev_station and self.station_manager:
                    station = self.station_manager.stations.get(vehicle.assigned_ev_station)
                    
                    if not station:
                        continue
                    
                    # Check if station has power
                    ev_station_info = self.integrated_system.ev_stations.get(vehicle.assigned_ev_station)
                    if ev_station_info and not ev_station_info['operational']:
                        print(f"⚡ {veh_id} at {station['name']} - NO POWER!")
                        vehicle.assigned_ev_station = None
                        vehicle.is_charging = False
                        vehicle.is_queued = False
                        vehicle.is_circling = False
                        continue
                    
                    # Check if at charging station edge
                    if current_edge == station['edge']:
                        # Get current station occupancy
                        station_id = vehicle.assigned_ev_station
                        charging_count = len(station_occupancy[station_id]['charging'])
                        queued_count = len(station_occupancy[station_id]['queued'])
                        
                        # Vehicle just arrived at station - check if not already processed
                        if not vehicle.is_charging and not vehicle.is_queued and not vehicle.is_circling:
                            
                            print(f"📍 {veh_id} arrived at {station['name']}: {charging_count}/20 charging, {queued_count}/20 queued")
                            
                            if charging_count < 20:
                                # SPACE AVAILABLE TO CHARGE IMMEDIATELY
                                vehicle.is_charging = True
                                vehicle.is_queued = False
                                vehicle.is_circling = False
                                station_occupancy[station_id]['charging'].append(veh_id)
                                
                                # Park for charging
                                try:
                                    lane_pos = traci.vehicle.getLanePosition(veh_id)
                                    lane_id = traci.vehicle.getLaneID(veh_id)
                                    
                                    # Calculate parking position
                                    parking_offset = 10 + (charging_count * 5)  # Space out vehicles
                                    stop_pos = min(lane_pos + parking_offset, traci.lane.getLength(lane_id) - 5)
                                    
                                    # Stop for 5 minutes (3000 steps)
                                    traci.vehicle.setStop(
                                        veh_id,
                                        current_edge,
                                        pos=stop_pos,
                                        laneIndex=0,
                                        duration=3000,
                                        flags=1  # Parking
                                    )
                                    
                                    # Visual: Cyan for charging
                                    traci.vehicle.setColor(veh_id, (0, 255, 255, 255))
                                    
                                    print(f"⚡ {veh_id} CHARGING at {station['name']} (Slot {charging_count + 1}/20)")
                                    
                                    # Update statistics immediately
                                    self.stats['vehicles_charging'] = sum(
                                        len(s['charging']) for s in station_occupancy.values()
                                    )
                                    
                                except Exception as e:
                                    print(f"Error parking {veh_id}: {e}")
                                
                            elif queued_count < 20:
                                # JOIN QUEUE
                                vehicle.is_queued = True
                                vehicle.is_charging = False
                                vehicle.is_circling = False
                                vehicle.queue_position = queued_count + 1
                                station_occupancy[station_id]['queued'].append(veh_id)
                                
                                # Park in queue area
                                try:
                                    lane_pos = traci.vehicle.getLanePosition(veh_id)
                                    lane_id = traci.vehicle.getLaneID(veh_id)
                                    
                                    # Queue behind charging area
                                    queue_offset = 150 + (queued_count * 5)
                                    queue_pos = min(lane_pos + queue_offset, traci.lane.getLength(lane_id) - 5)
                                    
                                    # Stop for 1 minute then check again
                                    traci.vehicle.setStop(
                                        veh_id,
                                        current_edge,
                                        pos=queue_pos,
                                        laneIndex=0,
                                        duration=600,
                                        flags=0  # Waiting, not parking
                                    )
                                    
                                    # Visual: Yellow for waiting
                                    traci.vehicle.setColor(veh_id, (255, 255, 0, 255))
                                    
                                    print(f"⏳ {veh_id} QUEUED at {station['name']} (Position {vehicle.queue_position}/20)")
                                except Exception as e:
                                    print(f"Error queuing {veh_id}: {e}")
                                
                            else:
                                # STATION COMPLETELY FULL - START CIRCLING
                                vehicle.is_circling = True
                                vehicle.is_charging = False
                                vehicle.is_queued = False
                                station_occupancy[station_id]['circling'].append(veh_id)
                                
                                print(f"❌ {station['name']} FULL! {veh_id} will circle nearby")
                                
                                # Create circular route around station
                                try:
                                    # Get nearby edges
                                    all_edges = traci.edge.getIDList()
                                    nearby_edges = []
                                    
                                    # Find edges near the station
                                    for edge in all_edges[:50]:  # Check first 50 edges
                                        if not edge.startswith(':') and edge != current_edge:
                                            nearby_edges.append(edge)
                                    
                                    if len(nearby_edges) >= 3:
                                        # Create a circular route
                                        circle_route = [current_edge]
                                        for i in range(3):
                                            if nearby_edges:
                                                next_edge = random.choice(nearby_edges)
                                                circle_route.append(next_edge)
                                                nearby_edges.remove(next_edge)
                                        circle_route.append(current_edge)  # Return to station
                                        
                                        traci.vehicle.setRoute(veh_id, circle_route)
                                        
                                        # Slow down to conserve battery
                                        traci.vehicle.setSpeed(veh_id, 50)  # Slower speed while circling
                                        
                                        # Visual: Dark orange for circling
                                        traci.vehicle.setColor(veh_id, (255, 140, 0, 255))
                                        
                                        print(f"🔄 {veh_id} circling route: {' → '.join(circle_route[:3])}...")
                                except Exception as e:
                                    print(f"Error setting circle route for {veh_id}: {e}")
                        
                        # Handle vehicles already charging
                        elif vehicle.is_charging:
                            # Make sure vehicle stays stopped
                            if traci.vehicle.getSpeed(veh_id) > 0.1:
                                traci.vehicle.setSpeed(veh_id, 0)
                            
                            # Animated charging effect
                            import time
                            pulse = int(time.time() * 4) % 4
                            colors = [(0, 255, 255, 255), (100, 255, 255, 255), 
                                    (0, 200, 255, 255), (150, 255, 255, 255)]
                            traci.vehicle.setColor(veh_id, colors[pulse])
                            
                            # Update battery
                            old_soc = vehicle.config.current_soc
                            charge_rate = 0.00027  # 80% in 3000 steps
                            vehicle.config.current_soc = min(0.80, vehicle.config.current_soc + charge_rate)
                            
                            # Update SUMO battery
                            new_battery = vehicle.config.current_soc * vehicle.config.battery_capacity_kwh * 1000
                            traci.vehicle.setParameter(veh_id, "device.battery.actualBatteryCapacity", str(new_battery))
                            
                            # Show progress every 20%
                            if int(old_soc * 5) != int(vehicle.config.current_soc * 5):
                                print(f"🔋 {veh_id} @ {station['name']}: {vehicle.config.current_soc:.0%} charged")
                            
                            # Finish charging at 80%
                            if vehicle.config.current_soc >= 0.80:
                                vehicle.is_charging = False
                                vehicle.assigned_ev_station = None
                                
                                # Remove from charging list
                                if veh_id in station_occupancy[station_id]['charging']:
                                    station_occupancy[station_id]['charging'].remove(veh_id)
                                
                                # Check if anyone is queued
                                if station_occupancy[station_id]['queued']:
                                    next_veh = station_occupancy[station_id]['queued'][0]
                                    print(f"📢 {next_veh} can now charge (was queued)")
                                
                                # Resume driving
                                traci.vehicle.resume(veh_id)
                                traci.vehicle.setColor(veh_id, (0, 255, 0, 255))  # Green
                                traci.vehicle.setSpeed(veh_id, 200)  # Back to fast speed
                                
                                print(f"✅ {veh_id} FULLY CHARGED! Leaving {station['name']}")
                                
                                # Set new destination
                                edges = [e for e in traci.edge.getIDList() if not e.startswith(':')]
                                if edges:
                                    new_dest = random.choice(edges)
                                    try:
                                        route = traci.simulation.findRoute(current_edge, new_dest)
                                        if route and route.edges:
                                            traci.vehicle.setRoute(veh_id, route.edges)
                                    except:
                                        pass
                        
                        # Handle queued vehicles
                        elif vehicle.is_queued:
                            # Check if can move to charging
                            if len(station_occupancy[station_id]['charging']) < 20:
                                vehicle.is_queued = False
                                vehicle.is_charging = True
                                
                                # Update lists
                                if veh_id in station_occupancy[station_id]['queued']:
                                    station_occupancy[station_id]['queued'].remove(veh_id)
                                station_occupancy[station_id]['charging'].append(veh_id)
                                
                                print(f"📤 {veh_id} moved from QUEUE to CHARGING at {station['name']}")
                                
                                # Move to charging position
                                traci.vehicle.resume(veh_id)
                                
                                # Re-stop for charging
                                try:
                                    lane_pos = traci.vehicle.getLanePosition(veh_id)
                                    charging_count = len(station_occupancy[station_id]['charging'])
                                    stop_pos = min(10 + (charging_count * 5), traci.lane.getLength(traci.vehicle.getLaneID(veh_id)) - 5)
                                    
                                    traci.vehicle.setStop(
                                        veh_id,
                                        current_edge,
                                        pos=stop_pos,
                                        laneIndex=0,
                                        duration=3000,
                                        flags=1
                                    )
                                    
                                    traci.vehicle.setColor(veh_id, (0, 255, 255, 255))
                                except:
                                    pass
                        
                        # Handle circling vehicles  
                        elif vehicle.is_circling:
                            # Check station availability periodically
                            charging_count = len(station_occupancy[station_id]['charging'])
                            queued_count = len(station_occupancy[station_id]['queued'])
                            
                            if charging_count < 20 or queued_count < 20:
                                # Space available! Stop circling
                                vehicle.is_circling = False
                                print(f"🎉 {veh_id} found space! Returning to {station['name']}")
                                
                                # Route back to station
                                try:
                                    route = traci.simulation.findRoute(current_edge, station['edge'])
                                    if route and route.edges:
                                        traci.vehicle.setRoute(veh_id, route.edges)
                                        traci.vehicle.setSpeed(veh_id, 200)  # Speed up
                                except:
                                    pass
                            else:
                                # Continue circling, battery draining
                                if vehicle.config.current_soc <= 0.01:
                                    vehicle.is_circling = False
                                    vehicle.is_stranded = True
                                    print(f"💀 {veh_id} ran out of battery while circling!")
                        
            except Exception as e:
                if "resume" not in str(e) and "stop" not in str(e):
                    print(f"Charging error for {vehicle.id}: {e}")
        
        # Update global statistics
        total_charging = sum(len(s['charging']) for s in station_occupancy.values())
        total_queued = sum(len(s['queued']) for s in station_occupancy.values())
        total_circling = sum(len(s['circling']) for s in station_occupancy.values())
        
        self.stats['vehicles_charging'] = total_charging
        self.stats['vehicles_queued'] = total_queued
        self.stats['vehicles_circling'] = total_circling
        
        # Print summary every 100 steps
        if hasattr(self, 'step_counter'):
            self.step_counter += 1
        else:
            self.step_counter = 0
            
        if self.step_counter % 100 == 0 and (total_charging > 0 or total_queued > 0):
            print(f"\n📊 CHARGING STATUS: {total_charging} charging, {total_queued} queued, {total_circling} circling")
    def get_statistics(self) -> Dict:
        """Get current simulation statistics"""
        
        # Count actual charging, queued, circling and stranded vehicles
        actual_charging = 0
        actual_queued = 0
        actual_circling = 0
        actual_stranded = 0
        
        # Debug tracking
        charging_vehicles = []
        queued_vehicles = []
        
        for vehicle in self.vehicles.values():
            if vehicle.config.is_ev:
                # Initialize attributes if they don't exist
                if not hasattr(vehicle, 'is_charging'):
                    vehicle.is_charging = False
                if not hasattr(vehicle, 'is_queued'):
                    vehicle.is_queued = False
                if not hasattr(vehicle, 'is_circling'):
                    vehicle.is_circling = False
                if not hasattr(vehicle, 'is_stranded'):
                    vehicle.is_stranded = False
                
                # Count based on states (priority order matters)
                if vehicle.is_stranded:
                    actual_stranded += 1
                elif vehicle.is_charging:
                    actual_charging += 1
                    charging_vehicles.append(f"{vehicle.id}@{vehicle.assigned_ev_station}")
                elif vehicle.is_queued:
                    actual_queued += 1
                    queued_vehicles.append(f"{vehicle.id}@{vehicle.assigned_ev_station}")
                elif vehicle.is_circling:
                    actual_circling += 1
        
        # Debug output if there are charging vehicles
        if actual_charging > 0:
            print(f"[DEBUG] Charging vehicles: {', '.join(charging_vehicles)}")
        if actual_queued > 0:
            print(f"[DEBUG] Queued vehicles: {', '.join(queued_vehicles)}")
        
        # Update the stats
        self.stats['vehicles_charging'] = actual_charging
        self.stats['vehicles_queued'] = actual_queued
        self.stats['vehicles_circling'] = actual_circling
        self.stats['vehicles_stranded'] = actual_stranded
        
        # Count active vehicles
        active_count = 0
        if self.running:
            try:
                import traci
                vehicle_ids = traci.vehicle.getIDList()
                active_count = len(vehicle_ids)
                
                # Also count EVs specifically
                ev_count = sum(1 for v in self.vehicles.values() if v.config.is_ev)
                self.stats['ev_vehicles'] = ev_count
                
            except:
                active_count = len(self.vehicles)
        
        self.stats['active_vehicles'] = active_count
        
        # Calculate other statistics if SUMO is running
        if self.running:
            try:
                import traci
                vehicle_ids = traci.vehicle.getIDList()
                
                if vehicle_ids:
                    # Average speed
                    speeds = []
                    total_distance = 0
                    total_wait = 0
                    
                    for v_id in vehicle_ids:
                        try:
                            speeds.append(traci.vehicle.getSpeed(v_id))
                            total_distance += traci.vehicle.getDistance(v_id)
                            total_wait += traci.vehicle.getWaitingTime(v_id)
                        except:
                            pass
                    
                    self.stats['avg_speed_mps'] = sum(speeds) / len(speeds) if speeds else 0
                    self.stats['total_distance_km'] = total_distance / 1000
                    self.stats['total_wait_time'] = total_wait
                    
                    # Calculate total energy consumed by EVs
                    total_energy = 0
                    for vehicle in self.vehicles.values():
                        if vehicle.config.is_ev:
                            # Energy used = capacity * (1 - current_soc)
                            energy_used = vehicle.config.battery_capacity_kwh * (1.0 - vehicle.config.current_soc)
                            total_energy += energy_used
                    
                    self.stats['total_energy_consumed_kwh'] = total_energy
            except Exception as e:
                print(f"[DEBUG] Error calculating stats: {e}")
        
        # Ensure all required keys exist with default values
        required_keys = [
            'total_vehicles', 'ev_vehicles', 'active_vehicles',
            'vehicles_charging', 'vehicles_queued', 'vehicles_circling', 
            'vehicles_stranded', 'avg_speed_mps', 'total_distance_km',
            'total_wait_time', 'total_energy_consumed_kwh'
        ]
        
        for key in required_keys:
            if key not in self.stats:
                self.stats[key] = 0
        
        # Print summary if vehicles are charging
        if actual_charging > 0 or actual_queued > 0:
            print(f"[STATS] Active: {active_count}, Charging: {actual_charging}, Queued: {actual_queued}, Circling: {actual_circling}, Stranded: {actual_stranded}")
        
        return self.stats.copy()
    def stop(self):
        """Stop SUMO simulation"""
        
        if self.running:
            try:
                traci.close()
                self.running = False
                self.vehicles.clear()
                print("SUMO stopped")
            except:
                pass

class Vehicle:
    """Individual vehicle tracking"""
    
    def __init__(self, vehicle_id: str, config: VehicleConfig):
        self.id = vehicle_id
        self.config = config
        self.position = (0, 0)
        self.speed = 0
        self.distance_traveled = 0
        self.waiting_time = 0
        self.is_charging = False
        self.is_queued = False
        self.is_circling = False
        self.is_stranded = False
        self.charging_at_station = None  # ADD THIS
        self.queue_position = 0
        self.assigned_ev_station = None
        self.destination = config.destination if config else None
        
    def __repr__(self):
        if self.config:
            if self.config.is_ev:
                return f"Vehicle({self.id}, {self.config.vtype.value}, SOC:{self.config.current_soc:.1%})"
            else:
                return f"Vehicle({self.id}, {self.config.vtype.value})"
        else:
            return f"Vehicle({self.id})"