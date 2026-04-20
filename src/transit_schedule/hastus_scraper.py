import datetime
import json
import logging
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.retry import Retry

from transit_schedule.const import TARGET_DIRECTION, TRANSIT

_LOGGER = logging.getLogger("transit-schedule")

class HostnameIgnoreAdapter(HTTPAdapter):
    """
    Custom adapter to bypass hostname mismatch errors while still verifying 
    the certificate chain. This is needed because Python's SSL module 
    is strict about underscores in hostnames (e.g. madprep_i).
    """
    def __init__(self, *args, **kwargs):
        self.max_retries = kwargs.pop('max_retries', None)
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            assert_hostname=False,
            **pool_kwargs
        )

class HastusScraper:
    BASE_URL = "https://madprep_i.rtl-longueuil.qc.ca/madOper.php"
    CACHE_FILE = "data/hastus_cache.json"
    
    def __init__(self):
        self.buildtime = None
        self.stop_mappings = {} # stop_code (str) -> list of (feed_id:stop_id)
        self._mappings_fetched = False
        # cache: (stop_id, pattern_id, week_start_date) -> { 'weekday': [...], 'samedi': [...], 'dimanche': [...] }
        self.schedule_cache = {} 
        
        # Initialize session with custom adapter and retry logic
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HostnameIgnoreAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._load_cache()
        self._initialize()

    def _initialize(self):
        """Fetch current buildtime and basic metadata."""
        try:
            params = {"q": "routers", "s": "RTL", "api": "0"}
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.buildtime = data.get("buildtime")
            _LOGGER.info(f"HastusScraper initialized with buildtime: {self.buildtime}")
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Network error during HastusScraper initialization: {e}")
        except ValueError as e:
            _LOGGER.error(f"JSON parsing error during HastusScraper initialization: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error during HastusScraper initialization: {e}")

    def _load_cache(self):
        """Load cache from disk."""
        if not os.path.exists(self.CACHE_FILE):
            return
        
        try:
            with open(self.CACHE_FILE) as f:
                raw_cache = json.load(f)
                
            self.schedule_cache = {}
            for key_str, data in raw_cache.items():
                # Key format: "stop|pattern|week_start"
                parts = key_str.split('|')
                if len(parts) != 3:
                    continue
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
            response = self.session.get(self.BASE_URL, params=params, timeout=20)
            response.raise_for_status()
            content = response.text
            self.stop_mappings = {}
            for entry in content.split(';'):
                if not entry:
                    continue
                parts = entry.split(',')
                if len(parts) >= 6:
                    internal_id = parts[0]
                    stop_code = parts[5]
                    if stop_code not in self.stop_mappings:
                        self.stop_mappings[stop_code] = []
                    if internal_id not in self.stop_mappings[stop_code]:
                        self.stop_mappings[stop_code].append(internal_id)
            self._mappings_fetched = True
            _LOGGER.info(f"Fetched {len(self.stop_mappings)} stop mappings.")
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Network error while fetching stop mappings: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error while fetching stop mappings: {e}")

    def get_stop_code_from_id(self, stop_id: int) -> str | None:
        """Find the public stop code for a given internal stop_id."""
        if not self._mappings_fetched:
            self.fetch_stop_mappings()
        
        target_id_suffix = f":{stop_id}"
        for code, ids in self.stop_mappings.items():
            for internal_id in ids:
                if internal_id.endswith(target_id_suffix):
                    return code
        return None

    def get_stop_patterns(self, stop_code: str, stop_id: int | None = None) -> list[dict]:
        """Fetch available patterns/routes for a given stop code."""
        if not self._mappings_fetched:
            self.fetch_stop_mappings()
        
        internal_ids = self.stop_mappings.get(stop_code, [])
        if not internal_ids:
            if stop_id:
                # Try common feed IDs
                internal_ids = [f"15:{stop_id}", f"14:{stop_id}", f"1:{stop_id}"]
                _LOGGER.info(f"Stop code {stop_code} not in mapping, trying fallback IDs: {internal_ids}")
            else:
                # Fallback to guessing feed 15 if not in mapping
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
                response = self.session.get(self.BASE_URL, params=params, timeout=15)
                new_patterns = self._parse_patterns_html(response.text)
                if not new_patterns and response.text:
                    _LOGGER.debug(f"No patterns found in response for {p_id}. Response snippet: {response.text[:200]}")
                patterns.extend(new_patterns)
            except Exception as e:
                _LOGGER.error(f"Failed to fetch patterns for {p_id}: {e}")
                
        unique_patterns = {p['pattern']: p for p in patterns}.values()
        return list(unique_patterns)

    def _parse_patterns_html(self, html: str) -> list[dict]:
        """Parse the HTML from stops_patterns to extract urlHoraireArret parameters."""
        patterns = []
        # Support both single and double quotes, and optional spaces
        pattern = re.compile(r"urlHoraireArret\s*\((.*?)\)\s*;")
        matches = pattern.findall(html)
        for match in matches:
            # More robust argument splitting
            args = [arg.strip().strip("'\"") for arg in match.split(',')]
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

    def get_schedule_by_params(self, params: dict, date: datetime.date) -> list[datetime.datetime]:
        """Fetch schedule using parameters derived from urlHoraireArret with caching."""
        if not self.buildtime:
            self._initialize()
            
        def ensure_cached(d):
            week_start = d - datetime.timedelta(days=d.weekday())
            cache_key = (params['stop'], params['pattern'], week_start)
            if cache_key not in self.schedule_cache:
                self._fetch_and_cache(params, d, cache_key)
            return cache_key

        current_key = ensure_cached(date)
        
        # If searching late at night, or if we just want robustness, 
        # ensure next day is also cached.
        next_day = date + datetime.timedelta(days=1)
        ensure_cached(next_day)

        _LOGGER.info(f"CACHE HIT: Using cached schedule for {params['ligne']} on {date}")
        return self._get_times_from_cache(self.schedule_cache[current_key], date)

    def _fetch_and_cache(self, params, date, cache_key):
        """Fetch data from network and populate cache."""
        # Step 1: Fetch landing page to discover service periods (different 't' values)
        landing_params = {
            "q": "stops_stoptimes",
            "p": params['stop'],
            "s": "RTL",
            "web": "",
            "pp": params['pattern'],
            "l": params['ligne']
        }
        
        try:
            _LOGGER.info(f"Fetching landing page to discover service periods for {params['ligne']}")
            landing_res = self.session.get(self.BASE_URL, params=landing_params, timeout=15)
            soup = BeautifulSoup(landing_res.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'q=stops_stoptimes'))
            
            combined_weekly_data = {'semaine': [], 'samedi': [], 'dimanche': []}
            
            # Step 2: Fetch each "regulier" schedule found
            found_any = False
            for link in links:
                href = link.get('href')
                if "regulier" not in href and "t=" not in href:
                    continue
                
                # Extract full URL or build it
                if href.startswith('/'):
                    url = f"https://madprep_i.rtl-longueuil.qc.ca{href}"
                elif href.startswith('madOper.php'):
                    url = f"https://madprep_i.rtl-longueuil.qc.ca/{href}"
                else:
                    # Might be relative or already absolute
                    url = href if "://" in href else f"https://madprep_i.rtl-longueuil.qc.ca/{href}"

                _LOGGER.info(f"Fetching schedule period from: {url}")
                response = self.session.get(url, timeout=15)
                found_any = True
                
                try:
                    json_data = response.json()
                    if isinstance(json_data, dict) and 'data' in json_data:
                        _LOGGER.info("Successfully fetched JSON schedule")
                        period_data = self._parse_json_weekly_schedule(json_data, params['stop'], params['pattern'], date)
                        for cat in combined_weekly_data:
                            combined_weekly_data[cat].extend(period_data[cat])
                    else:
                        _LOGGER.warning("Response was not the expected JSON format")
                except ValueError:
                    _LOGGER.warning("Failed to parse JSON from service period link")

            if not found_any:
                _LOGGER.warning("No service period links found on landing page")

            # Deduplicate and sort
            for cat in combined_weekly_data:
                combined_weekly_data[cat] = sorted(set(combined_weekly_data[cat]))

            self.schedule_cache[cache_key] = combined_weekly_data
            self._save_cache()
            
        except Exception as e:
            _LOGGER.error(f"Scraping failed: {e}")
            import traceback
            _LOGGER.error(traceback.format_exc())

    def _parse_json_weekly_schedule(self, json_data: dict, stop_id: str, pattern_id: str, target_date: datetime.date) -> dict[str, list[datetime.time]]:
        """Parse the new JSON format into weekly categories, filtering by stop and pattern."""
        weekly_data = {'semaine': [], 'samedi': [], 'dimanche': []}

        data_entries = json_data.get('data', [])

        # The JSON might contain multiple stops/patterns if the URL didn't filter strictly enough
        for entry in data_entries:
            # Check if this entry matches our requested stop and pattern
            # The 'id' field in JSON is often 'pattern_id:index' (e.g. '15:44:1:01')
            if entry.get('stopid') != stop_id or not entry.get('id', '').startswith(f"{pattern_id}:"):
                continue

            arrival_seconds = entry.get('scheduledarrival')
            if arrival_seconds is None:
                continue

            # Convert seconds since midnight to time
            try:
                h, m = divmod(arrival_seconds // 60, 60)
                t = datetime.time(h % 24, m)
            except (ValueError, OverflowError):
                _LOGGER.error(f"Invalid arrival seconds: {arrival_seconds}")
                continue

            # Identify which day this belongs to
            date_str = entry.get('date')
            if date_str:
                try:
                    entry_date = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                    weekday = entry_date.weekday()
                    if weekday < 5:
                        weekly_data['semaine'].append(t)
                    elif weekday == 5:
                        weekly_data['samedi'].append(t)
                    else:
                        weekly_data['dimanche'].append(t)
                except ValueError:
                    _LOGGER.error(f"Failed to parse date string in JSON: {date_str}")
            else:
                # Fallback if no date is provided: use the target_date's category
                # This is less ideal for filling the whole cache but better than nothing
                weekday = target_date.weekday()
                if weekday < 5:
                    weekly_data['semaine'].append(t)
                elif weekday == 5:
                    weekly_data['samedi'].append(t)
                else:
                    weekly_data['dimanche'].append(t)

        # Deduplicate and sort
        for cat in weekly_data:
            weekly_data[cat] = sorted(set(weekly_data[cat]))

        return weekly_data

    def _get_times_from_cache(self, weekly_data: dict[str, list[datetime.time]], date: datetime.date) -> list[datetime.datetime]:
        """Helper to convert cached time list to datetime list for a specific date, including early morning of next day."""
        
        def get_category_times(d: datetime.date):
            wd = d.weekday()
            if wd < 5:
                return weekly_data.get('semaine', [])
            elif wd == 5:
                return weekly_data.get('samedi', [])
            else:
                return weekly_data.get('dimanche', [])

        current_day_times = get_category_times(date)
        next_day = date + datetime.timedelta(days=1)
        next_day_times = get_category_times(next_day)
            
        result = []
        for t in current_day_times:
            result.append(datetime.datetime.combine(date, t))
        
        # Also include very early morning of next day (e.g. 00:00 to 04:00)
        # to handle late night bus searches correctly.
        for t in next_day_times:
            if t.hour < 4:
                result.append(datetime.datetime.combine(next_day, t))
            
        return sorted(result)

    def _parse_html_weekly_schedule(self, html: str) -> dict[str, list[datetime.time]]:
        """Parse the weekly HTML table into three categories: semaine, samedi, dimanche."""
        soup = BeautifulSoup(html, 'html.parser')
        weekly_data = {'semaine': [], 'samedi': [], 'dimanche': []}
        
        # Search for tables that contain category markers in their bold headers
        tables = soup.find_all('table')
        
        for table in tables:
            header_row = table.find('tr')
            if not header_row:
                continue
            
            # Categories are often in <b>Semaine</b>, <b>Samedi</b>, etc.
            category_cells = table.find_all('b')
            category = None
            for cell in category_cells:
                text = cell.get_text(strip=True).lower()
                if 'semaine' in text:
                    category = 'semaine'
                    break
                elif 'samedi' in text:
                    category = 'samedi'
                    break
                elif 'dimanche' in text:
                    category = 'dimanche'
                    break
            
            if category:
                # We found a schedule table for a category
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    for cell in cells:
                        time_str = cell.get_text(strip=True)
                        # Match HH:MM format
                        match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
                        if match:
                            h, m = map(int, match.groups())
                            # Handle times past midnight (e.g. 25:15)
                            weekly_data[category].append(datetime.time(h % 24, m))
        
        # Deduplicate and sort
        for cat in weekly_data:
            weekly_data[cat] = sorted(set(weekly_data[cat]))

        return weekly_data

    def get_schedule(self, stop_id: int, date: datetime.date, feed_id: int = 15) -> list[dict[str, Any]]:
        """Smart fallback: discovers patterns for the stop and fetches all schedules."""
        if TRANSIT != "RTL":
            _LOGGER.debug(f"Live scraper not available for {TRANSIT}")
            return []
            
        stop_code = self.get_stop_code_from_id(stop_id)
        if not stop_code:
            _LOGGER.error(f"Could not map internal stop_id {stop_id} to a stop code.")
            return []
            
        _LOGGER.info(f"Fallback: Discovered stop code {stop_code} for ID {stop_id}")
        patterns = self.get_stop_patterns(stop_code, stop_id=stop_id)
        
        if not patterns:
            _LOGGER.warning(f"No patterns found for stop code {stop_code}")
            return []
            
        all_arrivals = []
        # Filter for target direction if requested
        for p in patterns:
            if TARGET_DIRECTION and TARGET_DIRECTION not in p['ligne']:
                _LOGGER.debug(f"Skipping pattern {p['ligne']} (not {TARGET_DIRECTION})")
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
