import requests
from datetime import datetime, timedelta
import pytz
import os
import logging
from typing import Dict, List
import time
from icalendar import Calendar, Event

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScreenSlateAPI:
    def __init__(self, rate_limit: float = 1.0):
        self.session = requests.Session()
        self.base_url = 'https://www.screenslate.com'
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        self.session.headers.update({
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': 'https://www.screenslate.com',
            'Referer': 'https://www.screenslate.com/screenings'
        })
        
        logging.info("✅ API client initialized")

    def _rate_limit_wait(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def fetch_screenings_for_date(self, date_str: str) -> List[Dict]:
        """Fetch screenings for a specific date"""
        logging.info(f"🎬 Fetching screenings for date: {date_str}")
        
        url = f"{self.base_url}/api/screenings/date"
        params = {
            '_format': 'json',
            'date': date_str,
            'field_city_target_id': '10969'  # NYC
        }
        
        self._rate_limit_wait()
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            screenings = response.json()
            logging.info(f"✅ Found {len(screenings)} screening slots")
            
            # Get movie details for these screenings
            if screenings:
                screening_ids = [str(s['nid']) for s in screenings]
                movie_details = self.fetch_movie_details(screening_ids)
                
                # Combine screening times with movie details
                combined_screenings = []
                for screening in screenings:
                    nid = str(screening['nid'])
                    if nid in movie_details:
                        movie = movie_details[nid]
                        combined_screenings.append({
                            **self.parse_movie_details(movie),
                            'datetime': datetime.fromisoformat(screening['field_timestamp'].replace('Z', '+00:00')),
                            'note': screening.get('field_note', '')
                        })
                        
                return combined_screenings
            return []
            
        except Exception as e:
            logging.error(f"Error fetching screenings: {str(e)}")
            return []

    def fetch_movie_details(self, screening_ids: List[str], batch_size: int = 20) -> Dict:
        """Fetch movie details for multiple screenings"""
        if not screening_ids:
            return {}
            
        logging.info(f"🎥 Fetching details for {len(screening_ids)} screenings")
        all_results = {}
        
        # Process in batches
        for i in range(0, len(screening_ids), batch_size):
            batch = screening_ids[i:i + batch_size]
            ids_param = '+'.join(batch)
            url = f"{self.base_url}/api/screenings/{ids_param}"
            
            self._rate_limit_wait()
            try:
                response = self.session.get(url, params={'_format': 'json'}, timeout=30)
                response.raise_for_status()
                batch_data = response.json()
                all_results.update(batch_data)
                logging.info(f"✅ Got details for {len(batch_data)} movies")
            except Exception as e:
                logging.error(f"Error fetching movie batch: {str(e)}")
                continue
        
        return all_results

    def parse_movie_details(self, movie_data: Dict) -> Dict:
        """Parse movie details from API response"""
        result = {
            'title': '',
            'director': '',
            'year': '',
            'runtime': '',
            'series': '',
            'venue': '',
            'format': '',
            'url': movie_data.get('field_url', '')
        }
        
        # Extract title and venue
        title = movie_data.get('title', '')
        venue_suffixes = [
            ' at Film Forum',
            ' at IFC Center',
            ' at Anthology Film Archives',
            ' at Film at Lincoln Center',
            ' at Metrograph'
        ]
        for suffix in venue_suffixes:
            if title.endswith(suffix):
                result['title'] = title.replace(suffix, '')
                result['venue'] = suffix.replace(' at ', '')
                break
        else:
            result['title'] = title
        
        # Parse series
        series = movie_data.get('field_series', '')
        if series:
            result['series'] = series.replace('\\u003C', '<').replace('\\u003E', '>').strip('<>')
        
        # Parse media_title_info
        info = movie_data.get('media_title_info', '')
        if info:
            import re
            # Clean up HTML and Unicode escapes
            info = info.replace('\\u003C', '<').replace('\\u003E', '>')
            info = re.sub(r'<[^>]+>', '', info)
            
            parts = [p.strip() for p in info.split(',')]
            for part in parts:
                part = part.strip()
                if re.match(r'^(19|20)\d{2}$', part):
                    result['year'] = part
                elif 'M' in part.upper():
                    result['runtime'] = part.upper().rstrip('M')
                elif part in ['DCP', '35MM', '16MM', '70MM']:
                    result['format'] = part
                elif part and not result['director']:
                    result['director'] = part.strip('"')
        
        return result

def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening information"""
    event = Event()
    
    # Set timezone to NYC
    nyc_tz = pytz.timezone('America/New_York')
    
    # Create event title
    title = screening['title']
    if screening['year']:
        title += f" ({screening['year']})"
    if screening['format']:
        title += f" [{screening['format']}]"
    
    # Create description
    description_parts = []
    if screening['director']:
        description_parts.append(f"Director: {screening['director']}")
    if screening['runtime']:
        description_parts.append(f"Runtime: {screening['runtime']} minutes")
    if screening['series']:
        description_parts.append(f"Series: {screening['series']}")
    if screening.get('note'):
        description_parts.append(f"Note: {screening['note']}")
    if screening['url']:
        description_parts.append(f"More info: {screening['url']}")
    
    # Add event details
    event.add('summary', f"{title} at {screening['venue']}")
    event.add('description', '\n'.join(description_parts))
    
    # Set start time
    start_time = screening['datetime']
    if not start_time.tzinfo:
        start_time = nyc_tz.localize(start_time)
    event.add('dtstart', start_time)
    
    # Set duration
    duration_minutes = int(screening.get('runtime', 120))  # Default to 2 hours
    event.add('duration', timedelta(minutes=duration_minutes))
    
    # Set location and URL
    event.add('location', screening['venue'])
    if screening['url']:
        event.add('url', screening['url'])
    
    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    """Generate ICS calendar file for the next 7 days"""
    logging.info("🎬 Starting calendar generation")
    
    # Create calendar object
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    
    # Get date range
    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime('%Y%m%d') for i in range(7)]
    
    # Fetch all screenings
    all_screenings = []
    for date_str in dates:
        screenings = api_client.fetch_screenings_for_date(date_str)
        all_screenings.extend(screenings)
    
    if not all_screenings:
        logging.error("❌ No screenings found!")
        return
    
    # Create events
    for screening in all_screenings:
        try:
            event = create_calendar_event(screening)
            cal.add_component(event)
        except Exception as e:
            logging.error(f"Error creating event: {str(e)}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Save calendar file
    calendar_path = os.path.join(output_dir, 'nyc-screenings.ics')
    with open(calendar_path, 'wb') as f:
        f.write(cal.to_ical())
    logging.info(f"✅ Calendar saved with {len(all_screenings)} events")

def main():
    """Main entry point"""
    try:
        api = ScreenSlateAPI(rate_limit=1.0)
        generate_calendar(api)
        logging.info("✨ Calendar generation complete!")
    except Exception as e:
        logging.error(f"❌ Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
