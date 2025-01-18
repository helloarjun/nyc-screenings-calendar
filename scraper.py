import requests
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event
import os
import logging
from typing import Dict, List, Optional
import time
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScreenSlateAPI:
    def __init__(self, rate_limit: float = 1.0):
        self.session = requests.Session()
        self.base_url = 'https://www.screenslate.com'
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        # Headers based on successful API requests
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/listings/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        logger.info("✅ API client initialized")

    def _rate_limit_wait(self):
        """Implement rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        return re.sub(r'<[^>]+>', '', text)

    def _parse_venue_from_html(self, venue_html: str) -> str:
        """Extract venue name from HTML string"""
        match = re.search(r'href="/venues/[^"]+">([^<]+)</a>', venue_html)
        return match.group(1) if match else venue_html

    def fetch_screenings_for_date(self, date_str: str) -> List[Dict]:
        """Fetch screenings for a specific date using the JSON API"""
        logger.info(f"🎬 Fetching screenings for date: {date_str}")
        
        # First API call: Get screening times
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
            screening_times = response.json()
            
            if not screening_times:
                logger.warning(f"No screenings found for date {date_str}")
                return []
            
            screening_ids = [str(time['nid']) for time in screening_times]
            logger.info(f"Found {len(screening_ids)} screening times")
            
            # Second API call: Get movie details
            movies = self.fetch_movie_details(screening_ids)
            if not movies:
                logger.warning("Failed to fetch movie details")
                return []
            
            # Combine screening times with movie details
            screenings = []
            for time_slot in screening_times:
                movie_id = str(time_slot['nid'])
                if movie_id not in movies:
                    continue
                
                movie = movies[movie_id]
                try:
                    # Parse timestamp
                    datetime_str = time_slot['field_timestamp']
                    datetime_obj = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
                    
                    # Clean up the movie info
                    title = self._clean_html(movie.get('title', '')).split(' at ')[0]
                    venue = self._parse_venue_from_html(movie.get('venue_title', ''))
                    
                    # Extract movie details
                    media_info = movie.get('media_title_info', '')
                    director = ''
                    year = ''
                    runtime = ''
                    
                    # Parse media_title_info
                    if media_info:
                        # Extract year (4 digits)
                        year_match = re.search(r'\b(19|20)\d{2}\b', media_info)
                        if year_match:
                            year = year_match.group(0)
                        
                        # Extract runtime (digits followed by M)
                        runtime_match = re.search(r'\b(\d+)M\b', media_info)
                        if runtime_match:
                            runtime = runtime_match.group(1)
                        
                        # Extract director (usually before the year)
                        if year:
                            director_part = media_info.split(year)[0]
                            director = director_part.strip().strip(',')
                    
                    screening = {
                        'title': title,
                        'director': director,
                        'year': year,
                        'runtime': runtime,
                        'series': movie.get('field_series', ''),
                        'venue': venue,
                        'datetime': datetime_obj,
                        'url': movie.get('field_url', '')
                    }
                    screenings.append(screening)
                    
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing screening {movie_id}: {str(e)}")
                    continue
            
            logger.info(f"✅ Successfully processed {len(screenings)} screenings")
            return screenings
            
        except Exception as e:
            logger.error(f"Error fetching screenings: {str(e)}")
            return []

    def fetch_movie_details(self, screening_ids: List[str]) -> Dict:
        """Fetch movie details for a list of screening IDs"""
        if not screening_ids:
            return {}
        
        logger.info(f"🎥 Fetching details for {len(screening_ids)} screenings")
        
        # Process in batches of 20
        batch_size = 20
        all_results = {}
        
        for i in range(0, len(screening_ids), batch_size):
            batch = screening_ids[i:i + batch_size]
            ids_param = '+'.join(str(id) for id in batch)
            url = f"{self.base_url}/api/screenings/{ids_param}"
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

def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening information"""
    event = Event()
    
    # Set timezone to NYC
    nyc_tz = pytz.timezone('America/New_York')
    
    # Create event title
    title = screening['title']
    if screening['year']:
        title += f" ({screening['year']})"
    
    # Create description
    description_parts = []
    if screening['director']:
        description_parts.append(f"Director: {screening['director']}")
    if screening['runtime']:
        description_parts.append(f"Runtime: {screening['runtime']} minutes")
    if screening['series']:
        description_parts.append(f"Series: {screening['series']}")
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
    
    # Set duration (default 2 hours if not specified)
    duration_minutes = int(screening.get('runtime', 120))
    event.add('duration', timedelta(minutes=duration_minutes))
    
    # Set location and URL
    event.add('location', screening['venue'])
    if screening['url']:
        event.add('url', screening['url'])
    
    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    """Generate ICS calendar file for the next 7 days"""
    logger.info("🎬 Starting calendar generation")
    
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
    for date_str in dates:
        screenings = api_client.fetch_screenings_for_date(date_str)
        all_screenings.extend(screenings)
    
    if not all_screenings:
        logger.error("❌ No screenings found!")
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
    logger.info(f"✅ Calendar saved with {len(all_screenings)} events")

def main():
    """Main entry point"""
    try:
        api = ScreenSlateAPI(rate_limit=1.0)
        generate_calendar(api)
        logger.info("✨ Calendar generation complete!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
