"""
Download Manhattan street network for SUMO simulation
"""

import requests
import os
import subprocess

def download_manhattan_osm():
    """Download Manhattan street data from OpenStreetMap"""
    
    # Midtown Manhattan bounding box
    bbox = "-74.000,40.745,-73.965,40.770"
    
    url = f"https://overpass-api.de/api/map?bbox={bbox}"
    
    print("Downloading Manhattan street network...")
    response = requests.get(url)
    
    os.makedirs('data', exist_ok=True)
    with open('data/manhattan.osm', 'wb') as f:
        f.write(response.content)
    
    print("Downloaded manhattan.osm")
    
    # Convert to SUMO format if netconvert is available
    try:
        print("Converting to SUMO network format...")
        subprocess.run([
            "netconvert",
            "--osm-files", "data/manhattan.osm",
            "--output-file", "data/manhattan.net.xml",
            "--no-warnings",
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess-signals", "true",
            "--tls.discard-simple",
            "--tls.join"
        ], check=True)
        print("Created manhattan.net.xml")
    except:
        print("SUMO netconvert not found. Install SUMO to convert the network.")
        print("You can still use the OSM file with other tools.")

if __name__ == "__main__":
    download_manhattan_osm()