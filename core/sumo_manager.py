"""
Manhattan SUMO Vehicle Manager - World Class Integration
Manages vehicle simulation with proper routing, EV behavior, and traffic light synchronization
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
    battery_capacity_kwh: float = 75.0  # Tesla Model 3 like
    current_soc: float = 0.8  # State of charge (0-1)
    consumption_kwh_per_km: float = 0.2  # ~200 Wh/km
    max_speed_mps: float = 22.2  # 80 km/h in city
    acceleration: float = 2.6  # m/s²
    deceleration: float = 4.5  # m/s²
    length: float = 4.5  # meters
    min_gap: float = 2.5  # meters
    charging_threshold: float = 0.2  # Go charge at 20%
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
    """Time-of-day scenarios with realistic patterns"""
    NIGHT = "night"  # 00:00-06:00 - Very light traffic
    MORNING_RUSH = "morning_rush"  # 06:00-10:00 - Heavy inbound
    MIDDAY = "midday"  # 10:00-15:00 - Moderate
    EVENING_RUSH = "evening_rush"  # 15:00-20:00 - Heavy outbound
    EVENING = "evening"  # 20:00-00:00 - Light to moderate

class ManhattanSUMOManager:
    """
    World-class SUMO integration for Manhattan Power Grid
    Handles vehicle spawning, routing, EV charging, and traffic light sync
    """
    
    def __init__(self, integrated_system, network_file='data/sumo/manhattan.net.xml'):
        self.integrated_system = integrated_system
        self.network_file = network_file
        self.net = None  # SUMO network
        self.running = False
        self.vehicles: Dict[str, ManhattanVehicle] = {}
        self.current_scenario = SimulationScenario.MIDDAY
        self.simulation_time = 0
        self.step_length = 0.1  # 100ms steps for smooth movement
        
        # Load SUMO network for analysis
        self.net = sumolib.net.readNet(network_file)
        
        # Manhattan area bounds from your system
        self.bounds = {
            'min_lat': 40.745,
            'max_lat': 40.775,
            'min_lon': -74.010,
            'max_lon': -73.960
        }
        
        # Traffic light mapping (SUMO ID -> Your System ID)
        self.tls_mapping = {}
        
        # EV station mapping with locations
        self.ev_stations_sumo = {}
        
        # Vehicle type definitions
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
                consumption_kwh_per_km=0  # Uses fuel instead
            ),
        }
        
        # Route cache for performance
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
    
    def start_sumo(self, gui=True, seed=42):
        """Start SUMO with professional configuration"""
        
        # Clean up any existing connection first
        try:
            traci.close()
        except:
            pass
        
        sumo_binary = "sumo-gui" if gui else "sumo"
        
        # Professional SUMO configuration
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
        
        # DON'T add route file if it contains vehicle types we haven't defined yet
        # We'll add routes dynamically
        
        # Add additional file if exists and doesn't conflict
        add_file = self.network_file.replace('.net.xml', '.add.xml')
        if os.path.exists(add_file):
            # Check if add file has vehicle types that might conflict
            # For now, skip it to avoid conflicts
            pass
        
        print(f"Starting SUMO with command: {' '.join(sumo_cmd)}")
        
        try:
            traci.start(sumo_cmd)
            self.running = True
            
            # IMPORTANT: Define vehicle types FIRST before any vehicles are added
            self._define_vehicle_types()
            
            # Now map traffic lights
            self._map_traffic_lights()
            
            # Map EV stations to edges
            self._map_ev_stations()
            
            print(f"✅ SUMO started successfully")
            print(f"  - Found {len(traci.trafficlight.getIDList())} traffic lights")
            print(f"  - Network has {len(self.net.getEdges())} edges")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start SUMO: {e}")
            self.running = False
            return False

    def _define_vehicle_types(self):
        """Define vehicle types in SUMO with realistic parameters"""
        
        # Get existing vehicle types first
        existing_types = traci.vehicletype.getIDList()
        
        for vtype, config in self.vehicle_types.items():
            type_id = vtype.value
            
            try:
                # Check if type already exists, if not it will be created when first vehicle uses it
                if type_id not in existing_types:
                    # In SUMO 1.24.0, we can't add types directly
                    # They will be created automatically when we spawn vehicles
                    # We'll just store the configs for now
                    print(f"  ℹ Vehicle type {type_id} will be created on first use")
                else:
                    # Type exists, we can modify it
                    traci.vehicletype.setLength(type_id, config.length)
                    traci.vehicletype.setMinGap(type_id, config.min_gap)
                    traci.vehicletype.setMaxSpeed(type_id, config.max_speed_mps)
                    traci.vehicletype.setAccel(type_id, config.acceleration)
                    traci.vehicletype.setDecel(type_id, config.deceleration)
                    
                    # Visual parameters
                    if "taxi" in type_id:
                        traci.vehicletype.setColor(type_id, (255, 255, 0, 255))  # Yellow
                    elif config.is_ev:
                        traci.vehicletype.setColor(type_id, (0, 255, 0, 255))  # Green for EVs
                    else:
                        traci.vehicletype.setColor(type_id, (100, 100, 255, 255))  # Blue for gas
                        
                    print(f"  ✓ Modified existing vehicle type: {type_id}")
                    
            except Exception as e:
                print(f"  ⚠ Note: {type_id} will use default parameters")


    
    def _map_traffic_lights(self):
        """Map SUMO traffic lights to your system's traffic lights"""
        
        # Get all SUMO traffic lights
        sumo_tls = traci.trafficlight.getIDList()
        
        # Map based on location proximity
        for tls_id in sumo_tls:
            # Get traffic light position in SUMO
            # Note: This gets the position of the first controlled link
            controlled_links = traci.trafficlight.getControlledLinks(tls_id)
            if controlled_links:
                # Get the lane of the first controlled link
                lane_id = controlled_links[0][0][0]
                if lane_id:
                    # Get position at the end of the lane (where traffic light is)
                    x, y = traci.lane.getShape(lane_id)[-1]
                    lon, lat = traci.simulation.convertGeo(x, y)
                    
                    # Find nearest traffic light in your system
                    min_dist = float('inf')
                    nearest_tl = None
                    
                    for sys_tl_id, sys_tl in self.integrated_system.traffic_lights.items():
                        dist = self._calculate_distance(lat, lon, sys_tl['lat'], sys_tl['lon'])
                        if dist < min_dist and dist < 0.0005:  # ~50 meters
                            min_dist = dist
                            nearest_tl = sys_tl_id
                    
                    if nearest_tl:
                        self.tls_mapping[tls_id] = nearest_tl
        
        print(f"  - Mapped {len(self.tls_mapping)} traffic lights between SUMO and power system")
    
    def _map_ev_stations(self):
        """Map EV charging stations to nearest SUMO edges"""
        
        for ev_id, ev_station in self.integrated_system.ev_stations.items():
            # Find nearest edge in SUMO network
            x, y = self.net.convertLonLat2XY(ev_station['lon'], ev_station['lat'])
            
            # Get nearest edge
            edges = self.net.getNeighboringEdges(x, y, r=100)  # 100m radius
            if edges:
                # Sort by distance
                edges_sorted = sorted(edges, key=lambda e: e[1])
                nearest_edge = edges_sorted[0][0]
                
                self.ev_stations_sumo[ev_id] = {
                    'edge_id': nearest_edge.getID(),
                    'position': (x, y),
                    'capacity': ev_station['chargers'],
                    'available': ev_station['chargers'],
                    'system_id': ev_id
                }
        
        print(f"  - Mapped {len(self.ev_stations_sumo)} EV stations to SUMO edges")
    
