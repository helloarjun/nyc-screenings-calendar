import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import pytz
import os
import re

def fetch_screenings_for_date(session, date):
    """Fetch screenings for a specific date"""
    print(f"\n📅 Fetching screenings for {date}")
    url = 'https://www.screenslate.com/api/screenings/date'
    
    params = {
        '_format': 'json',
        'date': date,
        'field_city_target_id': '10969'  # NYC
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Error fetching screenings: {e}")
        return None

def fetch_movie_details(session, screening_ids):
    """Fetch movie details for a list of screening IDs"""
    print(f"\n🎬 Fetching details for {len(screening_ids)} screenings")
    url = 'https://www.screenslate.com/api/screenings/'
    
    # Join IDs with + for batch request
    ids_param = '+'.join(map(str, screening_ids))
    
    params = {
        '_format': 'json'
    }
    
    try:
        response = session.get(f"{url}{ids_param}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Error fetching movie details: {e}")
        return None

def parse_movie_info(movie_data):
    """Parse movie details from API response"""
    title = movie_data.get('title', '').replace(' at IFC Center', '').replace(' at Film Forum', '').replace(' at Metrograph', '').replace(' at Anthology Film Archives', '')
    
    # Parse media_title_info for director, year, and runtime
    info = movie_data.get('media_title_info', '')
    director = ''
    year = ''
    runtime = ''
    
    if info:
        # Remove HTML tags and split by commas
        info = re.sub(r'\u003C.*?\u003E', '', info).strip()
        parts = [p.strip() for p in info.split(',')]
        
        for part in parts:
            if part.strip().isdigit() and len(part.strip()) == 4:  # Year
                year = part.strip()
            elif part.strip().endswith('M'):  # Runtime (e.g., "166M")
                runtime = part.strip().rstrip('M').strip()  # Remove 'M' and any whitespace
            else:  # Director
                director = part.strip()
    
    # Get series
    series = movie_data.get('field_series', '')
    if series:
        series = re.sub(r'\u003C.*?\u003E', '', series).strip()
    
    # Get venue
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
    
    return {
        'title': title,
        'director': director,
        'year': year,
        'runtime': runtime,
        'series': series,
        'venue': venue,
        'url': movie_data.get('field_url', '')
    }

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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.6;
        }
        h1, h2 { color: #333; margin-top: 2em; }
        .screening {
            border-bottom: 1px solid #eee;
            padding: 1em 0;
        }
        .venue { 
            color: #666;
            font-weight: 500;
        }
        .time { color: #1a73e8; }
        .series { 
            color: #9333ea;
            font-size: 0.9em;
        }
        .download {
            display: inline-block;
            background: #1a73e8;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .download:hover {
            background: #1557b0;
        }
    </style>
</head>
<body>
    <h1>NYC Indie Cinema Screenings</h1>
    <p>Last updated: """ + datetime.now().strftime('%Y-%m-%d %I:%M %p') + """</p>
    <a href="nyc-screenings.ics" class="download">Download the ICS Calendar</a>
    """)
        
        # Group screenings by date
        screenings.sort(key=lambda x: x['datetime'])
        current_date = None
        
        for screening in screenings:
            date = screening['datetime'].strftime('%Y-%m-%d')
            if date != current_date:
                if current_date:
                    f.write('\n')
                f.write(f"\n    <h2>{screening['datetime'].strftime('%A, %B %d')}</h2>")
                current_date = date
            
            f.write(f"""
    <div class="screening">
        <strong>{screening['title']}</strong>
        {f" ({screening['year']})" if screening['year'] else ""}
        {f" - {screening['director']}" if screening['director'] else ""}<br>
        {f'<div class="series">{screening["series"]}</div>' if screening['series'] else ''}
        <span class="venue">{screening['venue']}</span> - 
        <span class="time">{screening['datetime'].strftime('%I:%M %p')}</span>
        {f"<br>Runtime: {screening['runtime']} minutes" if screening['runtime'] else ""}
        {f'<br><a href="{screening["url"]}" target="_blank">More info</a>' if screening['url'] else ""}
    </div>""")
            
        f.write("\n</body>\n</html>")

def generate_calendar():
    """Generate the complete calendar"""
    print("\n🎬 Starting NYC Indie Cinema Calendar Generator")
    
    # Set up session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    
    all_screenings = []
    start_date = datetime.now()
    
    # Get screenings for next 7 days
    for i in range(7):
        date = (start_date + timedelta(days=i)).strftime('%Y%m%d')
        
        # Step 1: Get screenings for the date
        time_slots = fetch_screenings_for_date(session, date)
        if not time_slots:
            continue
        
        # Collect screening IDs
        screening_ids = [slot['nid'] for slot in time_slots]
        
        # Step 2: Get movie details
        movie_details = fetch_movie_details(session, screening_ids)
        if not movie_details:
            continue
        
        # Step 3: Combine time slots with movie details
        print(f"\n🔄 Processing screenings for {date}")
        for slot in time_slots:
            slot_id = slot['nid']
            if slot_id in movie_details:
                # Parse movie details
                movie = parse_movie_info(movie_details[slot_id])
                if movie['venue']:  # Only include if we have a valid venue
                    dt = datetime.strptime(slot['field_timestamp'], '%Y-%m-%dT%H:%M:%S')
                    screening = {**movie, 'datetime': dt}
                    all_screenings.append(screening)
                    print(f"  • Added: {movie['title']} at {movie['venue']} ({dt.strftime('%I:%M %p')})")
    
    if not all_screenings:
        print("❌ No screenings found!")
        return
    
    print(f"\n📊 Found {len(all_screenings)} total screenings")
    
    # Generate calendar file
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    
    for screening in all_screenings:
        event = Event()
        
        # Create summary
        summary = screening['title']
        if screening['year']:
            summary += f" ({screening['year']})"
        summary += f" at {screening['venue']}"
        
        # Create description
        description = []
        if screening['director']:
            description.append(f"Director: {screening['director']}")
        if screening['runtime']:
            description.append(f"Runtime: {screening['runtime']} minutes")
        if screening['series']:
            description.append(f"Series: {screening['series']}")
        if screening['url']:
            description.append(f"More info: {screening['url']}")
        
        event.add('summary', summary)
        event.add('description', '\n'.join(description))
        event.add('dtstart', screening['datetime'])
        
        # Set duration based on runtime if available, otherwise default to 2 hours
        duration_minutes = int(screening['runtime']) if screening['runtime'] else 120
        event.add('duration', timedelta(minutes=duration_minutes))
        
        event.add('location', screening['venue'])
        if screening['url']:
            event.add('url', screening['url'])
        
        cal.add_component(event)
    
    # Create output directory
    os.makedirs('_site', exist_ok=True)
    
    # Write calendar file
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    print("✅ Created calendar file")
    
    # Generate HTML
    generate_html(all_screenings)
    print("✅ Created HTML page")
    
    print("\n🎉 Calendar generation complete!")

if __name__ == '__main__':
    generate_calendar()
