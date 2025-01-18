import requests
import json
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

# Base URL and endpoints
BASE_URL = "https://www.screenslate.com"
DATE_ENDPOINT = "/api/screenings/date?_format=json&date={date}"

# Function to get data from the DATE endpoint
def get_date_data(date):
    formatted_date = date.strftime("%Y%m%d")
    url = BASE_URL + DATE_ENDPOINT.format(date=formatted_date)
    print(f"Fetching data from URL: {url}")
    response = requests.get(url)
    if response.status_code == 404:
        print(f"404 Error: URL not found - {url}")
        return []
    response.raise_for_status()
    return response.json()

# Function to create an ICS calendar file
def create_ics_calendar(events):
    cal = Calendar()
    cal.add('prodid', '-//NYC Indie Cinema Calendar//mxm.dk//')
    cal.add('version', '2.0')

    for event in events:
        cal_event = Event()
        cal_event.add('summary', event['title'])
        cal_event.add('dtstart', event['start_time'])
        cal_event.add('dtend', event['end_time'])
        cal_event.add('location', event['location'])
        cal_event.add('description', event['description'])
        cal.add_component(cal_event)

    with open('nyc_indie_cinema.ics', 'wb') as f:
        f.write(cal.to_ical())

# Function to generate events from scraped data
def generate_events(start_date, days):
    events = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        screenings = get_date_data(current_date)

        for screening in screenings:
            # Extract event details
            event = {
                'title': screening.get('field_display_title', f"Screening {screening['nid']}"),
                'start_time': datetime.fromisoformat(screening['field_timestamp']),
                'end_time': datetime.fromisoformat(screening['field_timestamp']),  # End time not provided, use start time
                'location': screening.get('field_location', 'Unknown Location'),
                'description': screening.get('field_note', ''),
            }
            events.append(event)
    return events

# Main script execution
def main():
    start_date = datetime.now(pytz.timezone('America/New_York'))
    days_to_scrape = 7

    print("Scraping data...")
    events = generate_events(start_date, days_to_scrape)

    print("Creating ICS calendar...")
    create_ics_calendar(events)

    print("Calendar created: nyc_indie_cinema.ics")

if __name__ == "__main__":
    main()
