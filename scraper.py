#!/usr/bin/env python3
"""
NWA Job Tracker — Schools + Community + IT
Three categories, 35+ sources, daily email digest.
"""

import requests
from bs4 import BeautifulSoup
import json, os, hashlib, logging, smtplib, re, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RECIPIENT          = "bthompsonnwa@gmail.com"
SENDER             = "bthompsonnwa@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
JOBS_FILE          = "docs/jobs.json"
DASHBOARD_URL      = "https://bthompsonnwa.github.io/job-tracker/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ──────────────────────────────────────────────────────────────────────────────
# KEYWORD FILTERS
# ──────────────────────────────────────────────────────────────────────────────

# Primary skillset — jobs matching these go in Schools or Community tabs
INCLUDE_KEYWORDS = [
    "makerspace", "maker space", "maker lab",
    "stem lab", "stem coordinator", "stem teacher", "steam teacher",
    "fabrication lab", "fab lab", "innovation lab",
    "digital fabrication", "3d print", "laser engraving", "laser cutting",
    "cnc", "vinyl cutting", "large-format",
    "arduino", "robotics", "electronics teacher",
    "audio/video", "audio visual", "audiovisual", "a/v technician",
    "av technician", "av coordinator", "av specialist", "av manager",
    "av tech", "av teacher", "av support",
    "media production", "media technician", "media technology",
    "broadcast technician", "broadcast specialist", "broadcast production",
    "production specialist", "production coordinator", "production technician",
    "video production", "audio production", "recording studio",
    "multimedia", "multimedia specialist", "multimedia coordinator",
    "library media", "media specialist", "digital media",
    "librarian", "library assistant", "library technician", "library coordinator",
    "technology integration", "technology specialist", "technology coordinator",
    "technology teacher", "technology support", "technology coach",
    "instructional technology", "digital learning", "digital services",
    "cte teacher", "cte coordinator", "career and technical",
    "after school coordinator", "after-school coordinator",
    "cclc", "21st cclc", "21cclc", "21st century",
    "college and career", "college & career", "career coach", "career center",
    "program coordinator", "program director", "program specialist",
    "workshop facilitator", "workshop instructor", "workshop coordinator",
    "learning coordinator", "instructional design", "instructional designer",
    "curriculum developer", "curriculum coordinator", "curriculum designer",
    "theater technical", "technical theatre", "technical theater",
    "stagecraft", "theatre arts", "performing arts coordinator",
    "computer science", "computer teacher", "coding teacher",
    "tinkercad", "blender", "adobe creative",
    "community outreach", "volunteer coordinator", "event coordinator",
    "outreach coordinator", "community program", "public services",
    "communications coordinator", "communications specialist",
    "graphic designer", "graphic design", "web designer",
    "content creator", "social media coordinator",
    "training coordinator", "workforce development",
    "youth program", "youth services", "youth coordinator",
    "innovation coach", "tech coach", "maker education",
]

# IT jobs — matches go in the IT tab regardless of source
IT_KEYWORDS = [
    "help desk", "help-desk", "service desk", "service-desk",
    "desktop support", "it support", "it technician", "it specialist",
    "it assistant", "it coordinator", "it manager", "it director",
    "systems administrator", "sysadmin", "network technician",
    "network administrator", "network engineer", "network support",
    "computer technician", "hardware technician", "field technician",
    "technical support", "tech support", "tier 1", "tier 2", "tier i", "tier ii",
    "systems support", "application support", "software support",
    "cybersecurity", "cyber security", "information security", "security analyst",
    "data analyst", "database administrator", "dba",
    "cloud support", "cloud administrator", "cloud engineer",
    "sharepoint", "microsoft 365 admin", "office 365 admin",
    "active directory", "azure admin", "endpoint management",
    "information technology", "information systems",
    "it infrastructure", "it operations",
]

HARD_EXCLUDE_KEYWORDS = [
    "bus driver", "bus monitor",
    "custodian", "custodial",
    "food service", "cafeteria worker",
    "school nurse", "registered nurse", " rn ",
    "school psychologist", "psychologist",
    "speech language", "speech-language",
    "occupational therapist", "physical therapist",
    "groundskeeper", "maintenance mechanic", "plumber", "electrician",
    "bookkeeper", "accountant", "accounts payable",
    "wastewater", "water treatment", "utility worker",
    "police officer", "firefighter", "dispatcher",
    "animal control", "code enforcement",
    "truck driver", "cdl driver", "freight driver",
]

# ──────────────────────────────────────────────────────────────────────────────
# SOURCE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

APPLITRACK_DISTRICTS = [
    {"id": "bentonville", "name": "Bentonville SD",
     "list_url": "https://www.applitrack.com/bentonville/onlineapp/default.aspx?all=1"},
    {"id": "farmcards",   "name": "Farmington SD",
     "list_url": "https://www.applitrack.com/farmcards/onlineapp/jobpostings/view.asp?internaltransferform.Url=&all=1"},
]

