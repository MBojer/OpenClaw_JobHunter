"""
scripts/commute/test_commute.py
Quick end-to-end test for commute scoring.
Usage: python3 scripts/commute/test_commute.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.commute.ors_client import get_coordinates, get_commute_minutes, is_available, ORSError

ORIGIN = "Copenhagen, Denmark"
DESTINATION = "Roskilde, Denmark"  # ~35km west of Copenhagen

print("=== Commute scoring test ===\n")

print("1. ORS health check...")
if not is_available():
    print("   FAIL — ORS is not reachable. Check ORS_BASE_URL in .env")
    sys.exit(1)
print("   OK\n")

print(f"2. Geocoding origin: {ORIGIN}")
try:
    origin_coords = get_coordinates(ORIGIN)
    if not origin_coords:
        print("   FAIL — no result from Nominatim")
        sys.exit(1)
    print(f"   OK — {origin_coords}\n")
except ORSError as e:
    print(f"   FAIL — {e}")
    sys.exit(1)

print(f"3. Geocoding destination: {DESTINATION}")
try:
    dest_coords = get_coordinates(DESTINATION)
    if not dest_coords:
        print("   FAIL — no result from Nominatim")
        sys.exit(1)
    print(f"   OK — {dest_coords}\n")
except ORSError as e:
    print(f"   FAIL — {e}")
    sys.exit(1)

print(f"4. Routing {ORIGIN} → {DESTINATION} (driving-car)...")
try:
    minutes = get_commute_minutes(origin_coords, DESTINATION, "driving-car")
    if minutes is None:
        print("   FAIL — route returned None.")
        print("   If you see ORS error 2010 (no routable point), the ORS graph may not")
        print("   cover Denmark. Check which OSM extract is loaded on your ORS server.")
        sys.exit(1)
    print(f"   OK — {minutes} min\n")
except ORSError as e:
    print(f"   FAIL — {e}")
    if "2010" in str(e):
        print("   ORS error 2010 = no routable point. Check ORS map data covers Denmark.")
    sys.exit(1)

print("All checks passed.")
