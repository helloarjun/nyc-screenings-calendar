import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz
import os
import json
from itertools import groupby
from operator import itemgetter

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
    print(f"\nFetching screenings for date: {date}")
    base_url = 'https://www.screenslate.com/listings/date'
    
    params = {
        '_format': 'json',
        'date': date,
        'field_city_target_id': '10969'  # NYC
    }
    
    try:
        response = session.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"Successfully fetched data for {date}")
        return data
    except requests.RequestException as e:
        print(f"Error fetching screenings for {date}: {e}")
        return None

def parse_venue_name(venue_obj):
    """Extract venue name from venue object"""
    target_venues = ['Film Forum', 'Metrograph', 'IFC Center', 'Anthology Film Archives']
    name = venue_obj.get('name', '')
    return name if name in target_venues else None

def parse_screenings(screenings_data):
    """Parse screenings from API response"""
    parsed_screenings = []
    
    if not screenings_data:
        return parsed_screenings
        
    for screening in screenings_data:
        venue_name = parse_venue_name(screening.get('venue', {}))
        if not venue_name:
            continue
            
        title = screening.get('title', '')
        showtime = screening.get('datetime', '')
        director = screening.get('director', '')
        year = screening.get('year', '')
        series = screening.get('series', {}).get('name', '')
        
        if title and showtime:
            try:
                dt = datetime.fromisoformat(showtime.replace('Z', '+00:00'))
                parsed_screenings.append({
                    'title': title,
                    'director': director,
                    'year': year,
                    'series': series,
                    'datetime': dt,
                    'venue': venue_name,
                    'url': f'https://www.screenslate.com/listings/{screening.get("id", "")}'
                })
            except ValueError as e:
                print(f"Error parsing datetime {showtime}: {e}")
    
    return parsed_screenings

def create_event(screening):
    """Create an iCalendar event from screening information"""
    event = Event()
    
    # Localize datetime
    timezone = pytz.timezone('America/New_York')
    dt = timezone.localize(screening['datetime'])
    
    # Create detailed summary
    summary = screening['title']
    if screening['year']:
        summary += f" ({screening['year']})"
    
    # Create detailed description
    description = []
    if screening['director']:
        description.append(f"Director: {screening['director']}")
    if screening['series']:
        description.append(f"Series: {screening['series']}")
    description.append(f"More info: {screening['url']}")
    
    event.add('summary', f"{summary} at {screening['venue']}")
    event.add('description', '\n'.join(description))
    event.add('dtstart', dt)
    event.add('duration', {'hours': 2})  # Default duration
    event.add('location', screening['venue'])
    event.add('url', screening['url'])
    
    return event

def generate_html(screenings):
    """Generate a simple HTML page with the screenings"""
    html = """<!DOCTYPE html>
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
        h1 {
            color: #333;
        }
        .screening {
            border-bottom: 1px solid #eee;
            padding: 10px 0;
        }
        .venue {
            color: #666;
        }
        .time {
            color: #0066cc;
        }
        .no-screenings {
            color: #666;
            font-style: italic;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <h1>NYC Indie Cinema Screenings</h1>
    <p>Last updated: {}</p>
    <p>Total screenings found: {}</p>
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(screenings))

    if not screenings:
        html += '<p class="no-screenings">No screenings found for the next 7 days.</p>'
    else:
        # Sort screenings by datetime
        sorted_screenings = sorted(screenings, key=lambda x: x['datetime'])
        
        # Group by date
        for date, group in groupby(sorted_screenings, key=lambda x: x['datetime'].strftime('%Y-%m-%d')):
            html += f"<h2>{date}</h2>"
            for screening in group:
                html += f"""
                <div class="screening">
                    <strong>{screening['title']}</strong>
                    {f" ({screening['year']})" if screening['year'] else ""}
                    {f" - {screening['director']}" if screening['director'] else ""}<br>
                    <span class="venue">{screening['venue']}</span> - 
                    <span class="time">{screening['datetime'].strftime('%I:%M %p')}</span>
                    {f"<br>Series: {screening['series']}" if screening['series'] else ""}
                </div>
                """

    html += """
    </body>
    </html>
    """

    # Ensure the output directory exists
    os.makedirs('_site', exist_ok=True)
    
    # Write the HTML file
    with open('_site/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

def generate_calendar():
    """Generate the complete iCalendar file and HTML page"""
    cal = create_calendar()
    
    # Set up session with more browser-like headers
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.screenslate.com/',
        'Origin': 'https://www.screenslate.com'
    })
    
    all_screenings = []
    dates = get_date_range()
    
    for date in dates:
        print(f"Fetching screenings for {date}")
        screenings_data = fetch_screenings_for_date(session, date)
        if screenings_data:
            screenings = parse_screenings(screenings_data)
            all_screenings.extend(screenings)
    
    # Ensure the output directory exists
    os.makedirs('_site', exist_ok=True)
    
    # Generate calendar file even if no screenings found
    for screening in all_screenings:
        event = create_event(screening)
        cal.add_component(event)
    
    # Write the calendar file
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    
    # Generate HTML page
    generate_html(all_screenings)
    print(f"Generated calendar with {len(all_screenings)} screenings")

if __name__ == "__main__":
    generate_calendar()
