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
        dates.append(date.strftime('%Y-%m-%d'))  # Changed to YYYY-MM-DD format
    return dates

def fetch_screenings_for_date(session, date):
    print(f"\nFetching screenings for date: {date}")
    url = f'https://www.screenslate.com/nyc/screenings/{date}'
    
    try:
        response = session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all screening blocks
        screenings = []
        screening_blocks = soup.find_all('div', class_='screening-block')
        
        for block in screening_blocks:
            venue = block.find('div', class_='venue')
            if not venue:
                continue
                
            venue_name = venue.get_text(strip=True)
            if venue_name not in ['Film Forum', 'Metrograph', 'IFC Center', 'Anthology Film Archives']:
                continue
                
            title = block.find('h3', class_='title')
            if not title:
                continue
                
            time_block = block.find('div', class_='time')
            if not time_block:
                continue
                
            screening = {
                'title': title.get_text(strip=True),
                'venue': venue_name,
                'datetime': f"{date} {time_block.get_text(strip=True)}",
                'url': 'https://www.screenslate.com' + block.find('a')['href'] if block.find('a') else None
            }
            
            # Optional fields
            director = block.find('div', class_='director')
            if director:
                screening['director'] = director.get_text(strip=True)
            
            year = block.find('div', class_='year')
            if year:
                screening['year'] = year.get_text(strip=True)
                
            screenings.append(screening)
            
        return screenings
    except requests.RequestException as e:
        print(f"Error fetching screenings for {date}: {e}")
        return None

def create_event(screening):
    event = Event()
    
    try:
        dt = datetime.strptime(screening['datetime'], '%Y-%m-%d %I:%M %p')
        timezone = pytz.timezone('America/New_York')
        dt = timezone.localize(dt)
    except ValueError as e:
        print(f"Error parsing datetime: {e}")
        return None
    
    summary = screening['title']
    if screening.get('year'):
        summary += f" ({screening['year']})"
    
    description = []
    if screening.get('director'):
        description.append(f"Director: {screening['director']}")
    if screening.get('url'):
        description.append(f"More info: {screening['url']}")
    
    event.add('summary', f"{summary} at {screening['venue']}")
    event.add('description', '\n'.join(description))
    event.add('dtstart', dt)
    event.add('duration', {'hours': 2})
    event.add('location', screening['venue'])
    if screening.get('url'):
        event.add('url', screening['url'])
    
    return event

def generate_html(screenings):
    template = """<!DOCTYPE html>
<html>
<head>
<title>NYC Indie Cinema Screenings</title>
<meta charset="utf-8">
<style>
body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
h1 { color: #333; }
.screening { border-bottom: 1px solid #eee; padding: 10px 0; }
.venue { color: #666; }
.time { color: #0066cc; }
.no-screenings { color: #666; font-style: italic; margin: 20px 0; }
</style>
</head>
<body>
<h1>NYC Indie Cinema Screenings</h1>
<p>Last updated: {}</p>
<p>Total screenings found: {}</p>
{}
</body>
</html>"""

    content = ""
    if not screenings:
        content = '<p class="no-screenings">No screenings found for the next 7 days.</p>'
    else:
        # Sort screenings by datetime
        sorted_screenings = sorted(screenings, key=lambda x: x['datetime'])
        
        # Group by date
        current_date = None
        for screening in sorted_screenings:
            date = screening['datetime'].split()[0]
            if date != current_date:
                if current_date is not None:
                    content += "</div>"
                current_date = date
                content += f"<h2>{date}</h2><div>"
            
            content += f"""
<div class="screening">
<strong>{screening['title']}</strong>
{f" ({screening['year']})" if screening.get('year') else ""}
{f" - {screening['director']}" if screening.get('director') else ""}<br>
<span class="venue">{screening['venue']}</span> - 
<span class="time">{screening['datetime'].split()[-2:][0]} {screening['datetime'].split()[-2:][1]}</span>
</div>"""
        
        if current_date is not None:
            content += "</div>"

    html = template.format(
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        len(screenings),
        content
    )

    os.makedirs('_site', exist_ok=True)
    with open('_site/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

def generate_calendar():
    cal = create_calendar()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    })
    
    all_screenings = []
    dates = get_date_range()
    
    for date in dates:
        screenings = fetch_screenings_for_date(session, date)
        if screenings:
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
