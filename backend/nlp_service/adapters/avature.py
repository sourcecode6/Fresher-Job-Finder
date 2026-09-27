import time
from datetime import datetime
from backend.nlp_service.utils import queue_http

def scrape_avature(company, filters):
    # Synopsys uses avature
    endpoint = company.get('careerUrl', '').replace('/careers', '/api/jobs')
    jobs = []
    
    res = queue_http(endpoint, method='GET')
    if res.status_code == 200:
        pass
        # TODO: Add specific Avature JSON parsing logic during testing phase
        
    return jobs
