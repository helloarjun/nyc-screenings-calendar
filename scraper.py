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
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//screenslate.com//')
    cal.add('version', '2.0')
    return cal

def get_date_range():
    today = datetime.now()
    dates = []
    for i in range(7):
        date = today + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))  # Using YYYY-MM-DD format
    return dates

def fetch_screenings_for_date(session, date):
    print(f"\nFetching screenings for date: {date}")
    url = f'https://www.screenslate.com/listings/date/{date}'
    
    try:
        response = session.get(url)
        response.raise_for_status()
        print(f"Successfully fetched data for {date}")
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching screenings for {date}: {e}")
        return None

def parse_screenings(html_content, date):
    if not html_content:
        return []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    parsed_screenings = []
    
    # Find all venue sections
    venues = soup.find_all('div', class_='venue')
    
    for venue in venues:
        venue_name = venue.find('h3').find('a').text.strip()
        if venue_name not in ['Film Forum', 'Metrograph', 'IFC Center', 'Anthology Film Archives']:
            continue
            
        # Find all listings within this venue
        listings = venue.find_all('div', class_='listing')
        
        for listing in listings:
            # Get series information
            series_div = listing.find('div', class_='series')
            series = series_div.find('a').text.strip() if series_div and series_div.find('a') else ''
            
            # Get movie title and info
            media_title = listing.find('div', class_='media-title')
            if not media_title:
                continue
                
            title_span = media_title.find('span', class_='field--name-title')
            if not title_span:
                continue
                
            title = title_span.text.strip()
            
            # Get director and year
            info_div = media_title.find('div', class_='media-title-info')
            director = ''
            year = ''
            if info_div:
                spans = info_div.find_all('span')
                for span in spans:
                    text = span.text.strip().strip('"')
                    if text.isdigit() and len(text) == 4:
                        year = text
                    elif text and not any(char.isdigit() for char in text) and 'M' not in text:
                        director = text
            
            # Get showtimes
            showtimes_container = listing.find('div', class_='showtimes-container')
            if showtimes_container:
                showtimes = showtimes_container.find_all('span')
                for time in showtimes:
                    time_text = time.text.strip()
                    try:
                        dt = datetime.strptime(f"{date} {time_text}", '%Y-%m-%d %I:%M%p')
                        parsed_screenings.append({
                            'title': title,
                            'director': director,
                            'year': year,
                            'series': series,
                            'datetime': dt,
                            'venue': venue_name,
                            'url': f'https://www.screenslate.com/screenings/{date}'
                        })
                    except ValueError as e:
                        print(f"Error parsing time {time_text}: {e}")
    
    return parsed_screenings

def create_event(screening):
    event = Event()
    timezone = pytz.timezone('America/New_York')
    dt = timezone.localize(screening['datetime'])
    
    summary = screening['title']
    if screening['year']:
        summary += f" ({screening['year']})"
    
    description = []
    if screening['director']:
        description.append(f"Director: {screening['director']}")
    if screening['series']:
        description.append(f"Series: {screening['series']}")
    description.append(f"More info: {screening['url']}")
    
    event.add('summary', f"{summary} at {screening['venue']}")
    event.add('description', '\n'.join(description))
    event.add('dtstart', dt)
    event.add('duration', {'hours': 2})
    event.add('location', screening['venue'])
    event.add('url', screening['url'])
    
    return event

def generate_html(screenings):
    os.makedirs('_site', exist_ok=True)
    
    with open('_site/index.html', 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>NYC Indie Cinema Screenings</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1, h2 { color: #333; }
        .screening { border-bottom: 1px solid #eee; padding: 10px 0; }
        .venue { color: #666; }
        .time { color: #0066cc; }
        .series { color: #9933cc; font-size: 0.9em; }
        .no-screenings { color: #666; font-style: italic; margin: 20px 0; }
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
        {f" - {screening['director']}" if screening['director'] else ""}<br>
        {f'<span class="series">{screening["series"]}</span><br>' if screening['series'] else ''}
        <span class="venue">{screening['venue']}</span> - 
        <span class="time">{screening['datetime'].strftime('%I:%M %p')}</span>
    </div>""")
        
        f.write("\n</body>\n</html>")

def generate_calendar():
    cal = create_calendar()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    
    all_screenings = []
    dates = get_date_range()
    
    for date in dates:
        html_content = fetch_screenings_for_date(session, date)
        if html_content:
            screenings = parse_screenings(html_content, date)
            all_screenings.extend(screenings)
            print(f"Found {len(screenings)} screenings for {date}")
    
    print(f"\nTotal screenings found: {len(all_screenings)}")
    
    # Create output directory
    os.makedirs('_site', exist_ok=True)
    
    # Generate calendar file
    for screening in all_screenings:
        event = create_event(screening)
        if event:
            cal.add_component(event)
    
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    
    # Generate HTML
    generate_html(all_screenings)
    print(f"Generated calendar and HTML with {len(all_screenings)} screenings")

if __name__ == "__main__":
    generate_calendar()
