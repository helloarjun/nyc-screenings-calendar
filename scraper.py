import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz
import os
import json
from itertools import groupby
from operator import itemgetter
import re

def create_calendar():
    """Initialize a new iCalendar object"""
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    return cal

def get_date_range():
    """Get date range for next 7 days"""
    today = datetime.now()
    dates = []
    for i in range(7):
        date = today + timedelta(days=i)
        dates.append(date.strftime('%Y%m%d'))  # Format: YYYYMMDD
    return dates

def fetch_screenings_for_date(session, date):
    """Fetch screenings for a specific date"""
    print(f"\n📅 Fetching screenings for date: {date}")
    base_url = 'https://www.screenslate.com/date'
    
    params = {
        '_format': 'json',
        'date': date,
        'field_city_target_id': '10969'  # NYC
    }
    
    try:
        print(f"🔍 Requesting URL: {base_url}")
        print(f"📝 With parameters: {params}")
        response = session.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Success! Found {len(data)} time slots")
        return data
    except requests.RequestException as e:
        print(f"❌ Error fetching screenings: {e}")
        return None

def fetch_movie_details(session, screening_ids):
    """Fetch movie details for a list of screening IDs"""
    print(f"\n🎬 Fetching movie details for {len(screening_ids)} screenings")
    base_url = 'https://www.screenslate.com/api/screenings'
    
    # Join IDs with + for the API query
    ids_param = '+'.join(screening_ids)
    
    params = {
        '_format': 'json'
    }
    
    try:
        print(f"🔍 Requesting URL: {base_url}/{ids_param}")
        response = session.get(f"{base_url}/{ids_param}", params=params)
        response.raise_for_status()
        data = response.json()
        
        # Print sample of movie details
        if data:
            print("\n📋 Sample movie details:")
            sample_id = next(iter(data))
            movie = data[sample_id]
            print(f"  • Title: {movie.get('title', 'N/A')}")
            print(f"  • Venue: {movie.get('venue_title', 'N/A')}")
        
        print(f"✅ Successfully fetched details for {len(data)} movies")
        return data
    except requests.RequestException as e:
        print(f"❌ Error fetching movie details: {e}")
        return None

def parse_movie_details(movie_data):
    """Parse individual movie details from API response"""
    # Extract title (remove " at VENUE" suffix)
    title = movie_data.get('title', '')
    for venue in ['at IFC Center', 'at Film Forum', 'at Metrograph', 'at Anthology Film Archives']:
        title = title.replace(f" {venue}", "")
    
    # Parse media_title_info for director and year
    info = movie_data.get('media_title_info', '')
    director = ''
    year = ''
    runtime = ''
    if info:
        # Remove HTML tags and extra whitespace
        info = info.replace('\u003Cspan\u003E', '').replace('\u003C/span\u003E', '').strip()
        parts = [p.strip() for p in info.split(',')]
        for part in parts:
            if part.strip().isdigit() and len(part.strip()) == 4:  # Year
                year = part.strip()
            elif 'M' in part.strip() and any(c.isdigit() for c in part):  # Runtime
                runtime = part.strip().rstrip('M')
            elif part.strip():  # Director
                director = part.strip()
    
    # Parse series (remove HTML encoding)
    series = movie_data.get('field_series', '')
    if series:
        series = series.replace('\u003C', '<').replace('\u003E', '>').replace('\u0022', '"')
        # Extract text between >Series Name< if it exists
        series_match = re.search(r'>([^<]+)<', series)
        if series_match:
            series = series_match.group(1)
    
    # Get venue (extract from venue_title)
    venue_title = movie_data.get('venue_title', '')
    venue = ''
    if 'IFC Center' in venue_title:
        venue = 'IFC Center'
    elif 'Film Forum' in venue_title:
        venue = 'Film Forum'
    elif 'Metrograph' in venue_title:
        venue = 'Metrograph'
    elif 'Anthology Film Archives' in venue_title:
        venue = 'Anthology Film Archives'
    
    # Get movie URL
    url = movie_data.get('field_url', '')
    
    return {
        'title': title,
        'director': director,
        'year': year,
        'runtime': runtime,
        'series': series,
        'venue': venue,
        'url': url
    }

def create_event(screening):
    """Create an iCalendar event from screening information"""
    event = Event()
    
    # Localize datetime to NYC timezone
    timezone = pytz.timezone('America/New_York')
    dt = timezone.localize(screening['datetime'])
    
    # Create summary
    summary = screening['title']
    if screening['year']:
        summary += f" ({screening['year']})"
    
    # Create description
    description = []
    if screening['director']:
        description.append(f"Director: {screening['director']}")
    if screening['runtime']:
        description.append(f"Runtime: {screening['runtime']} minutes")
    if screening['series']:
        description.append(f"Series: {screening['series']}")
    description.append(f"More info: {screening['url']}")
    
    event.add('summary', f"{summary} at {screening['venue']}")
    event.add('description', '\n'.join(description))
    event.add('dtstart', dt)
    
    # Set duration based on runtime if available, otherwise default to 2 hours
    duration_minutes = int(screening['runtime']) if screening['runtime'] else 120
    event.add('duration', {'minutes': duration_minutes})
    
    event.add('location', screening['venue'])
    event.add('url', screening['url'])
    
    return event

