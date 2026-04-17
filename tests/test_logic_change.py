
import datetime
import logging
import os

# Mock environment variable for the test
os.environ["RETRIEVAL_METHOD"] = "live"

from rtl_schedule.const import RETRIEVAL_METHOD
from rtl_schedule.data_parser import ParseRTLData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtl-schedule")

def test_retrieval_logic():
    print(f"Testing with RETRIEVAL_METHOD: {RETRIEVAL_METHOD}")
    
    parser = ParseRTLData()
    stop_id = 2752 # Stop 32752
    now = datetime.datetime(2026, 3, 30, 12, 0)
    
    # This should log "Skipping GTFS check"
    next_stop = parser.get_next_stop(stop_id, now)
    
    if next_stop is not None:
        print(f"Result method: {next_stop.get('retrieve_method')}")
    else:
        print("No next stop found.")

if __name__ == "__main__":
    test_retrieval_logic()
