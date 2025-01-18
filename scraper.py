import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
from typing import Dict, List

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.screenslate.com"

class ScreenSlateAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
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

            # Debug log for API response
            logger.info(f"Raw batch data: {batch_data}")

            if isinstance(batch_data, list):
                for item in batch_data:
                    if isinstance(item, dict) and "nid" in item:
                        all_results[item["nid"]] = item
            elif isinstance(batch_data, dict):
                all_results.update(batch_data)
            else:
                logger.error("Unexpected data structure in API response.")
        except Exception as e:
            logger.error(f"Error fetching batch: {str(e)}")
            continue

    return all_results
    
def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening information."""
    event = Event()
    nyc_tz = pytz.timezone("America/New_York")
    
    title = screening.get("title", "Untitled")
    venue = screening.get("venue", "Unknown Venue")
    start_time = nyc_tz.localize(screening.get("datetime", datetime.now()))

    description = [
        f"Director: {screening.get('director', 'N/A')}",
        f"Runtime: {screening.get('runtime', 'N/A')} minutes",
        f"More info: {screening.get('url', '')}",
    ]
    
    event.add("summary", f"{title} at {venue}")
    event.add("description", "\n".join(description))
    event.add("dtstart", start_time)
    event.add("duration", timedelta(minutes=int(screening.get("runtime", 120))))
    event.add("location", venue)
    if "url" in screening:
        event.add("url", screening["url"])
    
    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir="_site"):
    """Generate ICS calendar file for the next 7 days."""
    logger.info("Starting calendar generation...")
    cal = Calendar()
    cal.add("prodid", "-//NYC Indie Cinema Calendar//screenslate.com//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "NYC Independent Cinema")
    cal.add("x-wr-timezone", "America/New_York")

    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]

    all_screenings = []
    for date in dates:
        screenings = api_client.fetch_screenings_by_date(date)
        if not screenings:
            logger.warning(f"No screenings found for date {date}")
            continue

        ids = [screening["nid"] for screening in screenings]
        details = api_client.fetch_screening_details(ids)
        for nid, detail in details.items():
            screening = {
                "title": detail.get("title", "Untitled"),
                "venue": detail.get("venue_title", "Unknown Venue"),
                "datetime": datetime.strptime(detail.get("field_timestamp", ""), "%Y-%m-%dT%H:%M:%S"),
                "director": detail.get("media_title_info", ""),
                "runtime": detail.get("field_runtime", "120"),
                "url": detail.get("field_url", ""),
            }
            all_screenings.append(screening)

    if not all_screenings:
        logger.error("No screenings found!")
        return

    for screening in all_screenings:
        event = create_calendar_event(screening)
        cal.add_component(event)

    os.makedirs(output_dir, exist_ok=True)
    calendar_path = os.path.join(output_dir, "nyc-screenings.ics")
    with open(calendar_path, "wb") as f:
        f.write(cal.to_ical())
    logger.info(f"Calendar saved at {calendar_path}")

def main():
    api = ScreenSlateAPI()
    generate_calendar(api)

if __name__ == "__main__":
    main()