def generate_html(screenings):
    """Generate a simple HTML page with the screenings"""
    os.makedirs('_site', exist_ok=True)
    
    with open('_site/index.html', 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>NYC Indie Cinema Screenings</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
        }
        h1, h2 { color: #333; }
        .screening {
            border-bottom: 1px solid #eee;
            padding: 10px 0;
        }
        .venue { color: #666; }
        .time { color: #0066cc; }
        .series { color: #9933cc; font-size: 0.9em; }
        .no-screenings {
            color: #666;
            font-style: italic;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <h1>NYC Indie Cinema Screenings</h1>
    <p>Last updated: """ + datetime.now().strftime('%Y-%m-%d %I:%M%p') + """</p>
    <p>Total screenings found: """ + str(len(screenings)) + """</p>""")
        
        if not screenings:
            f.write('\n    <p class="no-screenings">No screenings found for the next 7 days.</p>')
        else:
            # Sort screenings by datetime
            sorted_screenings = sorted(screenings, key=lambda x: x['datetime'])
            
            # Group by date
            for date, group in groupby(sorted_screenings, key=lambda x: x['datetime'].strftime('%Y-%m-%d')):
                f.write(f"\n    <h2>{date}</h2>")
                for screening in list(group):
                    f.write(f"""
    <div class="screening">
        <strong>{screening['title']}</strong>
        {f" ({screening['year']})" if screening['year'] else ""}
        {f" - {screening['director']}" if screening['director'] else ""}
        {f" - {screening['runtime']}min" if screening['runtime'] else ""}<br>
        {f'<span class="series">{screening["series"]}</span><br>' if screening['series'] else ''}
        <span class="venue">{screening['venue']}</span> - 
        <span class="time">{screening['datetime'].strftime('%I:%M %p')}</span>
    </div>""")
        
        f.write("\n</body>\n</html>")

def generate_calendar():
    """Generate the complete calendar"""
    print("\n🎬 Starting NYC Indie Cinema Calendar Generator 🎬")
    cal = create_calendar()
    
    print("\n📡 Setting up session...")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.screenslate.com/screenings'
    })
    
    all_screenings = []
    dates = get_date_range()
    print(f"🗓️ Will fetch screenings for dates: {', '.join(dates)}")
    
    for date in dates:
        print(f"\n📅 Processing date: {date}")
        # Step 1: Get time slots for the date
        time_slots = fetch_screenings_for_date(session, date)
        if not time_slots:
            print(f"⚠️ No time slots found for {date}, skipping...")
            continue
            
        # Extract screening IDs from time slots
        screening_ids = [str(slot['nid']) for slot in time_slots]
        
        # Step 2: Get movie details for these time slots
        movie_details = fetch_movie_details(session, screening_ids)
        if not movie_details:
            print(f"⚠️ No movie details found for {date}, skipping...")
            continue
            
        # Combine time slots with movie details
        print("\n🔄 Combining time slots with movie details...")
        day_screenings = 0
        for slot in time_slots:
            slot_id = str(slot['nid'])
            if slot_id in movie_details:
                movie = parse_movie_details(movie_details[slot_id])
                if movie['venue']:  # If we successfully parsed a valid venue
                    screening = {
                        'title': movie['title'],
                        'director': movie['director'],
                        'year': movie['year'],
                        'runtime': movie['runtime'],
                        'series': movie['series'],
                        'datetime': datetime.strptime(slot['field_timestamp'], '%Y-%m-%dT%H:%M:%S'),
                        'venue': movie['venue'],
                        'url': movie['url']
                    }
                    all_screenings.append(screening)
                    day_screenings += 1
                    print(f"  • Added: {screening['title']} at {screening['venue']} ({screening['datetime'].strftime('%I:%M %p')})")
    
    total_screenings = len(all_screenings)
    print(f"\n📊 Total screenings found: {total_screenings}")
    
    if total_screenings == 0:
        print("❌ No screenings found! Something might be wrong...")
        return
    
    print("\n💾 Generating output files...")
    # Create output directory
    os.makedirs('_site', exist_ok=True)
    
    # Generate calendar file
    calendar_events = 0
    for screening in all_screenings:
        event = create_event(screening)
        if event:
            cal.add_component(event)
            calendar_events += 1
    
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    print(f"✅ Created calendar file with {calendar_events} events")
    
    # Generate HTML
    generate_html(all_screenings)
    print("✅ Created HTML page")
    
    print("\n🎉 Calendar generation complete! 🎉")

if __name__ == "__main__":
    generate_calendar()
