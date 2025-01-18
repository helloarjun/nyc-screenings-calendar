import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
import re
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs if needed
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
            ids_param = '+'.join(str(id) for id in batch)  # Plus-separated IDs
            url = f"{BASE_URL}/api/screenings/id/{ids_param}"
            params = {"_format": "json"}

            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                batch_data = response.json()

                if isinstance(batch_data, dict):
                    all_results.update(batch_data)
                elif isinstance(batch_data, list):
                    for item in batch_data:
                        nid = item.get('nid')
                        if nid:
                            all_results[str(nid)] = item
                else:
                    logger.error(
                        f"Unexpected response format for screening details: {type(batch_data)}. "
                        f"Raw response: {response.text[:200]}"
                    )
            except Exception as e:
                logger.error(f"Error fetching batch for IDs {ids_param}: {str(e)}")
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

    # Safely convert runtime to an integer, defaulting to 120 minutes if not found
    runtime_value = screening.get('runtime')
    try:
        duration_minutes = int(runtime_value) if runtime_value and runtime_value.isdigit() else 120
    except ValueError:
        duration_minutes = 120
    event.add('duration', timedelta(minutes=duration_minutes))

    event.add('location', screening['venue'])
    if screening.get('url'):
        event.add('url', screening['url'])

    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    logger.info("Starting calendar generation")
    
    group1_venues = ["Metrograph", "AFA"]
    group2_venues = ["Film Forum", "IFC Center"]

    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime('%Y%m%d') for i in range(7)]

    all_screenings = []
    for date in dates:
        logger.info(f"Fetching screenings for {date}...")
        screenings = api_client.fetch_screenings_by_date(date)
        screening_ids = [screening['nid'] for screening in screenings if 'nid' in screening]
        details = api_client.fetch_screening_details(screening_ids)

        for screening in screenings:
            movie_id = screening['nid']
            movie_data = details.get(str(movie_id))
            if not movie_data:
                continue

            try:
                start_time_str = screening['field_timestamp']
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")

                runtime = movie_data.get('field_runtime', '')
                if not runtime:
                    media_info = movie_data.get('media_title_info', '')
                    match = re.search(r'(\d+)M', media_info)
                    if match:
                        runtime = match.group(1)

                screening_event = {
                    'title': movie_data.get('title', 'Untitled'),
                    'director': movie_data.get('field_director', ''),
                    'year': movie_data.get('field_year', ''),
                    'runtime': runtime,
                    'series': movie_data.get('field_series', ''),
                    'venue': movie_data.get('venue_title', 'Unknown Venue'),
                    'datetime': start_time,
                    'url': movie_data.get('field_url', '')
                }

                all_screenings.append(screening_event)
            except Exception as e:
                logger.error(f"Error processing screening {movie_id}: {e}")

    if not all_screenings:
        logger.error("No screenings found!")
        return

    group1, group2, group3 = [], [], []
    for screening in all_screenings:
        venue = screening.get('venue', '')
        if any(v.lower() in venue.lower() for v in group1_venues):
            group1.append(screening)
        elif any(v.lower() in venue.lower() for v in group2_venues):
            group2.append(screening)
        else:
            group3.append(screening)

    def add_screenings_to_calendar(screenings, cal):
        nyc_tz = pytz.timezone('America/New_York')
        for screening in screenings:
            start_time = screening['datetime']
            if start_time.tzinfo is None:
                start_time = nyc_tz.localize(start_time)
            # Filter out weekday screenings before 5PM
            if start_time.weekday() < 5 and start_time.hour < 17:
                continue
            try:
                event = create_calendar_event(screening)
                cal.add_component(event)
            except Exception as e:
                logger.error(f"Error creating event: {e}")

    os.makedirs(output_dir, exist_ok=True)

    groups = [
        (group1, 'metrograph_afa.ics', 'NYC Indie Cinema - Metrograph & AFA'),
        (group2, 'filmforum_ifc.ics', 'NYC Indie Cinema - Film Forum & IFC Center'),
        (group3, 'others.ics', 'NYC Indie Cinema - Other Venues')
    ]

    for screenings_group, filename, cal_name in groups:
        cal = Calendar()
        cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
        cal.add('version', '2.0')
        cal.add('x-wr-calname', cal_name)
        cal.add('x-wr-timezone', 'America/New_York')

        add_screenings_to_calendar(screenings_group, cal)

        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(cal.to_ical())
        logger.info(f"Calendar saved: {filename} with {len(cal.subcomponents)} events")

def main():
    api = ScreenSlateAPI()
    generate_calendar(api)

if __name__ == "__main__":
    main()
