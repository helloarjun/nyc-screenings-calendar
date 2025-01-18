import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
from typing import Dict, List
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.screenslate.com"

class ScreenSlateAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        })

    def fetch_screenings_by_date(self, date: str) -> List[Dict]:
        """Fetch screenings for a specific date."""
        url = f"{BASE_URL}/api/screenings/date"
        params = {"_format": "json", "date": date, "field_city_target_id": "10969"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def fetch_screening_details(self, screening_ids: List[str]) -> Dict:
        """Fetch movie details for a list of screening IDs."""
        if not screening_ids:
            return {}

        logger.info(f"Fetching details for {len(screening_ids)} screenings")
        batch_size = 20
        all_results = {}

        for i in range(0, len(screening_ids), batch_size):
            batch = screening_ids[i:i + batch_size]
            ids_param = '+'.join(str(id) for id in batch)
            url = f"{BASE_URL}/api/screenings/id/{ids_param}"
            params = {"_format": "json"}

            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                batch_data = response.json()
                if isinstance(batch_data, dict):
                    all_results.update(batch_data)
                else:
                    logger.error("Unexpected response format")
            except Exception as e:
                logger.error(f"Error fetching batch: {str(e)}")
                continue

        return all_results

def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening information."""
    event = Event()

    # Set timezone to NYC
    nyc_tz = pytz.timezone('America/New_York')

    # Create event title
    title = screening['title']
    if screening.get('year'):
        title += f" ({screening['year']})"

    # Create description
    description_parts = []
    if screening.get('director'):
        description_parts.append(f"Director: {screening['director']}")
    if screening.get('runtime'):
        description_parts.append(f"Runtime: {screening['runtime']} minutes")
    if screening.get('series'):
        description_parts.append(f"Series: {screening['series']}")
    if screening.get('url'):
        description_parts.append(f"More info: {screening['url']}")

    # Add event details
    event.add('summary', f"{title} at {screening['venue']}")
    event.add('description', '\n'.join(description_parts))

    # Set start time
    start_time = screening['datetime']
    if not start_time.tzinfo:
        start_time = nyc_tz.localize(start_time)
    event.add('dtstart', start_time)

    # Set duration (default 2 hours if not specified)
    duration_minutes = int(screening.get('runtime', 120))
    event.add('duration', timedelta(minutes=duration_minutes))

    # Set location and URL
    event.add('location', screening['venue'])
    if screening.get('url'):
        event.add('url', screening['url'])

    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    """Generate ICS calendar file for the next 7 days"""
    logger.info("Starting calendar generation")

    # Create calendar object
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'NYC Independent Cinema')
    cal.add('x-wr-timezone', 'America/New_York')

    # Get date range
    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime('%Y%m%d') for i in range(7)]

    # Fetch all screenings
    all_screenings = []
    for date in dates:
        logger.info(f"Fetching screenings for {date}...")
        screenings = api_client.fetch_screenings_by_date(date)

        # Extract screening IDs
        screening_ids = [screening['nid'] for screening in screenings]
        details = api_client.fetch_screening_details(screening_ids)

        for screening in screenings:
            movie_id = screening['nid']
            if movie_id not in details:
                continue

            movie = details[movie_id]

            # Parse start time
            start_time_str = screening['field_timestamp']
            start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")

            # Create a structured screening dictionary
            screening_event = {
                'title': movie.get('title', 'Untitled'),
                'director': movie.get('field_director', ''),
                'year': movie.get('field_year', ''),
                'runtime': movie.get('field_runtime', ''),
                'series': movie.get('field_series', ''),
                'venue': movie.get('venue_title', 'Unknown Venue'),
                'datetime': start_time,
                'url': movie.get('field_url', '')
            }

            all_screenings.append(screening_event)

    if not all_screenings:
        logger.error("No screenings found!")
        return

    # Create events
    for screening in all_screenings:
        try:
            event = create_calendar_event(screening)
            cal.add_component(event)
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save calendar file
    calendar_path = os.path.join(output_dir, 'nyc-screenings.ics')
    with open(calendar_path, 'wb') as f:
        f.write(cal.to_ical())
    logger.info(f"Calendar saved with {len(all_screenings)} events")

def main():
    """Main entry point"""
    api = ScreenSlateAPI()
    generate_calendar(api)

if __name__ == "__main__":
    main()
