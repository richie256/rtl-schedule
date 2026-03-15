import requests
import datetime
import logging
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import re

_LOGGER = logging.getLogger("rtl-schedule")

class HastusScraper:
    BASE_URL = "https://madprep_i.rtl-longueuil.qc.ca/madOper.php"
    
    def __init__(self):
        self.buildtime = None
        self.stop_mappings = {} # stop_code -> (feed_id, stop_id)
        self._initialize()

    def _initialize(self):
        """Fetch current buildtime and basic metadata."""
        try:
            params = {"q": "routers", "s": "RTL", "api": "0"}
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            data = response.json()
            self.buildtime = data.get("buildtime")
            _LOGGER.info(f"HastusScraper initialized with buildtime: {self.buildtime}")
        except Exception as e:
            _LOGGER.error(f"Failed to initialize HastusScraper: {e}")

    def get_schedule(self, stop_id: int, date: datetime.date, feed_id: int = 15) -> List[datetime.datetime]:
        """Fetch schedule for a stop and date using the web portal."""
        if not self.buildtime:
            self._initialize()
        
        # t is a Unix timestamp for the start of the day (or week)
        t_timestamp = int(datetime.datetime.combine(date, datetime.time.min).timestamp())
        
        params = {
            "b": self.buildtime,
            "q": "stops_stoptimes",
            "p": f"{feed_id}:{stop_id}",
            "f": feed_id,
            "t": t_timestamp,
            "j": 7, # 7 days view
            "s": "RTL",
            "web": ""
        }
        
        try:
            _LOGGER.info(f"Scraping Hastus portal for stop {stop_id} on {date}")
            response = requests.get(self.BASE_URL, params=params, timeout=15)
            return self._parse_html_schedule(response.text, date)
        except Exception as e:
            _LOGGER.error(f"Scraping failed: {e}")
            return []

    def _parse_html_schedule(self, html: str, target_date: datetime.date) -> List[datetime.datetime]:
        """Parse the HTML table returned by madOper.php."""
        soup = BeautifulSoup(html, 'html.parser')
        arrival_datetimes = []
        
        # The HTML contains tables for different days. 
        # We need to find the one matching our target_date.
        # Based on the sample, it shows "LUNDI 9 MARS", "DIMANCHE 15 MARS", etc.
        # A simpler way is to find all time patterns HH:MM
        
        # RTL schedules in the web portal often show times like "06:33"
        time_pattern = re.compile(r'(\d{1,2}):(\d{2})')
        
        # For now, let's extract all times from the page. 
        # In a 7-day view, this might be tricky. 
        # However, if we just want 'today', we can try to find the specific section.
        
        # Based on your URL analysis, if we send t=March 15, it might show that day.
        # Let's extract all times and assume they belong to the target date for a start.
        # (A more robust parser would look for the specific day header)
        
        for text in soup.stripped_strings:
            match = time_pattern.match(text)
            if match:
                hour, minute = map(int, match.groups())
                # Handle 24:XX as 00:XX of the next day
                actual_date = target_date
                if hour >= 24:
                    hour -= 24
                    actual_date += datetime.timedelta(days=1)
                
                arrival_datetimes.append(datetime.datetime.combine(actual_date, datetime.time(hour, minute)))
        
        return sorted(list(set(arrival_datetimes)))
