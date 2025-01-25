# GPX Street Extractor

GPX Street Extractor is a Python script for analyzing a GPX file (from Garmin or other devices) and determining which streets you walked or ran on. It uses reverse-geocoding (via [OpenStreetMap’s Nominatim service](https://nominatim.openstreetmap.org/)) and a “debouncing” system to avoid quickly flipping between streets at intersections.

## Features

- Debounce logic: Requires a certain number of consecutive points (configurable) on a new street before confirming you actually turned onto it.  
- Final partial confirm: Ensures short final segments aren’t missed.  
- Down-sampling: Only geocodes 1 out of every N points to avoid hitting usage limits.  
- Command-line flags: Customize thresholds, request delays, debug output, etc.

## Installation

1. Install [Python 3](https://www.python.org/downloads/) if you don’t already have it.  
2. Download or clone this repository (so you have `gpx_street_extractor.py`).  
3. Install required packages:

    pip install gpxpy requests

   (If using Python 3 specifically, you might do `pip3 install gpxpy requests` instead.)

## Usage

Run the script from a terminal or command prompt:

    python gpx_street_extractor.py <path_to_gpx_file> [options]

Example:

    python gpx_street_extractor.py activity.gpx \
        --downsample 5 \
        --request-delay 0.5 \
        --threshold 3 \
        --final-threshold 2 \
        --debug

### Command-Line Arguments

| Argument            | Default | Description                                                                                                                |
|---------------------|---------|----------------------------------------------------------------------------------------------------------------------------|
| `gpx_file`          | _N/A_   | Path to your GPX file (required).                                                                                         |
| `--downsample`      | `5`     | Only geocode 1 out of every N points (reduces requests/time).                                                              |
| `--request-delay`   | `0.5`   | Delay in seconds between each request to avoid being blocked by Nominatim.                                                 |
| `--threshold`       | `3`     | Number of consecutive geocode hits on a new street required to confirm you turned onto it.                                 |
| `--final-threshold` | `2`     | If you end with fewer consecutive hits than `--threshold` but at least this many, confirm the last street anyway.           |
| `--debug`           | _off_   | Prints verbose debug info: GPX structure, each geocoded point, etc.                                                       |

### Example Workflows

1. **Basic (default settings)**

        python gpx_street_extractor.py my_activity.gpx

2. **Fine-grained (less down-sampling, slightly higher delay)**

        python gpx_street_extractor.py my_activity.gpx \
            --downsample 2 \
            --request-delay 1 \
            --threshold 3 \
            --final-threshold 2

   This will geocode 1 out of every 2 points and pause 1 second between requests.

3. **Debugging**

        python gpx_street_extractor.py my_activity.gpx --debug

   You’ll see lines like:

        DEBUG: i=10, lat=35.123456, lon=-79.987654, street=Main Street

## Notes on Nominatim Usage

- **User-Agent**: The script sets a default User-Agent string in `get_street_name` (required by [Nominatim’s usage policy](https://operations.osmfoundation.org/policies/nominatim/)). You can edit it to include your own contact info.  
- **Rate-Limiting**: If you get `403` errors, try increasing `--request-delay` or down-sampling more aggressively.

## Contributing

- Issues/Requests: Feel free to open an issue or pull request on GitHub.  

## Author

[dbmathis / GitHub handle](https://github.com/dbmathis)
