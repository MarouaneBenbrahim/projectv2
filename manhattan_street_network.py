"""
REAL Manhattan Street Network for Vehicle Routing
Uses actual street grid with proper intersections
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import heapq

@dataclass
class Street:
    """Real street segment"""
    id: str
    name: str
    start_intersection: str
    end_intersection: str
    start_coords: Tuple[float, float]  # (lat, lon)
    end_coords: Tuple[float, float]
    direction: str  # 'NS', 'EW', 'both'
    lanes: int
    speed_limit: float  # mph
    
@dataclass 
class Intersection:
    """Real intersection with traffic light"""
    id: str
    lat: float
    lon: float
    streets: List[str]  # Connected street IDs
    has_light: bool
    light_id: Optional[str]
    
class ManhattanStreetNetwork:
    """
    ACTUAL Manhattan street grid for realistic vehicle movement
    """
    
    def __init__(self):
        self.intersections = {}
        self.streets = {}
        self.graph = defaultdict(list)  # For pathfinding
        
        # Build the real grid
        self._build_manhattan_grid()
        
    def _build_manhattan_grid(self):
        """Build actual Manhattan street grid"""
        
        # AVENUES (North-South) - Real positions
        avenues = [
            ('12th Ave', -74.0080, 'both'),
            ('11th Ave', -74.0050, 'both'),
            ('10th Ave', -74.0020, 'both'),
            ('9th Ave', -73.9990, 'both'),
            ('8th Ave', -73.9960, 'both'),
            ('7th Ave', -73.9915, 'both'),
            ('Broadway', -73.9870, 'both'),  # Diagonal!
            ('6th Ave', -73.9845, 'both'),
            ('5th Ave', -73.9820, 'both'),
            ('Madison Ave', -73.9795, 'both'),
            ('Park Ave', -73.9770, 'both'),
            ('Lexington Ave', -73.9745, 'both'),
            ('3rd Ave', -73.9720, 'both'),
            ('2nd Ave', -73.9695, 'both'),
            ('1st Ave', -73.9670, 'both'),
            ('York Ave', -73.9645, 'both'),
            ('FDR Drive', -73.9620, 'NS')  # Highway
        ]
        
        # STREETS (East-West) - Every block from 34th to 59th
        streets = list(range(34, 60))
        base_lat = 40.7486  # 34th Street latitude
        lat_per_block = 0.00145  # ~260 feet per block
        
        # Create all intersections
        intersection_id = 0
        for street_num in streets:
            street_lat = base_lat + (street_num - 34) * lat_per_block
            
            for ave_name, ave_lon, ave_dir in avenues:
                # Skip some combinations that don't exist
                if ave_name == 'FDR Drive' and street_num not in [34, 42, 57]:
                    continue
                    
                int_id = f"int_{street_num}_{ave_name.replace(' ', '_')}"
                
                self.intersections[int_id] = Intersection(
                    id=int_id,
                    lat=street_lat,
                    lon=ave_lon,
                    streets=[],
                    has_light=True,  # Most intersections have lights
                    light_id=f"tl_{intersection_id}"
                )
                intersection_id += 1
        
        # Create street segments
        street_id = 0
        
        # East-West streets
        for street_num in streets:
            street_lat = base_lat + (street_num - 34) * lat_per_block
            street_name = f"{street_num}th Street"
            
            # One-way or two-way based on real Manhattan
            if street_num in [34, 42, 57, 14, 23]:  # Major two-way streets
                direction = 'both'
            elif street_num % 2 == 0:  # Even streets go East
                direction = 'E'
            else:  # Odd streets go West
                direction = 'W'
            
            # Connect consecutive avenues
            for i in range(len(avenues) - 1):
                ave1_name, ave1_lon, _ = avenues[i]
                ave2_name, ave2_lon, _ = avenues[i + 1]
                
                start_int = f"int_{street_num}_{ave1_name.replace(' ', '_')}"
                end_int = f"int_{street_num}_{ave2_name.replace(' ', '_')}"
                
                if start_int in self.intersections and end_int in self.intersections:
                    street = Street(
                        id=f"st_{street_id}",
                        name=f"{street_name} ({ave1_name} to {ave2_name})",
                        start_intersection=start_int,
                        end_intersection=end_int,
                        start_coords=(street_lat, ave1_lon),
                        end_coords=(street_lat, ave2_lon),
                        direction=direction,
                        lanes=2 if street_num in [34, 42, 57] else 1,
                        speed_limit=25.0
                    )
                    
                    self.streets[street.id] = street
                    
                    # Add to intersections
                    self.intersections[start_int].streets.append(street.id)
                    self.intersections[end_int].streets.append(street.id)
                    
                    # Add to graph for pathfinding
                    if direction in ['E', 'both']:
                        self.graph[start_int].append((end_int, street.id))
                    if direction in ['W', 'both']:
                        self.graph[end_int].append((start_int, street.id))
                    
                    street_id += 1
        
        # North-South avenues
        for ave_name, ave_lon, ave_dir in avenues:
            # Skip FDR for now (highway)
            if ave_name == 'FDR Drive':
                continue
                
            # Avenues are mostly one-way
            if ave_name in ['5th Ave', '6th Ave', '7th Ave', '8th Ave', '9th Ave']:
                direction = 'S' if ave_name in ['5th Ave', '7th Ave', '9th Ave'] else 'N'
            else:
                direction = 'both'
            
            # Connect consecutive streets
            for i in range(len(streets) - 1):
                street1 = streets[i]
                street2 = streets[i + 1]
                
                start_int = f"int_{street1}_{ave_name.replace(' ', '_')}"
                end_int = f"int_{street2}_{ave_name.replace(' ', '_')}"
                
                if start_int in self.intersections and end_int in self.intersections:
                    lat1 = base_lat + (street1 - 34) * lat_per_block
                    lat2 = base_lat + (street2 - 34) * lat_per_block
                    
                    street = Street(
                        id=f"st_{street_id}",
                        name=f"{ave_name} ({street1} to {street2})",
                        start_intersection=start_int,
                        end_intersection=end_int,
                        start_coords=(lat1, ave_lon),
                        end_coords=(lat2, ave_lon),
                        direction=direction,
                        lanes=3 if ave_name in ['Park Ave', 'Lexington Ave'] else 2,
                        speed_limit=25.0
                    )
                    
                    self.streets[street.id] = street
                    
                    # Add to intersections
                    self.intersections[start_int].streets.append(street.id)
                    self.intersections[end_int].streets.append(street.id)
                    
                    # Add to graph
                    if direction in ['N', 'both']:
                        self.graph[start_int].append((end_int, street.id))
                    if direction in ['S', 'both']:
                        self.graph[end_int].append((start_int, street.id))
                    
                    street_id += 1
        
        print(f"Built Manhattan grid: {len(self.intersections)} intersections, {len(self.streets)} street segments")
    
    def find_nearest_intersection(self, lat: float, lon: float) -> str:
        """Find nearest intersection to coordinates"""
        min_dist = float('inf')
        nearest = None
        
        for int_id, intersection in self.intersections.items():
            dist = abs(lat - intersection.lat) + abs(lon - intersection.lon)
            if dist < min_dist:
                min_dist = dist
                nearest = int_id
        
        return nearest
    
    def find_path_intersections(self, start_intersection: str, end_intersection: str) -> List[str]:
        """Find path between two intersections, returning list of intersection IDs"""
        if start_intersection not in self.intersections or end_intersection not in self.intersections:
            return []
        
        return self._a_star(start_intersection, end_intersection)
    
    def find_path(self, start_lat: float, start_lon: float, 
                  end_lat: float, end_lon: float) -> List[Tuple[float, float]]:
        """Find realistic path following streets"""
        
        # Find nearest intersections
        start_int = self.find_nearest_intersection(start_lat, start_lon)
        end_int = self.find_nearest_intersection(end_lat, end_lon)
        
        if not start_int or not end_int:
            return [(start_lat, start_lon), (end_lat, end_lon)]  # Fallback
        
        # A* pathfinding
        path_intersections = self._a_star(start_int, end_int)
        
        if not path_intersections:
            return [(start_lat, start_lon), (end_lat, end_lon)]  # Fallback
        
        # Convert to coordinates
        path = []
        for int_id in path_intersections:
            intersection = self.intersections[int_id]
            path.append((intersection.lat, intersection.lon))
        
        return path
    
    def _a_star(self, start: str, goal: str) -> List[str]:
        """A* pathfinding on street network"""
        
        if start not in self.intersections or goal not in self.intersections:
            return []
        
        # Heuristic: Manhattan distance
        def h(node):
            n = self.intersections[node]
            g = self.intersections[goal]
            return abs(n.lat - g.lat) + abs(n.lon - g.lon)
        
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        f_score = {start: h(start)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == goal:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return list(reversed(path))
            
            for neighbor, street_id in self.graph[current]:
                tentative_g = g_score[current] + 1  # Simple cost
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + h(neighbor)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return []  # No path found
    
    def get_street_segments(self) -> List[Dict]:
        """Get all street segments for visualization"""
        segments = []
        
        for street in self.streets.values():
            segments.append({
                'id': street.id,
                'name': street.name,
                'coordinates': [
                    [street.start_coords[1], street.start_coords[0]],
                    [street.end_coords[1], street.end_coords[0]]
                ],
                'direction': street.direction,
                'lanes': street.lanes
            })
        
        return segments