class ScreenSlateAPI:
    def __init__(self):
        print("\n🔧 Initializing ScreenSlate API client...")
        self.session = self._create_session()
        self.base_url = 'https://www.screenslate.com'
        print("✅ API client initialized")
    
    def fetch_screenings_for_date(self, date):
        """Fetch screenings for a specific date"""
        print(f"\n🎬 Fetching screenings for date: {date}")
        url = f"{self.base_url}/api/screenings/date"
        params = {
            '_format': 'json',
            'date': date,
            'field_city_target_id': '10969'  # NYC
        }
        
        try:
            print(f"🔍 Making request to: {url}")
            print(f"📝 With parameters: {params}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Found {len(data)} screening slots")
            return data
            
        except Exception as e:
            print(f"❌ Error fetching screenings: {str(e)}")
            return None

    def fetch_movie_details(self, screening_ids):
        """Fetch movie details for multiple screenings"""
        print(f"\n🎥 Fetching details for {len(screening_ids)} screenings")
        
        if not screening_ids:
            print("⚠️ No screening IDs provided")
            return {}
            
        ids_param = '+'.join(str(id) for id in screening_ids)
        url = f"{self.base_url}/api/screenings/{ids_param}"
        
        try:
            print(f"🔍 Making request to: {url}")
            response = self.session.get(url, params={'_format': 'json'})
            response.raise_for_status()
            data = response.json()
            print(f"✅ Successfully fetched details for {len(data)} movies")
            
            # Print sample movie info
            if data:
                sample_id = next(iter(data))
                sample = data[sample_id]
                print("\n📋 Sample movie details:")
                print(f"  • Title: {sample.get('title', 'N/A')}")
                print(f"  • Venue: {sample.get('venue_title', 'N/A')}")
            
            return data
            
        except Exception as e:
            print(f"❌ Error fetching movie details: {str(e)}")
            return {}

    def get_screenings(self, date_str):
        """Get complete screening information for a date"""
        print(f"\n🎬 Getting all screenings for date: {date_str}")
        
        # Step 1: Get screening times
        print("\n📅 STEP 1: Fetching screening times...")
        slots = self.fetch_screenings_for_date(date_str)
        if not slots:
            print("❌ No screening times found")
            return []
            
        # Step 2: Get movie details
        print("\n🎥 STEP 2: Fetching movie details...")
        screening_ids = [slot['nid'] for slot in slots]
        print(f"📝 Found {len(screening_ids)} screening IDs")
        movies = self.fetch_movie_details(screening_ids)
        
        # Step 3: Combine data
        print("\n🔄 STEP 3: Combining screening times with movie details...")
        screenings = []
        for slot in slots:
            nid = slot['nid']
            if nid in movies:
                print(f"\n📽️ Processing screening ID: {nid}")
                print(f"  • Time: {slot['field_time']}")
                movie = self.parse_movie_details(movies[nid])
                if movie:
                    screenings.append({
                        **movie,
                        'datetime': slot['field_timestamp']
                    })
                    print(f"  ✅ Added: {movie['title']} at {movie['venue']}")
            else:
                print(f"⚠️ No details found for screening ID: {nid}")
        
        print(f"\n✨ Successfully processed {len(screenings)} screenings")
        return screenings
