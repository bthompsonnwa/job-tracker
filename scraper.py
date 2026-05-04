#!/usr/bin/env python3
"""
NWA School District Job Tracker
Scrapes 16 district job boards, filters by skillset,
updates dashboard JSON, and sends a daily email digest.
"""

import requests
from bs4 import BeautifulSoup
import json, os, hashlib, logging, smtplib, re, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

RECIPIENT = "bthompsonnwa@gmail.com"
SENDER    = "bthompsonnwa@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
JOBS_FILE = "docs/jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ──────────────────────────────────────────────────────────────────────────────
# KEYWORD FILTERS  (all lowercase for matching)
# ──────────────────────────────────────────────────────────────────────────────

INCLUDE_KEYWORDS = [
    "makerspace", "maker space", "maker lab",
    "stem lab", "stem coordinator", "stem teacher", "steam teacher",
    "fabrication lab", "fab lab", "innovation lab",
    "technology integration", "digital learning", "digital fabrication",
    "cte teacher", "cte coordinator", "career and technical",
    "after school coordinator", "after-school coordinator",
    "cclc", "21st cclc", "21cclc", "21st century",
    "college and career", "college & career", "career coach", "career center",
    "program coordinator", "workshop facilitator",
    "theater technical", "technical theatre",
    "instructional technology", "technology specialist",
    "technology coordinator", "technology teacher",
    "computer science", "computer teacher", "coding teacher",
    "3d print", "laser engraving", "laser cutting", "robotics",
    "arduino", "electronics teacher",
    "audio/video", "av tech", "av teacher", "media production",
    "library media", "media specialist",
    "digital media", "instructional design", "learning coordinator",
    "maker education", "innovation coach", "tech coach",
    "it support", "help desk", "technology support",
    "curriculum developer", "curriculum coordinator",
    "community outreach", "volunteer coordinator", "event coordinator",
    "tinkercad", "blender", "adobe creative",
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
]

# ──────────────────────────────────────────────────────────────────────────────
# DISTRICT CONFIG
# ──────────────────────────────────────────────────────────────────────────────

APPLITRACK_DISTRICTS = [
    {
        "id":   "bentonville",
        "name": "Bentonville SD",
        "list_url": "https://www.applitrack.com/bentonville/onlineapp/default.aspx?all=1",
    },
    {
        "id":   "farmcards",
        "name": "Farmington SD",
        "list_url": "https://www.applitrack.com/farmcards/onlineapp/jobpostings/view.asp?internaltransferform.Url=&all=1",
    },
]

TEDK12_DISTRICTS = [
    {"name": "Elkins SD",   "url": "https://elkinsdistrict.tedk12.com/hire/index.aspx"},
    {"name": "Greenland SD","url": "https://greenlandschools.tedk12.com/hire/index.aspx"},
]

SCHOOLSPRING_DISTRICTS = [
    {"subdomain": "decatursd",      "name": "Decatur SD"},
    {"subdomain": "gravette",       "name": "Gravette SD"},
    {"subdomain": "gentry",         "name": "Gentry SD"},
    {"subdomain": "district",       "name": "District SD"},     # verify exact name
    {"subdomain": "hsd",            "name": "Huntsville SD"},
    {"subdomain": "pearidge",       "name": "Pea Ridge SD"},
    {"subdomain": "pgtigers",       "name": "Prairie Grove SD"},
    {"subdomain": "rogersschools",  "name": "Rogers SD"},
    {"subdomain": "siloamschools",  "name": "Siloam Springs SD"},
]

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def make_id(district, title, url):
    return hashlib.md5(f"{district}|{title}|{url}".encode()).hexdigest()[:12]

def is_relevant(title, extra=""):
    combined = (title + " " + extra).lower()
    for kw in HARD_EXCLUDE_KEYWORDS:
        if kw in combined:
            return False, f"excluded:{kw.strip()}"
    for kw in INCLUDE_KEYWORDS:
        if kw in combined:
            return True, kw
    return False, "no_match"

def make_job(district, title, url, platform, location="", posted="", match_reason=""):
    return {
        "id":           make_id(district, title, url),
        "title":        title,
        "district":     district,
        "location":     location,
        "url":          url,
        "platform":     platform,
        "match_reason": match_reason,
        "posted_date":  posted,
        "first_seen":   datetime.now().strftime("%Y-%m-%d"),
    }

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE) as f:
            return json.load(f)
    return {"last_updated": None, "jobs": []}

