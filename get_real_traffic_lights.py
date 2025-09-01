"""
Get REAL traffic lights from OpenStreetMap
This actually works without special permissions
"""

import requests
import json
import os

def get_manhattan_traffic_lights():
    """Download traffic signals from OpenStreetMap using Overpass API"""
    
    # Overpass API query for traffic signals in Midtown Manhattan
    query = """
    [out:json][timeout:25];
    (
      node["highway"="traffic_signals"]
        (40.745,-74.000,40.770,-73.965);
    );
    out body;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    
    print("Downloading traffic signals from OpenStreetMap...")
    response = requests.post(url, data={'data': query})
    
    if response.status_code == 200:
        data = response.json()
        
        signals = []
        for element in data['elements']:
            if 'lat' in element and 'lon' in element:
                signals.append({
                    'id': element['id'],
                    'lat': element['lat'],
                    'lon': element['lon'],
                    'tags': element.get('tags', {})
                })
        
        # Save to file
        os.makedirs('data', exist_ok=True)
        with open('data/manhattan_traffic_lights.json', 'w') as f:
            json.dump(signals, f, indent=2)
        
        print(f"Downloaded {len(signals)} real traffic signals")
        return signals
    else:
        print(f"Error: {response.status_code}")
        return []

def get_manhattan_intersections():
    """Get all intersections (for traffic lights that might not be tagged)"""
    
    query = """
    [out:json][timeout:25];
    way["highway"~"primary|secondary|tertiary|residential"]
      (40.745,-74.000,40.770,-73.965);
    node(w);
    out;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    response = requests.post(url, data={'data': query})
    
    if response.status_code == 200:
        data = response.json()
        
        # Find nodes that appear multiple times (intersections)
        node_count = {}
        for element in data['elements']:
            if element['type'] == 'node':
                node_id = element['id']
                if node_id not in node_count:
                    node_count[node_id] = {
                        'count': 0,
                        'lat': element['lat'],
                        'lon': element['lon']
                    }
                node_count[node_id]['count'] += 1
        
        # Intersections are nodes with count > 2
        intersections = []
        for node_id, info in node_count.items():
            if info['count'] > 2:
                intersections.append({
                    'id': f"intersection_{node_id}",
                    'lat': info['lat'],
                    'lon': info['lon'],
                    'type': 'intersection'
                })
        
        print(f"Found {len(intersections)} intersections")
        return intersections
    
    return []

if __name__ == "__main__":
    # Get traffic signals
    signals = get_manhattan_traffic_lights()
    
    # If not enough signals, use intersections
    if len(signals) < 50:
        print("Not enough tagged signals, using intersections...")
        intersections = get_manhattan_intersections()
        signals.extend(intersections)
        
        with open('data/manhattan_traffic_lights.json', 'w') as f:
            json.dump(signals, f, indent=2)
        
        print(f"Total traffic control points: {len(signals)}")