TEDK12_DISTRICTS = [
    {"name": "Elkins SD",    "url": "https://elkinsdistrict.tedk12.com/hire/index.aspx"},
    {"name": "Greenland SD", "url": "https://greenlandschools.tedk12.com/hire/index.aspx"},
]

SCHOOLSPRING_DISTRICTS = [
    {"subdomain": "decatursd",     "name": "Decatur SD"},
    {"subdomain": "gravette",      "name": "Gravette SD"},
    {"subdomain": "gentry",        "name": "Gentry SD"},
    {"subdomain": "district",      "name": "District SD"},
    {"subdomain": "hsd",           "name": "Huntsville SD"},
    {"subdomain": "pearidge",      "name": "Pea Ridge SD"},
    {"subdomain": "pgtigers",      "name": "Prairie Grove SD"},
    {"subdomain": "rogersschools", "name": "Rogers SD"},
    {"subdomain": "siloamschools", "name": "Siloam Springs SD"},
    {"subdomain": "lisaacademy",   "name": "LISA Academy"},
]

WORKDAY_SOURCES = [
    {"name": "University of Arkansas (UAF)", "category": "community",
     "api_url":  "https://uasys.wd5.myworkdayjobs.com/wday/cxs/uasys/UAF_External_Career_Site/jobs",
     "base_url": "https://uasys.wd5.myworkdayjobs.com/en-US/UAF_External_Career_Site"},
    {"name": "NWACC", "category": "community",
     "api_url":  "https://nwacc.wd1.myworkdayjobs.com/wday/cxs/nwacc/NWACC_External_Career_Site/jobs",
     "base_url": "https://nwacc.wd1.myworkdayjobs.com/en-US/NWACC_External_Career_Site"},
    {"name": "UA System", "category": "community",
     "api_url":  "https://uasys.wd5.myworkdayjobs.com/wday/cxs/uasys/UASYS/jobs",
     "base_url": "https://uasys.wd5.myworkdayjobs.com/en-US/UASYS"},
    {"name": "J.B. Hunt", "category": "it",
     "api_url":  "https://jbhunt.wd1.myworkdayjobs.com/wday/cxs/jbhunt/JBH_Jobs/jobs",
     "base_url": "https://jbhunt.wd1.myworkdayjobs.com/en-US/JBH_Jobs"},
]

