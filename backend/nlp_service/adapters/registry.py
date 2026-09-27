from backend.nlp_service.adapters.amd import scrape_amd
from backend.nlp_service.adapters.apple import scrape_apple
from backend.nlp_service.adapters.arm import scrape_arm
from backend.nlp_service.adapters.ashbyhq import scrape_ashbyhq
from backend.nlp_service.adapters.cisco import scrape_cisco
from backend.nlp_service.adapters.eightfold import scrape_eightfold
from backend.nlp_service.adapters.eightfold_v2 import scrape_eightfold_v2
from backend.nlp_service.adapters.greenhouse import scrape_greenhouse
from backend.nlp_service.adapters.ibm import scrape_ibm
from backend.nlp_service.adapters.smartrecruiters import scrape_smartrecruiters
from backend.nlp_service.adapters.workday import scrape_workday
from backend.nlp_service.adapters.successfactors import scrape_successfactors
from backend.nlp_service.adapters.mediatek import scrape_mediatek
from backend.nlp_service.adapters.ti import scrape_ti
from backend.nlp_service.adapters.avature import scrape_avature
from backend.nlp_service.adapters.jibe import scrape_jibe

def get_target_url(ats, company):
    urls = {
        'eightfold': lambda c: f"{c.get('eightfoldBaseUrl')}/api/pcsx/search",
        'eightfold_v2': lambda c: f"{c.get('eightfoldBaseUrl')}/api/apply/v2/jobs",
        'workday': lambda c: f"https://{c.get('workdaySubdomain')}.myworkdayjobs.com/wday/cxs/{c.get('workdayTenant')}/{c.get('workdaySite')}/jobs",
        'smartrecruiters': lambda c: f"https://api.smartrecruiters.com/v1/companies/{c.get('smartRecruitersId')}/postings",
        'ashbyhq': lambda c: f"https://api.ashbyhq.com/posting-api/job-board/{c.get('board_token')}?includeMultipleLocations=true",
        'greenhouse': lambda c: f"https://boards-api.greenhouse.io/v1/boards/{c.get('board_token')}/jobs?content=true",
        'successfactors': lambda c: f"https://careers.{c.get('sf_domain')}.com/search/",
        'mediatek': lambda c: c.get('careerUrl'),
        'ti': lambda c: c.get('careerUrl'),
        'avature': lambda c: c.get('careerUrl'),
        'jibe': lambda c: c.get('careerUrl')
    }
    if ats in urls:
        return urls[ats](company)
    return company.get('careerUrl')

def run_adapter(ats, company, filters):
    adapters = {
        'amd': scrape_amd,
        'apple': scrape_apple,
        'arm': scrape_arm,
        'ashbyhq': scrape_ashbyhq,
        'cisco': scrape_cisco,
        'eightfold': scrape_eightfold,
        'eightfold_v2': scrape_eightfold_v2,
        'greenhouse': scrape_greenhouse,
        'ibm': scrape_ibm,
        'smartrecruiters': scrape_smartrecruiters,
        'workday': scrape_workday,
        'successfactors': scrape_successfactors,
        'mediatek': scrape_mediatek,
        'ti': scrape_ti,
        'avature': scrape_avature,
        'jibe': scrape_jibe
    }
    if ats in adapters:
        return adapters[ats](company, filters)
    raise ValueError(f"Unknown ATS type: {ats}")
