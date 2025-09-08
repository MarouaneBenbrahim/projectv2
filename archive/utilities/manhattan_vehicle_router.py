"""
Manhattan Smart Vehicle Router - Google Maps-Level Intelligence
World-class routing for EVs and gas vehicles using real street network
"""

import sumolib
import traci
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import heapq
import random
from collections import defaultdict
import json
import math

class VehicleType(Enum):
    """Vehicle types with realistic specs"""
    TESLA_MODEL_3 = "tesla_model3"
    TESLA_MODEL_Y = "tesla_modely"
    NISSAN_LEAF = "nissan_leaf"
    RIVIAN_R1T = "rivian_r1t"
    BMW_I4 = "bmw_i4"
    FORD_MUSTANG_MACH_E = "ford_mache"
    # Gas vehicles
    TOYOTA_CAMRY = "toyota_camry"
    HONDA_ACCORD = "honda_accord"
    FORD_F150 = "ford_f150"
    
@dataclass
class VehicleSpecs:
    """Realistic vehicle specifications"""
    vehicle_type: VehicleType
    is_ev: bool
    battery_capacity_kwh: float = 0  # 0 for gas vehicles
    consumption_kwh_per_km: float = 0.18  # Average EV consumption
    charging_rate_kw: float = 150  # Fast charging
    min_battery_percent: float = 15  # Go charge at 15%
    target_charge_percent: float = 80  # Charge to 80%
    max_speed_kmh: float = 120
    acceleration: float = 2.5
    color: str = "1,1,1"
    
