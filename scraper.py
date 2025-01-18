import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
import re
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

    logger.info(f"🎥 Fetching details for {len(screening_ids)} screenings")

    # Process in batches of 20
    batch_size = 20
    all_results = {}

    for i in range(0, len(screening_ids), batch_size):
        batch = screening_ids[i:i + batch_size]
        ids_param = '+'.join(str(id) for id in batch)
        url = f"{self.base_url}/api/screenings/id/{ids_param}"
        params = {'_format': 'json'}

        self._rate_limit_wait()
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            batch_data = response.json()
            logger.info(f"✅ Got details for {len(batch_data)} movies")
            all_results.update(batch_data)

        except Exception as e:
            logger.error(f"Error fetching batch: {str(e)}")
            continue

    return all_results


def clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)

def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening data."""
    event = Event()
    nyc_tz = pytz.timezone("America/New_York")

    # Event details
    title = screening.get("title", "Untitled")
    venue = clean_html(screening.get("venue_title", "Unknown Location"))
    start_time = datetime.fromisoformat(screening["datetime"]).astimezone(nyc_tz)

    # Event description
    description_parts = [
        f"Director: {screening.get('director', 'N/A')}",
        f"Year: {screening.get('year', 'N/A')}",
        f"Runtime: {screening.get('runtime', 'N/A')} minutes",
        f"More info: {screening.get('url', 'N/A')}",
    ]

    # Add fields to event
    event.add("summary", f"{title} at {venue}")
    event.add("dtstart", start_time)
    event.add("description", "\n".join(description_parts))
    event.add("location", venue)

    return event

def generate_calendar(api: ScreenSlateAPI, output_path: str = "_site/nyc-screenings.ics"):
    """Generate an ICS calendar file for the next 7 days."""
    cal = Calendar()
    cal.add("prodid", "-//NYC Indie Cinema Calendar//screenslate.com//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "NYC Independent Cinema")
    cal.add("x-wr-timezone", "America/New_York")

    today = datetime.now()
    screenings = []

    for i in range(7):  # Next 7 days
        date_str = (today + timedelta(days=i)).strftime("%Y%m%d")
        logger.info(f"Fetching screenings for {date_str}...")
        daily_screenings = api.fetch_screenings_by_date(date_str)

        if daily_screenings:
            ids = [str(s["nid"]) for s in daily_screenings]
            details = api.fetch_screening_details(ids)
            for screening in daily_screenings:
                nid = str(screening["nid"])
                if nid in details:
                    movie = details[nid]
                    screenings.append({
                        "title": clean_html(movie.get("title", "Untitled")),
                        "venue_title": movie.get("venue_title", "Unknown Location"),
                        "datetime": screening["field_timestamp"],
                        "director": clean_html(movie.get("media_title_info", "").split(",")[0]),
                        "year": re.search(r"(19|20)\\d{2}", movie.get("media_title_info", "")).group(0) if re.search(r"(19|20)\\d{2}", movie.get("media_title_info", "")) else "",
                        "runtime": re.search(r"\\b(\\d+)M\\b", movie.get("media_title_info", "")).group(1) if re.search(r"\\b(\\d+)M\\b", movie.get("media_title_info", "")) else "N/A",
                        "url": movie.get("field_url", ""),
                    })

    if not screenings:
        logger.warning("No screenings found for the next 7 days.")
        return

    for screening in screenings:
        try:
            event = create_calendar_event(screening)
            cal.add_component(event)
        except Exception as e:
            logger.error(f"Error adding screening to calendar: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
    logger.info(f"Calendar saved to {output_path}")

def main():
    api = ScreenSlateAPI()
    generate_calendar(api)

if __name__ == "__main__":
    main()