def save_jobs(data):
    os.makedirs("docs", exist_ok=True)
    with open(JOBS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ──────────────────────────────────────────────────────────────────────────────
# SCRAPERS
# ──────────────────────────────────────────────────────────────────────────────

def scrape_applitrack(district):
    """AppliTrack / Frontline — try RSS feed, fall back to HTML."""
    name     = district["name"]
    list_url = district["list_url"]
    did      = district["id"]
    jobs     = []

    # ── RSS / XML feed (cleaner) ──────────────────────────────────────────
    xml_url = f"https://www.applitrack.com/{did}/onlineapp/JobPostingFeed.aspx"
    try:
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        if r.status_code == 200 and "<item>" in r.text:
            soup = BeautifulSoup(r.text, "xml")
            for item in soup.find_all("item"):
                title = (item.find("title").text or "").strip()
                url   = (item.find("link").text or list_url).strip()
                desc  = (item.find("description").text or "").strip()
                ok, reason = is_relevant(title, desc)
                if ok:
                    jobs.append(make_job(name, title, url, "AppliTrack",
                                         match_reason=reason))
            log.info(f"{name}: {len(jobs)} jobs (XML)")
            return jobs
    except Exception as e:
        log.warning(f"{name} XML: {e}")

    # ── HTML fallback ─────────────────────────────────────────────────────
    try:
        r = requests.get(list_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not any(x in href for x in ["JobDetails", "ViewJob", "jobpostings"]):
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue
            full_url = href if href.startswith("http") else \
                       f"https://www.applitrack.com{href}"
            ok, reason = is_relevant(title)
            if ok:
                jobs.append(make_job(name, title, full_url, "AppliTrack",
                                     match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs (HTML)")
    except Exception as e:
        log.error(f"{name} HTML: {e}")
    return jobs


def scrape_tedk12(district):
    """PowerSchool / TedK12 — clean HTML table."""
    name, base_url = district["name"], district["url"]
    jobs = []
    try:
        r    = requests.get(base_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"ViewJob\.aspx")):
            title    = a.get_text(strip=True)
            href     = a["href"]
            full_url = href if href.startswith("http") else \
                       re.sub(r"/[^/]*$", "/" + href.lstrip("/"), base_url)
            row      = a.find_parent("tr")
            cells    = row.find_all("td") if row else []
            posted   = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            location = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            ok, reason = is_relevant(title)
            if ok:
                jobs.append(make_job(name, title, full_url, "PowerSchool",
                                     location=location, posted=posted,
                                     match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_smartrecruiters():
    """Lincoln SD — SmartRecruiters (SSR HTML)."""
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
            ok, reason = is_relevant(title)
            if ok:
                jobs.append(make_job(name, title, a["href"], "SmartRecruiters",
                                     location="Lincoln, AR", match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_springdale():
    """Springdale SD — WinOcular custom system."""
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
            # Extract posting ID from javascript:ViewJobPosting('013866', ...)
            m = re.search(r"ViewJobPosting\('(\w+)'", a["href"])
            pid      = m.group(1) if m else ""
            job_url  = (
                f"https://apply.sdale.org/winocular/workspace/wSpace.exe"
                f"?Action=wsViewPosting&postingID={pid}"
            ) if pid else url
            # Row context for type and location
            row    = a.find_parent("tr")
            cells  = row.find_all("td") if row else []
            jtype  = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            posted = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            loc    = cells[7].get_text(strip=True) if len(cells) > 7 else ""
            ok, reason = is_relevant(title, jtype)
            if ok:
                jobs.append(make_job(name, title, job_url, "WinOcular",
                                     location=loc, posted=posted,
                                     match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_westfork():
    """West Fork SD — FlowPoint (WordPress)."""
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
            full_url = a["href"] if a["href"].startswith("http") \
                       else "https://flowpoint.wftigers.org" + a["href"]
            ok, reason = is_relevant(title)
            if ok:
                jobs.append(make_job(name, title, full_url, "FlowPoint",
                                     location="West Fork, AR",
                                     match_reason=reason))
        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name}: {e}")
    return jobs


def scrape_schoolspring(district):
    """SchoolSpring — React SPA, requires Playwright headless browser."""
    name   = district["name"]
    sub    = district["subdomain"]
    url    = f"https://{sub}.schoolspring.com/"
    jobs   = []

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.warning(f"Playwright not installed — skipping {name}")
        return jobs

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx     = browser.new_context(user_agent=HEADERS["User-Agent"])
            page    = ctx.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                page.wait_for_timeout(5000)   # partial load is still useful

            time.sleep(3)   # extra buffer for React render
            soup = BeautifulSoup(page.content(), "html.parser")
            browser.close()

        # ── Try to find job links ──────────────────────────────────────────
        added = set()
        for a in soup.find_all("a", href=True):
            href  = a["href"]
            text  = a.get_text(strip=True)

            # SchoolSpring job links typically contain /job/ or jobID param
            is_job_link = (
                "/job/" in href
                or "jobID" in href.lower()
                or "job-listing" in href
                or (sub in href and "/jobs/" in href)
            )
            if not is_job_link or not text or len(text) < 5:
                continue

            full_url = href if href.startswith("http") \
                       else f"https://{sub}.schoolspring.com{href}"
            if full_url in added:
                continue
            added.add(full_url)

            ok, reason = is_relevant(text)
            if ok:
                jobs.append(make_job(name, text, full_url, "SchoolSpring",
                                     match_reason=reason))

        # ── Fallback: look for any card-like job containers ────────────────
        if not jobs:
            for el in soup.find_all(class_=re.compile(r"job|listing|posting|result", re.I)):
                a = el.find("a", href=True)
                if not a:
                    continue
                title    = a.get_text(strip=True) or el.get_text(" ", strip=True)[:80]
                href     = a["href"]
                full_url = href if href.startswith("http") \
                           else f"https://{sub}.schoolspring.com{href}"
                if full_url in added or not title:
                    continue
                added.add(full_url)
                ok, reason = is_relevant(title)
                if ok:
                    jobs.append(make_job(name, title, full_url, "SchoolSpring",
                                         match_reason=reason))

        log.info(f"{name}: {len(jobs)} jobs")
    except Exception as e:
        log.error(f"{name} SchoolSpring: {e}")
    return jobs

# ──────────────────────────────────────────────────────────────────────────────
# ORCHESTRATION
# ──────────────────────────────────────────────────────────────────────────────

def scrape_all():
    all_jobs = []

    for d in APPLITRACK_DISTRICTS:
        all_jobs.extend(scrape_applitrack(d))
        time.sleep(1)

    for d in TEDK12_DISTRICTS:
        all_jobs.extend(scrape_tedk12(d))
        time.sleep(1)

    all_jobs.extend(scrape_smartrecruiters())
    time.sleep(1)
    all_jobs.extend(scrape_springdale())
    time.sleep(1)
    all_jobs.extend(scrape_westfork())
    time.sleep(1)

    for d in SCHOOLSPRING_DISTRICTS:
        all_jobs.extend(scrape_schoolspring(d))
        time.sleep(2)

    # Deduplicate by ID
    seen, unique = set(), []
    for j in all_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    log.info(f"Total relevant jobs found: {len(unique)}")
    return unique


def find_new_jobs(old_data, new_jobs):
    existing_ids = {j["id"] for j in old_data.get("jobs", [])}
    return [j for j in new_jobs if j["id"] not in existing_ids]

# ──────────────────────────────────────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────────────────────────────────────

def build_email_html(new_jobs, total_jobs):
    today = datetime.now().strftime("%B %d, %Y")
    rows  = ""
    for j in new_jobs:
        rows += f"""
        <tr>
          <td style="padding:12px 8px;border-bottom:1px solid #eee;">
            <a href="{j['url']}" style="font-weight:600;color:#1a56db;text-decoration:none;">
              {j['title']}
            </a><br>
            <small style="color:#6b7280;">{j['district']}
              {(' · ' + j['location']) if j['location'] else ''}
              {(' · Posted ' + j['posted_date']) if j['posted_date'] else ''}
            </small><br>
            <span style="font-size:11px;background:#dbeafe;color:#1e40af;
                         padding:2px 6px;border-radius:999px;">
              {j['match_reason']}
            </span>
          </td>
        </tr>"""

    empty = "" if new_jobs else \
        "<p style='color:#6b7280;'>No new positions today — check back tomorrow.</p>"

    return f"""
    <html><body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:20px;">
      <h2 style="color:#111827;">🎓 Daily Job Report — {today}</h2>
      <p style="color:#374151;">
        <strong>{len(new_jobs)} new position(s)</strong> matching your skillset
        &nbsp;|&nbsp; {total_jobs} total tracked
      </p>
      {empty}
      <table style="width:100%;border-collapse:collapse;">{rows}</table>
      <hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb;">
      <p style="font-size:12px;color:#9ca3af;">
        View full dashboard →
        <a href="https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/">Job Tracker Dashboard</a>
      </p>
    </body></html>"""


def send_email(new_jobs, total_jobs):
    if not GMAIL_APP_PASSWORD:
        log.warning("GMAIL_APP_PASSWORD not set — skipping email")
        return
    if not new_jobs:
        log.info("No new jobs — skipping email")
        return

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
        log.info(f"Email sent: {len(new_jobs)} new jobs")
    except Exception as e:
        log.error(f"Email failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    log.info("── Job Tracker starting ──")

    old_data = load_jobs()
    new_jobs = scrape_all()

    # Preserve first_seen dates from existing records
    existing = {j["id"]: j for j in old_data.get("jobs", [])}
    for j in new_jobs:
        if j["id"] in existing:
            j["first_seen"] = existing[j["id"]]["first_seen"]

    brand_new = find_new_jobs(old_data, new_jobs)
    log.info(f"New since last run: {len(brand_new)}")

    updated = {
        "last_updated": datetime.now().isoformat(timespec="minutes"),
        "jobs": new_jobs,
    }
    save_jobs(updated)

    send_email(brand_new, len(new_jobs))
    log.info("── Done ──")


if __name__ == "__main__":
    main()
