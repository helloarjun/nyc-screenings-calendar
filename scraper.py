import requests
import json
from ics import Calendar, Event
from datetime import datetime

# Define the API endpoint and parameters
API_URL = "https://example.com/path-to-endpoint"  # Replace with the actual API URL
PARAMS = {
    "date": "20250118",  # Replace with dynamic date generation if needed
    "_format": "json",
    "field_city_target_id": "10969",  # Adjust based on requirements
}

def fetch_screenings():
    """Fetch screenings data from the API."""
    try:
        response = requests.get(API_URL, params=PARAMS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

def generate_calendar(screenings):
    """Generate an ICS calendar from screenings data."""
    calendar = Calendar()

    for screening in screenings:
        title = screening.get("title", "Untitled Screening")
        venue = screening.get("venue_title", "Unknown Location")
        start_time = screening.get("date")  # Assuming API returns ISO 8601 date
        description = screening.get("media_title_info", "").strip()

        if not start_time:
            print(f"Skipping screening '{title}' due to missing start time.")
            continue

        # Create event
        event = Event()
        event.name = title
        event.begin = start_time
        event.location = venue
        event.description = description

        calendar.events.add(event)

    return calendar

def save_calendar(calendar, filename="nyc_indie_cinema.ics"):
    """Save the ICS calendar to a file."""
    with open(filename, "w") as f:
        f.writelines(calendar)

def main():
    print("Fetching screenings...")
    screenings = fetch_screenings()

    if not screenings:
        print("No screenings found.")
        return

    print(f"Fetched {len(screenings)} screenings. Generating calendar...")
    calendar = generate_calendar(screenings)

    print("Saving calendar...")
    save_calendar(calendar)
    print(f"Calendar saved as 'nyc_indie_cinema.ics'.")

if __name__ == "__main__":
    main()
