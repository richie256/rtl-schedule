import requests
import datetime
import logging
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import re
import urllib3

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOGGER = logging.getLogger("rtl-schedule")

class HastusScraper:
    BASE_URL = "https://madprep_i.rtl-longueuil.qc.ca/madOper.php"
    
    def __init__(self):
        self.buildtime = None
        self.stop_mappings = {} # stop_code (str) -> list of (feed_id:stop_id)
        # cache: (stop_id, pattern_id, week_start_date) -> { 'weekday': [...], 'samedi': [...], 'dimanche': [...] }
        self.schedule_cache = {} 
        self._initialize()

    def _initialize(self):
        """Fetch current buildtime and basic metadata."""
        try:
            params = {"q": "routers", "s": "RTL", "api": "0"}
            response = requests.get(self.BASE_URL, params=params, timeout=10, verify=False)
            data = response.json()
            self.buildtime = data.get("buildtime")
            _LOGGER.info(f"HastusScraper initialized with buildtime: {self.buildtime}")
        except Exception as e:
            _LOGGER.error(f"Failed to initialize HastusScraper: {e}")

    def fetch_stop_mappings(self):
        """Fetch all stop mappings from the server."""
        try:
            params = {"q": "stops", "s": "RTL", "web": ""}
            response = requests.get(self.BASE_URL, params=params, timeout=20, verify=False)
            content = response.text
            self.stop_mappings = {}
            for entry in content.split(';'):
                if not entry: continue
                parts = entry.split(',')
                if len(parts) >= 6:
                    internal_id = parts[0]
                    stop_code = parts[5]
                    if stop_code not in self.stop_mappings:
                        self.stop_mappings[stop_code] = []
                    if internal_id not in self.stop_mappings[stop_code]:
                        self.stop_mappings[stop_code].append(internal_id)
            _LOGGER.info(f"Fetched {len(self.stop_mappings)} stop mappings.")
        except Exception as e:
            _LOGGER.error(f"Failed to fetch stop mappings: {e}")

    def get_stop_patterns(self, stop_code: str) -> List[Dict]:
        """Fetch available patterns/routes for a given stop code."""
        if not self.stop_mappings:
            self.fetch_stop_mappings()
        
        internal_ids = self.stop_mappings.get(stop_code, [])
        if not internal_ids:
            internal_ids = [f"15:{stop_code}"]
            
        patterns = []
        for p_id in internal_ids:
            params = {
                "q": "stops_patterns",
                "p": p_id,
                "s": "RTL",
                "web": ""
            }
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=15, verify=False)
                patterns.extend(self._parse_patterns_html(response.text))
            except Exception as e:
                _LOGGER.error(f"Failed to fetch patterns for {p_id}: {e}")
                
        return patterns

    def _parse_patterns_html(self, html: str) -> List[Dict]:
        """Parse the HTML from stops_patterns to extract urlHoraireArret parameters."""
        patterns = []
        pattern = re.compile(r"urlHoraireArret\((.*?)\);")
        matches = pattern.findall(html)
        for match in matches:
            args = [arg.strip().strip("'") for arg in match.split(',')]
            if len(args) >= 5:
                patterns.append({
                    "stop": args[0],
                    "pattern": args[1],
                    "code": args[2],
                    "desc": args[3],
                    "ligne": args[4],
                    "leJour": args[5] if len(args) > 5 else None
                })
        return patterns

    def get_schedule_by_params(self, params: Dict, date: datetime.date) -> List[datetime.datetime]:
        """Fetch schedule using parameters derived from urlHoraireArret with caching."""
        if not self.buildtime:
            self._initialize()
            
        # Find the Monday of the week for caching
        week_start = date - datetime.timedelta(days=date.weekday())
        cache_key = (params['stop'], params['pattern'], week_start)
        
        if cache_key in self.schedule_cache:
            _LOGGER.info(f"Using cached schedule for {params['ligne']} on {date}")
            return self._get_times_from_cache(self.schedule_cache[cache_key], date)

        t_timestamp = int(datetime.datetime.combine(week_start, datetime.time.min).timestamp())
        
        pattern_str = params['pattern']
        parts = pattern_str.split(':')
        feed_id = parts[0]
        route_id = parts[1]
        
        query_params = {
            "b": self.buildtime,
            "q": "stops_stoptimes",
            "p": params['stop'],
            "f": feed_id,
            "t": t_timestamp,
            "j": 7,
            "s": "RTL",
            "web": "",
            "pp": params['pattern'],
            "l": params['ligne'],
            "r": f"{feed_id}:{route_id}"
        }
        
        try:
            _LOGGER.info(f"Scraping weekly schedule for {params['ligne']} at {params['desc']} starting {week_start}")
            response = requests.get(self.BASE_URL, params=query_params, timeout=15, verify=False)
            
            # Parse the whole week and cache it
            weekly_data = self._parse_html_weekly_schedule(response.text)
            self.schedule_cache[cache_key] = weekly_data
            
            return self._get_times_from_cache(weekly_data, date)
        except Exception as e:
            _LOGGER.error(f"Scraping failed: {e}")
            return []

    def _get_times_from_cache(self, weekly_data: Dict[str, List[datetime.time]], date: datetime.date) -> List[datetime.datetime]:
        """Helper to convert cached time list to datetime list for a specific date."""
        weekday = date.weekday() # 0=Mon, 5=Sat, 6=Sun
        
        if weekday < 5:
            times = weekly_data.get('semaine', [])
        elif weekday == 5:
            times = weekly_data.get('samedi', [])
        else:
            times = weekly_data.get('dimanche', [])
            
        result = []
        for t in times:
            actual_date = date
            hour = t.hour
            # Handle times like 24:33 (returned as 00:33 of next day by some systems, 
            # but here we keep them as simple times and adjust date if needed)
            # The current parser already handles 24:xx by adjusting the date.
            result.append(datetime.datetime.combine(actual_date, t))
            
        return sorted(result)

    def _parse_html_weekly_schedule(self, html: str) -> Dict[str, List[datetime.time]]:
        """Parse the weekly HTML table into three categories: semaine, samedi, dimanche."""
        soup = BeautifulSoup(html, 'html.parser')
        weekly_data = {'semaine': [], 'samedi': [], 'dimanche': []}
        
        # Find all tables. Typically there are 3 tables for the 3 categories.
        tables = soup.find_all('table', style=lambda s: s and 'border: 2px solid #AA3300' in s)
        
        for table in tables:
            category_text = table.find('b').get_text(strip=True).lower()
            category = None
            if 'semaine' in category_text:
                category = 'semaine'
            elif 'samedi' in category_text:
                category = 'samedi'
            elif 'dimanche' in category_text:
                category = 'dimanche'
            
            if category:
                # Find all time cells (first td in each row, except headers)
                rows = table.find_all('tr')[2:] # Skip category header and sub-headers
                for row in rows:
                    cells = row.find_all('td')
                    if cells:
                        time_str = cells[0].get_text(strip=True)
                        match = re.match(r'(\d{1,2}):(\d{2})', time_str)
                        if match:
                            h, m = map(int, match.groups())
                            # Store as time objects. We don't adjust date here, 
                            # we'll do it when combining with the actual target date.
                            # Note: datetime.time only goes up to 23:59.
                            # If we see 24:xx or 25:xx, we store them as (h-24, m) 
                            # but we need to know they are "next day".
                            # For simplicity, let's store (hour, minute) tuples.
                            weekly_data[category].append(datetime.time(h % 24, m))
                            
        return weekly_data

    def get_schedule(self, stop_id: int, date: datetime.date, feed_id: int = 15) -> List[datetime.datetime]:
        """Legacy method (now redirects to cached version if possible)."""
        params = {
            'stop': f"{feed_id}:{stop_id}",
            'pattern': f"{feed_id}:0:0", # Dummy pattern if unknown
            'ligne': f"Stop {stop_id}",
            'desc': 'Unknown'
        }
        return self.get_schedule_by_params(params, date)