class RouterService:
    """World-class routing service for Manhattan vehicles"""
    
    def __init__(self, network_file: str = "data/manhattan_real.net.xml"):
        # Load real network
        self.net = sumolib.net.readNet(network_file)
        print(f"✅ Router initialized with {len(self.net.getEdges())} streets")
        
        # Build routing graph
        self.graph = self._build_routing_graph()
        
        # Charging stations with real Manhattan locations
        self.charging_stations = self._init_charging_stations()
        
        # Vehicle tracking
        self.vehicles = {}
        self.charging_queue = defaultdict(list)
        
        # Configuration
        self.config = {
            'ev_percentage': 70,  # 70% EVs, 30% gas
            'initial_battery_random': True,  # Random initial charge
            'min_initial_battery': 20,  # Minimum starting battery %
            'max_initial_battery': 95,  # Maximum starting battery %
            'realistic_traffic': True,
            'charging_reservation': True
        }
        
        # Vehicle specifications
        self.vehicle_specs = self._init_vehicle_specs()
        
    def _init_vehicle_specs(self) -> Dict[VehicleType, VehicleSpecs]:
        """Initialize realistic vehicle specifications"""
        return {
            VehicleType.TESLA_MODEL_3: VehicleSpecs(
                VehicleType.TESLA_MODEL_3, True, 75, 0.16, 250, 15, 80, 160, 2.5, "0.8,0.1,0.1"
            ),
            VehicleType.TESLA_MODEL_Y: VehicleSpecs(
                VehicleType.TESLA_MODEL_Y, True, 82, 0.18, 250, 15, 80, 155, 3.0, "0.9,0.9,0.9"
            ),
            VehicleType.NISSAN_LEAF: VehicleSpecs(
                VehicleType.NISSAN_LEAF, True, 40, 0.17, 50, 20, 80, 145, 2.8, "0,0.6,0.3"
            ),
            VehicleType.RIVIAN_R1T: VehicleSpecs(
                VehicleType.RIVIAN_R1T, True, 135, 0.25, 200, 15, 80, 180, 3.0, "0.2,0.4,0.2"
            ),
            VehicleType.BMW_I4: VehicleSpecs(
                VehicleType.BMW_I4, True, 80, 0.16, 200, 15, 80, 190, 2.4, "0,0.3,0.7"
            ),
            VehicleType.FORD_MUSTANG_MACH_E: VehicleSpecs(
                VehicleType.FORD_MUSTANG_MACH_E, True, 88, 0.19, 150, 15, 80, 180, 2.6, "1,0.5,0"
            ),
            # Gas vehicles
            VehicleType.TOYOTA_CAMRY: VehicleSpecs(
                VehicleType.TOYOTA_CAMRY, False, 0, 0, 0, 0, 0, 180, 2.8, "0.7,0.7,0.7"
            ),
            VehicleType.HONDA_ACCORD: VehicleSpecs(
                VehicleType.HONDA_ACCORD, False, 0, 0, 0, 0, 0, 175, 2.9, "0.2,0.2,0.2"
            ),
            VehicleType.FORD_F150: VehicleSpecs(
                VehicleType.FORD_F150, False, 0, 0, 0, 0, 0, 160, 3.5, "0,0,0.5"
            )
        }
    
    def _init_charging_stations(self) -> Dict[str, Dict]:
        """Initialize real Manhattan charging stations"""
        stations = {
            'cs_times_square': {
                'edge_id': None,  # Will find nearest edge
                'lat': 40.7580, 'lon': -73.9855,
                'capacity': 20, 'available': 20,
                'power_kw': 250,  # Tesla Supercharger speeds
                'name': 'Times Square Supercharger'
            },
            'cs_penn_station': {
                'edge_id': None,
                'lat': 40.7505, 'lon': -73.9934,
                'capacity': 15, 'available': 15,
                'power_kw': 150,
                'name': 'Penn Station Fast Charging'
            },
            'cs_grand_central': {
                'edge_id': None,
                'lat': 40.7527, 'lon': -73.9772,
                'capacity': 25, 'available': 25,
                'power_kw': 250,
                'name': 'Grand Central Supercharger'
            },
            'cs_bryant_park': {
                'edge_id': None,
                'lat': 40.7536, 'lon': -73.9832,
                'capacity': 10, 'available': 10,
                'power_kw': 150,
                'name': 'Bryant Park Charging Hub'
            },
            'cs_columbus_circle': {
                'edge_id': None,
                'lat': 40.7681, 'lon': -73.9819,
                'capacity': 18, 'available': 18,
                'power_kw': 200,
                'name': 'Columbus Circle Station'
            },
            'cs_chelsea': {
                'edge_id': None,
                'lat': 40.7465, 'lon': -74.0014,
                'capacity': 12, 'available': 12,
                'power_kw': 150,
                'name': 'Chelsea Market Charging'
            },
            'cs_midtown_east': {
                'edge_id': None,
                'lat': 40.7614, 'lon': -73.9647,
                'capacity': 15, 'available': 15,
                'power_kw': 200,
                'name': 'Midtown East Hub'
            },
            'cs_hells_kitchen': {
                'edge_id': None,
                'lat': 40.7638, 'lon': -73.9918,
                'capacity': 10, 'available': 10,
                'power_kw': 150,
                'name': "Hell's Kitchen Charging"
            }
        }
        
        # Find nearest edge for each station
        for station_id, station in stations.items():
            station['edge_id'] = self._find_nearest_edge(station['lat'], station['lon'])
            print(f"  📍 {station['name']}: {station['capacity']} chargers at edge {station['edge_id']}")
        
        return stations
    
    def _build_routing_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build graph for A* routing from SUMO network"""
        graph = defaultdict(list)
        
        for edge in self.net.getEdges():
            edge_id = edge.getID()
            # Get outgoing edges from this edge's end node
            outgoing_node = edge.getToNode()
            for outgoing_edge in outgoing_node.getOutgoing():
                to_edge_id = outgoing_edge.getID()
                # Weight is travel time (length / speed)
                weight = edge.getLength() / max(1, edge.getSpeed())
                graph[edge_id].append((to_edge_id, weight))
        
        return graph
    
    def _find_nearest_edge(self, lat: float, lon: float) -> str:
        """Find nearest edge to given coordinates"""
        x, y = self.net.convertLonLat2XY(lon, lat)
        edges = self.net.getNeighboringEdges(x, y, r=200)  # 200m radius
        
        if edges:
            # Sort by distance and return closest
            edges_sorted = sorted(edges, key=lambda e: e[1])
            return edges_sorted[0][0].getID()
        
        # Fallback to any edge
        return list(self.net.getEdges())[0].getID()
    
    def find_shortest_path(self, from_edge: str, to_edge: str, 
                          avoid_edges: List[str] = None) -> Tuple[List[str], float]:
        """A* pathfinding for shortest route"""
        
        if from_edge == to_edge:
            return [from_edge], 0
        
        # A* implementation
        open_set = [(0, from_edge, [])]
        closed_set = set()
        g_score = {from_edge: 0}
        
        # Get end coordinates for heuristic
        try:
            to_edge_obj = self.net.getEdge(to_edge)
            to_x, to_y = to_edge_obj.getToNode().getCoord()
        except:
            return [], float('inf')
        
        while open_set:
            f_score, current, path = heapq.heappop(open_set)
            
            if current == to_edge:
                return path + [current], g_score[current]
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # Check neighbors
            for next_edge, weight in self.graph.get(current, []):
                if avoid_edges and next_edge in avoid_edges:
                    continue
                
                tentative_g = g_score[current] + weight
                
                if next_edge not in g_score or tentative_g < g_score[next_edge]:
                    g_score[next_edge] = tentative_g
                    
                    # Heuristic: Euclidean distance
                    try:
                        edge_obj = self.net.getEdge(next_edge)
                        x, y = edge_obj.getToNode().getCoord()
                        h = math.sqrt((x - to_x)**2 + (y - to_y)**2) / 10  # Rough time estimate
                    except:
                        h = 0
                    
                    f = tentative_g + h
                    heapq.heappush(open_set, (f, next_edge, path + [current]))
        
        return [], float('inf')  # No path found
    
    def find_nearest_charging_station(self, current_edge: str, 
                                     current_battery_kwh: float,
                                     battery_capacity_kwh: float,
                                     consumption_rate: float) -> Optional[str]:
        """Find best charging station considering range and availability"""
        
        best_station = None
        best_score = float('inf')
        
        current_range_km = current_battery_kwh / consumption_rate
        
        for station_id, station in self.charging_stations.items():
            if station['available'] <= 0:
                continue
            
            # Find path to station
            path, distance = self.find_shortest_path(current_edge, station['edge_id'])
            
            if not path:
                continue
            
            # Check if we can reach it
            distance_km = distance / 1000
            if distance_km > current_range_km * 0.9:  # 10% safety margin
                continue
            
            # Score based on distance and availability
            availability_factor = station['available'] / station['capacity']
            charging_speed_factor = station['power_kw'] / 250  # Normalized to supercharger
            
            score = distance / (availability_factor * charging_speed_factor)
            
            if score < best_score:
                best_score = score
                best_station = station_id
        
        return best_station
    
    def create_smart_vehicle(self, vehicle_id: str, start_edge: str, 
                           destination_edge: str) -> Dict:
        """Create a vehicle with smart routing capabilities"""
        
        # Decide if EV or gas based on configuration
        is_ev = random.random() < (self.config['ev_percentage'] / 100)
        
        if is_ev:
            # Choose random EV type
            ev_types = [t for t, s in self.vehicle_specs.items() if s.is_ev]
            vehicle_type = random.choice(ev_types)
        else:
            # Choose random gas vehicle
            gas_types = [t for t, s in self.vehicle_specs.items() if not s.is_ev]
            vehicle_type = random.choice(gas_types)
        
        specs = self.vehicle_specs[vehicle_type]
        
        # Set initial battery for EVs
        battery_kwh = 0
        if is_ev:
            if self.config['initial_battery_random']:
                # Some vehicles start with low battery to trigger immediate charging
                if random.random() < 0.2:  # 20% start very low
                    battery_percent = random.uniform(10, 25)
                else:
                    battery_percent = random.uniform(
                        self.config['min_initial_battery'],
                        self.config['max_initial_battery']
                    )
            else:
                battery_percent = 70  # Default
            
            battery_kwh = specs.battery_capacity_kwh * (battery_percent / 100)
        
        # Find initial route
        route, distance = self.find_shortest_path(start_edge, destination_edge)
        
        # Check if EV needs charging for this trip
        needs_charging = False
        charging_station = None
        
        if is_ev:
            trip_consumption = (distance / 1000) * specs.consumption_kwh_per_km
            battery_after_trip = battery_kwh - trip_consumption
            
            if battery_after_trip < specs.battery_capacity_kwh * (specs.min_battery_percent / 100):
                needs_charging = True
                charging_station = self.find_nearest_charging_station(
                    start_edge, battery_kwh, specs.battery_capacity_kwh, 
                    specs.consumption_kwh_per_km
                )
        
        vehicle_data = {
            'id': vehicle_id,
            'type': vehicle_type.value,
            'specs': specs,
            'is_ev': is_ev,
            'battery_kwh': battery_kwh,
            'battery_percent': (battery_kwh / specs.battery_capacity_kwh * 100) if is_ev else 0,
            'start_edge': start_edge,
            'destination_edge': destination_edge,
            'current_edge': start_edge,
            'route': route,
            'needs_charging': needs_charging,
            'charging_station': charging_station,
            'state': 'traveling',  # traveling, charging, waiting_for_charger, arrived
            'distance_traveled': 0,
            'color': specs.color
        }
        
        self.vehicles[vehicle_id] = vehicle_data
        return vehicle_data
    
    def update_vehicle_position(self, vehicle_id: str, current_edge: str, 
                              position_on_edge: float):
        """Update vehicle position and check if rerouting needed"""
        
        if vehicle_id not in self.vehicles:
            return
        
        vehicle = self.vehicles[vehicle_id]
        vehicle['current_edge'] = current_edge
        
        # Update battery for EVs
        if vehicle['is_ev']:
            # Calculate consumption since last update
            edge_obj = self.net.getEdge(current_edge)
            distance_m = edge_obj.getLength() * position_on_edge
            consumption = (distance_m / 1000) * vehicle['specs'].consumption_kwh_per_km
            vehicle['battery_kwh'] = max(0, vehicle['battery_kwh'] - consumption)
            vehicle['battery_percent'] = (vehicle['battery_kwh'] / 
                                         vehicle['specs'].battery_capacity_kwh * 100)
            
            # Check if we need to find charging
            if (vehicle['battery_percent'] < vehicle['specs'].min_battery_percent and 
                not vehicle['needs_charging']):
                
                station = self.find_nearest_charging_station(
                    current_edge,
                    vehicle['battery_kwh'],
                    vehicle['specs'].battery_capacity_kwh,
                    vehicle['specs'].consumption_kwh_per_km
                )
                
                if station:
                    vehicle['needs_charging'] = True
                    vehicle['charging_station'] = station
                    vehicle['state'] = 'seeking_charger'
                    
                    # Reroute to charging station
                    self.reroute_to_charging(vehicle_id)
    
    def reroute_to_charging(self, vehicle_id: str):
        """Reroute vehicle to charging station"""
        
        vehicle = self.vehicles[vehicle_id]
        if not vehicle['charging_station']:
            return
        
        station = self.charging_stations[vehicle['charging_station']]
        
        # Find route from current position to charging station
        new_route, distance = self.find_shortest_path(
            vehicle['current_edge'],
            station['edge_id']
        )
        
        if new_route:
            vehicle['route'] = new_route
            vehicle['destination_edge'] = station['edge_id']
            
            # Reserve charging slot
            if self.config['charging_reservation']:
                station['available'] -= 1
                self.charging_queue[vehicle['charging_station']].append(vehicle_id)
            
            return new_route
        
        return None
    
    def start_charging(self, vehicle_id: str):
        """Start charging process for vehicle"""
        
        vehicle = self.vehicles[vehicle_id]
        vehicle['state'] = 'charging'
        vehicle['charging_start_time'] = traci.simulation.getTime()
        
    def update_charging(self, vehicle_id: str, dt: float):
        """Update vehicle charging status"""
        
        vehicle = self.vehicles[vehicle_id]
        if vehicle['state'] != 'charging':
            return
        
        station = self.charging_stations[vehicle['charging_station']]
        
        # Calculate charge added
        charge_rate_kwh_per_sec = station['power_kw'] / 3600
        charge_added = charge_rate_kwh_per_sec * dt
        
        vehicle['battery_kwh'] = min(
            vehicle['specs'].battery_capacity_kwh,
            vehicle['battery_kwh'] + charge_added
        )
        vehicle['battery_percent'] = (vehicle['battery_kwh'] / 
                                     vehicle['specs'].battery_capacity_kwh * 100)
        
        # Check if charging complete
        if vehicle['battery_percent'] >= vehicle['specs'].target_charge_percent:
            self.finish_charging(vehicle_id)
    
    def finish_charging(self, vehicle_id: str):
        """Finish charging and resume trip"""
        
        vehicle = self.vehicles[vehicle_id]
        station = self.charging_stations[vehicle['charging_station']]
        
        # Release charging slot
        station['available'] += 1
        if vehicle_id in self.charging_queue[vehicle['charging_station']]:
            self.charging_queue[vehicle['charging_station']].remove(vehicle_id)
        
        vehicle['state'] = 'traveling'
        vehicle['needs_charging'] = False
        vehicle['charging_station'] = None
        
        # Resume original route or set new destination
        # (Implementation depends on your trip generation logic)
    
    def get_vehicle_telemetry(self, vehicle_id: str) -> Dict:
        """Get real-time vehicle data for visualization"""
        
        if vehicle_id not in self.vehicles:
            return {}
        
        vehicle = self.vehicles[vehicle_id]
        
        # Get actual position from SUMO
        try:
            x, y = traci.vehicle.getPosition(vehicle_id)
            lon, lat = self.net.convertXY2LonLat(x, y)
            speed = traci.vehicle.getSpeed(vehicle_id)
        except:
            # Fallback if vehicle not in SUMO yet
            edge_obj = self.net.getEdge(vehicle['current_edge'])
            x, y = edge_obj.getFromNode().getCoord()
            lon, lat = self.net.convertXY2LonLat(x, y)
            speed = 0
        
        return {
            'id': vehicle_id,
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed * 3.6,
            'type': vehicle['type'],
            'is_ev': vehicle['is_ev'],
            'battery_percent': vehicle.get('battery_percent', 0),
            'state': vehicle['state'],
            'needs_charging': vehicle.get('needs_charging', False),
            'destination': vehicle.get('charging_station') or 'destination',
            'color': vehicle['color']
        }

# Integration with SUMO
class SmartVehicleManager:
    """Manages smart vehicles in SUMO simulation"""
    
    def __init__(self, router: RouterService):
        self.router = router
        self.active_vehicles = {}
        
    def spawn_vehicle(self, vehicle_id: str, start_edge: str, end_edge: str):
        """Spawn a smart vehicle in SUMO"""
        
        # Create smart vehicle data
        vehicle_data = self.router.create_smart_vehicle(vehicle_id, start_edge, end_edge)
        
        # Add to SUMO
        traci.vehicle.add(
            vehicle_id,
            routeID="",
            typeID=vehicle_data['type'],
            depart='now'
        )
        
        # Set route
        traci.vehicle.setRoute(vehicle_id, vehicle_data['route'])
        
        # Color is already set by vehicle type, no need to set again
        
        self.active_vehicles[vehicle_id] = vehicle_data
        
    def update_all_vehicles(self):
        """Update all vehicle positions and states"""
        
        for vehicle_id in traci.vehicle.getIDList():
            if vehicle_id not in self.active_vehicles:
                continue
            
            # Get current position
            try:
                edge_id = traci.vehicle.getRoadID(vehicle_id)
                position = traci.vehicle.getLanePosition(vehicle_id)
                
                # Update router
                self.router.update_vehicle_position(vehicle_id, edge_id, position)
                
                # Check if rerouting needed
                vehicle = self.router.vehicles[vehicle_id]
                if vehicle['state'] == 'seeking_charger':
                    new_route = self.router.reroute_to_charging(vehicle_id)
                    if new_route:
                        traci.vehicle.setRoute(vehicle_id, new_route)
                
            except:
                pass
    
    def get_all_telemetry(self) -> List[Dict]:
        """Get telemetry for all vehicles"""
        
        telemetry = []
        for vehicle_id in self.active_vehicles:
            data = self.router.get_vehicle_telemetry(vehicle_id)
            if data:
                telemetry.append(data)
        
        return telemetry