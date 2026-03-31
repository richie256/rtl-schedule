
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import datetime
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtl-debug")

class HostnameIgnoreAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            assert_hostname=False,
            **pool_kwargs
        )

def debug_scrape():
    BASE_URL = "https://madprep_i.rtl-longueuil.qc.ca/madOper.php"
    session = requests.Session()
    session.mount(BASE_URL, HostnameIgnoreAdapter())
    
    # 1. Get buildtime
    params = {"q": "routers", "s": "RTL", "api": "0"}
    res = session.get(BASE_URL, params=params)
    buildtime = res.json().get("buildtime")
    logger.info(f"Buildtime: {buildtime}")
    
    # 1.5 Get stops mapping
    params = {"q": "stops", "s": "RTL", "web": ""}
    res = session.get(BASE_URL, params=params)
    logger.info(f"Stops data length: {len(res.text)}")
    print("Stops snippet:", res.text[:200])
    
    # Find internal IDs for 32752
    import re
    # Entry format: internal_id,lat,lon,name,code,stop_code
    # Example: 15:32752,45.4,-73.4,Stop Name,32752,32752
    matches = [entry for entry in res.text.split(';') if '32752' in entry]
    print("Matches for 32752:", matches)
    
    # 2. Get patterns for stop 32752 using found internal IDs
    if matches:
        p_id = matches[0].split(',')[0]
        logger.info(f"Using internal ID: {p_id}")
        params = {"q": "stops_patterns", "p": p_id, "s": "RTL", "web": ""}
        res = session.get(BASE_URL, params=params)
        # ... rest unchanged
    logger.info(f"Patterns HTML length: {len(res.text)}")
    print("Patterns HTML snippet:", res.text[:500])
    
    import re
    pattern = re.compile(r"urlHoraireArret\((.*?)\);")
    matches = pattern.findall(res.text)
    print("Matches:", matches)
    
    # 3. Try to fetch schedule for the first pattern found
    if matches:
        args = [arg.strip().strip("'") for arg in matches[0].split(',')]
        # args: stop, pattern, code, desc, ligne, leJour
        print("Args for first match:", args)
        
        # First, fetch the landing page to find the correct 't' parameter
        landing_params = {
            "q": "stops_stoptimes",
            "p": args[0],
            "s": "RTL",
            "web": "",
            "pp": args[1],
            "l": args[4]
        }
        logger.info(f"Fetching landing page with params: {landing_params}")
        res = session.get(BASE_URL, params=landing_params)
        
        # Parse landing page for the correct link
        soup_landing = BeautifulSoup(res.text, 'html.parser')
        links = soup_landing.find_all('a', href=re.compile(r'q=stops_stoptimes'))
        
        target_url = None
        for link in links:
            href = link.get('href')
            if "regulier" in href:
                # Basic check: does "30 mars" fall into this range? 
                # For now, let's just take the first one that mentions "5 janvier" to "5 avril"
                if "5 janvier" in href and "5 avril" in href:
                    target_url = href
                    break
        
        if not target_url and links:
            target_url = links[0].get('href')
            
        if target_url:
            if target_url.startswith('/'):
                target_url = "https://madprep_i.rtl-longueuil.qc.ca" + target_url
            else:
                target_url = "https://madprep_i.rtl-longueuil.qc.ca/" + target_url
                
            logger.info(f"Fetching actual schedule from: {target_url}")
            res = session.get(target_url)
            logger.info(f"Actual Schedule HTML length: {len(res.text)}")
            
            with open("debug_schedule.html", "w") as f:
                f.write(res.text)
            
            soup = BeautifulSoup(res.text, 'html.parser')
            tables = soup.find_all('table')
            logger.info(f"Found {len(tables)} tables in actual schedule")
            for i, table in enumerate(tables):
                # Check for category markers
                category_cells = table.find_all('b')
                for cell in category_cells:
                    if any(cat in cell.get_text().lower() for cat in ['semaine', 'samedi', 'dimanche']):
                        logger.info(f"Table {i} is a category table: {cell.get_text()}")
                        # Print some times
                        times = [td.get_text(strip=True) for td in table.find_all('td') if re.match(r'^\d{1,2}:\d{2}$', td.get_text(strip=True))]
                        logger.info(f"First 5 times: {times[:5]}")
        if i < 5:
             logger.info(f"Table {i} snippet: {str(table)[:200]}")

    with open("debug_output.html", "w") as f:
        f.write(res.text)

if __name__ == "__main__":
    debug_scrape()
