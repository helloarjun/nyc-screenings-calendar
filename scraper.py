import requests
import json
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

# Base URL and endpoints
BASE_URL = "https://www.screenslate.com"
DATE_ENDPOINT = "/date?_format=json&date={date}&field_city_target_id=10969"
SCREENING_ENDPOINT = "/api/screenings/{id}?_format=json"

# Function to get data from the DATE endpoint
def get_date_data(date):
    formatted_date = date.strftime("%Y%m%d")
    url = BASE_URL + DATE_ENDPOINT.format(date=formatted_date)
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Function to get screening details by ID
def get_screening_data(screening_id):
    url = BASE_URL + SCREENING_ENDPOINT.format(id=screening_id)
    response = requests.get(url)
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
        date_data = get_date_data(current_date)

        for screening in date_data.get('data', []):
            screening_id = screening['id']
            screening_data = get_screening_data(screening_id)

            # Extract event details
            event = {
                'title': screening_data.get('title', 'Untitled Event'),
                'start_time': datetime.fromisoformat(screening_data['start_time']),
                'end_time': datetime.fromisoformat(screening_data.get('end_time', screening_data['start_time'])),
                'location': screening_data.get('location', {}).get('name', 'Unknown Location'),
                'description': screening_data.get('description', ''),
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
