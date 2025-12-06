import gpxpy
import json
import glob
import os
import argparse
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def load_styles(pattern):
    """Load JSON style files."""
    style_files = glob.glob(pattern)
    styles = {}
    
    for style_file in sorted(style_files):
        try:
            with open(style_file, 'r') as f:
                name = os.path.splitext(os.path.basename(style_file))[0]
                styles[name] = json.load(f)
                print(f"Loaded style: {name}")
        except Exception as e:
            print(f"Skipping {style_file}: {e}")
    
    return styles

def parse_gpx(filename):
    """Parse GPX and return coords + stats."""
    try:
        with open(filename, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        
        # Simplify the track to reduce HTML size (preserve topology)
        # This is CRITICAL for long runs
        for track in gpx.tracks:
            track.simplify(max_distance=10) # Max error 10 meters

        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({'lat': point.latitude, 'lng': point.longitude})
        
        # Calculate stats
        total_dist = round(gpx.length_2d() / 1000, 2)
        start_time = gpx.get_time_bounds().start_time
        date_str = start_time.strftime("%Y-%m-%d %H:%M") if start_time else "N/A"

        return points, total_dist, date_str
    except Exception as e:
        print(f"Error parsing GPX: {e}")
        return [], 0, ""

def load_all_gpx_files(routes_dir):
    """Load all GPX files from routes directory."""
    gpx_files = glob.glob(os.path.join(routes_dir, '*.gpx'))
    routes = {}
    
    for gpx_file in sorted(gpx_files):
        try:
            coords, distance, date = parse_gpx(gpx_file)
            if coords:
                filename = os.path.basename(gpx_file)
                routes[filename] = {
                    'coords': coords,
                    'distance': distance,
                    'date': date
                }
                print(f"Loaded route: {filename}")
        except Exception as e:
            print(f"Skipping {gpx_file}: {e}")
    
    return routes

def generate_map(gpx_path, output_path, style_pattern, template_file, routes_dir='routes'):
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        raise ValueError("Missing GOOGLE_MAPS_API_KEY in .env")

    # 1. Get Data for primary GPX file
    print("Processing primary GPX...")
    coords, distance, date = parse_gpx(gpx_path)
    if not coords:
        return

    # 2. Load all GPX files for selector
    print("Loading all routes...")
    all_routes = load_all_gpx_files(routes_dir)
    
    # Add primary route if not already in all_routes
    primary_filename = os.path.basename(gpx_path)
    if primary_filename not in all_routes:
        all_routes[primary_filename] = {
            'coords': coords,
            'distance': distance,
            'date': date
        }

    # 3. Get Styles
    print("Loading Styles...")
    styles = load_styles(style_pattern)
    default_style = list(styles.keys())[0] if styles else 'default'

    # 4. Setup Jinja2 Environment
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(template_file)

    # 5. Render HTML
    print("Rendering HTML...")
    html_output = template.render(
        api_key=api_key,
        route_coords=coords,
        all_styles=styles,
        style_names=list(styles.keys()),
        default_style=default_style,
        total_distance_km=distance,
        start_time=date,
        all_routes=all_routes,
        default_route=primary_filename
    )

    # 6. Save
    with open(output_path, 'w') as f:
        f.write(html_output)
    print(f"Done! Map saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Marathon Map")
    parser.add_argument('gpx_file', nargs='?', help="Path to input GPX file (optional, defaults to first file in routes folder)")
    parser.add_argument('--output', default='marathon_map.html', help="Output HTML file")
    parser.add_argument('--routes-dir', default='routes', help="Directory containing GPX files (default: routes)")
    
    args = parser.parse_args()
    
    # If no GPX file provided, find one from routes directory
    if not args.gpx_file:
        routes_dir = args.routes_dir
        gpx_files = glob.glob(os.path.join(routes_dir, '*.gpx'))
        
        if not gpx_files:
            print(f"Error: No GPX files found in '{routes_dir}' directory.")
            print("Please provide a GPX file as an argument or add GPX files to the routes folder.")
            exit(1)
        
        # Use the first (alphabetically sorted) GPX file as default
        args.gpx_file = sorted(gpx_files)[0]
        print(f"No GPX file specified. Using default: {args.gpx_file}")
    
    generate_map(
        gpx_path=args.gpx_file,
        output_path=args.output,
        style_pattern='styles/*.json',
        template_file='template.html',
        routes_dir=args.routes_dir
    )