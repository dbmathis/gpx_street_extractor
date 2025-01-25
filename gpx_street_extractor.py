import sys
import gpxpy
import requests
import time
import argparse
from datetime import datetime

def format_time_delta(seconds: float) -> str:
    """
    Convert float seconds into [MM:SS] format.
    """
    mm = int(seconds // 60)
    ss = int(seconds % 60)
    return f"{mm:02d}:{ss:02d}"

def debug_print(debug_mode, *args):
    """
    Only print if debug_mode is True.
    """
    if debug_mode:
        print("DEBUG:", *args)

def debug_gpx_contents(gpx, debug_mode):
    """
    If debug_mode is True, print how many tracks, segments, and points are found,
    plus counts of routes and waypoints.
    """
    if not debug_mode:
        return
    print("DEBUG: Number of tracks =", len(gpx.tracks))
    for t_index, track in enumerate(gpx.tracks):
        print(f"DEBUG:   Track {t_index} has {len(track.segments)} segment(s).")
        for s_index, segment in enumerate(track.segments):
            print(f"DEBUG:     Segment {s_index} has {len(segment.points)} point(s).")

    print("DEBUG: Number of routes =", len(gpx.routes))
    for r_index, route in enumerate(gpx.routes):
        print(f"DEBUG:   Route {r_index} has {len(route.points)} point(s).")

    print("DEBUG: Number of waypoints =", len(gpx.waypoints))

def get_street_name(lat: float, lon: float, debug_mode: bool) -> str:
    """
    Reverse-geocodes latitude/longitude using the public Nominatim API.
    Returns the street name (if found) or None.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=jsonv2"

    # REQUIRED: Provide a descriptive User-Agent per Nominatim usage policy
    headers = {
        "User-Agent": "MyStreetExtractor/1.0 (myemail@example.com)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            # Usually "road"; fallback to "footway"/"pedestrian"
            street_name = address.get("road") or address.get("footway") or address.get("pedestrian")
            return street_name
        else:
            if debug_mode:
                print(f"WARNING: Nominatim returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        if debug_mode:
            print(f"WARNING: Nominatim request failed: {e}")

    return None

def collect_points(gpx) -> list:
    """
    Collect all points from the GPX in a single list of (lat, lon, time).
    Priority:
      1) Tracks (trkpt)
      2) Routes (rtept)
      3) Waypoints (wpt)

    Once we find track points, we skip routes/waypoints.
    """
    points = []

    # 1) Tracks
    if gpx.tracks:
        for track in gpx.tracks:
            for segment in track.segments:
                for pt in segment.points:
                    points.append((pt.latitude, pt.longitude, pt.time))
        if points:
            return points

    # 2) Routes
    if gpx.routes:
        for route in gpx.routes:
            for pt in route.points:
                points.append((pt.latitude, pt.longitude, pt.time))
        if points:
            return points

    # 3) Waypoints
    if gpx.waypoints:
        for wpt in gpx.waypoints:
            points.append((wpt.latitude, wpt.longitude, wpt.time))

    return points

def process_points(points: list,
                   downsample: int,
                   request_delay: float,
                   threshold: int,
                   final_threshold: int,
                   debug_mode: bool):
    """
    Loops over points (down-sampled), does a reverse-geocode,
    and prints [MM:SS StreetName] for the street we are truly on.

    - We store each "candidate" street's consecutive hits in a list of times.
      Once we reach `threshold` hits, we confirm the new street.
      The printed offset is from the *first* time we saw that candidate street.
    - If we end with a candidate having >= `final_threshold` hits (but < threshold),
      we confirm it anyway so we don't miss a short final segment.

    If debug_mode is True, also print each processed coordinate and returned street.
    """

    if not points:
        print("No track, route, or waypoint data found in this GPX.")
        return

    # Find first non-None time to serve as the "start"
    start_time = None
    for _, _, t in points:
        if t is not None:
            start_time = t
            break

    confirmed_street = None  # Street we have fully confirmed
    candidate_street = None  # Street we are considering (not yet confirmed)
    candidate_times = []     # List of time offsets for consecutive hits on candidate_street

    for i, (lat, lon, point_time) in enumerate(points):
        if i % downsample != 0:
            continue

        # Polite delay to avoid Nominatim blocking
        time.sleep(request_delay)

        # Compute time offset for this point
        if start_time and point_time:
            time_diff = (point_time - start_time).total_seconds()
        else:
            time_diff = 0.0

        # Reverse-geocode the current lat/lon
        street = get_street_name(lat, lon, debug_mode)

        # Print debug info about each processed point
        debug_print(debug_mode, f"i={i}, lat={lat:.6f}, lon={lon:.6f}, street={street}")

        if not street:
            # If we fail to get a street, skip it
            continue

        if street == confirmed_street:
            # We're still on the confirmed street, so reset candidate
            candidate_street = None
            candidate_times = []
            continue

        # If it's the same as our current candidate, keep counting
        if street == candidate_street:
            candidate_times.append(time_diff)

            # If we meet the threshold, confirm the new street
            if len(candidate_times) >= threshold:
                # Confirm at the time offset of the *first* candidate hit
                confirm_offset = candidate_times[0]
                confirmed_street = candidate_street
                print(f"{format_time_delta(confirm_offset)} {confirmed_street}")
        else:
            # It's a different street than our candidate => new candidate
            candidate_street = street
            candidate_times = [time_diff]

    # After the loop ends, if we still have a candidate but never reached `threshold`,
    # check if we meet the final_threshold to confirm it anyway.
    if candidate_street and candidate_street != confirmed_street:
        if len(candidate_times) >= final_threshold:
            confirm_offset = candidate_times[0]
            print(f"{format_time_delta(confirm_offset)} {candidate_street}")

def main():
    # -----------------------
    # 1. Parse Command-Line
    # -----------------------
    parser = argparse.ArgumentParser(description="Extract streets from a GPX file with debouncing.")
    parser.add_argument("gpx_file", help="Path to the GPX file.")
    parser.add_argument("--downsample", type=int, default=5,
                        help="Only geocode 1 out of every N points (default 5).")
    parser.add_argument("--request-delay", type=float, default=0.5,
                        help="Delay in seconds between requests to avoid throttling (default 0.5).")
    parser.add_argument("--threshold", type=int, default=3,
                        help="Number of consecutive hits required to confirm a new street (default 3).")
    parser.add_argument("--final-threshold", type=int, default=2,
                        help="If we end the track with fewer than 'threshold' hits, but at least this many, we confirm the last street (default 2).")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode (prints geocode results for each point).")

    args = parser.parse_args()

    # -----------------------
    # 2. Parse the GPX file
    # -----------------------
    with open(args.gpx_file, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    # -----------------------
    # 3. Debug info if needed
    # -----------------------
    debug_gpx_contents(gpx, args.debug)

    # -----------------------
    # 4. Collect all points
    # -----------------------
    points = collect_points(gpx)
    if not points:
        print("No track/route/waypoint data found in this GPX.")
        return

    # -----------------------
    # 5. Process points
    # -----------------------
    process_points(
        points=points,
        downsample=args.downsample,
        request_delay=args.request_delay,
        threshold=args.threshold,
        final_threshold=args.final_threshold,
        debug_mode=args.debug
    )

if __name__ == "__main__":
    main()