def spawn_vehicles(self, count: int = 10, ev_percentage: float = 0.7):
    """
    Spawn vehicles with intelligent routing
    70% EVs, 30% gas vehicles by default
    """
    
    if not self.running:
        print("SUMO not running!")
        return
    
    # Get valid edges for spawning (not internal edges)
    valid_edges = [e for e in self.net.getEdges() 
                  if not e.isSpecial() and e.allows("passenger")]
    
    if not valid_edges:
        print("No valid edges for spawning!")
        return
    
    spawned = 0
    for i in range(count):
        veh_id = f"veh_{self.stats['total_vehicles']}_{int(time.time())}"
        
        # Determine vehicle type
        is_ev = random.random() < ev_percentage
        if is_ev:
            vtype = random.choice([VehicleType.SEDAN_EV, VehicleType.SUV_EV, VehicleType.TAXI_EV])
        else:
            vtype = random.choice([VehicleType.SEDAN_GAS])
        
        config = self.vehicle_types[vtype]
        
        # Select random start and end edges
        start_edge = random.choice(valid_edges)
        end_edge = random.choice(valid_edges)
        
        # Make sure they're different
        while end_edge == start_edge:
            end_edge = random.choice(valid_edges)
        
        # Create route
        route = self._compute_route(start_edge.getID(), end_edge.getID())
        
        if route:
            try:
                # Add route to SUMO
                route_id = f"route_{veh_id}"
                traci.route.add(route_id, route)
                
                # Add vehicle WITHOUT specifying typeID first
                # This creates a default vehicle
                traci.vehicle.add(
                    veh_id,
                    route_id,
                    depart="now"
                )
                
                # Now set the vehicle parameters individually
                traci.vehicle.setLength(veh_id, config.length)
                traci.vehicle.setMinGap(veh_id, config.min_gap)
                traci.vehicle.setMaxSpeed(veh_id, config.max_speed_mps)
                traci.vehicle.setAccel(veh_id, config.acceleration)
                traci.vehicle.setDecel(veh_id, config.deceleration)
                
                # Set color based on type
                if "taxi" in vtype.value:
                    traci.vehicle.setColor(veh_id, (255, 255, 0, 255))  # Yellow
                elif config.is_ev:
                    traci.vehicle.setColor(veh_id, (0, 255, 0, 255))  # Green for EVs
                else:
                    traci.vehicle.setColor(veh_id, (100, 100, 255, 255))  # Blue for gas
                
                # Set emission class
                if config.is_ev:
                    try:
                        traci.vehicle.setEmissionClass(veh_id, "HBEFA3/zero")
                    except:
                        pass  # Emission class might not be available
                
                # Create vehicle object
                vehicle = ManhattanVehicle(
                    id=veh_id,
                    config=config,
                    route=route,
                    destination=end_edge.getID()
                )
                
                if config.is_ev:
                    initial_soc = random.uniform(0.3, 0.9)
                    vehicle.config.current_soc = initial_soc
                
                self.vehicles[veh_id] = vehicle
                self.stats['total_vehicles'] += 1
                if config.is_ev:
                    self.stats['ev_vehicles'] += 1
                
                spawned += 1
                print(f"  ✓ Spawned {veh_id} ({vtype.value}) - Battery: {initial_soc*100:.0f}%" if config.is_ev else f"  ✓ Spawned {veh_id} ({vtype.value})")
                
            except Exception as e:
                print(f"  ✗ Failed to spawn vehicle: {e}")
    
    print(f"Successfully spawned {spawned}/{count} vehicles")
    return spawned
    
    def _compute_route(self, from_edge: str, to_edge: str) -> Optional[List[str]]:
        """Compute shortest route between two edges"""
        
        # Check cache first
        cache_key = f"{from_edge}_{to_edge}"
        if cache_key in self.route_cache:
            return self.route_cache[cache_key]
        
        try:
            # Get route from SUMO
            route = traci.simulation.findRoute(from_edge, to_edge)
            if route and route.edges:
                self.route_cache[cache_key] = route.edges
                return route.edges
        except:
            pass
        
        return None
    
    def update_traffic_lights(self):
        """Synchronize traffic lights with your power system"""
        
        if not self.running:
            return
        
        for sumo_tls_id, system_tl_id in self.tls_mapping.items():
            if system_tl_id in self.integrated_system.traffic_lights:
                tl = self.integrated_system.traffic_lights[system_tl_id]
                
                if not tl['powered']:
                    # No power - set to flashing red (all red)
                    try:
                        program = traci.trafficlight.getProgram(sumo_tls_id)
                        state = "r" * len(traci.trafficlight.getRedYellowGreenState(sumo_tls_id))
                        traci.trafficlight.setRedYellowGreenState(sumo_tls_id, state)
                    except:
                        pass
                else:
                    # Normal operation - sync with your system's phase
                    # This is simplified - you may need to map phases more carefully
                    phase = tl.get('phase', 'normal')
                    
                    try:
                        current_state = traci.trafficlight.getRedYellowGreenState(sumo_tls_id)
                        new_state = list(current_state)
                        
                        # Simple mapping - adjust based on your actual SUMO network
                        if phase == 'green':
                            # Set some lights to green
                            for i in range(0, min(4, len(new_state)), 2):
                                new_state[i] = 'G'
                        elif phase == 'yellow':
                            # Set to yellow
                            for i in range(len(new_state)):
                                if new_state[i] == 'G':
                                    new_state[i] = 'y'
                        else:  # red
                            # All red
                            new_state = ['r'] * len(new_state)
                        
                        traci.trafficlight.setRedYellowGreenState(sumo_tls_id, ''.join(new_state))
                    except:
                        pass
    
    def step(self):
        """Execute one simulation step with full integration"""
        
        if not self.running:
            return False
        
        try:
            # Step SUMO simulation
            traci.simulationStep()
            self.simulation_time += self.step_length
            
            # Update traffic light states
            self.update_traffic_lights()
            
            # Update vehicle states
            self._update_vehicle_states()
            
            # Check for EV charging needs
            self._check_ev_charging()
            
            # Update statistics
            self._update_statistics()
            
            return True
            
        except Exception as e:
            print(f"Simulation step error: {e}")
            return False
    
    def _update_vehicle_states(self):
        """Update all vehicle states from SUMO"""
        
        current_vehicles = set(traci.vehicle.getIDList())
        
        # Update existing vehicles
        for veh_id in list(self.vehicles.keys()):
            if veh_id in current_vehicles:
                vehicle = self.vehicles[veh_id]
                
                # Update position
                x, y = traci.vehicle.getPosition(veh_id)
                vehicle.position = (x, y)
                
                # Update speed
                vehicle.speed = traci.vehicle.getSpeed(veh_id)
                
                # Update distance
                vehicle.distance_traveled = traci.vehicle.getDistance(veh_id)
                
                # Update waiting time
                vehicle.waiting_time = traci.vehicle.getWaitingTime(veh_id)
                
                # Update edge
                vehicle.current_edge = traci.vehicle.getRoadID(veh_id)
                
                # Update battery for EVs
                if vehicle.config.is_ev:
                    try:
                        # Get battery level from SUMO
                        battery_wh = float(traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity"))
                        vehicle.config.current_soc = battery_wh / (vehicle.config.battery_capacity_kwh * 1000)
                    except:
                        # Estimate based on distance
                        energy_used = vehicle.distance_traveled * vehicle.config.consumption_kwh_per_km / 1000
                        vehicle.config.current_soc = max(0, vehicle.config.current_soc - energy_used / vehicle.config.battery_capacity_kwh)
                
                # Update emissions for gas vehicles
                if not vehicle.config.is_ev:
                    vehicle.co2_emission = traci.vehicle.getCO2Emission(veh_id)
                    vehicle.fuel_consumption = traci.vehicle.getFuelConsumption(veh_id)
            else:
                # Vehicle has left the simulation
                if veh_id in self.vehicles:
                    del self.vehicles[veh_id]
    
    def _check_ev_charging(self):
        """Check if EVs need charging and route them to stations"""
        
        for veh_id, vehicle in self.vehicles.items():
            if not vehicle.config.is_ev:
                continue
            
            # Check if needs charging
            if vehicle.config.current_soc < vehicle.config.charging_threshold and not vehicle.is_charging:
                # Find nearest available charging station
                nearest_station = self._find_nearest_ev_station(vehicle.position)
                
                if nearest_station:
                    # Reroute to charging station
                    current_edge = vehicle.current_edge
                    target_edge = nearest_station['edge_id']
                    
                    new_route = self._compute_route(current_edge, target_edge)
                    if new_route:
                        try:
                            # Update route in SUMO
                            traci.vehicle.setRoute(veh_id, new_route)
                            vehicle.assigned_ev_station = nearest_station['system_id']
                            vehicle.destination = target_edge
                            
                            print(f"  ⚡ {veh_id} routing to charging station (SOC: {vehicle.config.current_soc*100:.1f}%)")
                        except:
                            pass
            
            # Check if at charging station
            elif vehicle.assigned_ev_station and vehicle.current_edge == self.ev_stations_sumo[vehicle.assigned_ev_station]['edge_id']:
                if not vehicle.is_charging:
                    # Start charging
                    vehicle.is_charging = True
                    self.stats['vehicles_charging'] += 1
                    
                    # Update power grid load
                    if vehicle.assigned_ev_station in self.integrated_system.ev_stations:
                        ev_station = self.integrated_system.ev_stations[vehicle.assigned_ev_station]
                        ev_station['vehicles_charging'] = min(
                            ev_station['vehicles_charging'] + 1,
                            ev_station['chargers']
                        )
                    
                    print(f"  🔌 {veh_id} started charging at {vehicle.assigned_ev_station}")
                    
                    # Stop vehicle for charging
                    try:
                        traci.vehicle.setSpeed(veh_id, 0)
                        traci.vehicle.setColor(veh_id, (255, 165, 0, 255))  # Orange while charging
                    except:
                        pass
                
                # Simulate charging
                vehicle.config.current_soc = min(1.0, vehicle.config.current_soc + 0.001)  # Charge rate
                
                # Check if fully charged
                if vehicle.config.current_soc >= 0.8:  # Charge to 80%
                    vehicle.is_charging = False
                    vehicle.assigned_ev_station = None
                    self.stats['vehicles_charging'] -= 1
                    
                    # Update power grid
                    if vehicle.assigned_ev_station in self.integrated_system.ev_stations:
                        ev_station = self.integrated_system.ev_stations[vehicle.assigned_ev_station]
                        ev_station['vehicles_charging'] = max(0, ev_station['vehicles_charging'] - 1)
                    
                    # Resume normal routing
                    try:
                        traci.vehicle.setSpeed(veh_id, -1)  # Resume normal speed
                        traci.vehicle.setColor(veh_id, (0, 255, 0, 255))  # Green for EV
                        
                        # Set new random destination
                        valid_edges = [e.getID() for e in self.net.getEdges() if not e.isSpecial()]
                        new_dest = random.choice(valid_edges)
                        new_route = self._compute_route(vehicle.current_edge, new_dest)
                        if new_route:
                            traci.vehicle.setRoute(veh_id, new_route)
                    except:
                        pass
                    
                    print(f"  ✅ {veh_id} finished charging (SOC: {vehicle.config.current_soc*100:.0f}%)")
    
    def _find_nearest_ev_station(self, position: Tuple[float, float]) -> Optional[Dict]:
        """Find nearest available EV charging station"""
        
        min_dist = float('inf')
        nearest = None
        
        for station_id, station in self.ev_stations_sumo.items():
            if station['available'] > 0:  # Has available chargers
                dist = np.sqrt((position[0] - station['position'][0])**2 + 
                             (position[1] - station['position'][1])**2)
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
            
            # Calculate total energy consumed by EVs
            total_energy = 0
            for vehicle in self.vehicles.values():
                if vehicle.config.is_ev:
                    energy_used = (1 - vehicle.config.current_soc) * vehicle.config.battery_capacity_kwh
                    total_energy += energy_used
            self.stats['total_energy_consumed_kwh'] = total_energy
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points"""
        return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)
    
    def get_vehicle_positions(self) -> List[Dict]:
        """Get all vehicle positions for visualization"""
        
        positions = []
        for veh_id, vehicle in self.vehicles.items():
            lon, lat = traci.simulation.convertGeo(vehicle.position[0], vehicle.position[1])
            
            positions.append({
                'id': veh_id,
                'lat': lat,
                'lon': lon,
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
            traci.close()
            self.running = False
            print("SUMO simulation stopped")