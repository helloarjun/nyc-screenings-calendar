import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time
from typing import Dict, List

class ScreenSlateAPI:
    def __init__(self, rate_limit: float = 1.0):
        """Initialize the ScreenSlate API client"""
        self.session = requests.Session()
        self.base_url = 'https://www.screenslate.com'
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
        # Updated headers based on browser inspection
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': 'https://www.screenslate.com',
            'Referer': 'https://www.screenslate.com/screenings'
        })
        
        logging.info("✅ API client initialized")

    def _rate_limit_wait(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def fetch_screenings_for_date(self, date_str: str) -> List[Dict]:
        """Fetch screenings for a specific date"""
        logging.info(f"🎬 Fetching screenings for date: {date_str}")
        
        # Updated URL to match the website structure
        url = f"{self.base_url}/listings/{date_str}"
        
        self._rate_limit_wait()
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            screenings = []
            
            # Find all venues
            venues = soup.find_all('div', class_='venue')
            for venue in venues:
                venue_title = venue.find('h3').text.strip()
                
                # Process each listing in the venue
                listings = venue.find_all('div', class_='listing')
                for listing in listings:
                    try:
                        # Get series info
                        series = listing.find('div', class_='series')
                        series_name = series.text.strip() if series else ''
                        
                        # Get movie info
                        media_title = listing.find('div', class_='media-title')
                        if not media_title:
                            continue
                            
                        title = media_title.find('span', class_='field--name-title').text.strip()
                        url = media_title.find('a', class_='screening-link')['href']
                        
                        # Get director, year, and runtime
                        info = media_title.find('div', class_='media-title-info')
                        director = ''
                        year = ''
                        runtime = ''
                        format_info = ''
                        
                        if info:
                            info_text = info.text.strip()
                            parts = [p.strip() for p in info_text.split(',')]
                            
                            for part in parts:
                                if part.isdigit() and len(part) == 4:  # Year
                                    year = part
                                elif 'M' in part:  # Runtime
                                    runtime = part.rstrip('M')
                                elif part in ['DCP', '35MM', '16MM', '70MM']:
                                    format_info = part
                                else:
                                    director = part.strip('"')
                        
                        # Get showtimes
                        showtimes = listing.find_all('span', class_='time')
                        times = [time.text.strip() for time in showtimes]
                        
                        for time_str in times:
                            # Convert date and time to datetime
                            date_obj = datetime.strptime(date_str, '%Y%m%d')
                            time_obj = datetime.strptime(time_str, '%I:%M%p').time()
                            datetime_obj = datetime.combine(date_obj, time_obj)
                            
                            screening = {
                                'title': title,
                                'director': director,
                                'year': year,
                                'runtime': runtime,
                                'format': format_info,
                                'series': series_name,
                                'venue': venue_title,
                                'datetime': datetime_obj,
                                'url': f"{self.base_url}{url}"
                            }
                            screenings.append(screening)
                            
                    except Exception as e:
                        logging.error(f"❌ Error processing listing: {str(e)}")
            
            logging.info(f"✅ Found {len(screenings)} screenings")
            return screenings
            
        except Exception as e:
            logging.error(f"❌ Error fetching screenings: {str(e)}")
            return []

    def get_screenings(self, date_str: str) -> List[Dict]:
        """Get complete screening information for a date"""
        return self.fetch_screenings_for_date(date_str)
