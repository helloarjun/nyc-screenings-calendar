import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
from typing import Dict, List
import re

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
        url = f"{BASE_URL}/api/screenings/date"
        params = {"_format": "json", "date": date, "field_city_target_id": "10969"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, list):
                logger.error("Unexpected response format for screenings by date")
                return []
            return data
        except Exception as e:
            logger.error(f"Failed to parse screenings by date: {e}")
            return []

    def fetch_screening_details(self, screening_ids: List[str]) -> Dict:
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
                    logger.error("Unexpected response format for screening details")
            except Exception as e:
                logger.error(f"Error fetching batch: {str(e)}")
                continue

        return all_results

def create_calendar_event(screening: Dict) -> Event:
    event = Event()
    nyc_tz = pytz.timezone('America/New_York')
    title = screening['title']
    if screening.get('year'):
        title += f" ({screening['year']})"

    description_parts = []
    if screening.get('director'):
        description_parts.append(f"Director: {screening['director']}")
    if screening.get('runtime'):
        description_parts.append(f"Runtime: {screening['runtime']} minutes")
    if screening.get('series'):
        description_parts.append(f"Series: {screening['series']}")
    if screening.get('url'):
        description_parts.append(f"More info: {screening['url']}")

    event.add('summary', f"{title} at {screening['venue']}")
    event.add('description', '\n'.join(description_parts))

    start_time = screening['datetime']
    if not start_time.tzinfo:
        start_time = nyc_tz.localize(start_time)
    event.add('dtstart', start_time)

    duration_minutes = int(screening.get('runtime', 120))
    event.add('duration', timedelta(minutes=duration_minutes))

    event.add('location', screening['venue'])
    if screening.get('url'):
        event.add('url', screening['url'])

    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    logger.info("Starting calendar generation")
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'NYC Independent Cinema')
    cal.add('x-wr-timezone', 'America/New_York')

    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime('%Y%m%d') for i in range(7)]

    all_screenings = []
    for date in dates:
        logger.info(f"Fetching screenings for {date}...")
        screenings = api_client.fetch_screenings_by_date(date)
        screening_ids = [screening['nid'] for screening in screenings]
        details = api_client.fetch_screening_details(screening_ids)

        for screening in screenings:
            movie_id = screening['nid']
            if movie_id not in details:
                continue

            movie = details[movie_id]
            try:
                start_time_str = screening['field_timestamp']
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")

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
            except Exception as e:
                logger.error(f"Error processing screening {movie_id}: {e}")

    if not all_screenings:
        logger.error("No screenings found!")
        return

    for screening in all_screenings:
        try:
            event = create_calendar_event(screening)
            cal.add_component(event)
        except Exception as e:
            logger.error(f"Error creating event: {e}")

    os.makedirs(output_dir, exist_ok=True)
    calendar_path = os.path.join(output_dir, 'nyc-screenings.ics')
    with open(calendar_path, 'wb') as f:
        f.write(cal.to_ical())
    logger.info(f"Calendar saved with {len(all_screenings)} events")

def main():
    api = ScreenSlateAPI()
    generate_calendar(api)

if __name__ == "__main__":
    main()
