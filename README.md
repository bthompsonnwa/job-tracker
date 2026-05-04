# NWA School District Job Tracker

Automatically scrapes 16 NWA school district job boards daily, filters for
your skillset, and sends an email digest of new matches.

**Dashboard:** `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

---

## One-Time Setup (do this once)

### 1 · Create a GitHub account
Go to [github.com](https://github.com) → Sign Up (free).

### 2 · Create a new repository
- Click **+** → **New repository**
- Name it something like `school-job-tracker`
- Set it to **Public** (required for free GitHub Pages)
- Click **Create repository**

### 3 · Upload these files
Drag and drop the entire `job-tracker/` folder contents into the repo, or use
GitHub Desktop to commit them.

Your repo should look like:
```
.github/workflows/daily.yml
docs/
  index.html
  jobs.json
scraper.py
requirements.txt
README.md
```

### 4 · Enable GitHub Pages
- Go to your repo → **Settings** → **Pages**
- Source: **Deploy from a branch**
- Branch: `main` · Folder: `/docs`
- Click **Save**

Your dashboard will be live at:
`https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

### 5 · Add your Gmail App Password as a Secret
This lets the scraper email you without storing your password in code.

**First — enable 2-Step Verification on your Gmail:**
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "How you sign in to Google," click **2-Step Verification** → Turn on

**Then — create an App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail** · Select device: **Other** → type `Job Tracker`
3. Click **Generate** — copy the 16-character password shown

**Then — add it to GitHub:**
1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GMAIL_APP_PASSWORD`
4. Value: paste the 16-character password
5. Click **Add secret**

### 6 · Update the dashboard email link
In `scraper.py`, find the line near the bottom:
```
https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/
```
Replace with your actual GitHub Pages URL.

### 7 · Run it manually the first time
- Go to your repo → **Actions** tab
- Click **Daily Job Scraper** → **Run workflow** → **Run workflow**
- Watch it run (~5 min). When done, your dashboard will have results.

---

## Schedule
The scraper runs automatically every morning at **8:00 AM CDT**.
You can also trigger it manually any time from the Actions tab.

## How filtering works
Jobs are **included** if the title or description contains any of these keywords:
makerspace, stem lab, fabrication lab, cte, steam, cclc, technology
integration, instructional technology, digital learning, 3d print, robotics,
arduino, program coordinator, workshop facilitator, media specialist, and more.

Jobs are **hard excluded** if the title contains:
bus driver, custodian, food service, school nurse, psychologist, etc.

## Adjusting filters
Edit the `INCLUDE_KEYWORDS` and `HARD_EXCLUDE_KEYWORDS` lists in `scraper.py`,
then commit the change. The next run will use the updated filters.

## Troubleshooting
- **No email received:** Check that `GMAIL_APP_PASSWORD` secret is set correctly
- **SchoolSpring shows 0 jobs:** SchoolSpring's DOM may have changed — open
  an issue or check the scraper logs in the Actions tab
- **A district fails:** Look at the Actions run log for error messages
