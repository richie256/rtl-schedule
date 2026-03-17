import requests
import datetime
import logging
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import re
import urllib3
import json
import os

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOGGER = logging.getLogger("rtl-schedule")

class HastusScraper:
    BASE_URL = "https://madprep_i.rtl-longueuil.qc.ca/madOper.php"
    CACHE_FILE = "data/hastus_cache.json"
    
    def __init__(self):
        self.buildtime = None
        self.stop_mappings = {} # stop_code (str) -> list of (feed_id:stop_id)
        # cache: (stop_id, pattern_id, week_start_date) -> { 'weekday': [...], 'samedi': [...], 'dimanche': [...] }
        self.schedule_cache = {} 
        self._load_cache()
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

    def _load_cache(self):
        """Load cache from disk."""
        if not os.path.exists(self.CACHE_FILE):
            return
        
        try:
            with open(self.CACHE_FILE, 'r') as f:
                raw_cache = json.load(f)
                
            self.schedule_cache = {}
            for key_str, data in raw_cache.items():
                # Key format: "stop|pattern|week_start"
                parts = key_str.split('|')
                if len(parts) != 3: continue
                stop, pattern, week_start_str = parts
                week_start = datetime.date.fromisoformat(week_start_str)
                key = (stop, pattern, week_start)
                
                # Convert time strings back to datetime.time
                weekly_data = {}
                for cat, times in data.items():
                    weekly_data[cat] = [datetime.time.fromisoformat(t) for t in times]
                
                self.schedule_cache[key] = weekly_data
            _LOGGER.info(f"Loaded {len(self.schedule_cache)} entries from disk cache.")
        except Exception as e:
            _LOGGER.error(f"Failed to load cache from disk: {e}")

    def _save_cache(self):
        """Save cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            serializable_cache = {}
            for (stop, pattern, week_start), data in self.schedule_cache.items():
                key_str = f"{stop}|{pattern}|{week_start.isoformat()}"
                serializable_data = {}
                for cat, times in data.items():
                    serializable_data[cat] = [t.isoformat() for t in times]
                serializable_cache[key_str] = serializable_data
                
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
            _LOGGER.info("Saved cache to disk.")
        except Exception as e:
            _LOGGER.error(f"Failed to save cache to disk: {e}")

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

    def get_stop_code_from_id(self, stop_id: int) -> Optional[str]:
        """Find the public stop code for a given internal stop_id."""
        if not self.stop_mappings:
            self.fetch_stop_mappings()
        
        target_id_suffix = f":{stop_id}"
        for code, ids in self.stop_mappings.items():
            for internal_id in ids:
                if internal_id.endswith(target_id_suffix):
                    return code
        return None

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
                
        unique_patterns = {p['pattern']: p for p in patterns}.values()
        return list(unique_patterns)

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
            
        week_start = date - datetime.timedelta(days=date.weekday())
        cache_key = (params['stop'], params['pattern'], week_start)
        
        if cache_key in self.schedule_cache:
            _LOGGER.debug(f"Using cached schedule for {params['ligne']} on {date}")
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
            
            weekly_data = self._parse_html_weekly_schedule(response.text)
            if not weekly_data['semaine'] and not weekly_data['samedi'] and not weekly_data['dimanche']:
                _LOGGER.warning(f"No times found in scraped HTML for {params['ligne']}")
                
            self.schedule_cache[cache_key] = weekly_data
            self._save_cache()
            
            return self._get_times_from_cache(weekly_data, date)
        except Exception as e:
            _LOGGER.error(f"Scraping failed: {e}")
            return []

    def _get_times_from_cache(self, weekly_data: Dict[str, List[datetime.time]], date: datetime.date) -> List[datetime.datetime]:
        """Helper to convert cached time list to datetime list for a specific date."""
        weekday = date.weekday()
        
        if weekday < 5:
            times = weekly_data.get('semaine', [])
        elif weekday == 5:
            times = weekly_data.get('samedi', [])
        else:
            times = weekly_data.get('dimanche', [])
            
        result = []
        for t in times:
            result.append(datetime.datetime.combine(date, t))
            
        return sorted(result)

    def _parse_html_weekly_schedule(self, html: str) -> Dict[str, List[datetime.time]]:
        """Parse the weekly HTML table into three categories: semaine, samedi, dimanche."""
        soup = BeautifulSoup(html, 'html.parser')
        weekly_data = {'semaine': [], 'samedi': [], 'dimanche': []}
        
        tables = soup.find_all('table', style=lambda s: s and 'border: 2px solid #AA3300' in s)
        
        for table in tables:
            header_row = table.find('tr')
            if not header_row: continue
            
            category_cell = header_row.find('b')
            if not category_cell: continue
            
            category_text = category_cell.get_text(strip=True).lower()
            category = None
            if 'semaine' in category_text:
                category = 'semaine'
            elif 'samedi' in category_text:
                category = 'samedi'
            elif 'dimanche' in category_text:
                category = 'dimanche'
            
            if category:
                rows = table.find_all('tr')[2:]
                for row in rows:
                    cells = row.find_all('td')
                    if cells:
                        time_str = cells[0].get_text(strip=True)
                        match = re.match(r'(\d{1,2}):(\d{2})', time_str)
                        if match:
                            h, m = map(int, match.groups())
                            weekly_data[category].append(datetime.time(h % 24, m))
                            
        return weekly_data

    def get_schedule(self, stop_id: int, date: datetime.date, feed_id: int = 15) -> List[Dict[str, Any]]:
        """Smart fallback: discovers patterns for the stop and fetches all schedules."""
        stop_code = self.get_stop_code_from_id(stop_id)
        if not stop_code:
            _LOGGER.error(f"Could not map internal stop_id {stop_id} to a stop code.")
            return []
            
        _LOGGER.info(f"Fallback: Discovered stop code {stop_code} for ID {stop_id}")
        patterns = self.get_stop_patterns(stop_code)
        
        if not patterns:
            _LOGGER.warning(f"No patterns found for stop code {stop_code}")
            return []
            
        all_arrivals = []
        # Filter for "Direction Terminus Panama" as requested
        target_direction = "Direction Terminus Panama"
        
        for p in patterns:
            if target_direction not in p['ligne']:
                _LOGGER.debug(f"Skipping pattern {p['ligne']} (not {target_direction})")
                continue
                
            arrivals = self.get_schedule_by_params(p, date)
            
            # Extract route number from ligne string (e.g. " 44 Direction Terminus Panama" -> "44")
            route_match = re.search(r'(\d+)', p['ligne'])
            route_id = route_match.group(1) if route_match else "0"
            
            for a_dt in arrivals:
                all_arrivals.append({
                    'arrival_datetime': a_dt,
                    'arrival_time': a_dt.strftime("%H:%M:%S"),
                    'route_id': route_id,
                    'trip_headsign': p['ligne'].strip()
                })
            
        # Sort by arrival time
        all_arrivals.sort(key=lambda x: x['arrival_datetime'])
        return all_arrivals
