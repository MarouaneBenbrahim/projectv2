"""
Manhattan SUMO Vehicle Manager - FIXED VERSION with Accurate Coordinate Projection
Professional integration with guaranteed valid routes and proper coordinate conversion
"""

import traci
import sumolib
import random
import numpy as np
import json
import os
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

class VehicleType(Enum):
    """Vehicle types with energy consumption"""
    SEDAN_EV = "sedan_ev"
    SUV_EV = "suv_ev"
    TAXI_EV = "taxi_ev"
    BUS_EV = "bus_ev"
    SEDAN_GAS = "sedan_gas"
    SUV_GAS = "suv_gas"
    TAXI_GAS = "taxi_gas"

@dataclass
class VehicleConfig:
    """Vehicle configuration with realistic parameters"""
    vtype: VehicleType
    battery_capacity_kwh: float = 75.0
    current_soc: float = 0.8
    consumption_kwh_per_km: float = 0.2
    max_speed_mps: float = 22.2
    acceleration: float = 2.6
    deceleration: float = 4.5
    length: float = 4.5
    min_gap: float = 2.5
    charging_threshold: float = 0.2
    is_ev: bool = True

@dataclass
class ManhattanVehicle:
    """Individual vehicle with full state tracking"""
    id: str
    config: VehicleConfig
    current_edge: str = ""
    current_lane: int = 0
    position: Tuple[float, float] = (0, 0)
    speed: float = 0
    route: List[str] = field(default_factory=list)
    destination: str = ""
    distance_traveled: float = 0
    is_charging: bool = False
    assigned_ev_station: Optional[str] = None
    waiting_time: float = 0
    co2_emission: float = 0
    fuel_consumption: float = 0

class SimulationScenario(Enum):
    """Time-of-day scenarios"""
    NIGHT = "night"
    MORNING_RUSH = "morning_rush"
    MIDDAY = "midday"
    EVENING_RUSH = "evening_rush"
    EVENING = "evening"

class NetworkAnalyzer:
    """Analyzes and validates SUMO network for proper routing"""
    
    def __init__(self, net_file):
        self.net_file = net_file
        self.net = sumolib.net.readNet(net_file)
        
        # Categories of edges
        self.drivable_edges = []
        self.connected_edges = {}
        self.main_component = set()
        self.routable_edges = []
        
        # Analyze network
        self._analyze_network()
        self._find_connected_components()
        
    def _analyze_network(self):
        """Analyze network structure"""
        print("Analyzing network structure...")
        
        for edge in self.net.getEdges():
            edge_id = edge.getID()
            
            # Skip internal junction edges
            if edge_id.startswith(':'):
                continue
                
            # Check if edge allows passenger vehicles
            if edge.allows('passenger'):
                self.drivable_edges.append(edge_id)
                
                # Find connected edges
                self.connected_edges[edge_id] = []
                to_node = edge.getToNode()
                for out_edge in to_node.getOutgoing():
                    if out_edge.allows('passenger') and not out_edge.getID().startswith(':'):
                        self.connected_edges[edge_id].append(out_edge.getID())
        
        print(f"  Found {len(self.drivable_edges)} drivable edges")
        
    def _find_connected_components(self):
        """Find the main connected component"""
        visited = set()
        components = []
        
        for edge in self.drivable_edges:
            if edge not in visited:
                component = self._dfs(edge, visited)
                components.append(component)
        
        # Find largest connected component
        if components:
            self.main_component = max(components, key=len)
            self.routable_edges = list(self.main_component)
            print(f"  Main component: {len(self.routable_edges)} edges ({len(self.routable_edges)*100//len(self.drivable_edges)}% connected)")
        else:
            self.routable_edges = self.drivable_edges
            print("  Warning: No connected components found, using all edges")
    
    def _dfs(self, start_edge, visited):
        """Depth-first search to find connected component"""
        stack = [start_edge]
        component = set()
        
        while stack:
            edge = stack.pop()
            if edge in visited:
                continue
                
            visited.add(edge)
            component.add(edge)
            
            for next_edge in self.connected_edges.get(edge, []):
                if next_edge not in visited:
                    stack.append(next_edge)
                    
        return component
    
    def get_valid_od_pair(self):
        """Get a valid origin-destination pair from connected edges"""
        if len(self.routable_edges) < 2:
            return None, None
            
        origin = random.choice(self.routable_edges)
        destination = random.choice(self.routable_edges)
        
        # Ensure they're different
        attempts = 0
        while destination == origin and attempts < 10:
            destination = random.choice(self.routable_edges)
            attempts += 1
            
        return origin, destination

