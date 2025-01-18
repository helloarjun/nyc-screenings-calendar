import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz
import os
import logging
from typing import Dict, List
import time

# Set up logging
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
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Connection': 'keep-alive'
        })
        
        logging.info("✅ API client initialized")

    def _rate_limit_wait(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def parse_venue_listing(self, listing):
        """Parse a single movie listing from HTML"""
        try:
            # Get series info (e.g., "First Run")
            series_elem = listing.find('div', class_='series')
            series = ''
            if series_elem and series_elem.find('a'):
                series = series_elem.find('a').text.strip()
                
            # Get movie title and URL
            media_title = listing.find('div', class_='media-title')
            if not media_title:
                return None
                
            title_elem = media_title.find('span', class_='field--name-title')
            if not title_elem:
                return None
                
            title = title_elem.text.strip()
            url = ''
            link = media_title.find('a', class_='screening-link')
            if link:
                url = link.get('href', '')
                
            # Get movie info (director, year, runtime)
            info = media_title.find('div', class_='media-title-info')
            director = ''
            year = ''
            runtime = ''
            
            if info:
                # Process each span separately
                spans = info.find_all('span')
                for span in spans:
                    text = span.text.strip()
                    # Skip empty spans and pseudo-elements (::after)
                    if not text or '::' in text:
                        continue
                        
                    if text.endswith('M'):  # Runtime (e.g., "166M")
                        runtime = text.rstrip('M')
                    elif text.isdigit() and len(text) == 4:  # Year
                        year = text
                    else:  # Director
                        director = text.strip('"')
            
            # Get showtimes
            times = []
            showtimes_container = listing.find('div', class_='showtimes-container')
            if showtimes_container:
                time_spans = showtimes_container.find_all('span')
                times = [span.text.strip() for span in time_spans if span.text.strip()]
            
            return {
                'title': title,
                'director': director,
                'year': year,
                'runtime': runtime,
                'series': series,
                'url': url,
                'times': times
            }
            
        except Exception as e:
            logging.error(f"Error parsing listing: {str(e)}")
            return None

    def fetch_screenings_for_date(self, date_str: str) -> List[Dict]:
        """Fetch screenings for a specific date"""
        logging.info(f"🎬 Fetching screenings for date: {date_str}")
        
        url = f"{self.base_url}/listings/{date_str}"
        
        self._rate_limit_wait()
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            screenings = []
            
            # Find all venues
            venues = soup.find_all('div', class_='venue')
            logging.info(f"Found {len(venues)} venues")
            
            for venue in venues:
                # Get venue name from h3
                venue_title = venue.find('h3')
                if not venue_title or not venue_title.find('a'):
                    continue
                    
                venue_name = venue_title.find('a').text.strip()
                
                # Find all listings in this venue
                listings = venue.find_all('div', class_='listing')
                for listing in listings:
                    movie = self.parse_venue_listing(listing)
                    if not movie:
                        continue
                        
                    # Create a screening for each showtime
                    for time_str in movie['times']:
                        try:
                            # Convert date and time to datetime
                            date_obj = datetime.strptime(date_str, '%Y%m%d')
                            time_obj = datetime.strptime(time_str, '%I:%M%p').time()
                            datetime_obj = datetime.combine(date_obj, time_obj)
                            
                            screening = {
                                'title': movie['title'],
                                'director': movie['director'],
                                'year': movie['year'],
                                'runtime': movie['runtime'],
                                'series': movie['series'],
                                'venue': venue_name,
                                'datetime': datetime_obj,
                                'url': movie['url']
                            }
                            screenings.append(screening)
                            logging.debug(f"Added: {movie['title']} at {venue_name} ({time_str})")
                            
                        except ValueError as e:
                            logging.error(f"Error parsing time '{time_str}': {str(e)}")
            
            logging.info(f"✅ Found {len(screenings)} total screenings")
            return screenings
            
        except Exception as e:
            logging.error(f"Error fetching screenings: {str(e)}")
            return []

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
