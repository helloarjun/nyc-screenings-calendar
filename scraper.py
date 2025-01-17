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
            
            # Get director, year, and runtime
            info = media_title.find('div', class_='media-title-info')
            director = ''
            year = ''
            runtime = ''
            if info:
                info_spans = info.find_all('span')
                for span in info_spans:
                    text = span.text.strip()
                    if text.isdigit() and len(text) == 4:  # Year (e.g., "2024")
                        year = text
                    elif text.endswith('M'):  # Runtime (e.g., "166M")
                        runtime = text.rstrip('M')
                    elif text and not any(x in text for x in ['DCP', '35MM', '16MM']):  # Exclude format info
                        director = text.strip('"')