class ManhattanSUMOManager:
    """
    Fixed SUMO integration for Manhattan Power Grid with accurate coordinate projection
    """
    
    def __init__(self, integrated_system, network_file='data/sumo/manhattan.net.xml'):
        self.integrated_system = integrated_system
        self.network_file = network_file
        self.net = None
        self.running = False
        self.vehicles: Dict[str, ManhattanVehicle] = {}
        self.current_scenario = SimulationScenario.MIDDAY
        self.simulation_time = 0
        self.step_length = 0.1
        
        # Network analyzer for valid routing
        self.network_analyzer = None
        self.valid_spawn_edges = []
        
        # Network bounds for accurate coordinate projection
        self.network_bounds = None  # Will store (x_min, y_min, x_max, y_max)
        
        # Traffic light zone bounds (where your infrastructure is)
        self.zone_bounds = {
            'min_lat': 40.745,
            'max_lat': 40.770,  # Midtown coverage
            'min_lon': -73.995,
            'max_lon': -73.965  # Times Square to Grand Central area
        }
        
        # Manhattan bounds for coordinate conversion
        self.bounds = {
            'min_lat': 40.745,
            'max_lat': 40.775,
            'min_lon': -74.010,
            'max_lon': -73.960
        }
        
        # Traffic light mapping
        self.tls_mapping = {}
        
        # EV stations
        self.ev_stations_sumo = {}
        
        # Vehicle types
        self.vehicle_types = {
            VehicleType.SEDAN_EV: VehicleConfig(
                vtype=VehicleType.SEDAN_EV,
                battery_capacity_kwh=75,
                consumption_kwh_per_km=0.18,
                is_ev=True
            ),
            VehicleType.SUV_EV: VehicleConfig(
                vtype=VehicleType.SUV_EV,
                battery_capacity_kwh=100,
                consumption_kwh_per_km=0.25,
                is_ev=True
            ),
            VehicleType.TAXI_EV: VehicleConfig(
                vtype=VehicleType.TAXI_EV,
                battery_capacity_kwh=60,
                consumption_kwh_per_km=0.16,
                is_ev=True
            ),
            VehicleType.SEDAN_GAS: VehicleConfig(
                vtype=VehicleType.SEDAN_GAS,
                is_ev=False,
                consumption_kwh_per_km=0
            ),
        }
        
        # Route cache for performance
        self.route_cache = {}
        self.failed_routes = set()  # Track failed route pairs
        
        # Statistics
        self.stats = {
            'total_vehicles': 0,
            'ev_vehicles': 0,
            'vehicles_charging': 0,
            'total_energy_consumed_kwh': 0,
            'avg_speed_mps': 0,
            'total_wait_time': 0,
            'spawn_success_rate': 0
        }
        
        # Edge categories
        self.edge_categories = {
            'avenues': [],
            'streets': [],
            'local': []
        }
        
        # Load and analyze network if exists
        if os.path.exists(network_file):
            try:
                self.net = sumolib.net.readNet(network_file)
                # Get network bounds immediately
                self.network_bounds = self.net.getBoundary()
                print(f"✅ Loaded SUMO network: {network_file}")
                print(f"  - Network bounds: {self.network_bounds}")
                self._analyze_network()
            except Exception as e:
                print(f"⚠️ Could not load network file: {e}")
    
    def _convert_sumo_to_geo(self, x: float, y: float) -> Tuple[float, float]:
        """Convert SUMO coordinates to geographic coordinates with proper projection"""
        if self.net:
            try:
                # Use SUMO's built-in projection - most accurate
                lon, lat = self.net.convertXY2LonLat(x, y)
                return lon, lat
            except Exception as e:
                # If projection fails, use network bounds for accurate conversion
                if self.network_bounds:
                    x_min, y_min, x_max, y_max = self.network_bounds
                    
                    # Avoid division by zero
                    if x_max != x_min and y_max != y_min:
                        # Accurate conversion using actual network bounds
                        x_normalized = (x - x_min) / (x_max - x_min)
                        y_normalized = (y - y_min) / (y_max - y_min)
                        
                        # Map to zone bounds for better accuracy
                        lon = self.zone_bounds['min_lon'] + x_normalized * (self.zone_bounds['max_lon'] - self.zone_bounds['min_lon'])
                        lat = self.zone_bounds['min_lat'] + y_normalized * (self.zone_bounds['max_lat'] - self.zone_bounds['min_lat'])
                        
                        return lon, lat
        
        # Last resort fallback - Times Square default
        # This should rarely happen if network is loaded correctly
        return -73.980, 40.758
    
    def _convert_geo_to_sumo(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert geographic coordinates to SUMO coordinates with proper projection"""
        if self.net:
            try:
                # Use SUMO's built-in projection - most accurate
                x, y = self.net.convertLonLat2XY(lon, lat)
                return x, y
            except Exception as e:
                # Use network bounds for accurate conversion
                if self.network_bounds:
                    x_min, y_min, x_max, y_max = self.network_bounds
                    
                    # Avoid division by zero
                    if (self.zone_bounds['max_lon'] != self.zone_bounds['min_lon'] and 
                        self.zone_bounds['max_lat'] != self.zone_bounds['min_lat']):
                        
                        # Normalize GPS coordinates
                        lon_normalized = (lon - self.zone_bounds['min_lon']) / (self.zone_bounds['max_lon'] - self.zone_bounds['min_lon'])
                        lat_normalized = (lat - self.zone_bounds['min_lat']) / (self.zone_bounds['max_lat'] - self.zone_bounds['min_lat'])
                        
                        # Clamp to [0, 1] range
                        lon_normalized = max(0, min(1, lon_normalized))
                        lat_normalized = max(0, min(1, lat_normalized))
                        
                        # Convert to SUMO coordinates using actual bounds
                        x = x_min + lon_normalized * (x_max - x_min)
                        y = y_min + lat_normalized * (y_max - y_min)
                        
                        return x, y
        
        # Last resort fallback
        return 0, 0
    
    def _analyze_network(self):
        """Analyze network and prepare valid edges for spawning within zone"""
        print("Analyzing network for valid routes...")
        
        # Initialize network analyzer
        self.network_analyzer = NetworkAnalyzer(self.network_file)
        
        # Load or save network analysis
        zone_file = 'data/sumo/zone_analysis.json'
        
        # Check if we have zone-specific analysis
        if os.path.exists(zone_file):
            # Load zone-specific edges
            with open(zone_file, 'r') as f:
                zone_data = json.load(f)
                self.valid_spawn_edges = zone_data.get('routable_edges', [])
                print(f"  Loaded zone analysis: {len(self.valid_spawn_edges)} edges in traffic light zone")
        else:
            # Create new analysis with zone filtering
            self.valid_spawn_edges = self.network_analyzer.routable_edges
            
            # Apply zone filter immediately
            self._filter_edges_by_traffic_light_zone()
        
        # Categorize edges by type for realistic spawning
        self._categorize_edges()
    
    def _filter_edges_by_traffic_light_zone(self):
        """Filter edges to only those within traffic light coverage area"""
        
        zone_edges = []
        edges_outside = []
        
        print("Filtering edges to traffic light zone...")
        
        for edge_id in self.network_analyzer.routable_edges:
            try:
                edge = self.net.getEdge(edge_id)
                # Get edge midpoint for better accuracy
                shape = edge.getShape()
                if shape and len(shape) >= 1:
                    # Calculate midpoint
                    if len(shape) > 1:
                        mid_x = sum(p[0] for p in shape) / len(shape)
                        mid_y = sum(p[1] for p in shape) / len(shape)
                    else:
                        mid_x, mid_y = shape[0]
                    
                    lon, lat = self._convert_sumo_to_geo(mid_x, mid_y)
                    
                    # Check if within zone
                    if (self.zone_bounds['min_lat'] <= lat <= self.zone_bounds['max_lat'] and
                        self.zone_bounds['min_lon'] <= lon <= self.zone_bounds['max_lon']):
                        zone_edges.append(edge_id)
                    else:
                        edges_outside.append(edge_id)
            except Exception as e:
                pass
        
        # Update valid spawn edges to only zone edges
        self.valid_spawn_edges = zone_edges
        
        print(f"  ✓ Zone filtering complete:")
        print(f"    - Edges in traffic light zone: {len(zone_edges)}")
        print(f"    - Edges outside zone: {len(edges_outside)}")
        if len(zone_edges) + len(edges_outside) > 0:
            print(f"    - Coverage: {len(zone_edges)*100//(len(zone_edges)+len(edges_outside))}% of network in control zone")
        
        # Save zone-specific analysis
        zone_analysis = {
            'zone_bounds': self.zone_bounds,
            'routable_edges': zone_edges,
            'total_zone_edges': len(zone_edges),
            'edges_outside_zone': len(edges_outside)
        }
        
        os.makedirs('data/sumo', exist_ok=True)
        with open('data/sumo/zone_analysis.json', 'w') as f:
            json.dump(zone_analysis, f, indent=2)
    
    def _verify_edge_in_zone(self, edge_id: str) -> bool:
        """Verify an edge is within the traffic light control zone"""
        
        try:
            edge = self.net.getEdge(edge_id)
            shape = edge.getShape()
            if shape:
                x, y = shape[0]
                lon, lat = self._convert_sumo_to_geo(x, y)
                
                return (self.zone_bounds['min_lat'] <= lat <= self.zone_bounds['max_lat'] and
                        self.zone_bounds['min_lon'] <= lon <= self.zone_bounds['max_lon'])
        except:
            return False
        
        return False
    
    def _categorize_edges(self):
        """Categorize edges by street type for realistic traffic patterns"""
        self.edge_categories = {
            'avenues': [],
            'streets': [],
            'local': []
        }
        
        if not self.net:
            return
            
        for edge_id in self.valid_spawn_edges:
            try:
                edge = self.net.getEdge(edge_id)
                edge_name = edge.getName() if edge.getName() else ""
                
                if any(ave in edge_name.lower() for ave in ['broadway', '5th', '7th', 'park', 'madison', 'lexington', '3rd', '2nd', '1st']):
                    self.edge_categories['avenues'].append(edge_id)
                elif any(st in edge_name for st in ['42nd', '34th', '57th', '23rd', '14th', '50th', '59th']):
                    self.edge_categories['streets'].append(edge_id)
                else:
                    self.edge_categories['local'].append(edge_id)
            except:
                self.edge_categories['local'].append(edge_id)
        
        print(f"  Edge categories in zone: {len(self.edge_categories['avenues'])} avenues, "
              f"{len(self.edge_categories['streets'])} streets, "
              f"{len(self.edge_categories['local'])} local roads")
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Manhattan distance between two points"""
        return abs(lat1 - lat2) + abs(lon1 - lon2)
    
    def start_sumo(self, gui=True, seed=42):
        """Start SUMO with professional configuration"""
        
        # Clean up any existing connection
        try:
            traci.close()
        except:
            pass
        
        # Delete old zone analysis to force regeneration with new network
        zone_file = 'data/sumo/zone_analysis.json'
        if os.path.exists(zone_file):
            os.remove(zone_file)
            print("Cleared old zone analysis for fresh start")
        
        sumo_binary = "sumo-gui" if gui else "sumo"
        
        # Build command
        sumo_cmd = [
            sumo_binary,
            "-n", self.network_file,
            "--step-length", str(self.step_length),
            "--no-step-log", "true",
            "--collision.action", "warn",
            "--collision.check-junctions", "true",
            "--seed", str(seed),
            "--no-warnings", "true",
            "--duration-log.disable", "true",
            "--device.emissions.probability", "1.0",
            "--device.battery.probability", "1.0",
            "--lateral-resolution", "0.8",
            "--start", "true",
            "--quit-on-end", "false",
            "--time-to-teleport", "300",
            "--max-depart-delay", "900",
            "--routing-algorithm", "dijkstra",
            "--device.rerouting.probability", "1.0",
            "--device.rerouting.period", "60"
        ]
        
        print(f"Starting SUMO...")
        
        try:
            traci.start(sumo_cmd)
            self.running = True
            
            # Update network bounds after SUMO starts
            if self.net:
                try:
                    self.network_bounds = self.net.getBoundary()
                    print(f"  - Updated network bounds: {self.network_bounds}")
                except:
                    pass
            
            # Re-analyze network with new fixed network
            self._analyze_network()
            
            # Define vehicle types
            self._define_vehicle_types()
            
            # Map traffic lights
            self._map_traffic_lights()
            
            # Map EV stations
            self._map_ev_stations()
            
            print(f"✅ SUMO started successfully")
            print(f"  - Found {len(traci.trafficlight.getIDList())} traffic lights")
            print(f"  - {len(self.valid_spawn_edges)} valid spawn edges in zone")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start SUMO: {e}")
            self.running = False
            return False
    
    def _define_vehicle_types(self):
        """Define vehicle types in SUMO"""
        
        try:
            # Define each vehicle type
            for vtype, config in self.vehicle_types.items():
                type_id = vtype.value
                
                # Check if type already exists
                existing_types = traci.vehicletype.getIDList()
                
                if type_id not in existing_types:
                    # Add new vehicle type
                    traci.vehicletype.copy("DEFAULT_VEHTYPE", type_id)
                
                # Set parameters
                traci.vehicletype.setLength(type_id, config.length)
                traci.vehicletype.setMinGap(type_id, config.min_gap)
                traci.vehicletype.setMaxSpeed(type_id, config.max_speed_mps)
                traci.vehicletype.setAccel(type_id, config.acceleration)
                traci.vehicletype.setDecel(type_id, config.deceleration)
                
                # Set colors
                if "taxi" in type_id:
                    traci.vehicletype.setColor(type_id, (255, 255, 0, 255))
                elif config.is_ev:
                    traci.vehicletype.setColor(type_id, (0, 255, 0, 255))
                else:
                    traci.vehicletype.setColor(type_id, (100, 100, 255, 255))
                
                print(f"  ✓ Defined vehicle type: {type_id}")
                
        except Exception as e:
            print(f"  ⚠️ Error defining vehicle types: {e}")
    
    def _map_traffic_lights(self):
        """Map SUMO traffic lights to power system traffic lights"""
        
        sumo_tls = traci.trafficlight.getIDList()
        
        for tls_id in sumo_tls:
            try:
                # Get traffic light position
                controlled_links = traci.trafficlight.getControlledLinks(tls_id)
                if controlled_links and controlled_links[0]:
                    lane_id = controlled_links[0][0][0]
                    if lane_id:
                        # Get position at the end of the lane
                        shape = traci.lane.getShape(lane_id)
                        if shape:
                            x, y = shape[-1]
                            lon, lat = self._convert_sumo_to_geo(x, y)
                            
                            # Only map if within zone
                            if (self.zone_bounds['min_lat'] <= lat <= self.zone_bounds['max_lat'] and
                                self.zone_bounds['min_lon'] <= lon <= self.zone_bounds['max_lon']):
                                
                                # Find nearest traffic light in power system
                                min_dist = float('inf')
                                nearest_tl = None
                                
                                for sys_tl_id, sys_tl in self.integrated_system.traffic_lights.items():
                                    dist = self._calculate_distance(lat, lon, sys_tl['lat'], sys_tl['lon'])
                                    if dist < min_dist and dist < 0.001:  # ~100 meters
                                        min_dist = dist
                                        nearest_tl = sys_tl_id
                                
                                if nearest_tl:
                                    self.tls_mapping[tls_id] = nearest_tl
            except Exception as e:
                pass
        
        print(f"  - Mapped {len(self.tls_mapping)} traffic lights to power system")
    
    def _map_ev_stations(self):
        """Map EV charging stations to SUMO edges within zone"""
        
        if not self.net:
            print("  - No network loaded, skipping EV station mapping")
            return
        
        for ev_id, ev_station in self.integrated_system.ev_stations.items():
            # Check if station is within zone
            if not (self.zone_bounds['min_lat'] <= ev_station['lat'] <= self.zone_bounds['max_lat'] and
                    self.zone_bounds['min_lon'] <= ev_station['lon'] <= self.zone_bounds['max_lon']):
                continue
            
            # Convert to SUMO coordinates
            x, y = self._convert_geo_to_sumo(ev_station['lon'], ev_station['lat'])
            
            # Get nearest edge
            edges = self.net.getNeighboringEdges(x, y, r=100)
            if edges:
                edges_sorted = sorted(edges, key=lambda e: e[1])
                nearest_edge = edges_sorted[0][0]
                
                # Only use if edge is in valid spawn edges (within zone)
                if nearest_edge.getID() in self.valid_spawn_edges:
                    self.ev_stations_sumo[ev_id] = {
                        'edge_id': nearest_edge.getID(),
                        'position': (x, y),
                        'capacity': ev_station['chargers'],
                        'available': ev_station['chargers'],
                        'system_id': ev_id
                    }
        
        print(f"  - Mapped {len(self.ev_stations_sumo)} EV stations within zone")
    
    def spawn_vehicles(self, count: int = 10, ev_percentage: float = 0.7):
        """Spawn vehicles with GUARANTEED valid routing within zone"""
        
        if not self.running:
            print("SUMO not running!")
            return 0
        
        if not self.valid_spawn_edges:
            print("No valid spawn edges available in zone!")
            return 0
        
        spawned = 0
        failed = 0
        route_attempts = 0
        
        print(f"Spawning {count} vehicles (using {len(self.valid_spawn_edges)} zone edges)...")
        
        for i in range(count):
            veh_id = f"veh_{self.stats['total_vehicles']}_{int(time.time())}{i}"
            
            # Determine vehicle type
            is_ev = random.random() < ev_percentage
            if is_ev:
                vtype = random.choice([VehicleType.SEDAN_EV, VehicleType.SUV_EV, VehicleType.TAXI_EV])
            else:
                vtype = VehicleType.SEDAN_GAS
            
            config = self.vehicle_types[vtype]
            
            # Get origin and destination from zone edges only
            if self.current_scenario == SimulationScenario.MORNING_RUSH:
                # Morning rush: residential to business areas
                origin = self._get_edge_by_type('local')
                destination = self._get_edge_by_type('streets')
            elif self.current_scenario == SimulationScenario.EVENING_RUSH:
                # Evening rush: business to residential
                origin = self._get_edge_by_type('streets')
                destination = self._get_edge_by_type('local')
            else:
                # Normal: random from zone edges
                origin = random.choice(self.valid_spawn_edges)
                destination = random.choice(self.valid_spawn_edges)
            
            # Extra safety check - ensure edges are in zone
            if not self._verify_edge_in_zone(origin):
                origin = random.choice(self.valid_spawn_edges[:min(50, len(self.valid_spawn_edges))])
            if not self._verify_edge_in_zone(destination):
                destination = random.choice(self.valid_spawn_edges[:min(50, len(self.valid_spawn_edges))])
            
            # Ensure different origin and destination
            attempts = 0
            while destination == origin and attempts < 5:
                destination = random.choice(self.valid_spawn_edges)
                attempts += 1
            
            # Skip if same edge
            if origin == destination:
                failed += 1
                continue
            
            # Check if this route pair has failed before
            route_key = f"{origin}_{destination}"
            if route_key in self.failed_routes:
                failed += 1
                continue
            
            # Try to find route
            route = None
            route_attempts += 1
            
            # First check cache
            if route_key in self.route_cache:
                route = self.route_cache[route_key]
            else:
                # Use traci to find route
                try:
                    route_result = traci.simulation.findRoute(origin, destination)
                    if route_result and route_result.edges and len(route_result.edges) > 1:
                        route = route_result.edges
                        self.route_cache[route_key] = route
                    else:
                        self.failed_routes.add(route_key)
                except:
                    self.failed_routes.add(route_key)
            
            if route:
                try:
                    # Create route in SUMO
                    route_id = f"route_{veh_id}"
                    traci.route.add(route_id, route)
                    
                    # Add vehicle with validated route
                    traci.vehicle.add(
                        veh_id,
                        route_id,
                        typeID=vtype.value,
                        depart="now",
                        departLane="best",
                        departSpeed="max"
                    )
                    
                    # Create vehicle object
                    vehicle = ManhattanVehicle(
                        id=veh_id,
                        config=config,
                        route=route,
                        destination=destination,
                        current_edge=origin
                    )
                    
                    if config.is_ev:
                        vehicle.config.current_soc = random.uniform(0.3, 0.9)
                    
                    self.vehicles[veh_id] = vehicle
                    self.stats['total_vehicles'] += 1
                    if config.is_ev:
                        self.stats['ev_vehicles'] += 1
                    
                    spawned += 1
                    
                except Exception as e:
                    failed += 1
                    # Clean up failed route
                    try:
                        traci.route.remove(route_id)
                    except:
                        pass
            else:
                failed += 1
        
        # Update success rate
        if count > 0:
            self.stats['spawn_success_rate'] = (spawned / count) * 100
        
        print(f"✅ Successfully spawned {spawned}/{count} vehicles ({self.stats['spawn_success_rate']:.0f}% success)")
        if failed > 0:
            print(f"  ⚠️ {failed} vehicles failed (no valid route in zone)")
        if route_attempts > 0:
            print(f"  📊 Route cache: {len(self.route_cache)} cached, {len(self.failed_routes)} failed pairs")
        
        return spawned
    
    def _get_edge_by_type(self, edge_type: str) -> str:
        """Get a random edge of specified type from zone edges"""
        if edge_type in self.edge_categories and self.edge_categories[edge_type]:
            return random.choice(self.edge_categories[edge_type])
        else:
            # Fallback to any valid zone edge
            return random.choice(self.valid_spawn_edges) if self.valid_spawn_edges else ""
    
    def update_traffic_lights(self):
        """Synchronize traffic lights with power system"""
        
        if not self.running:
            return
        
        for sumo_tls_id, system_tl_id in self.tls_mapping.items():
            if system_tl_id in self.integrated_system.traffic_lights:
                tl = self.integrated_system.traffic_lights[system_tl_id]
                
                try:
                    # Get current program
                    current_state = traci.trafficlight.getRedYellowGreenState(sumo_tls_id)
                    state_length = len(current_state)
                    
                    if not tl['powered']:
                        # No power - all red (safe mode)
                        new_state = "r" * state_length
                    else:
                        # Create proper state based on phase
                        if tl['phase'] == 'green':
                            # Allow NS or EW based on current cycle
                            pattern = "GGGgrrrrGGGgrrrr"
                        elif tl['phase'] == 'yellow':
                            pattern = "yyyyrrrryyyyrrrr"
                        else:  # red
                            pattern = "rrrrGGGgrrrrGGGg"
                        
                        # Adjust pattern to match state length
                        while len(pattern) < state_length:
                            pattern += pattern
                        new_state = pattern[:state_length]
                    
                    traci.trafficlight.setRedYellowGreenState(sumo_tls_id, new_state)
                    
                except Exception as e:
                    pass
    
    def step(self):
        """Execute one simulation step"""
        
        if not self.running:
            return False
        
        try:
            traci.simulationStep()
            self.simulation_time += self.step_length
            
            # Update traffic lights
            self.update_traffic_lights()
            
            # Update vehicle states
            self._update_vehicle_states()
            
            # Check for EV charging
            self._check_ev_charging()
            
            # Update statistics
            self._update_statistics()
            
            return True
            
        except Exception as e:
            print(f"Simulation step error: {e}")
            return False
    
    def _update_vehicle_states(self):
        """Update all vehicle states with accurate positioning"""
        
        try:
            current_vehicles = set(traci.vehicle.getIDList())
            
            for veh_id in list(self.vehicles.keys()):
                if veh_id in current_vehicles:
                    vehicle = self.vehicles[veh_id]
                    
                    try:
                        # Update position with accurate conversion
                        x, y = traci.vehicle.getPosition(veh_id)
                        lon, lat = self._convert_sumo_to_geo(x, y)
                        vehicle.position = (lon, lat)
                        
                        # Update other states
                        vehicle.speed = traci.vehicle.getSpeed(veh_id)
                        vehicle.distance_traveled = traci.vehicle.getDistance(veh_id)
                        vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                        vehicle.current_edge = traci.vehicle.getRoadID(veh_id)
                        
                        # Update battery for EVs
                        if vehicle.config.is_ev and not vehicle.is_charging:
                            distance_km = vehicle.distance_traveled / 1000
                            energy_used = distance_km * vehicle.config.consumption_kwh_per_km
                            vehicle.config.current_soc = max(0, vehicle.config.current_soc - 
                                                            energy_used / vehicle.config.battery_capacity_kwh)
                    except:
                        pass
                else:
                    # Vehicle has left simulation
                    del self.vehicles[veh_id]
        except Exception as e:
            pass
    
    def _check_ev_charging(self):
        """Check if EVs need charging and handle charging logic"""
        
        for veh_id, vehicle in self.vehicles.items():
            if not vehicle.config.is_ev:
                continue
            
            # Check if needs charging
            if vehicle.config.current_soc < vehicle.config.charging_threshold and not vehicle.is_charging:
                # Find nearest charging station within zone
                nearest_station = self._find_nearest_ev_station(vehicle.position)
                
                if nearest_station and nearest_station['available'] > 0:
                    # Reroute to charging station
                    try:
                        current_edge = vehicle.current_edge
                        target_edge = nearest_station['edge_id']
                        
                        # Find route to station
                        route_result = traci.simulation.findRoute(current_edge, target_edge)
                        if route_result and route_result.edges:
                            traci.vehicle.setRoute(veh_id, route_result.edges)
                            vehicle.assigned_ev_station = nearest_station['system_id']
                            vehicle.destination = target_edge
                            
                            print(f"  ⚡ {veh_id} routing to charging (SOC: {vehicle.config.current_soc*100:.1f}%)")
                    except:
                        pass
            
            # Check if at charging station
            elif vehicle.assigned_ev_station:
                station = self.ev_stations_sumo.get(vehicle.assigned_ev_station)
                if station and vehicle.current_edge == station['edge_id']:
                    if not vehicle.is_charging:
                        # Start charging
                        vehicle.is_charging = True
                        station['available'] -= 1
                        self.stats['vehicles_charging'] += 1
                        
                        # Stop vehicle for charging
                        try:
                            traci.vehicle.setStop(veh_id, station['edge_id'], duration=60)
                            traci.vehicle.setColor(veh_id, (255, 165, 0, 255))  # Orange when charging
                        except:
                            pass
                        
                        print(f"  🔌 {veh_id} started charging at {vehicle.assigned_ev_station}")
                    
                    # Simulate charging
                    vehicle.config.current_soc = min(1.0, vehicle.config.current_soc + 0.001)
                    
                    # Check if charged enough
                    if vehicle.config.current_soc >= 0.8:
                        vehicle.is_charging = False
                        vehicle.assigned_ev_station = None
                        station['available'] += 1
                        self.stats['vehicles_charging'] -= 1
                        
                        # Resume journey with new destination in zone
                        try:
                            traci.vehicle.resume(veh_id)
                            traci.vehicle.setColor(veh_id, (0, 255, 0, 255))  # Green for EV
                            
                            # Set new random destination from zone edges
                            if self.valid_spawn_edges:
                                new_dest = random.choice(self.valid_spawn_edges)
                                route_result = traci.simulation.findRoute(vehicle.current_edge, new_dest)
                                if route_result and route_result.edges:
                                    traci.vehicle.setRoute(veh_id, route_result.edges)
                        except:
                            pass
                        
                        print(f"  ✅ {veh_id} charged to {vehicle.config.current_soc*100:.0f}%")
    
    def _find_nearest_ev_station(self, position: Tuple[float, float]) -> Optional[Dict]:
        """Find nearest available EV charging station within zone"""
        
        min_dist = float('inf')
        nearest = None
        
        for station_id, station in self.ev_stations_sumo.items():
            if station['available'] > 0:
                # Convert station position to geo
                x, y = station['position']
                lon, lat = self._convert_sumo_to_geo(x, y)
                
                # Check if station is in zone
                if (self.zone_bounds['min_lat'] <= lat <= self.zone_bounds['max_lat'] and
                    self.zone_bounds['min_lon'] <= lon <= self.zone_bounds['max_lon']):
                    
                    dist = self._calculate_distance(position[1], position[0], lat, lon)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = station
        
        return nearest
    
    def _update_statistics(self):
        """Update simulation statistics"""
        
        if self.vehicles:
            speeds = [v.speed for v in self.vehicles.values()]
            self.stats['avg_speed_mps'] = np.mean(speeds) if speeds else 0
            
            wait_times = [v.waiting_time for v in self.vehicles.values()]
            self.stats['total_wait_time'] = sum(wait_times)
            
            # Calculate total energy consumed
            total_energy = 0
            for vehicle in self.vehicles.values():
                if vehicle.config.is_ev:
                    energy_used = (1 - vehicle.config.current_soc) * vehicle.config.battery_capacity_kwh
                    total_energy += energy_used
            self.stats['total_energy_consumed_kwh'] = total_energy
    
    def get_vehicle_positions(self) -> List[Dict]:
        """Get all vehicle positions for visualization with accurate coordinates"""
        
        positions = []
        for veh_id, vehicle in self.vehicles.items():
            # Only include vehicles within zone for visualization
            if (self.zone_bounds['min_lat'] <= vehicle.position[1] <= self.zone_bounds['max_lat'] and
                self.zone_bounds['min_lon'] <= vehicle.position[0] <= self.zone_bounds['max_lon']):
                
                positions.append({
                    'id': veh_id,
                    'lat': vehicle.position[1],
                    'lon': vehicle.position[0],
                    'type': vehicle.config.vtype.value,
                    'speed': vehicle.speed,
                    'soc': vehicle.config.current_soc if vehicle.config.is_ev else 1.0,
                    'is_charging': vehicle.is_charging,
                    'is_ev': vehicle.config.is_ev
                })
        
        return positions
    
    def get_statistics(self) -> Dict:
        """Get current simulation statistics"""
        return self.stats.copy()
    
    def stop(self):
        """Stop SUMO simulation"""
        if self.running:
            try:
                traci.close()
            except:
                pass
            self.running = False
            print("SUMO simulation stopped")