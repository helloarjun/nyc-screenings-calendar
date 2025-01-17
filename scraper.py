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
    url = 'https://www.screenslate.com/screenings'
    
    params = {
        'date': date,
        'city': 'nyc'
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching screenings for {date}: {e}")
        return None

def parse_screenings(html_content):
    if not html_content:
        return []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    parsed_screenings = []
    
    # Look for venue sections
    venue_sections = soup.find_all('div', class_='venue')
    
    for venue_section in venue_sections:
        venue_name = venue_section.find('h3').text.strip()
        if venue_name not in ['Film Forum', 'Metrograph', 'IFC Center', 'Anthology Film Archives']:
            continue
            
        listings = venue_section.find_all('div', class_='listing')
        
        for listing in listings:
            # Get series info
            series = listing.find('div', class_='series')
            series_name = series.text.strip() if series else ''
            
            # Get movie info
            media_title = listing.find('div', class_='media-title')
            if not media_title:
                continue
                
            title = media_title.find('span', class_='field--name-title').text.strip()
            
            # Get director and year
            info = media_title.find('div', class_='media-title-info')
            director = ''
            year = ''
            if info:
                info_spans = info.find_all('span')
                for span in info_spans:
                    text = span.text.strip()
                    if text.isdigit() and len(text) == 4:
                        year = text
                    elif 'M' not in text and text:
                        director = text.strip('"')
            
            # Get showtimes
            showtimes = listing.find('div', class_='showtimes')
            if not showtimes:
                continue
                
            time_spans = showtimes.find_all('span')
            for time_span in time_spans:
                time_text = time_span.text.strip()
                try:
                    dt = datetime.strptime(f"{date} {time_text}", '%Y-%m-%d %I:%M%p')
                    parsed_screenings.append({
                        'title': title,
                        'director': director,
                        'year': year,
                        'series': series_name,
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
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
        }
        h1, h2 {
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
        .series {
            color: #9933cc;
            font-size: 0.9em;
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
    <p>Last updated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    <p>Total screenings found: """ + str(len(screenings)) + """</p>
""")
        
        if not screenings:
            f.write('    <p class="no-screenings">No screenings found for the next 7 days.</p>\n')
        else:
            # Sort screenings by datetime
            sorted_screenings = sorted(screenings, key=lambda x: x['datetime'])
            
            # Group by date
            for date, group in groupby(sorted_screenings, key=lambda x: x['datetime'].strftime('%Y-%m-%d')):
                f.write(f"    <h2>{date}</h2>\n")
                for screening in group:
                    f.write(f"""    <div class="screening">
        <strong>{screening['title']}</strong>
        {f" ({screening['year']})" if screening['year'] else ""}
        {f" - {screening['director']}" if screening['director'] else ""}<br>
        {f'<span class="series">{screening["series"]}</span><br>' if screening['series'] else ''}
        <span class="venue">{screening['venue']}</span> - 
        <span class="time">{screening['datetime'].strftime('%I:%M %p')}</span>
    </div>\n""")
        
        f.write("</body>\n</html>")

def generate_calendar():
    cal = create_calendar()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    
    all_screenings = []
    dates = get_date_range()
    
    for date in dates:
        html_content = fetch_screenings_for_date(session, date)
        if html_content:
            screenings = parse_screenings(html_content)
            all_screenings.extend(screenings)
    
    os.makedirs('_site', exist_ok=True)
    
    for screening in all_screenings:
        event = create_event(screening)
        if event:
            cal.add_component(event)
    
    with open('_site/nyc-screenings.ics', 'wb') as f:
        f.write(cal.to_ical())
    
    generate_html(all_screenings)
    print(f"Generated calendar with {len(all_screenings)} screenings")

if __name__ == "__main__":
    generate_calendar()
