def generate_events(start_date, days):
    events = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        print(f"Fetching screenings for date: {current_date.date()}")
        screenings = get_date_data(current_date)

        for screening in screenings:
            runtime_str = screening.get('field_runtime', '')
            runtime_minutes = int(runtime_str.replace('M', '')) if 'M' in runtime_str else 0
            start_time = datetime.fromisoformat(screening['field_timestamp'])
            end_time = start_time + timedelta(minutes=runtime_minutes) if runtime_minutes else start_time

            # Replace 'Unknown Location' with real location data if available
            location = screening.get('field_location', 'Location not available')

            event = {
                'title': screening.get('field_display_title', f"Screening {screening['nid']}"),
                'start_time': start_time,
                'end_time': end_time,
                'location': location,
                'description': screening.get('field_note', ''),
            }
            print(f"Event created: {event}")
            events.append(event)
    print(f"Total events generated: {len(events)}")
    return events
