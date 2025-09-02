"""
Manhattan SUMO Vehicle Manager - FIXED VERSION
Professional integration with proper routing and traffic light synchronization
"""

import traci
import sumolib
import random
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import json
import os

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

class ManhattanSUMOManager:
    """
    Fixed SUMO integration for Manhattan Power Grid
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
        
        # Manhattan bounds for proper coordinate conversion
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
        
        # Route cache
        self.route_cache = {}
        
        # Statistics
        self.stats = {
            'total_vehicles': 0,
            'ev_vehicles': 0,
            'vehicles_charging': 0,
            'total_energy_consumed_kwh': 0,
            'avg_speed_mps': 0,
            'total_wait_time': 0
        }
        
        # Load network if exists
        if os.path.exists(network_file):
            try:
                self.net = sumolib.net.readNet(network_file)
                print(f"✅ Loaded SUMO network: {network_file}")
            except:
                print(f"⚠️ Could not load network file: {network_file}")
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points (Manhattan distance)"""
        # Simple Manhattan distance calculation
        return abs(lat1 - lat2) + abs(lon1 - lon2)
    
    def _manhattan_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Alias for calculate_distance"""
        return self._calculate_distance(lat1, lon1, lat2, lon2)
    
    def _convert_sumo_to_geo(self, x: float, y: float) -> Tuple[float, float]:
        """Convert SUMO coordinates to geographic coordinates"""
        # Proper conversion based on network projection
        if self.net:
            lon, lat = self.net.convertXY2LonLat(x, y)
            return lon, lat
        else:
            # Fallback linear conversion
            lon = self.bounds['min_lon'] + (x / 10000) * (self.bounds['max_lon'] - self.bounds['min_lon'])
            lat = self.bounds['min_lat'] + (y / 10000) * (self.bounds['max_lat'] - self.bounds['min_lat'])
            return lon, lat
    
    def _convert_geo_to_sumo(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert geographic coordinates to SUMO coordinates"""
        if self.net:
            x, y = self.net.convertLonLat2XY(lon, lat)
            return x, y
        else:
            # Fallback linear conversion
            x = ((lon - self.bounds['min_lon']) / (self.bounds['max_lon'] - self.bounds['min_lon'])) * 10000
            y = ((lat - self.bounds['min_lat']) / (self.bounds['max_lat'] - self.bounds['min_lat'])) * 10000
            return x, y
    
    def start_sumo(self, gui=True, seed=42):
        """Start SUMO with professional configuration"""
        
        # Clean up any existing connection
        try:
            traci.close()
        except:
            pass
        
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
            "--quit-on-end", "false"
        ]
        
        print(f"Starting SUMO with command: {' '.join(sumo_cmd)}")
        
        try:
            traci.start(sumo_cmd)
            self.running = True
            
            # Define vehicle types
            self._define_vehicle_types()
            
            # Map traffic lights
            self._map_traffic_lights()
            
            # Map EV stations
            self._map_ev_stations()
            
            print(f"✅ SUMO started successfully")
            print(f"  - Found {len(traci.trafficlight.getIDList())} traffic lights")
            if self.net:
                print(f"  - Network has {len(self.net.getEdges())} edges")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start SUMO: {e}")
            self.running = False
            return False
    
    def _define_vehicle_types(self):
        """Define vehicle types in SUMO"""
        
        existing_types = traci.vehicletype.getIDList()
        
        for vtype, config in self.vehicle_types.items():
            type_id = vtype.value
            
            try:
                if type_id not in existing_types:
                    # Type will be created when first vehicle uses it
                    print(f"  ℹ Vehicle type {type_id} will be created on first use")
                else:
                    # Modify existing type
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
                        
                    print(f"  ✓ Modified vehicle type: {type_id}")
                    
            except Exception as e:
                print(f"  ⚠ Note: {type_id} will use default parameters")
    
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
                print(f"Error mapping traffic light {tls_id}: {e}")
        
        print(f"  - Mapped {len(self.tls_mapping)} traffic lights")
    
    def _map_ev_stations(self):
        """Map EV charging stations to SUMO edges"""
        
        if not self.net:
            print("  - No network loaded, skipping EV station mapping")
            return
        
        for ev_id, ev_station in self.integrated_system.ev_stations.items():
            # Convert to SUMO coordinates
            x, y = self._convert_geo_to_sumo(ev_station['lon'], ev_station['lat'])
            
            # Get nearest edge
            edges = self.net.getNeighboringEdges(x, y, r=100)
            if edges:
                edges_sorted = sorted(edges, key=lambda e: e[1])
                nearest_edge = edges_sorted[0][0]
                
                self.ev_stations_sumo[ev_id] = {
                    'edge_id': nearest_edge.getID(),
                    'position': (x, y),
                    'capacity': ev_station['chargers'],
                    'available': ev_station['chargers'],
                    'system_id': ev_id
                }
        
        print(f"  - Mapped {len(self.ev_stations_sumo)} EV stations")
    
    def spawn_vehicles(self, count: int = 10, ev_percentage: float = 0.7):
        """Spawn vehicles with intelligent routing"""
        
        if not self.running:
            print("SUMO not running!")
            return 0
        
        if not self.net:
            print("Network not loaded!")
            return 0
        
        # Get valid edges
        valid_edges = [e for e in self.net.getEdges() 
                      if not e.isSpecial() and e.allows("passenger")]
        
        if not valid_edges:
            print("No valid edges for spawning!")
            return 0
        
        spawned = 0
        for i in range(count):
            veh_id = f"veh_{self.stats['total_vehicles']}_{int(time.time())}"
            
            # Determine vehicle type
            is_ev = random.random() < ev_percentage
            if is_ev:
                vtype = random.choice([VehicleType.SEDAN_EV, VehicleType.SUV_EV, VehicleType.TAXI_EV])
            else:
                vtype = VehicleType.SEDAN_GAS
            
            config = self.vehicle_types[vtype]
            
            # Select random start and end edges
            start_edge = random.choice(valid_edges)
            end_edge = random.choice(valid_edges)
            
            while end_edge == start_edge:
                end_edge = random.choice(valid_edges)
            
            # Create route
            route = self._compute_route(start_edge.getID(), end_edge.getID())
            
            if route:
                try:
                    # Add route to SUMO
                    route_id = f"route_{veh_id}"
                    traci.route.add(route_id, route)
                    
                    # Add vehicle
                    traci.vehicle.add(
                        veh_id,
                        route_id,
                        depart="now"
                    )
                    
                    # Set vehicle parameters
                    traci.vehicle.setLength(veh_id, config.length)
                    traci.vehicle.setMinGap(veh_id, config.min_gap)
                    traci.vehicle.setMaxSpeed(veh_id, config.max_speed_mps)
                    traci.vehicle.setAccel(veh_id, config.acceleration)
                    traci.vehicle.setDecel(veh_id, config.deceleration)
                    
                    # Set color
                    if "taxi" in vtype.value:
                        traci.vehicle.setColor(veh_id, (255, 255, 0, 255))
                    elif config.is_ev:
                        traci.vehicle.setColor(veh_id, (0, 255, 0, 255))
                    else:
                        traci.vehicle.setColor(veh_id, (100, 100, 255, 255))
                    
                    # Create vehicle object
                    vehicle = ManhattanVehicle(
                        id=veh_id,
                        config=config,
                        route=route,
                        destination=end_edge.getID()
                    )
                    
                    if config.is_ev:
                        vehicle.config.current_soc = random.uniform(0.3, 0.9)
                    
                    self.vehicles[veh_id] = vehicle
                    self.stats['total_vehicles'] += 1
                    if config.is_ev:
                        self.stats['ev_vehicles'] += 1
                    
                    spawned += 1
                    
                except Exception as e:
                    print(f"  ✗ Failed to spawn vehicle: {e}")
        
        print(f"Successfully spawned {spawned}/{count} vehicles")
        return spawned
    
    def _compute_route(self, from_edge: str, to_edge: str) -> Optional[List[str]]:
        """Compute shortest route between two edges"""
        
        cache_key = f"{from_edge}_{to_edge}"
        if cache_key in self.route_cache:
            return self.route_cache[cache_key]
        
        try:
            route = traci.simulation.findRoute(from_edge, to_edge)
            if route and route.edges:
                self.route_cache[cache_key] = route.edges
                return route.edges
        except:
            pass
        
        return None
    
    def update_traffic_lights(self):
        """Synchronize traffic lights with power system"""
        
        if not self.running:
            return
        
        for sumo_tls_id, system_tl_id in self.tls_mapping.items():
            if system_tl_id in self.integrated_system.traffic_lights:
                tl = self.integrated_system.traffic_lights[system_tl_id]
                
                try:
                    if not tl['powered']:
                        # No power - all red
                        state = traci.trafficlight.getRedYellowGreenState(sumo_tls_id)
                        all_red = "r" * len(state)
                        traci.trafficlight.setRedYellowGreenState(sumo_tls_id, all_red)
                    else:
                        # Normal operation - set based on phase
                        current_state = traci.trafficlight.getRedYellowGreenState(sumo_tls_id)
                        
                        # Map power system phase to SUMO state
                        if tl['phase'] == 'green':
                            # Allow some directions
                            new_state = self._get_green_state(len(current_state))
                        elif tl['phase'] == 'yellow':
                            new_state = self._get_yellow_state(len(current_state))
                        else:  # red
                            new_state = self._get_red_state(len(current_state))
                        
                        traci.trafficlight.setRedYellowGreenState(sumo_tls_id, new_state)
                except Exception as e:
                    pass
    
    def _get_green_state(self, length):
        """Get green light state pattern"""
        # Simple pattern - alternate green/red
        pattern = ""
        for i in range(length):
            if i % 4 < 2:
                pattern += "G"
            else:
                pattern += "r"
        return pattern
    
    def _get_yellow_state(self, length):
        """Get yellow light state pattern"""
        pattern = ""
        for i in range(length):
            if i % 4 < 2:
                pattern += "y"
            else:
                pattern += "r"
        return pattern
    
    def _get_red_state(self, length):
        """Get red light state pattern"""
        return "r" * length
    
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
        """Update all vehicle states"""
        
        current_vehicles = set(traci.vehicle.getIDList())
        
        for veh_id in list(self.vehicles.keys()):
            if veh_id in current_vehicles:
                vehicle = self.vehicles[veh_id]
                
                try:
                    # Update position
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
                        energy_used = (vehicle.distance_traveled / 1000) * vehicle.config.consumption_kwh_per_km
                        vehicle.config.current_soc = max(0, vehicle.config.current_soc - 
                                                        energy_used / vehicle.config.battery_capacity_kwh)
                except:
                    pass
            else:
                # Vehicle has left
                del self.vehicles[veh_id]
    
    def _check_ev_charging(self):
        """Check if EVs need charging"""
        
        for veh_id, vehicle in self.vehicles.items():
            if not vehicle.config.is_ev:
                continue
            
            # Check if needs charging
            if vehicle.config.current_soc < vehicle.config.charging_threshold and not vehicle.is_charging:
                # Find nearest charging station
                nearest_station = self._find_nearest_ev_station(vehicle.position)
                
                if nearest_station:
                    # Reroute to charging station
                    try:
                        current_edge = vehicle.current_edge
                        target_edge = nearest_station['edge_id']
                        
                        new_route = self._compute_route(current_edge, target_edge)
                        if new_route:
                            traci.vehicle.setRoute(veh_id, new_route)
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
                        self.stats['vehicles_charging'] += 1
                        
                        # Stop vehicle
                        try:
                            traci.vehicle.setSpeed(veh_id, 0)
                            traci.vehicle.setColor(veh_id, (255, 165, 0, 255))  # Orange
                        except:
                            pass
                        
                        print(f"  🔌 {veh_id} started charging")
                    
                    # Simulate charging
                    vehicle.config.current_soc = min(1.0, vehicle.config.current_soc + 0.001)
                    
                    # Check if charged enough
                    if vehicle.config.current_soc >= 0.8:
                        vehicle.is_charging = False
                        vehicle.assigned_ev_station = None
                        self.stats['vehicles_charging'] -= 1
                        
                        # Resume
                        try:
                            traci.vehicle.setSpeed(veh_id, -1)
                            traci.vehicle.setColor(veh_id, (0, 255, 0, 255))
                            
                            # Set new destination
                            if self.net:
                                valid_edges = [e.getID() for e in self.net.getEdges() if not e.isSpecial()]
                                new_dest = random.choice(valid_edges)
                                new_route = self._compute_route(vehicle.current_edge, new_dest)
                                if new_route:
                                    traci.vehicle.setRoute(veh_id, new_route)
                        except:
                            pass
                        
                        print(f"  ✅ {veh_id} charged to {vehicle.config.current_soc*100:.0f}%")
    
    def _find_nearest_ev_station(self, position: Tuple[float, float]) -> Optional[Dict]:
        """Find nearest available EV charging station"""
        
        min_dist = float('inf')
        nearest = None
        
        for station_id, station in self.ev_stations_sumo.items():
            if station['available'] > 0:
                # Convert station position to geo
                x, y = station['position']
                lon, lat = self._convert_sumo_to_geo(x, y)
                
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
        """Get all vehicle positions for visualization"""
        
        positions = []
        for veh_id, vehicle in self.vehicles.items():
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