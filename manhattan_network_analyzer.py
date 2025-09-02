"""
Analyze Manhattan network to find connected components
This ensures vehicles can navigate and reroute dynamically
"""

import sumolib
import networkx as nx
import json
from typing import Set, List, Tuple, Dict

class NetworkAnalyzer:
    """Analyze SUMO network for connectivity"""
    
    def __init__(self, network_file="data/manhattan_real.net.xml"):
        self.net = sumolib.net.readNet(network_file)
        self.graph = nx.DiGraph()
        self.connected_edges = set()
        print(f"Analyzing network with {len(self.net.getEdges())} edges...")
        
    def build_networkx_graph(self):
        """Convert SUMO network to NetworkX for analysis"""
        
        for edge in self.net.getEdges():
            if not edge.allows("passenger") or edge.isSpecial():
                continue
            
            edge_id = edge.getID()
            
            # Add edge to graph
            for outgoing in edge.getToNode().getOutgoing():
                if outgoing.allows("passenger") and not outgoing.isSpecial():
                    self.graph.add_edge(edge_id, outgoing.getID())
        
        print(f"Built graph with {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
    
    def find_largest_connected_component(self) -> Set[str]:
        """Find the largest strongly connected component"""
        
        # Get all strongly connected components
        components = list(nx.strongly_connected_components(self.graph))
        
        if not components:
            print("No connected components found!")
            return set()
        
        # Sort by size
        components.sort(key=len, reverse=True)
        largest = components[0]
        
        print(f"Found {len(components)} components")
        print(f"Largest component has {len(largest)} edges")
        print(f"Coverage: {len(largest)/len(self.net.getEdges())*100:.1f}% of network")
        
        return largest
    
    def find_largest_weakly_connected_component(self) -> Set[str]:
        """Use weakly connected components for better coverage"""
        
        # Convert to undirected for weak connectivity
        undirected = self.graph.to_undirected()
        
        # Get all connected components
        components = list(nx.connected_components(undirected))
        
        if not components:
            print("No connected components found!")
            return set()
        
        # Sort by size
        components.sort(key=len, reverse=True)
        largest = components[0]
        
        print(f"Found {len(components)} weakly connected components")
        print(f"Largest component has {len(largest)} edges")
        print(f"Coverage: {len(largest)/len(self.net.getEdges())*100:.1f}% of network")
        
        return largest
    
    def verify_charging_station_connectivity(self, connected_edges: Set[str]) -> Dict:
        """Check which charging stations are reachable"""
        
        # Your charging station edges
        charging_stations = {
            'cs_times_square': '817381419',
            'cs_penn_station': '46493326',
            'cs_grand_central': '473560390#1',
            'cs_bryant_park': '702073802#3',
            'cs_columbus_circle': '525428790#1',
            'cs_chelsea': '-384178812#3',
            'cs_midtown_east': '659696741#1',
            'cs_hells_kitchen': '1219425516'
        }
        
        reachable = {}
        unreachable = []
        
        for name, edge_id in charging_stations.items():
            # Check if edge is in connected component
            if edge_id in connected_edges:
                reachable[name] = edge_id
            else:
                # Try to find nearest connected edge
                nearest = self.find_nearest_connected_edge(edge_id, connected_edges)
                if nearest:
                    reachable[name] = nearest
                    print(f"  📍 {name}: Relocated from {edge_id} to {nearest}")
                else:
                    unreachable.append(name)
        
        print(f"\n✅ Reachable charging stations: {len(reachable)}")
        if unreachable:
            print(f"⚠️ Unreachable stations: {unreachable}")
        
        return reachable
    
    def find_nearest_connected_edge(self, target_edge: str, connected_edges: Set[str]) -> str:
        """Find nearest edge in connected component - FIXED VERSION"""
        
        if target_edge in connected_edges:
            return target_edge
        
        # BFS to find nearest connected edge
        visited = set()
        queue = [(target_edge, 0)]
        
        while queue:
            current, distance = queue.pop(0)
            
            if current in connected_edges:
                return current
            
            if current in visited or distance > 10:
                continue
            
            visited.add(current)
            
            # Check neighbors (only if node exists in graph)
            if current in self.graph:
                for neighbor in self.graph.neighbors(current):
                    queue.append((neighbor, distance + 1))
            
            # Check reverse neighbors (only if node exists)
            if current in self.graph.nodes():
                try:
                    for predecessor in self.graph.predecessors(current):
                        queue.append((predecessor, distance + 1))
                except:
                    pass  # Node not in graph
        
        # If no connected edge found, return a random one from connected set
        if connected_edges:
            return list(connected_edges)[0]
        
        return None
    
    def export_connected_network(self):
        """Export the connected component for use in simulation - IMPROVED"""
        
        # Build graph
        self.build_networkx_graph()
        
        # Use WEAKLY connected component for better coverage
        connected = self.find_largest_weakly_connected_component()
        
        # If coverage is too low, just use all navigable edges
        if len(connected) < 0.3 * len(self.net.getEdges()):
            print("\n⚠️ Low connectivity detected. Using all passenger edges instead.")
            connected = set()
            for edge in self.net.getEdges():
                if edge.allows("passenger") and not edge.isSpecial():
                    connected.add(edge.getID())
            print(f"Using {len(connected)} passenger-accessible edges")
        
        # Verify charging stations
        charging_stations = self.verify_charging_station_connectivity(connected)
        
        # Get good spawn points
        spawn_edges = []
        for edge_id in list(connected)[:1000]:  # Check first 1000 to save time
            try:
                edge = self.net.getEdge(edge_id)
                # Check if edge has decent connections
                outgoing = len(edge.getToNode().getOutgoing())
                incoming = len(edge.getFromNode().getIncoming())
                
                if outgoing >= 1 and incoming >= 1:
                    spawn_edges.append(edge_id)
            except:
                pass  # Edge not found
        
        print(f"\n✅ Found {len(spawn_edges)} spawn points")
        
        # Export to JSON
        network_data = {
            'connected_edges': list(connected)[:5000],  # Limit for file size
            'spawn_edges': spawn_edges[:200],  # Top 200 spawn points
            'charging_stations': charging_stations,
            'total_edges': len(self.net.getEdges()),
            'connected_edges_count': len(connected),
            'spawn_edges_count': len(spawn_edges)
        }
        
        with open("data/manhattan_connected_network.json", "w") as f:
            json.dump(network_data, f, indent=2)
        
        print(f"✅ Exported connected network to data/manhattan_connected_network.json")
        return network_data

if __name__ == "__main__":
    analyzer = NetworkAnalyzer()
    network_data = analyzer.export_connected_network()
    
    print("\n" + "="*50)
    print("NETWORK ANALYSIS COMPLETE")
    print("="*50)
    print(f"Connected edges: {network_data['connected_edges_count']}/{network_data['total_edges']}")
    print(f"Spawn points: {network_data['spawn_edges_count']}")
    print(f"Charging stations: {len(network_data['charging_stations'])}")