ALL_SOURCES = [
    # Schools
    {"name": "Bentonville SD",          "url": "https://www.applitrack.com/bentonville/onlineapp/default.aspx?all=1",                         "category": "school"},
    {"name": "Farmington SD",           "url": "https://www.applitrack.com/farmcards/onlineapp/jobpostings/view.asp?all=1",                    "category": "school"},
    {"name": "Elkins SD",               "url": "https://elkinsdistrict.tedk12.com/hire/index.aspx",                                           "category": "school"},
    {"name": "Greenland SD",            "url": "https://greenlandschools.tedk12.com/hire/index.aspx",                                         "category": "school"},
    {"name": "Decatur SD",              "url": "https://decatursd.schoolspring.com/",                                                          "category": "school"},
    {"name": "Gravette SD",             "url": "https://gravette.schoolspring.com/",                                                           "category": "school"},
    {"name": "Gentry SD",               "url": "https://gentry.schoolspring.com/",                                                             "category": "school"},
    {"name": "District SD",             "url": "https://district.schoolspring.com/",                                                           "category": "school"},
    {"name": "Huntsville SD",           "url": "https://hsd.schoolspring.com/",                                                                "category": "school"},
    {"name": "Pea Ridge SD",            "url": "https://pearidge.schoolspring.com/",                                                           "category": "school"},
    {"name": "Prairie Grove SD",        "url": "https://pgtigers.schoolspring.com/",                                                           "category": "school"},
    {"name": "Rogers SD",               "url": "https://rogersschools.schoolspring.com/",                                                      "category": "school"},
    {"name": "Siloam Springs SD",       "url": "https://siloamschools.schoolspring.com/",                                                      "category": "school"},
    {"name": "Lincoln Consolidated SD", "url": "https://careers.smartrecruiters.com/Lincoln2",                                                 "category": "school"},
    {"name": "Springdale SD",           "url": "https://apply.sdale.org/winocular/workspace/wSpace.exe?Action=wsJobsMain",                    "category": "school"},
    {"name": "West Fork SD",            "url": "https://flowpoint.wftigers.org/careers/opportunities/",                                       "category": "school"},
    {"name": "LISA Academy",            "url": "https://lisaacademy.schoolspring.com/",                                                        "category": "school"},
    {"name": "Haas Hall Academy",       "url": "https://haashall.org/welcome__trashed/employment/",                                           "category": "school"},
    {"name": "Thaden School",           "url": "https://www.thadenschool.org/about/career-opportunities",                                     "category": "school"},
    # Community
    {"name": "Rogers (City)",           "url": "https://www.rogersar.gov/Jobs.aspx",                                                          "category": "community"},
    {"name": "Bentonville (City)",      "url": "https://www.bentonvillear.com/jobs.aspx",                                                      "category": "community"},
    {"name": "City of Bella Vista",     "url": "https://recruiting.paylocity.com/recruiting/jobs/All/b1e8c19e-977f-41ec-89e7-a138ab6e72eb/City-of-Bella-Vista", "category": "community"},
    {"name": "Springdale Public Library","url": "https://springdalelibrary.org/employment/",                                                  "category": "community"},
    {"name": "Jones Center",            "url": "https://secure7.saashr.com/ta/6214802.careers?CareersSearch=&ein_id=119006097&lang=en-US",    "category": "community"},
    {"name": "University of Arkansas (UAF)", "url": "https://uasys.wd5.myworkdayjobs.com/UAF_External_Career_Site",                          "category": "community"},
    {"name": "NWACC",                   "url": "https://nwacc.wd1.myworkdayjobs.com/NWACC_External_Career_Site",                              "category": "community"},
    {"name": "UA System",               "url": "https://uasys.wd5.myworkdayjobs.com/UASYS",                                                   "category": "community"},
    {"name": "Arkansas State Univ.",    "url": "https://phe.tbe.taleo.net/phe02/ats/careers/v2/searchResults?org=ARKASTAT2&cws=40",           "category": "community"},
    {"name": "Arkansas Tech Univ.",     "url": "https://atu.csod.com/ux/ats/careersite/1/home?c=atu",                                         "category": "community"},
    {"name": "UCA",                     "url": "https://jobs.uca.edu/postings/search",                                                         "category": "community"},
    {"name": "Hendrix College",         "url": "https://www.hendrix.edu/humanresources/jobs.aspx",                                            "category": "community"},
    {"name": "JBU (Staff)",             "url": "https://www.jbu.edu/human-resources/staff-job-listings/",                                     "category": "community"},
    {"name": "JBU (Faculty)",           "url": "https://www.jbu.edu/human-resources/faculty-job-listings/",                                   "category": "community"},
    {"name": "Carl Albert College",     "url": "https://carlalbert.edu/about-casc/job-openings/",                                             "category": "community"},
    {"name": "ArcBest",                 "url": "https://careers.arcb.com/careersmarketplace/OpenPositions/",                                  "category": "community"},
    {"name": "AR State Jobs",           "url": "https://arcareers.arkansas.gov/search/",                                                       "category": "community"},
    {"name": "ADP (NWA)",               "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=a75698d1-4927-42e2-8b24-4b1e4d60fa54", "category": "community"},
    # IT
    {"name": "VA Arkansas (USAJobs)",   "url": "https://www.usajobs.gov/Search/Results/?j=2299&j=2210&j=1550&j=1598&l=arkansas&d=VA&p=1",   "category": "it"},
    {"name": "J.B. Hunt",               "url": "https://jbhunt.wd1.myworkdayjobs.com/JBH_Jobs",                                              "category": "it"},
]

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def make_id(source, title, url=""):
    return hashlib.md5(f"{source}|{title}|{url}".encode()).hexdigest()[:12]

def categorize(title, extra="", default_category="school"):
    """
    Returns (category, match_reason) or (None, reason) if excluded/no match.
    Primary skillset keywords take precedence over IT keywords.
    """
    combined = (title + " " + extra).lower()
    for kw in HARD_EXCLUDE_KEYWORDS:
        if kw in combined:
            return None, f"excluded:{kw.strip()}"
    for kw in INCLUDE_KEYWORDS:
        if kw in combined:
            return default_category, kw
    for kw in IT_KEYWORDS:
        if kw in combined:
            return "it", kw
    return None, "no_match"

def categorize_it_source(title, extra=""):
    """For dedicated IT sources — only IT keywords filter, result always tagged 'it'."""
    combined = (title + " " + extra).lower()
    for kw in HARD_EXCLUDE_KEYWORDS:
        if kw in combined:
            return None, f"excluded:{kw.strip()}"
    for kw in IT_KEYWORDS:
        if kw in combined:
            return "it", kw
    # Also catch generic tech titles on IT sources
    for kw in ["analyst", "engineer", "developer", "programmer", "administrator",
                "architect", "technologist", "specialist", "coordinator", "manager"]:
        if kw in combined and any(t in combined for t in ["technology", "digital", "computer", "data", "software", "hardware", "system", "network", "cyber", "cloud", "information"]):
            return "it", kw
    return None, "no_match"

def make_job(source, title, url, platform, category="school",
             location="", posted="", match_reason=""):
    return {
        "id":           make_id(source, title, url),
        "title":        title,
        "district":     source,
        "location":     location,
        "url":          url,
        "platform":     platform,
        "category":     category,
        "match_reason": match_reason,
        "posted_date":  posted,
        "first_seen":   datetime.now().strftime("%Y-%m-%d"),
    }

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE) as f:
            return json.load(f)
    return {"last_updated": None, "jobs": [], "sources": []}

