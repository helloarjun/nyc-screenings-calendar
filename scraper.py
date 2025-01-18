import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz
import os
import logging
import time
from typing import Dict, List

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detail
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScreenSlateAPI:
    def __init__(self, rate_limit: float = 1.0):
        """Initialize the ScreenSlate API client"""
        self.session = requests.Session()
        self.base_url = 'https://www.screenslate.com'
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        logging.info("✅ API client initialized")

    def fetch_screenings_for_date(self, date_str: str) -> List[Dict]:
        """Fetch screenings for a specific date"""
        logging.info(f"🎬 Fetching screenings for date: {date_str}")
        
        url = f"{self.base_url}/listings/{date_str}"
        logging.debug(f"Requesting URL: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Log response details
            logging.debug(f"Response status: {response.status_code}")
            logging.debug(f"Response headers: {dict(response.headers)}")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Log HTML structure for debugging
            logging.debug(f"HTML content sample: {soup.prettify()[:500]}")
            
            screenings = []
            venues = soup.find_all('div', class_='venue')
            logging.info(f"Found {len(venues)} venues")
            
            for venue in venues:
                venue_title = venue.find('h3')
                if not venue_title:
                    logging.warning("Missing venue title")
                    continue
                    
                venue_name = venue_title.text.strip()
                logging.debug(f"Processing venue: {venue_name}")
                
                listings = venue.find_all('div', class_='listing')
                logging.debug(f"Found {len(listings)} listings for {venue_name}")
                
                for listing in listings:
                    try:
                        # Extract movie info
                        media_title = listing.find('div', class_='media-title')
                        if not media_title:
                            logging.warning("Skipping listing - no media title found")
                            continue
                        
                        # Get title
                        title_elem = media_title.find('span', class_='field--name-title')
                        if not title_elem:
                            logging.warning("Skipping listing - no title element found")
                            continue
                            
                        title = title_elem.text.strip()
                        logging.debug(f"Processing movie: {title}")
                        
                        # Get showtimes
                        showtimes_div = listing.find('div', class_='showtimes')
                        if not showtimes_div:
                            logging.warning(f"No showtimes found for {title}")
                            continue
                            
                        times = showtimes_div.find_all('span')
                        for time_elem in times:
                            time_str = time_elem.text.strip()
                            try:
                                # Parse datetime
                                date_obj = datetime.strptime(date_str, '%Y%m%d')
                                time_obj = datetime.strptime(time_str, '%I:%M%p').time()
                                datetime_obj = datetime.combine(date_obj, time_obj)
                                
                                screening = {
                                    'title': title,
                                    'venue': venue_name,
                                    'datetime': datetime_obj
                                }
                                screenings.append(screening)
                                logging.debug(f"Added screening: {screening}")
                                
                            except ValueError as e:
                                logging.error(f"Error parsing time '{time_str}': {str(e)}")
                                
                    except Exception as e:
                        logging.error(f"Error processing listing: {str(e)}", exc_info=True)
            
            logging.info(f"✅ Successfully processed {len(screenings)} screenings")
            return screenings
            
        except requests.RequestException as e:
            logging.error(f"Request failed: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}", exc_info=True)
            return []

def create_calendar_event(screening: Dict) -> Event:
    """Create an iCalendar event from screening information"""
    event = Event()
    
    # Set timezone to NYC
    nyc_tz = pytz.timezone('America/New_York')
    
    # Set event properties
    event.add('summary', f"{screening['title']} at {screening['venue']}")
    
    # Set start time
    start_time = screening['datetime']
    if not start_time.tzinfo:
        start_time = nyc_tz.localize(start_time)
    event.add('dtstart', start_time)
    
    # Set duration (default 2 hours)
    event.add('duration', timedelta(hours=2))
    
    # Set location
    event.add('location', screening['venue'])
    
    return event

def generate_calendar(api_client: ScreenSlateAPI, output_dir: str = '_site'):
    """Generate ICS calendar file for the next 7 days"""
    logging.info("🎬 Starting calendar generation")
    
    try:
        # Create calendar object
        cal = Calendar()
        cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
        cal.add('version', '2.0')
        
        # Get date range
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime('%Y%m%d') for i in range(7)]
        logging.info(f"Processing dates: {dates}")
        
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
                logging.error(f"Error creating event: {str(e)}", exc_info=True)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Save calendar file
        calendar_path = os.path.join(output_dir, 'nyc-screenings.ics')
        with open(calendar_path, 'wb') as f:
            f.write(cal.to_ical())
            
        logging.info(f"✅ Calendar saved with {len(all_screenings)} events")
        
    except Exception as e:
        logging.error(f"❌ Error generating calendar: {str(e)}", exc_info=True)
        raise

def main():
    """Main entry point"""
    try:
        api = ScreenSlateAPI(rate_limit=1.0)
        generate_calendar(api)
        logging.info("✨ Calendar generation complete!")
    except Exception as e:
        logging.error(f"❌ Fatal error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
