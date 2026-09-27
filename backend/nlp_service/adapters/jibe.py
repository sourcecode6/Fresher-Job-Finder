import time
from datetime import datetime
from backend.nlp_service.utils import queue_http

def scrape_jibe(company, filters):
    # Keysight uses Jibe API
    endpoint = f"https://careers.{company.get('sf_domain', 'keysight')}.com/api/jobs"
    jobs = []
    
    locations = filters.get('locations', [''])
    if not locations:
        locations = ['']
        
    for loc in locations:
        page = 1
        while True:
            payload = {
                "page": page,
                "q": filters.get('searchText', '')
            }
            
            if loc:
                payload['location'] = loc
                
            res = queue_http(endpoint, method='GET', params=payload, headers={'Accept': 'application/json'})
            if res.status_code != 200:
                if page == 1:
                    raise Exception(f"{res.status_code} Client Error: {res.reason} for url: {res.url}")
                break
                
            data = res.json()
            hits = data.get('jobs', [])
            
            if not hits:
                break
                
            for hit in hits:
                d = hit.get('data', {})
                jobs.append({
                    "companyName": company['name'],
                    "jobId": str(d.get('req_id', '')),
                    "jobTitle": d.get('title', 'Unknown Title'),
                    "location": d.get('full_location', ''),
                    "department": d.get('department', ''),
                    "postedDate": d.get('update_date', datetime.utcnow().isoformat() + 'Z'),
                    "employmentType": 'Full-time',
                    "jobDescription": d.get('description', ''),
                    "url": d.get('apply_url', company.get('careerUrl')),
                    "applyUrl": d.get('apply_url', company.get('careerUrl'))
                })
                
            page += 1
            time.sleep(3) # Compliance rate limiting
            
    return jobs