def save_jobs(data):
    os.makedirs("docs", exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def pw_get_soup(url, wait=3):
    """Shared Playwright helper."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.warning("Playwright not installed")
        return None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx     = browser.new_context(user_agent=HEADERS["User-Agent"])
            page    = ctx.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                page.wait_for_timeout(5000)
            time.sleep(wait)
            html = page.content()
            browser.close()
        return BeautifulSoup(html, "html.parser")
    except Exception as e:
        log.error(f"Playwright error on {url}: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# SCHOOL SCRAPERS
# ──────────────────────────────────────────────────────────────────────────────

def scrape_applitrack(district):
    name, list_url, did = district["name"], district["list_url"], district["id"]
    jobs = []
    xml_url = f"https://www.applitrack.com/{did}/onlineapp/JobPostingFeed.aspx"
    try:
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and "<item>" in r.text:
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                title = (item.find("title").text or "").strip()
                url   = (item.find("link").text or list_url).strip()
                desc  = (item.find("description").text or "").strip()
                cat, reason = categorize(title, desc)
                if cat:
                    jobs.append(make_job(name, title, url, "AppliTrack", category=cat, match_reason=reason))
            log.info(f"{name}: {len(jobs)} jobs (XML)")
            return jobs
    except Exception as e:
        log.warning(f"{name} XML: {e}")
    try:
        r    = requests.get(list_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not any(x in href for x in ["JobDetails", "ViewJob", "jobpostings"]):
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue
            full_url = href if href.startswith("http") else f"https://www.applitrack.com{href}"
            cat, reason = categorize(title)
            if cat:
                jobs.append(make_job(name, title, full_url, "AppliTrack", category=cat, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs (HTML)")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_tedk12(district):
    name, base_url = district["name"], district["url"]
    jobs = []
    try:
        r    = requests.get(base_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"ViewJob\.aspx")):
            title    = a.get_text(strip=True)
            href     = a["href"]
            full_url = href if href.startswith("http") else base_url.rsplit("/", 1)[0] + "/" + href.lstrip("/")
            row      = a.find_parent("tr")
            cells    = row.find_all("td") if row else []
            posted   = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            location = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            cat, reason = categorize(title)
            if cat:
                jobs.append(make_job(name, title, full_url, "PowerSchool",
                                     category=cat, location=location, posted=posted, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_smartrecruiters():
    name = "Lincoln Consolidated SD"
    url  = "https://careers.smartrecruiters.com/Lincoln2"
    jobs = []
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"jobs\.smartrecruiters\.com")):
            el    = a.find(["h4", "h3", "h2", "strong"])
            title = el.get_text(strip=True) if el else a.get_text(strip=True)
            if not title:
                continue
            cat, reason = categorize(title)
            if cat:
                jobs.append(make_job(name, title, a["href"], "SmartRecruiters",
                                     category=cat, location="Lincoln, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_springdale_sd():
    name = "Springdale SD"
    url  = "https://apply.sdale.org/winocular/workspace/wSpace.exe?Action=wsJobsMain"
    jobs = []
    try:
        r    = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"ViewJobPosting")):
            title = a.get_text(strip=True)
            if not title:
                continue
            m   = re.search(r"ViewJobPosting\('(\w+)'", a["href"])
            pid = m.group(1) if m else ""
            job_url = (f"https://apply.sdale.org/winocular/workspace/wSpace.exe"
                       f"?Action=wsViewPosting&postingID={pid}") if pid else url
            row   = a.find_parent("tr")
            cells = row.find_all("td") if row else []
            jtype  = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            posted = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            loc    = cells[7].get_text(strip=True) if len(cells) > 7 else ""
            if posted and not re.search(r"\d{1,2}/\d{1,2}/\d{4}", posted):
                posted = ""
            cat, reason = categorize(title, jtype)
            if cat:
                jobs.append(make_job(name, title, job_url, "WinOcular",
                                     category=cat, location=loc, posted=posted, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_westfork():
    name = "West Fork SD"
    url  = "https://flowpoint.wftigers.org/careers/opportunities/"
    jobs = []
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"/careers/opportunities/entry/")):
            title = a.get_text(strip=True)
            if not title:
                parent = a.find_parent(["h2", "h3", "h4"])
                title  = parent.get_text(strip=True) if parent else ""
            if not title or title in seen:
                continue
            seen.add(title)
            full_url = a["href"] if a["href"].startswith("http") else "https://flowpoint.wftigers.org" + a["href"]
            cat, reason = categorize(title)
            if cat:
                jobs.append(make_job(name, title, full_url, "FlowPoint",
                                     category=cat, location="West Fork, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_schoolspring(district):
    name = district["name"]
    sub  = district["subdomain"]
    url  = f"https://{sub}.schoolspring.com/"
    jobs = []
    soup = pw_get_soup(url, wait=3)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        is_job = "/job/" in href or "jobID" in href.lower() or "job-listing" in href
        if not is_job or not text or len(text) < 5 or href in added:
            continue
        added.add(href)
        full_url = href if href.startswith("http") else f"https://{sub}.schoolspring.com{href}"
        cat, reason = categorize(text)
        if cat:
            jobs.append(make_job(name, text, full_url, "SchoolSpring", category=cat, match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_haashall():
    name = "Haas Hall Academy"
    url  = "https://haashall.org/welcome__trashed/employment/"
    jobs = []
    try:
        r       = requests.get(url, headers=HEADERS, timeout=15)
        soup    = BeautifulSoup(r.text, "html.parser")
        content = soup.find("main") or soup.find(class_=re.compile(r"entry|content|post", re.I)) or soup
        if any(x in content.get_text().lower() for x in ["no open", "no current", "no position"]):
            log.info(f"{name}: no open positions")
            return jobs
        for a in content.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            if any(x in href for x in ["#", "mailto", "tel:", "facebook", "twitter", "instagram"]):
                continue
            cat, reason = categorize(title)
            if cat:
                full_url = href if href.startswith("http") else "https://haashall.org" + href
                jobs.append(make_job(name, title, full_url, "WordPress",
                                     category=cat, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
# COMMUNITY SCRAPERS
# ──────────────────────────────────────────────────────────────────────────────

def scrape_civicengage(name, jobs_url, base_url):
    jobs = []
    try:
        r    = requests.get(jobs_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"UniqueId|JobID", re.I)):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href     = a["href"]
            full_url = href if href.startswith("http") else base_url.rstrip("/") + href
            parent   = a.find_parent(["li", "div", "tr", "article"])
            date_m   = re.search(r"\d{1,2}/\d{1,2}/\d{4}", parent.get_text() if parent else "")
            posted   = date_m.group(0) if date_m else ""
            cat, reason = categorize(title)
            if cat:
                jobs.append(make_job(name, title, full_url, "CivicPlus",
                                     category=cat, location=name, posted=posted, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_springdale_library():
    name = "Springdale Public Library"
    url  = "https://springdalelibrary.org/employment/"
    jobs = []
    try:
        r       = requests.get(url, headers=HEADERS, timeout=15)
        soup    = BeautifulSoup(r.text, "html.parser")
        content = soup.find("main") or soup.find(class_=re.compile(r"content|entry|post", re.I)) or soup
        if any(x in content.get_text().lower() for x in ["no open position", "no current"]):
            log.info(f"{name}: no open positions")
            return jobs
        for a in content.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            if any(x in href for x in ["#", "mailto", "tel:", "/wp-"]):
                continue
            cat, reason = categorize(title)
            if cat:
                full_url = href if href.startswith("http") else "https://springdalelibrary.org" + href
                jobs.append(make_job(name, title, full_url, "Library",
                                     category=cat, location="Springdale, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_workday(source):
    name     = source["name"]
    api_url  = source["api_url"]
    src_cat  = source.get("category", "community")
    jobs     = []
    payload  = {"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}}
    api_hdrs = {**HEADERS, "Content-Type": "application/json", "Accept": "application/json"}
    try:
        r        = requests.post(api_url, json=payload, headers=api_hdrs, timeout=20)
        data     = r.json()
        postings = data.get("jobPostings", [])
        log.info(f"{name}: {len(postings)} total from Workday API")
        for p in postings:
            title    = p.get("title", "").strip()
            ext_url  = p.get("externalPath", "")
            full_url = source["base_url"].rstrip("/") + ext_url if ext_url else source["base_url"]
            posted   = p.get("postedOn", "")
            loc      = p.get("locationsText", "") or p.get("primaryLocation", "")
            # IT sources use IT filter; others use primary filter
            if src_cat == "it":
                cat, reason = categorize_it_source(title)
            else:
                cat, reason = categorize(title, default_category=src_cat)
            if cat:
                jobs.append(make_job(name, title, full_url, "Workday",
                                     category=cat, location=loc, posted=posted, match_reason=reason))
        log.info(f"{name}: {len(jobs)} relevant jobs")
    except Exception as e:
        log.error(f"{name} Workday: {e}")
    return jobs


def scrape_taleo_rss(name, rss_url, base_url, category="community"):
    jobs = []
    try:
        r    = requests.get(rss_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item"):
            title    = (item.find("title").text or "").strip()
            link_tag = item.find("link")
            url      = (link_tag.next_sibling.strip()
                        if link_tag and link_tag.next_sibling else base_url)
            if not url or not url.startswith("http"):
                url = base_url
            cat, reason = categorize(title, default_category=category)
            if cat:
                jobs.append(make_job(name, title, url, "Taleo",
                                     category=cat, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs (RSS)")
    except Exception as e:
        log.error(f"{name} Taleo RSS: {e}")
    return jobs


def scrape_jbu(url, name):
    jobs = []
    try:
        r       = requests.get(url, headers=HEADERS, timeout=15)
        soup    = BeautifulSoup(r.text, "html.parser")
        content = soup.find("main") or soup.find(id=re.compile(r"content|main", re.I)) or soup
        skip    = ["#", "mailto", "facebook", "twitter", "linkedin", "instagram",
                   "jbu.edu/about", "jbu.edu/admissions", "jbu.edu/student",
                   "jbu.edu/academic", "eaglenet", "catalog", "calendar", "news", "giving", "alumni"]
        for a in content.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            if any(x in href for x in skip):
                continue
            cat, reason = categorize(title)
            if cat:
                full_url = href if href.startswith("http") else "https://www.jbu.edu" + href
                jobs.append(make_job(name, title, full_url, "HubSpot",
                                     category=cat, location="Siloam Springs, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_hendrix():
    name = "Hendrix College"
    url  = "https://www.hendrix.edu/humanresources/jobs.aspx"
    jobs = []
    try:
        r       = requests.get(url, headers=HEADERS, timeout=15)
        soup    = BeautifulSoup(r.text, "html.parser")
        content = soup.find("main") or soup.find(id=re.compile(r"content|main", re.I)) or soup
        skip    = ["#", "mailto", "facebook", "twitter", "hendrix.edu/academics",
                   "hendrix.edu/apply", "hendrix.edu/giving"]
        for a in content.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            if any(x in href for x in skip):
                continue
            cat, reason = categorize(title)
            if cat:
                full_url = href if href.startswith("http") else "https://www.hendrix.edu" + href
                jobs.append(make_job(name, title, full_url, "HTML",
                                     category=cat, location="Conway, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_carl_albert():
    name = "Carl Albert State College"
    url  = "https://carlalbert.edu/about-casc/job-openings/"
    jobs = []
    try:
        r       = requests.get(url, headers=HEADERS, timeout=15)
        soup    = BeautifulSoup(r.text, "html.parser")
        content = soup.find("main") or soup.find(class_=re.compile(r"content|entry", re.I)) or soup
        if any(x in content.get_text().lower() for x in ["no open", "no position", "no current"]):
            log.info(f"{name}: no open positions")
            return jobs
        skip = ["#", "mailto", "tel:", "carlalbert.edu/admissions",
                "carlalbert.edu/student", "carlalbert.edu/about-casc/job"]
        for a in content.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            if any(x in href for x in skip):
                continue
            cat, reason = categorize(title)
            if cat:
                full_url = href if href.startswith("http") else "https://carlalbert.edu" + href
                jobs.append(make_job(name, title, full_url, "WordPress",
                                     category=cat, location="Poteau, OK", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_saashr(name, url, category="community"):
    jobs = []
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"CareerID|CareersDetail|career_id", re.I)):
            title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue
            href     = a["href"]
            full_url = href if href.startswith("http") else "https://secure7.saashr.com" + href
            cat, reason = categorize(title, default_category=category)
            if cat:
                jobs.append(make_job(name, title, full_url, "SaaSHR",
                                     category=cat, match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_bella_vista():
    name = "City of Bella Vista"
    url  = "https://recruiting.paylocity.com/recruiting/jobs/All/b1e8c19e-977f-41ec-89e7-a138ab6e72eb/City-of-Bella-Vista"
    jobs = []
    soup = pw_get_soup(url, wait=4)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=True):
        href  = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 5 or href in added:
            continue
        if not any(x in href for x in ["recruiting/jobs", "Details", "b1e8c19e"]):
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://recruiting.paylocity.com" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "Paylocity",
                                 category=cat, location="Bella Vista, AR", match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_uca():
    name = "UCA"
    url  = "https://jobs.uca.edu/postings/search"
    jobs = []
    soup = pw_get_soup(url, wait=4)
    if not soup:
        return jobs
    for a in soup.find_all("a", href=re.compile(r"/postings/\d+")):
        title    = a.get_text(strip=True)
        href     = a["href"]
        full_url = href if href.startswith("http") else "https://jobs.uca.edu" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "PeopleAdmin",
                                 category=cat, location="Conway, AR", match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_atu():
    name = "Arkansas Tech Univ."
    url  = "https://atu.csod.com/ux/ats/careersite/1/home?c=atu"
    jobs = []
    soup = pw_get_soup(url, wait=5)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=re.compile(r"requisition|careersite.*req", re.I)):
        title    = a.get_text(strip=True)
        href     = a["href"]
        if not title or len(title) < 5 or href in added:
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://atu.csod.com" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "Cornerstone",
                                 category=cat, location="Russellville, AR", match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_arcbest():
    name = "ArcBest"
    url  = "https://careers.arcb.com/careersmarketplace/OpenPositions/?10509=%5B27807%2C27810%2C36756%2C56719%2C28134%2C1738333%2C36692%2C36697%2C36733%2C36821%5D&10509_format=3533&10508=8400047&10508_format=3532&listFilterMode=1&jobRecordsPerPage=6&"
    jobs = []
    soup = pw_get_soup(url, wait=4)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=True):
        href  = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 5 or href in added:
            continue
        if not any(x in href for x in ["OpenPosition", "JobDetail", "careers.arcb"]):
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://careers.arcb.com" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "CareersMarketplace",
                                 category=cat, match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_ar_state_jobs():
    name = "AR State Jobs"
    url  = "https://arcareers.arkansas.gov/search/?searchby=location&q=&locationsearch=northwest+arkansas"
    jobs = []
    soup = pw_get_soup(url, wait=5)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=re.compile(r"/job/|/go/|requisition", re.I)):
        title    = a.get_text(strip=True)
        href     = a["href"]
        if not title or len(title) < 5 or href in added:
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://arcareers.arkansas.gov" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "SuccessFactors",
                                 category=cat, location="NW Arkansas", match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


def scrape_adp():
    name = "ADP (NWA)"
    url  = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=a75698d1-4927-42e2-8b24-4b1e4d60fa54&ccId=19000101_000001&lang=en_US"
    jobs = []
    soup = pw_get_soup(url, wait=5)
    if not soup:
        return jobs
    added = set()
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href  = a["href"]
        if not title or len(title) < 5 or href in added:
            continue
        if not any(x in href for x in ["recruitment", "job", "posting", "req"]):
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://workforcenow.adp.com" + href
        cat, reason = categorize(title)
        if cat:
            jobs.append(make_job(name, title, full_url, "ADP",
                                 category=cat, match_reason=reason))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
# IT SCRAPERS
# ──────────────────────────────────────────────────────────────────────────────

def scrape_usajobs_va():
    """VA Arkansas IT jobs via USAJobs — Playwright required (React SPA)."""
    name = "VA Arkansas (USAJobs)"
    url  = "https://www.usajobs.gov/Search/Results/?j=2299&j=2210&j=1550&j=1598&l=arkansas&d=VA&p=1&r=25"
    jobs = []
    soup = pw_get_soup(url, wait=5)
    if not soup:
        return jobs
    added = set()
    # USAJobs job cards have links to /Job/...
    for a in soup.find_all("a", href=re.compile(r"/Job/\d+|/job/\d+", re.I)):
        title    = a.get_text(strip=True)
        href     = a["href"]
        if not title or len(title) < 5 or href in added:
            continue
        added.add(href)
        full_url = href if href.startswith("http") else "https://www.usajobs.gov" + href
        # All results from this search are pre-filtered IT/VA jobs, so accept all non-excluded
        combined = title.lower()
        excluded = any(kw in combined for kw in HARD_EXCLUDE_KEYWORDS)
        if not excluded:
            jobs.append(make_job(name, title, full_url, "USAJobs",
                                 category="it", location="Arkansas", match_reason="VA IT"))
    log.info(f"{name}: {len(jobs)} jobs")
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
# ORCHESTRATION
# ──────────────────────────────────────────────────────────────────────────────

def scrape_all():
    all_jobs = []

    log.info("── School districts ──")
    for d in APPLITRACK_DISTRICTS:
        all_jobs.extend(scrape_applitrack(d)); time.sleep(1)
    for d in TEDK12_DISTRICTS:
        all_jobs.extend(scrape_tedk12(d)); time.sleep(1)
    all_jobs.extend(scrape_smartrecruiters()); time.sleep(1)
    all_jobs.extend(scrape_springdale_sd()); time.sleep(1)
    all_jobs.extend(scrape_westfork()); time.sleep(1)
    all_jobs.extend(scrape_haashall()); time.sleep(1)
    for d in SCHOOLSPRING_DISTRICTS:
        all_jobs.extend(scrape_schoolspring(d)); time.sleep(2)

    log.info("── Community sources ──")
    all_jobs.extend(scrape_civicengage("Rogers (City)", "https://www.rogersar.gov/Jobs.aspx", "https://www.rogersar.gov")); time.sleep(1)
    all_jobs.extend(scrape_civicengage("Bentonville (City)", "https://www.bentonvillear.com/jobs.aspx", "https://www.bentonvillear.com")); time.sleep(1)
    all_jobs.extend(scrape_springdale_library()); time.sleep(1)
    all_jobs.extend(scrape_saashr("Jones Center", "https://secure7.saashr.com/ta/6214802.careers?CareersSearch=&ein_id=119006097&lang=en-US")); time.sleep(1)
    for s in WORKDAY_SOURCES:
        all_jobs.extend(scrape_workday(s)); time.sleep(1)
    all_jobs.extend(scrape_taleo_rss(
        "Arkansas State Univ.",
        "https://phe.tbe.taleo.net/phe02/ats/servlet/Rss?org=ARKASTAT2&cws=40&WebPage=SRCHR_V2&WebVersion=0&_rss_version=2",
        "https://phe.tbe.taleo.net/phe02/ats/careers/v2/searchResults?org=ARKASTAT2&cws=40"
    )); time.sleep(1)
    all_jobs.extend(scrape_jbu("https://www.jbu.edu/human-resources/staff-job-listings/", "JBU (Staff)")); time.sleep(1)
    all_jobs.extend(scrape_jbu("https://www.jbu.edu/human-resources/faculty-job-listings/", "JBU (Faculty)")); time.sleep(1)
    all_jobs.extend(scrape_hendrix()); time.sleep(1)
    all_jobs.extend(scrape_carl_albert()); time.sleep(1)
    all_jobs.extend(scrape_bella_vista()); time.sleep(2)
    all_jobs.extend(scrape_uca()); time.sleep(2)
    all_jobs.extend(scrape_atu()); time.sleep(2)
    all_jobs.extend(scrape_ar_state_jobs()); time.sleep(2)
    all_jobs.extend(scrape_arcbest()); time.sleep(2)
    all_jobs.extend(scrape_adp()); time.sleep(2)

    log.info("── IT sources ──")
    all_jobs.extend(scrape_usajobs_va()); time.sleep(2)

    seen, unique = set(), []
    for j in all_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)
    log.info(f"Total relevant jobs: {len(unique)}")
    return unique


def find_new_jobs(old_data, new_jobs):
    existing_ids = {j["id"] for j in old_data.get("jobs", [])}
    return [j for j in new_jobs if j["id"] not in existing_ids]


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────────────────────────────────────

def build_section_html(jobs, label, accent):
    if not jobs:
        return ""
    rows = ""
    for j in jobs:
        det  = " · ".join(x for x in [j.get("location",""), ("Posted " + j["posted_date"]) if j.get("posted_date") else ""] if x)
        rows += f"""<tr><td style="padding:12px 8px;border-bottom:1px solid #f3f4f6;">
            <a href="{j['url']}" style="font-weight:600;color:{accent};text-decoration:none;">{j['title']}</a><br>
            <small style="color:#6b7280;">{j['district']}{(' · ' + det) if det else ''}</small><br>
            <span style="font-size:11px;background:#eff6ff;color:#1d4ed8;padding:2px 6px;border-radius:999px;">{j.get('match_reason','')}</span>
        </td></tr>"""
    return f"""<h3 style="font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
        color:#374151;margin:24px 0 10px;padding-bottom:6px;border-bottom:2px solid {accent};">
        {label} — {len(jobs)} new</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:8px;">{rows}</table>"""


def build_email_html(new_jobs, total_jobs):
    today  = datetime.now().strftime("%B %d, %Y")
    school = [j for j in new_jobs if j.get("category","school") == "school"]
    comm   = [j for j in new_jobs if j.get("category") == "community"]
    it     = [j for j in new_jobs if j.get("category") == "it"]
    body   = (build_section_html(school, "🏫 School Districts",                    "#1a56db") +
              build_section_html(comm,   "🏛️ Libraries, Universities & City Jobs", "#059669") +
              build_section_html(it,     "💻 IT Jobs",                              "#7c3aed"))
    if not new_jobs:
        body = "<p style='color:#6b7280;'>No new matching positions today.</p>"
    return f"""<html><body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:20px;">
      <h2 style="color:#111827;margin-bottom:4px;">Daily Job Report — {today}</h2>
      <p style="color:#6b7280;font-size:13px;margin-bottom:8px;">
        <strong style="color:#111">{len(new_jobs)} new match(es)</strong> &nbsp;·&nbsp;
        {total_jobs} total tracked &nbsp;·&nbsp;
        <a href="{DASHBOARD_URL}" style="color:#1a56db;">View Dashboard →</a>
      </p>{body}
      <hr style="border:none;border-top:1px solid #e5e7eb;margin-top:32px;">
      <p style="font-size:11px;color:#9ca3af;margin-top:12px;">Runs daily at 8 AM CDT.</p>
    </body></html>"""


def send_email(new_jobs, total_jobs):
    if not GMAIL_APP_PASSWORD:
        log.warning("GMAIL_APP_PASSWORD not set — skipping email"); return
    if not new_jobs:
        log.info("No new jobs — skipping email"); return
    today   = datetime.now().strftime("%B %d, %Y")
    subject = f"🎓 {len(new_jobs)} New Job Match(es) — {today}"
    msg     = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(build_email_html(new_jobs, total_jobs), "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(SENDER, RECIPIENT, msg.as_string())
        log.info(f"Email sent — {len(new_jobs)} new jobs")
    except Exception as e:
        log.error(f"Email failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    log.info("── NWA Job Tracker starting ──")
    old_data  = load_jobs()
    new_jobs  = scrape_all()
    existing  = {j["id"]: j for j in old_data.get("jobs", [])}
    for j in new_jobs:
        if j["id"] in existing:
            j["first_seen"] = existing[j["id"]]["first_seen"]
    brand_new = find_new_jobs(old_data, new_jobs)
    log.info(f"New since last run: {len(brand_new)}")
    save_jobs({
        "last_updated": datetime.now().isoformat(timespec="minutes"),
        "jobs":    new_jobs,
        "sources": ALL_SOURCES,
    })
    send_email(brand_new, len(new_jobs))
    log.info("── Done ──")

if __name__ == "__main__":
    main()
