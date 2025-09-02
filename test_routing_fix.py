"""
Test the improved routing system
"""

from core.network_analyzer import ManhattanNetworkAnalyzer
import os

# Analyze the network
print("="*60)
print("TESTING MANHATTAN NETWORK ROUTING")
print("="*60)

analyzer = ManhattanNetworkAnalyzer('data/sumo/manhattan.net.xml')

# Test route finding
print("\nTesting route generation...")
successful_routes = 0
failed_routes = 0

for i in range(100):
    origin, dest = analyzer.get_valid_od_pair()
    route = analyzer.find_route(origin, dest)
    
    if route:
        successful_routes += 1
        if i < 3:  # Show first 3 routes
            print(f"  Route {i+1}: {len(route)} edges from {origin} to {dest}")
    else:
        failed_routes += 1

print(f"\nRoute success rate: {successful_routes}/100 ({successful_routes}%)")

# Save analysis for faster loading
analyzer.save_analysis()

print("\n✅ Network analysis complete!")