import time
import json
import re
from datetime import datetime
from backend.nlp_service.utils import queue_http

def scrape_lever(company, filters):
    lever_company = company.get('lever_company') or company.get('leverSite')
    if not lever_company:
        print(f"[{company['name']}] Missing lever_company or leverSite in config")
        return []

    endpoint = f"https://api.lever.co/v0/postings/{lever_company}?mode=json"
    
    res = queue_http(endpoint)
    if res.status_code != 200:
        res.raise_for_status()

    postings = res.json()
    jobs = []
    
    locations_filter = filters.get('locations') or ([filters.get('location')] if filters.get('location') else [])

    for p in postings:
        categories = p.get('categories') or {}
        loc = categories.get('location', '')
        
        # Apply location filter if exists
        if locations_filter:
            loc_lower = loc.lower()
            all_locs = [l.lower() for l in categories.get('allLocations', [])]
            matched = any(f.lower() in loc_lower or any(f.lower() in al for al in all_locs) for f in locations_filter)
            if not matched:
                continue

        job_id = p.get('id', str(int(time.time())))
        title = p.get('text', 'Unknown Title')
        job_url = p.get('hostedUrl', company.get('careerUrl', ''))
        apply_url = p.get('applyUrl', job_url)
        
        # Build description text from plain content or opening
        desc_parts = []
        if p.get('descriptionPlain'):
            desc_parts.append(p['descriptionPlain'])
        if p.get('openingPlain'):
            desc_parts.append(p['openingPlain'])
        if p.get('additionalPlain'):
            desc_parts.append(p['additionalPlain'])
            
        desc_text = "\n\n".join(desc_parts).strip()
        if not desc_text and p.get('description'):
            desc_text = re.sub(r'<[^>]+>', ' ', p.get('description', '')).strip()

        # Extract postedDate
        created_at_ms = p.get('createdAt')
        if created_at_ms:
            posted_date = datetime.utcfromtimestamp(created_at_ms / 1000.0).isoformat() + 'Z'
        else:
            posted_date = datetime.utcnow().isoformat() + 'Z'

        jobs.append({
            "companyName": company['name'],
            "jobId": str(job_id),
            "jobTitle": title,
            "location": loc,
            "department": categories.get('department') or categories.get('team') or '',
            "postedDate": posted_date,
            "employmentType": categories.get('commitment', 'Full-time'),
            "jobDescription": desc_text,
            "url": job_url,
            "applyUrl": apply_url
        })

    return jobs

