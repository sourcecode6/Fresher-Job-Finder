import time
from datetime import datetime
from bs4 import BeautifulSoup
from backend.nlp_service.utils import queue_http

def scrape_successfactors(company, filters):
    domain = company.get('sf_domain')
    endpoint = f"https://careers.{domain}.com/search/"
    
    jobs = []
    startrow = 0
    
    while True:
        payload = {
            "q": filters.get('searchText', ''),
            "startrow": startrow
        }
        
        if filters.get('locations'):
            payload['locationsearch'] = filters['locations'][0]
            
        res = queue_http(endpoint, method='GET', params=payload)
        if res.status_code != 200:
            if startrow == 0:
                raise Exception(f"{res.status_code} Client Error: {res.reason} for url: {res.url}")
            break
            
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('tr.data-row')
        
        if not rows:
            break
            
        for row in rows:
            title_a = row.select_one('.jobTitle-link')
            if not title_a: continue
            
            url = f"https://careers.{domain}.com" + title_a['href']
            title = title_a.get_text(strip=True)
            
            loc_span = row.select_one('.jobLocation')
            loc = loc_span.get_text(strip=True) if loc_span else ''
            
            date_span = row.select_one('.jobDate')
            date_str = date_span.get_text(strip=True) if date_span else datetime.utcnow().isoformat() + 'Z'
            
            job_id = url.split('/')[-2] if len(url.split('/')) > 2 else title.replace(' ', '-')
            
            jobs.append({
                "companyName": company['name'],
                "jobId": str(job_id),
                "jobTitle": title,
                "location": loc,
                "department": row.select_one('.jobFacility').get_text(strip=True) if row.select_one('.jobFacility') else '',
                "postedDate": date_str,
                "employmentType": 'Full-time',
                "jobDescription": '',
                "url": url,
                "applyUrl": url
            })
            
        startrow += 25
        time.sleep(3)
        
    return jobs
