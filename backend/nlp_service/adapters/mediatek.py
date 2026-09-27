import time
from datetime import datetime
from backend.nlp_service.utils import queue_http

def scrape_mediatek(company, filters):
    endpoint = "https://careers.mediatek.com/api/jobs"
    jobs = []
    
    payload = {}
    
    res = queue_http(endpoint, method='POST', json=payload)
    if res.status_code == 200:
        pass
        # TODO: Add specific JSON parsing logic during testing phase
        
    return jobs
