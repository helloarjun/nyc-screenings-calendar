import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
import re  # For regex operations
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs if needed
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.screenslate.com"

class ScreenSlateAPI:
    # ... [Keep the existing ScreenSlateAPI implementation unchanged] ...

def create_calendar_event(screening: Dict) -> Event:
    # ... [Keep the existing create_calendar_event implementation unchanged] ...
    # This function safely converts runtime and creates an event.

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    logger.info("Starting calendar generation")
    
    # Initialize calendars' metadata for later use in grouping
    group1_venues = ["Metrograph", "AFA"]
    group2_venues = ["Film Forum", "IFC Center"]

    # Fetch screenings for the next 7 days
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

                # Determine runtime: use field_runtime if available, else extract from media_title_info
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

    # Group screenings based on venue categories
    group1, group2, group3 = [], [], []
    for screening in all_screenings:
        venue = screening.get('venue', '')
        if any(v.lower() in venue.lower() for v in group1_venues):
            group1.append(screening)
        elif any(v.lower() in venue.lower() for v in group2_venues):
            group2.append(screening)
        else:
            group3.append(screening)

    # Helper function to add screenings to a calendar with weekday filtering
    def add_screenings_to_calendar(screenings, cal):
        nyc_tz = pytz.timezone('America/New_York')
        for screening in screenings:
            start_time = screening['datetime']
            # Convert to NYC timezone if not aware
            if start_time.tzinfo is None:
                start_time = nyc_tz.localize(start_time)
            # For weekdays, skip screenings before 5PM
            if start_time.weekday() < 5 and start_time.hour < 17:
                continue
            try:
                event = create_calendar_event(screening)
                cal.add_component(event)
            except Exception as e:
                logger.error(f"Error creating event: {e}")

    # Prepare output directory
    os.makedirs(output_dir, exist_ok=True)

    # Define groups and corresponding filenames
    groups = [
        (group1, 'metrograph_afa.ics', 'NYC Indie Cinema - Metrograph & AFA'),
        (group2, 'filmforum_ifc.ics', 'NYC Indie Cinema - Film Forum & IFC Center'),
        (group3, 'others.ics', 'NYC Indie Cinema - Other Venues')
    ]

    # Create separate calendars for each group
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
