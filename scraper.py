import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import pytz
import os
import re

def fetch_screenings_for_date(session, date):
    """Fetch screenings for a specific date"""
    url = f'https://www.screenslate.com/listings/{date}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"❌ Error fetching screenings: {e}")
        return None

def parse_movie_details(movie_div):
    """Parse movie details from a listing div"""
    # Get series info
    series_div = movie_div.find('div', class_='series')
    series = series_div.text.strip() if series_div else ''
    
    # Get movie title
    title_span = movie_div.find('span', class_='field--name-title')
    if not title_span:
        return None
    title = title_span.text.strip()
    
    # Get movie info (director, year, runtime)
    info_div = movie_div.find('div', class_='media-title-info')
    director = year = runtime = ''
    if info_div:
        info_text = info_div.text.strip()
        # Parse director, year, runtime
        parts = [p.strip() for p in info_text.split(',')]
        for part in parts:
            if part.strip().isdigit() and len(part.strip()) == 4:  # Year
                year = part.strip()
            elif 'M' in part.strip():  # Runtime
                runtime = part.strip().rstrip('M')
            else:  # Director
                director = part.strip()
    
    # Get showtimes
    showtimes_div = movie_div.find('div', class_='showtimes')
    showtimes = []
    if showtimes_div:
        for time_span in showtimes_div.find_all('span'):
            showtime = time_span.text.strip()
            if showtime:
                showtimes.append(showtime)
    
    # Get venue
    venue_div = movie_div.find_parent('div', class_='venue')
    venue = ''
    if venue_div:
        venue_title = venue_div.find('h3').text.strip()
        for known_venue in ['Film Forum', 'Metrograph', 'IFC Center', 'Anthology Film Archives']:
            if known_venue.lower() in venue_title.lower():
                venue = known_venue
                break
    
    return {
        'title': title,
        'director': director,
        'year': year,
        'runtime': runtime,
        'series': series,
        'venue': venue,
        'showtimes': showtimes
    }

def parse_screenings_page(html, date_str):
    """Parse the screenings page HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    screenings = []
    
    # Find all movie listings
    for listing in soup.find_all('div', class_='listing'):
        movie = parse_movie_details(listing)
        if movie and movie['venue']:
            # Convert showtimes to datetime objects
            for showtime in movie['showtimes']:
                try:
                    # Parse the date string to datetime
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    # Parse the time (assuming 12-hour format with AM/PM)
                    time_obj = datetime.strptime(showtime, '%I:%M%p').time()
                    # Combine date and time
                    dt = datetime.combine(date_obj.date(), time_obj)
                    
                    screening = movie.copy()
                    screening['datetime'] = dt
                    screening['showtime'] = showtime
                    screenings.append(screening)
                except ValueError as e:
                    print(f"⚠️ Error parsing time {showtime}: {e}")
                    continue
    
    return screenings

def generate_calendar(days=7):
    """Generate calendar for the next N days"""
    print("\n🎬 Starting NYC Indie Cinema Calendar Generator 🎬")
    
    session = requests.Session()
    all_screenings = []
    
    # Get date range
    start_date = datetime.now()
    dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
    
    for date in dates:
        print(f"\n📅 Fetching screenings for {date}")
        html = fetch_screenings_for_date(session, date)
        if html:
            screenings = parse_screenings_page(html, date)
            all_screenings.extend(screenings)
            print(f"✅ Found {len(screenings)} screenings for {date}")
    
    # Generate calendar file
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    
    # Add events to calendar
    for screening in all_screenings:
        event = Event()
        
        summary = f"{screening['title']}"
        if screening['year']:
            summary += f" ({screening['year']})"
        summary += f" at {screening['venue']}"
        
        description = []
        if screening['director']:
            description.append(f"Director: {screening['director']}")
        if screening['runtime']:
            description.append(f"Runtime: {screening['runtime']} minutes")
        if screening['series']:
            description.append(f"Series: {screening['series']}")
        
        event.add('summary', summary)
        event.add('description', '\n'.join(description))
        event.add('dtstart', screening['datetime'])
        event.add('duration', timedelta(minutes=int(screening['runtime']) if screening['runtime'] else 120))
        event.add('location', screening['venue'])
        
        cal.add_component(event)
    
    # Create output directory
    os.makedirs('_site', exist_ok=True)
    
    # Write calendar file
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    
    # Generate HTML
    generate_html(all_screenings)
    
    print(f"\n✅ Calendar generated with {len(all_screenings)} screenings")

if __name__ == '__main__':
    generate_calendar()
