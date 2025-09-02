"""
Distribute charging stations across Manhattan properly
"""

import json
import random

def fix_charging_station_distribution():
    """Redistribute charging stations to different edges"""
    
    # Load the network data
    with open("data/manhattan_connected_network.json", "r") as f:
        data = json.load(f)
    
    # Get spawn edges (these are well-connected)
    spawn_edges = data['spawn_edges']
    
    if len(spawn_edges) < 8:
        print("Not enough spawn edges!")
        return
    
    # Distribute charging stations across different areas
    # Pick edges that are spread out (every N edges)
    spacing = len(spawn_edges) // 8
    
    new_stations = {
        'cs_times_square': spawn_edges[0],
        'cs_penn_station': spawn_edges[spacing],
        'cs_grand_central': spawn_edges[spacing * 2],
        'cs_bryant_park': spawn_edges[spacing * 3],
        'cs_columbus_circle': spawn_edges[spacing * 4],
        'cs_chelsea': spawn_edges[spacing * 5],
        'cs_midtown_east': spawn_edges[spacing * 6],
        'cs_hells_kitchen': spawn_edges[spacing * 7]
    }
    
    # Update the data
    data['charging_stations'] = new_stations
    
    # Save back
    with open("data/manhattan_connected_network.json", "w") as f:
        json.dump(data, f, indent=2)
    
    print("✅ Redistributed charging stations:")
    for name, edge in new_stations.items():
        print(f"   📍 {name}: {edge}")

if __name__ == "__main__":
    fix_charging_station_distribution()