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
        
        spawn_edges = self.spawn_edges if self.spawn_edges else self.edges
        if not spawn_edges:
            print("No valid spawn edges found")
            return 0
        
        for i in range(count):
            vehicle_id = f"veh_{self.stats['total_vehicles'] + i}"
            
            is_ev = random.random() < ev_percentage
            if is_ev:
                vtype = "ev_sedan" if random.random() < 0.6 else "ev_suv"
            else:
                vtype = random.choice(["car", "taxi"])
            
            route_created = False
            
            for attempt in range(5):
                try:
                    # Use validated edges
                    origin_idx = random.randint(0, min(100, len(spawn_edges)-1))
                    dest_idx = random.randint(0, min(100, len(spawn_edges)-1))
                    
                    if origin_idx != dest_idx:
                        origin = spawn_edges[origin_idx]
                        destination = spawn_edges[dest_idx]
                        
                        route_id = f"route_{vehicle_id}_{attempt}"
                        
                        # Try to compute actual route
                        try:
                            route = traci.simulation.findRoute(origin, destination)
                            if route and route.edges:
                                traci.route.add(route_id, route.edges)
                            else:
                                traci.route.add(route_id, [origin, destination])
                        except:
                            traci.route.add(route_id, [origin, destination])
                        
                        traci.vehicle.add(
                            vehicle_id,
                            route_id,
                            typeID=vtype,
                            depart="now"
                        )
                        
                        route_created = True
                        
                        initial_soc = 1.0
                        if is_ev:
                            battery_capacity = 75000 if vtype == "ev_sedan" else 100000
                            initial_soc = random.uniform(0.3, 0.9)
                            
                            traci.vehicle.setParameter(vehicle_id, "device.battery.maximumBatteryCapacity", str(battery_capacity))
                            traci.vehicle.setParameter(vehicle_id, "device.battery.actualBatteryCapacity", str(battery_capacity * initial_soc))
                            traci.vehicle.setParameter(vehicle_id, "has.battery.device", "true")
                        
                        vtype_enum = VehicleType.CAR
                        if vtype == "taxi":
                            vtype_enum = VehicleType.TAXI
                        elif vtype == "ev_sedan":
                            vtype_enum = VehicleType.EV_SEDAN
                        elif vtype == "ev_suv":
                            vtype_enum = VehicleType.EV_SUV
                        
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
                                route=[origin, destination]
                            )
                        )
                        
                        spawned += 1
                        
                        if is_ev:
                            self.stats['ev_vehicles'] += 1
                        
                        break
                        
                except Exception as e:
                    continue
        
        self.stats['total_vehicles'] += spawned
        print(f"Successfully spawned {spawned}/{count} vehicles")
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
        """Sync traffic lights from power grid to SUMO"""
        
        if not self.running:
            return
        
        for power_tl_id, sumo_tl_id in self.tl_power_to_sumo.items():
            if power_tl_id in self.integrated_system.traffic_lights:
                power_tl = self.integrated_system.traffic_lights[power_tl_id]
                
                try:
                    if not power_tl['powered']:
                        program = traci.trafficlight.getProgram(sumo_tl_id)
                        phases = traci.trafficlight.getAllProgramLogics(sumo_tl_id)[0].phases
                        
                        red_state = 'r' * len(phases[0].state) if phases else 'rrrr'
                        
                        traci.trafficlight.setRedYellowGreenState(sumo_tl_id, red_state)
                    else:
                        pass
                        
                except Exception as e:
                    pass
    
    def step(self):
        """Advance simulation one step"""
        
        if not self.running:
            return
        
        try:
            traci.simulationStep()
            
            self._update_vehicles()
            self._handle_ev_charging()
            self._update_statistics()
            
        except Exception as e:
            print(f"Simulation step error: {e}")
    
    def _update_vehicles(self):
        """Update vehicle states"""
        
        vehicle_ids = traci.vehicle.getIDList()
        
        for veh_id in vehicle_ids:
            if veh_id in self.vehicles:
                vehicle = self.vehicles[veh_id]
                
                try:
                    vehicle.position = traci.vehicle.getPosition(veh_id)
                    vehicle.speed = traci.vehicle.getSpeed(veh_id)
                    vehicle.distance_traveled = traci.vehicle.getDistance(veh_id)
                    vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                    
                    if vehicle.config.is_ev:
                        try:
                            battery = traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity")
                            if battery:
                                vehicle.config.current_soc = float(battery) / (vehicle.config.battery_capacity_kwh * 1000)
                        except:
                            pass
                        
                        if vehicle.config.current_soc < 0.2 and not vehicle.is_charging:
                            self._route_to_charging_station(vehicle)
                    
                    route_index = traci.vehicle.getRouteIndex(veh_id)
                    route = traci.vehicle.getRoute(veh_id)
                    if route_index >= len(route) - 1:
                        new_route = self._generate_realistic_route()
                        if new_route and len(new_route) >= 2:
                            traci.vehicle.setRoute(veh_id, new_route)
                            vehicle.config.destination = new_route[-1]
                    
                except:
                    pass
        
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
        """Handle EV charging at stations"""
        
        for vehicle in self.vehicles.values():
            if not vehicle.config.is_ev:
                continue
            
            try:
                current_edge = traci.vehicle.getRoadID(vehicle.id)
                
                for ev_id, station in self.ev_stations_sumo.items():
                    if current_edge == station['edge'] and vehicle.config.current_soc < 0.8:
                        if not vehicle.is_charging and station['available'] > len(station['charging']):
                            vehicle.is_charging = True
                            vehicle.assigned_ev_station = ev_id
                            station['charging'].append(vehicle.id)
                            self.stats['vehicles_charging'] += 1
                            
                            traci.vehicle.setStop(
                                vehicle.id,
                                current_edge,
                                traci.vehicle.getLanePosition(vehicle.id),
                                duration=30
                            )
                
                if vehicle.is_charging:
                    vehicle.config.current_soc = min(1.0, vehicle.config.current_soc + 0.01)
                    
                    new_battery = vehicle.config.current_soc * vehicle.config.battery_capacity_kwh * 1000
                    traci.vehicle.setParameter(vehicle.id, "device.battery.actualBatteryCapacity", str(new_battery))
                    
                    if vehicle.config.current_soc >= 0.8:
                        vehicle.is_charging = False
                        if vehicle.assigned_ev_station in self.ev_stations_sumo:
                            station = self.ev_stations_sumo[vehicle.assigned_ev_station]
                            if vehicle.id in station['charging']:
                                station['charging'].remove(vehicle.id)
                        vehicle.assigned_ev_station = None
                        self.stats['vehicles_charging'] -= 1
                        
                        traci.vehicle.resume(vehicle.id)
                        
                        new_route = self._generate_realistic_route()
                        if new_route:
                            traci.vehicle.changeTarget(vehicle.id, new_route[-1])
                
            except:
                pass
    
    def _update_statistics(self):
        """Update simulation statistics"""
        
        if not self.running:
            return
        
        try:
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
                
                total_energy = 0
                for vehicle in self.vehicles.values():
                    if vehicle.config.is_ev:
                        energy_used = (vehicle.distance_traveled / 1000) * vehicle.config.consumption_kwh_per_km
                        total_energy += energy_used
                
                self.stats['total_energy_consumed_kwh'] = total_energy
        
        except:
            pass
    
    def get_statistics(self) -> Dict:
        """Get current simulation statistics"""
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