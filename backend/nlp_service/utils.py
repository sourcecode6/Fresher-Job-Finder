import html
import os
import re
import json
import time
import sqlite3
import base64
import urllib.robotparser
import socket
import urllib3.util.connection as connection
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from backend.nlp_service.logger import log_scrape_info, log_scrape_error, log_nlp_event
from backend.nlp_service.config import load_settings

# Force IPv4 to bypass getaddrinfo/NameResolutionError dual-stack DNS lookup failures on Windows
connection.allowed_gai_family = lambda: socket.AF_INET



# Global user agent
USER_AGENT = 'AIJobScraperBot/1.0 (Personal use job tracker; not for commercial use)'
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Robots.txt cache
ROBOTS_CACHE = {}




# Load skills vocab
def load_skills_vocab():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vocab_path = os.path.abspath(os.path.join(current_dir, '..', 'data', 'skills_vocab.json'))
    try:
        with open(vocab_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: skills_vocab.json not found: {e}")
        return {"skills": [], "aliases": {}}

VOCAB = load_skills_vocab()
ALL_SKILLS = VOCAB.get('skills', [])
ALIASES = VOCAB.get('aliases', {})

# Build flat lists for extraction
SKILL_LOWER_MAP = {s.lower(): s for s in ALL_SKILLS}
ALIAS_LOWER_MAP = {alias.lower(): canonical for alias, canonical in ALIASES.items()}

def escape_regex(term):
    return re.escape(term)

def build_regex(term):
    escaped = escape_regex(term)
    # Match boundaries for word vs non-word chars
    start = '(?<![a-zA-Z0-9_])' if re.match(r'^[a-zA-Z0-9_]', term) else ''
    end = '(?![a-zA-Z0-9_])' if re.search(r'[a-zA-Z0-9_]$', term) else ''
    return re.compile(start + escaped + end, re.IGNORECASE)

def extract_skills(text):
    if not text:
        return []
    lower = text.lower()
    found = set()

    for lower_skill, canonical in SKILL_LOWER_MAP.items():
        regex = build_regex(lower_skill)
        if regex.search(lower):
            found.add(canonical)

    for alias, canonical in ALIAS_LOWER_MAP.items():
        regex = build_regex(alias)
        if regex.search(lower):
            found.add(canonical)

    return list(found)

def derive_yoe_from_title(title):
    if not title:
        return None
    t = title.lower()

    # 1. Explicit years mentioned directly in title (e.g. '8-12 yrs', '7+ years', '4-8 Yrs', '10+ years')
    range_match = re.search(r'(\d+)\s*(?:-|to)\s*\d+\s*(?:yrs?|years?)', t)
    if range_match:
        return int(range_match.group(1))

    plus_match = re.search(r'(\d+)\s*\+?\s*(?:yrs?|years?)', t)
    if plus_match:
        return int(plus_match.group(1))

    # 2. Executive / High Leadership
    if re.search(r'\b(director|vice president|vp|head of)\b', t):
        return 10

    # 3. Principal / Architect
    if re.search(r'\b(principal|architect|fellow)\b', t):
        return 8

    # 4. Staff / Lead / Manager
    if re.search(r'\b(staff|lead|manager|tech lead|team lead)\b', t):
        return 6

    # 5. Senior
    if re.search(r'\b(senior|sr\b|sr\.)\b', t):
        return 4

    # 6. Level numbers (e.g. Engineer III / Level 3 vs Level 2 vs Level 1)
    if re.search(r'\b(?:engineer|developer|sde|mts)\s*(?:3|iii|iv|4)\b|\b(?:l3|l4|level\s*[34])\b', t):
        return 4
    if re.search(r'\b(?:engineer|developer|sde|mts)\s*(?:2|ii)\b|\b(?:l2|level\s*2|mid-level)\b', t):
        return 2
    if re.search(r'\b(?:associate|junior|jr\b|jr\.|entry|entry-level)\b|\b(?:engineer|developer|sde|mts)\s*(?:1|i)\b|\b(?:l1|level\s*1)\b', t):
        return 0

    # 7. Intern / College Grad / Trainee / Fresher
    if re.search(r'\b(intern|internship|trainee|graduate|campus|fresher|college grad|new grad|university grad)\b', t):
        return 0

    return None

def extract_yoe(text, title=None):
    title_yoe = derive_yoe_from_title(title) if title else None

    if not text:
        return title_yoe

    pattern = r'(?:minimum\s+(?:of\s+)?|min\s+)?(\d+)(?:\s*(?:-|to)\s*(\d+))?\s*\+?\s*years?'
    matches = []
    for match in re.finditer(pattern, text, re.IGNORECASE):
        min_val = int(match.group(1))
        start_idx = max(0, match.start() - 60)
        end_idx = min(len(text), match.end() + 40)
        context = text[start_idx:end_idx].lower()
        is_overall = any(w in context for w in ['total', 'overall', 'minimum', 'min', 'at least'])
        matches.append({'minVal': min_val, 'isOverall': is_overall})

    desc_yoe = None
    if matches:
        overall_match = next((m for m in matches if m['isOverall']), None)
        if overall_match:
            desc_yoe = overall_match['minVal']
        else:
            reasonable_matches = [m for m in matches if m['minVal'] <= 15]
            if reasonable_matches:
                desc_yoe = reasonable_matches[0]['minVal']

    if desc_yoe is not None and title_yoe is not None:
        return max(desc_yoe, title_yoe)
    return desc_yoe if desc_yoe is not None else title_yoe

# Robots.txt helpers
class RobotsTxtParser:
    def __init__(self, content):
        self.rules = {}
        self.crawl_delays = {}
        self.parse(content)

    def parse(self, content):
        current_agents = []
        for line in content.splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            key = parts[0].strip().lower()
            val = parts[1].strip()
            if key == 'user-agent':
                agent = val.lower()
                current_agents.append(agent)
                if agent not in self.rules:
                    self.rules[agent] = []
            elif key in ('allow', 'disallow'):
                for agent in current_agents:
                    self.rules[agent].append((key == 'allow', val))
            elif key == 'crawl-delay':
                try:
                    delay = float(val)
                    for agent in current_agents:
                        self.crawl_delays[agent] = delay
                except ValueError:
                    pass

    def is_allowed(self, user_agent, url):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if not path:
            path = '/'
        if parsed.query:
            path += '?' + parsed.query
        
        user_agent = user_agent.lower()
        agent_to_use = next((a for a in self.rules if a != '*' and a in user_agent), '*' if '*' in self.rules else None)
        if not agent_to_use:
            return True

        matching_rules = []
        for is_allow, pattern in self.rules[agent_to_use]:
            regex_parts = []
            for char in pattern:
                if char == '*':
                    regex_parts.append('.*')
                elif char == '$':
                    regex_parts.append('$')
                else:
                    regex_parts.append(re.escape(char))
            regex_str = '^' + ''.join(regex_parts)
            if not pattern.endswith('$'):
                regex_str += '.*'
            if re.match(regex_str, path):
                matching_rules.append((is_allow, pattern))

        if not matching_rules:
            return True

        matching_rules.sort(key=lambda x: (len(x[1]), x[0]), reverse=True)
        return matching_rules[0][0]

    def get_crawl_delay(self, user_agent):
        user_agent = user_agent.lower()
        for agent in self.crawl_delays:
            if agent != '*' and agent in user_agent:
                return self.crawl_delays[agent]
        return self.crawl_delays.get('*')

def fetch_robots(career_url):
    try:
        parsed_url = urllib.parse.urlparse(career_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

        if robots_url in ROBOTS_CACHE:
            return ROBOTS_CACHE[robots_url]

        req = urllib.request.Request(robots_url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read().decode('utf-8', errors='ignore')
        
        parser = RobotsTxtParser(content)
        ROBOTS_CACHE[robots_url] = parser
        return parser
    except Exception:
        return None

def is_allowed(target_url):
    rp = fetch_robots(target_url)
    if not rp:
        return True
    return rp.is_allowed(USER_AGENT, target_url)

def get_crawl_delay_ms(career_url, default_delay):
    rp = fetch_robots(career_url)
    if not rp:
        return default_delay
    delay = rp.get_crawl_delay(USER_AGENT)
    if delay is not None:
        return int(delay * 1000)
    return default_delay
    return default_delay

# Global connection pool
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=1)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

# Custom HTTP rate-limited queue simulation
GLOBAL_LAST_REQUEST_TIME = 0.0

def queue_http(url, method='GET', max_retries=3, **kwargs):
    global GLOBAL_LAST_REQUEST_TIME
    settings = load_settings()
    delay_sec = settings['globalRequestDelayMs'] / 1000.0

    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 15)
    
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        # Enforce global rate-limit gap
        elapsed = time.time() - GLOBAL_LAST_REQUEST_TIME
        if elapsed < delay_sec:
            time.sleep(delay_sec - elapsed)
            
        try:
            if method.upper() == 'POST':
                response = http_session.post(url, **kwargs)
            else:
                response = http_session.get(url, **kwargs)
                
            GLOBAL_LAST_REQUEST_TIME = time.time()
            
            if response.status_code == 429:
                log_scrape_info(f"Rate limited (429) on {url}. Retrying... ({attempt}/{max_retries})")
                time.sleep(delay_sec * attempt * 2) # Exponential backoff
                continue
                
            return response
            
        except requests.exceptions.RequestException as e:
            GLOBAL_LAST_REQUEST_TIME = time.time()
            if attempt < max_retries:
                log_scrape_info(f"Network error on {url}: {e}. Retrying... ({attempt}/{max_retries})")
                time.sleep(delay_sec * attempt)
                continue
            raise e
            
    raise Exception(f"Max retries ({max_retries}) exceeded for {url}")



def clean_html(html_str: str) -> str:
    if not html_str:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_str)
    return html.unescape(text).strip()

def filter_by_location(job_location: str, location_filters: list) -> bool:
    if not location_filters:
        return True
    if not job_location:
        return False
    loc_lower = job_location.lower()
    return any(f.lower() in loc_lower for f in location_filters)

def generate_fallback_job_id(prefix: str = "") -> str:
    suffix = str(int(time.time()))
    if prefix:
        prefix_clean = prefix.replace(' ', '-').lower()
        return f"{prefix_clean}-{suffix}"
    return suffix

class AdapterError(Exception):
    """Custom exception for adapter failures."""
    pass
