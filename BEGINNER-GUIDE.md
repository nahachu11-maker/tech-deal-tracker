# Tech Deal Tracker — The Totally-Beginner Guide

This guide assumes you know nothing about coding. If you can install an app and type a few words, you can do this. Follow it top to bottom. Each step ends with a ✅ checkpoint so you know it worked.

---

## Part 1 — Just look at the app (2 minutes, no setup)

The very simplest way: you don't need the zip file at all.

1. Find the file called **tech-deal-tracker.html** (from earlier in our chat).
2. Download it and double-click it. It opens in your web browser like a normal webpage.

✅ **Checkpoint:** You see "Tech Deal Tracker" with a bar chart and a big table of deals.

That version has the data built in. It works forever but never updates itself. If that's all you need, you can stop here. Parts 2–4 are for the self-updating version.

---

## Part 2 — Run the full app on your computer (15 minutes)

The full version lives in **deal-tracker.zip**. It keeps its data in a separate file, which is what makes automatic updates possible. One catch: because the app *fetches* its data, you can't just double-click it — you need to run a tiny "web server." That sounds scary. It's one command.

### Step 1: Install Python

Python is a free program that runs the scripts. You may already have it.

1. Go to **python.org/downloads** and click the big yellow download button.
2. Run the installer. **Important (Windows only):** on the first screen, tick the checkbox that says **"Add Python to PATH"** before clicking Install. If you miss this, nothing later will work.
3. Mac users: Python may already be installed. You'll find out in Step 3.

✅ **Checkpoint:** The installer says "Setup was successful."

### Step 2: Unzip the project

1. Download **deal-tracker.zip** and double-click it (Mac) or right-click → "Extract All" (Windows).
2. You now have a folder called **deal-tracker**. Put it somewhere easy, like your Desktop.
3. Peek inside. You should see: `index.html`, a `data` folder, a `pipeline` folder, and a `README.md`.

✅ **Checkpoint:** The deal-tracker folder is on your Desktop and has those files inside.

### Step 3: Open a terminal in that folder

The terminal is the black window where you type commands. Don't worry — you'll type exactly what's written here, nothing more.

- **Windows:** open the deal-tracker folder, click in the address bar at the top, type `cmd`, and press Enter. A black window opens, already pointed at your folder.
- **Mac:** open the **Terminal** app (press Cmd+Space, type "terminal", press Enter). Then type `cd `, with a space after it, drag the deal-tracker folder into the window, and press Enter.

✅ **Checkpoint:** A terminal window is open. The line ends with something like `deal-tracker>` or `deal-tracker %`.

### Step 4: Start the mini web server

Type this and press Enter:

```
python -m http.server 8000
```

If it says "python is not recognized" or "command not found," try `python3 -m http.server 8000` instead.

✅ **Checkpoint:** It says `Serving HTTP on ... port 8000`. The cursor just blinks — that's normal, it's running. **Leave this window open.**

### Step 5: Open the app

Open your web browser and go to:

```
http://localhost:8000
```

("localhost" just means "my own computer.")

✅ **Checkpoint:** The Tech Deal Tracker appears, and under the title it says "Data updated" with a date. That means it successfully loaded the data file.

To stop later: go back to the terminal and press **Ctrl+C**, or just close the window.

---

## Part 3 — How to actually use the app

- **The bar chart** shows deal activity per quarter (a quarter = 3 months, like Q1'25 = Jan–Mar 2025). **Click any quarter's bar** to see only that quarter's deals. Click again to un-filter.
- **The $ Value / # Count buttons** switch the chart between "how much money" and "how many deals."
- **The three colored buttons** (M&A / IPO / Follow-on) turn each deal type on and off. Quick translations:
  - **M&A** = one company buying another (Google buying Wiz).
  - **IPO** = a private company selling shares to the public for the first time (Figma listing on the stock exchange).
  - **Follow-on** = a company that's *already* public raising more money (CoreWeave selling convertible notes).
- **The dropdowns** filter by year, sector (industry), and status (Closed = done, Pending = agreed but not finished, Filed = paperwork submitted, Terminated = fell apart).
- **The search box** searches everything, including the notes — try typing "take-private" or "convertible."
- **Click any row** in the table to expand a short note explaining why that deal mattered.
- **Click column headers** to sort (click again to flip the order).

---

Two newer pages — **Comps** (deal pricing) and **Audit Room** (data trust) — are explained in Part 16.

## Part 4 — Make it update itself (30–45 minutes, optional)

This is the "real-time" part. You'll put the project on **GitHub** — a free website that stores code — and a robot there will check for new deals every 6 hours, ask Claude to read the announcements, and update your app automatically. You'll need two accounts, both free to create: **github.com** and **console.anthropic.com** (the Claude API — note the robot's Claude usage costs a small amount, typically well under a dollar per day at this volume; a parent's help with the payment setup may be needed).

### Step 1: Put the project on GitHub

1. Sign up at **github.com**, then click the **+** in the top-right corner → **New repository**.
2. Name it `deal-tracker`, keep it **Public**, click **Create repository**.
3. On the empty repository page, click **"uploading an existing file."**
4. Drag **everything inside** your deal-tracker folder (not the folder itself) into the upload box. Make sure hidden folders like `.github` come along — if your computer hides it, upload via "Add file → Create new file" later, or ask for help with this one step; it matters because that folder contains the robot's instructions.
5. Click **Commit changes**.

✅ **Checkpoint:** Your repository page shows index.html, data, pipeline, and README.md.

### Step 2: Turn on the free website (GitHub Pages)

1. In your repository, click **Settings** → **Pages** (left sidebar).
2. Under "Branch," choose **main**, folder **/ (root)**, click **Save**.
3. Wait 2 minutes, refresh the page, and GitHub shows your site's address: `https://YOURNAME.github.io/deal-tracker/`

✅ **Checkpoint:** Opening that address in your browser shows the app. This link works from any device, anywhere — share it with friends.

### Step 3: Give the robot its two keys

The robot needs (a) a Claude API key so it can read deal announcements, and (b) your contact email, because the SEC (the US government agency whose database we read) requires visitors to identify themselves.

1. At **console.anthropic.com**, go to **API Keys** → **Create Key**. Copy the long string starting with `sk-ant-`. Treat it like a password — never post it anywhere public.
2. Back in your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret.**
3. Create secret #1 — Name: `ANTHROPIC_API_KEY`, Value: the key you copied.
4. Create secret #2 — Name: `EDGAR_USER_AGENT`, Value: your name and email, like `Naha Kim naha@email.com`.

✅ **Checkpoint:** Both secrets appear in the list (GitHub hides their values — that's the point).

### Step 4: Wake the robot up

1. Click the **Actions** tab in your repository. If it asks, click "I understand… enable workflows."
2. Click **"Update deal data"** in the left list → **Run workflow** → green **Run workflow** button.
3. Wait a few minutes. A yellow dot means running; a green check means done.

✅ **Checkpoint:** Green check. From now on it re-runs by itself every 6 hours, forever, for free.

### Step 5: Review what the robot found

The robot is careful, but it's still a robot. Anything new it adds shows a yellow **"needs review"** badge in the app. Read the deal, check the source link, and if it looks right, approve it. On your computer, in the terminal (from Part 2, Step 3):

```
python pipeline/review.py              (shows the waiting list)
python pipeline/review.py approve 1    (approves item 1)
python pipeline/review.py reject 2     (deletes item 2 if it's wrong)
```

Then upload the changed `data/deals.json` back to GitHub (drag it into the repository page like in Step 1). Rule of thumb: never trust a number until you've clicked the source link. That habit will serve you well beyond this app.

---

## When something breaks

- **Page says "Could not load data/deals.json"** → you double-clicked index.html instead of using the server. Go back to Part 2, Steps 3–4.
- **"python is not recognized"** → Python isn't installed, or the PATH checkbox was missed. Reinstall and tick the box.
- **The chart is empty** → your filters are hiding everything. Turn all three colored buttons back on and set dropdowns to "All."
- **The robot's run shows a red X** → click it to read the log. The most common cause is a mistyped secret name — it must be exactly `ANTHROPIC_API_KEY`.
- **The site shows old data** → the app re-checks every 5 minutes; refresh the page or wait. If you view the tracker on your laptop, also remember to **Pull** in GitHub Desktop first (Part 19).
- **You uploaded a file to inbox/ and nothing happened** → check the Actions tab. If there's no run at all, the file probably went to the wrong folder — it must be inside `inbox`, not the repo root.
- **The Audit Room says "Could not load data/audit.json"** → the report hasn't been generated yet. Run any workflow once (Actions → Update deal data → Run workflow), then Pull.

That's everything. Look at deals, click around, and let the robot do the boring part.

---

## Part 5 — The News & Trends app (new!)

Your project now contains a **second app** called **Tech Tape** — a live news feed for technology and semiconductors. Good news: if you finished Parts 2 and 4, there is almost nothing new to do. Both apps live in the same folder and share the same robot.

### Opening it

- **On your computer:** with the mini server running (Part 2, Step 4), go to `http://localhost:8000/news.html`
- **On your GitHub site:** go to `https://YOURNAME.github.io/deal-tracker/news.html`
- Or just click the **"→ News & Trends"** link at the top of the Deal Tracker (and "→ Deal Tracker" to go back).

✅ **Checkpoint:** You see "Tech Tape" with a list of headlines and a "Heating up" box on the right.

### How to read it

- **Colored dots** next to headlines show importance: red = market-moving, gold = notable, gray = routine. Use the dropdown to hide the routine stuff.
- **The first row of buttons** filters by category (Semiconductors, AI & Infrastructure, Big Tech, Startups & VC, Markets & Macro).
- **The dashed buttons** filter by *why a banker cares*: M&A, Capital Raise, IPO, Earnings, Regulatory, and so on. Try clicking "Semiconductors" plus "Regulatory" — that combination is basically the export-controls story on demand.
- **Click any headline row** to expand a one-sentence "Why it matters" and links to other outlets covering the same story.
- **The "Heating up" box** shows which companies are being mentioned much more than usual. "3.0×" means three times its normal amount of news. A red **SPIKE** badge means something is genuinely happening — click the company name to see only its stories.

### Making it update itself

If you already did Part 4, you're done — the same two secrets power this app. There's just one new workflow to wake up:

1. Upload the new files to your GitHub repository (drag the whole folder contents in again, like Part 4 Step 1 — GitHub replaces old files with new versions automatically).
2. Go to the **Actions** tab → click **"Update news & trends"** → **Run workflow**.

✅ **Checkpoint:** Green check. From now on it refreshes every 30 minutes. Keep the page open and you'll see a green "+N new" appear when fresh stories arrive.

### Choosing which companies to track

Open **config/watchlist.json** in any text editor (Notepad works). You'll see a list of companies. Copy one of the existing blocks, change the name and ticker to whatever company you want, save, and upload the file to GitHub. The robot picks it up on its next run. Same for the "topics" list — add anything you want a standing search for, like "chip tariffs Korea".

### One clever thing to know

When the news robot spots a story it tags as **M&A**, it automatically hands that story to the *deal tracker's* robot, which tries to turn it into a proper deal entry (with the "needs review" badge, as always). So reading the news literally keeps your deal database growing. Two apps, one brain.

### The seed data note

The headlines you see before the robot's first run are examples I compiled so the app isn't empty — they aren't clickable links. Within a day or two of the robot running, real stories (with real links) take over and the examples age out automatically.

---

## Part 6 — The feature pack (digest, alerts, league tables, Korea, company pages)

Five new things. Two need a small one-time setup; three work instantly.

### Works instantly

- **League Tables** (`league.html`, or the "League" link in any header): ranks banks by how many tracked deals they advised and the money involved. Click a bank's row to see its mandates. Note the honest caveat at the bottom — advisor names are only known for some deals, so treat it as directional.
- **Company pages**: click any company name tag under a headline in the news feed, and you get that company's own page — how much it's in the news, its deals, its coverage. You can also go directly to `company.html?c=Samsung%20Electronics` style addresses or use the dropdown on the page.
- **Morning Digest** (`digest.html`): a one-page daily briefing — "Three things that matter," deal flow, and what to watch — written automatically at **7am California time, year-round**. An example digest is pre-loaded; real ones start after you enable the new "Morning digest" workflow (Actions tab → Run workflow, same as before).

  *How the 7am timing works (nothing for you to do — just so the Actions tab doesn't confuse you):* GitHub's scheduler only understands universal time (UTC) and doesn't know about daylight saving, so "7am in California" is a different UTC hour in summer than in winter. The workflow therefore wakes up at **both** possible times each day, and its first step simply asks "is it 7am in Los Angeles right now?" If yes, it writes the digest; if no, it goes back to sleep. So in the Actions tab you'll see two runs per day — one green and useful, one that skipped on purpose. That skipped run is normal, not an error. Manual runs (the Run workflow button) always go through, whatever the hour.

### Needs 5 minutes of setup

**Phone alerts (free, via Discord).** Easiest path: make a free Discord server (one button in the Discord app), then Server Settings → Integrations → Webhooks → New Webhook → Copy URL. In your GitHub repository: Settings → Secrets and variables → Actions → New repository secret, Name: `ALERT_WEBHOOK_URL`, Value: that URL. Done — market-moving stories, trend spikes, and new deals now ping your Discord within 30 minutes of being detected. (A Slack webhook URL works the same way if you prefer Slack.)

✅ **Checkpoint:** After the next news workflow run, a red-dot story posts to your Discord channel.

**The Korea layer.** Korean-language news for 삼성전자, SK하이닉스, 네이버, 카카오 and topics like HBM already flows in automatically — nothing to do, and summaries come out in English. To also get official DART regulatory disclosures (Korea's version of SEC filings): register for a free API key at **opendart.fss.or.kr** (10-year validity, instant issue), then add it as a repository secret named `DART_API_KEY`. Edit the companies in the `korea` section of `config/watchlist.json` the same way as Part 5.

✅ **Checkpoint:** Items labeled [DART] and Korean-outlet stories appear in the feed with English summaries.

### Don't forget

Upload the new files to GitHub (drag the folder contents in again) and click Run once on each workflow — "Update news & trends" and "Morning digest" — to wake everything up.

---

## Part 7 — Ask the Data

There's now an **Ask** link in every header. It's a question box: type a question in plain English — "Which bank ran the most IPO books?" or "Total M&A value in 2025 vs 2024?" — and Claude answers using *only* your tracker's own data, showing which deals it counted so you can check the math.

### One-time setup (2 minutes)

This page talks to Claude directly from your browser, so it needs your own API key — the same kind from Part 4, Step 3:

1. Go to **console.anthropic.com** → API Keys → Create Key. Copy it.
2. Open the Ask page, paste the key into the box, click **Save**.

That's it. The key stays in your browser only — it is never uploaded to GitHub or to your website's visitors. Three safety rules: (1) never paste your key into the website's *code* or any GitHub file, only into this box in your own browser; (2) on a shared or school computer, untick "Remember in this browser" and click "Forget key" when done; (3) each question costs a fraction of a cent from your Anthropic account.

### Using it

- Click a suggested question to try it instantly.
- Tick/untick **Deals / News / Trends** to control what it looks at.
- It remembers the last few questions, so follow-ups work: ask "rank sectors by deal value," then just "now only for 2025."
- If it says the data can't answer — that's on purpose. It's not allowed to guess or use outside knowledge, which is exactly what makes its answers trustworthy.

✅ **Checkpoint:** Ask "List every terminated deal" and you should get CoreWeave / Core Scientific with the shareholder-vote explanation.

**If you see an error:** "invalid x-api-key" means the key was mistyped — re-copy and Save again. A CORS or network error usually means a school/office network is blocking api.anthropic.com; try from home.

---

## Part 8 — The self-improving loop (advanced, but mostly automatic)

Your project now gets *better the more you use it*. Here's the plain-English version of how, and the one habit that powers all of it.

### The one habit: give a reason when you reject

When you review new deals (Part 4, Step 5), rejecting with a few words is what teaches the system:

```
python pipeline/review.py reject 2 value was a licensing deal, not an acquisition
```

That reason gets saved to a file called `data/feedback.jsonl`. Approvals get saved too. Over a couple of weeks this becomes a record of what "good" looks like — the raw material for everything below. You don't have to do anything else; just add reasons when you reject.

### What happens automatically

- **A second checker.** Right after the robot extracts a deal, a *different, cheaper* AI double-checks it — it sees only the news source and the extracted numbers (not the first robot's reasoning, so it can't be fooled by it) and asks "do these numbers actually appear in the article?" If not, the deal gets a red **"verify ⚠"** badge so you look extra closely. Nothing is ever thrown away silently.

- **A lessons notebook.** There's a file, `pipeline/LESSONS.md`, that's basically the robot's growing list of "things I've learned not to get wrong." It gets fed into the robot's instructions on every single run. It starts with a few basic rules and grows over time.

- **A weekly study session.** Every Monday, a workflow reads your rejection reasons from the week and proposes new lessons that would have caught those mistakes. But — and this is the important safety part — it does **not** just change its own instructions. It first tests the proposed lessons against a set of known-correct examples (`tests/eval_cases.jsonl`), and if the change would make accuracy *worse*, it's thrown out. If it passes, it opens a **pull request** — a proposed change that waits for *you* to click approve on GitHub. The robot never edits its own brain without your sign-off.

- **A progress report.** Your morning digest now ends with a line like "This week: 9 approved, 2 rejected" so you can literally watch the approval rate climb as the system learns.

### Setup

Almost nothing. It uses the same `ANTHROPIC_API_KEY` you already set. Just upload the new files and, if you want the weekly study session, go to the Actions tab and enable the **"Weekly lesson distillation"** workflow. When it opens a pull request, read the proposed lessons, and if they look sensible, click **Merge**. That's you, staying in charge of what your system learns.

### Why this matters (the interview version)

If someone asks what makes this project more than a dashboard: it has a feedback loop. Human corrections become training signal; an independent verifier catches hallucinated numbers; proposed improvements are gated by an automated eval before a human approves them. That's the difference between a tool that *accumulates* data and a system that *compounds* — and it's a genuinely current idea in how people build with AI agents in 2026.

---

## Part 9 — The master plan: what the whole system is, and which AI does which job

This part is the map of everything you've built, written for someone who has never coded. Read it once and you'll understand your own system better than most engineers understand theirs.

### The newsroom analogy

Think of your project as a small newsroom that never sleeps:

- **Scouts** go out and collect raw material (news feeds, SEC filings, Korean disclosures). They're not AI at all — just simple scripts. They cost nothing.
- **Reporters** read the raw material and turn it into structured stories (deal records, tagged headlines). This needs real judgment, so a capable AI does it.
- **Fact-checkers** double-check every story against the source before it runs. This is simple, repetitive work — a fast, cheap AI is perfect, and importantly it's a *different* AI than the reporter, so it can't be fooled by the reporter's own reasoning.
- **The editor-in-chief** does two jobs: writes the morning briefing, and once a week reviews everything that went wrong and updates the newsroom's style guide (the lessons file). Rare, high-stakes thinking — this is where the smartest (most expensive) AI earns its keep.
- **You are the publisher.** Nothing the newsroom "learns" becomes permanent until you approve it.

### The full staffing chart

Anthropic makes several Claude models at different price/intelligence levels. Your system already routes each job to the right one — these are the defaults, no action needed:

| Step | What it does | How often | Model (the "who") | Why this one |
|---|---|---|---|---|
| Polling feeds, EDGAR, DART | Collects raw headlines & filings | Every 30 min | **No AI** — plain scripts | Fetching text needs zero intelligence. Free. |
| Clustering, trends, merging | Groups duplicate stories, computes spikes, updates files | Every run | **No AI** — plain math | Counting and comparing is arithmetic. Free. |
| News classification | Tags each story: category, IB relevance, importance | Every 30 min, in batches | **Sonnet 4.6** | High volume + needs good judgment on "does a banker care?" Sonnet is the sweet spot of smart-and-affordable. |
| Deal extraction | Turns a press release into a structured deal record | A few times a day | **Sonnet 4.6** | Accuracy matters (real numbers!), but volume is low and the verifier backstops it. |
| Fact verification | Checks every extracted number against the source | After every extraction | **Haiku 4.5** | The cheapest, fastest model. The power here comes from *independence*, not brilliance — a fresh pair of eyes that never saw the reporter's reasoning. |
| Morning digest | Writes your daily briefing | Once a day | **Sonnet 4.6** | One call a day; Sonnet writes it well. |
| Weekly lesson distillation | Studies your rejections, proposes smarter rules, tests them | Once a week | **Opus 4.8** | This edits the system's own memory — the highest-stakes thinking in the whole build, but only ~1 call a week, so the premium model costs pennies here. |
| Eval gate | Re-tests proposed lessons on golden cases | Weekly, inside distillation | **Sonnet 4.6** | Deliberately the *same* model as extraction — you're testing the prompt your production reporter will actually use. |
| Ask the Data | Answers your questions | When you ask | **Sonnet 4.6** | Fast enough to feel conversational, smart enough for the math. |

**Where Fable 5 fits (optional upgrade).** Fable 5 is Anthropic's top "Mythos-class" tier — built for long, complex autonomous work. Most of your system doesn't need it: your jobs run for seconds, not days. The one seat where it could earn its price is the **weekly distiller** — the editor-in-chief role — because finding subtle patterns across weeks of feedback is genuine deep-thinking work, and one call a week keeps the cost trivial. It's an upgrade to try *after* you've collected a month of feedback, not on day one: with only a handful of rejections, there's nothing for extra intelligence to find.

**The cost picture, roughly:** the scouts and math are free; the everyday AI work (classification, extraction, verification, digest) runs on the order of a few cents a day; the weekly distillation adds pennies more, even on a premium model. The design principle behind the whole chart: *route by task, not by prestige.* Never pay editor-in-chief rates for fact-checking.

### How to change a model — with zero coding

Every model choice is a setting, not code carved in stone. Say you want the weekly distiller to use Fable 5:

1. Open your repository on **github.com** and click into `.github/workflows/distill.yml`.
2. Click the little **pencil icon** (top right of the file view) — this opens GitHub's built-in editor. You're not "coding," you're editing a settings file, like changing a value in a form.
3. Find these three lines:
```
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python pipeline/distill.py
```
4. Add one line so it reads (spacing matters — copy exactly, aligned with the line above):
```
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          DISTILL_MODEL: claude-fable-5
        run: python pipeline/distill.py
```
5. Click the green **Commit changes** button. Done — next Monday's distillation runs on Fable 5.

✅ **Checkpoint:** In the Actions tab, the next "Weekly lesson distillation" run's log shows it using the model you set.

The same trick works everywhere. The setting names (put them under any workflow's `env:` block the same way): `EXTRACT_MODEL` (extraction + classification), `VERIFY_MODEL` (fact-checker), `DIGEST_MODEL` (morning briefing), `DISTILL_MODEL` (weekly distiller). Model names you can use: `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-8`, `claude-fable-5`. To undo any change, edit the file again and delete the line — the smart default comes back automatically.

### The one-paragraph summary of your entire build

Free scripts collect tech and semiconductor news, SEC and Korean filings around the clock. Sonnet reads and structures it; Haiku independently fact-checks every number; the results flow into six linked pages — deals, news, league tables, company dossiers, a daily briefing, and a question box. Your approve/reject decisions are captured as training signal, and once a week a premium model distills them into sharper rules — which only take effect after an automated test proves they don't make things worse *and* you personally click approve. Each model is matched to its job's difficulty, so the whole thing runs for about the price of a coffee a month.

---

## Part 10 — The seven-feature pack

Everything from the ideas document is now built in. Nothing new to set up — it all runs on the secrets you already have. What you'll notice:

- **Rumor tags in the news feed.** Deal stories now carry a small outlined tag: RUMOR, TALKS, ANNOUNCED, CLOSED, or TERMINATED (a "?" means the robot wasn't sure). Watching a RUMOR turn into ANNOUNCED days later is the fun part.
- **Deal economics in the deal table.** Click open an M&A deal and, when the announcement stated them, you'll see a "Comps" line: the premium paid, price per share, cash vs. stock, break fee. These numbers are double-checked by the fact-checker AI before they appear.
- **A weekly Memo page.** Every Friday, the smartest model writes a one-page industry update in the style banks send clients. An example is pre-loaded; enable the "Weekly sector memo" workflow in the Actions tab for live ones.
- **An Interview Prep page.** Pick any deal from the dropdown and get: the question an interviewer would ask, a 60–90 second model answer built only from your own data, three follow-ups, and the trap candidates fall into. It uses the same API key you saved on the Ask page. Rehearse out loud.
- **Your digest, in Korean.** The morning digest now has an English / 한국어 toggle — same briefing, proper Korean financial-press style (인수합병, 전환사채). Handy for sharing with Korean contacts.
- **Earnings notes on company pages.** When a watchlist company reports results, a short banker-style note (the number, guidance, AI read-through, morning-meeting line) appears on that company's dossier page.
- **A weekly cleaning robot.** Every Friday a checker sweeps the deal database for duplicates, deals stuck "Pending" too long, and numbers that look like typos. It only *flags* — it never changes your data — and the open-issue count shows up in your morning digest. Fun fact: on its very first run it caught a stray test record that had snuck into the database. It already earned its keep.

**One click to do:** Actions tab → enable and Run the new **"Weekly sector memo"** workflow once. Everything else rides on the workflows you already turned on.

---

## Part 11 — The tune-up (nothing to configure, one thing to do)

The system went through a full audit and got five under-the-hood fixes: it no longer pays to re-read stories it already classified (this was quietly costing about 10× more than necessary), story IDs are now stable, anything scraped from the web is neutralized before it's displayed (so a maliciously crafted headline can't tamper with your site), and two scheduling collisions between the robots were resolved.

**The one thing to do:** re-upload the folder contents to your GitHub repository, same as always — fixes only take effect once the new files are up.

**One new thing you'll see (it's good news, not an error):** in the Actions tab, the news workflow's log now prints a line like *"87 candidates, 6 new after dedupe (saved 81 redundant classifications)"*. That's the cost fix working — the robot recognizing stories it already processed and skipping the paid step. A high "saved" number is the system being frugal, and it's why your API bill stays at pocket change even though the robot checks the news every half hour.

Nothing else changes: same pages, same workflows, same secrets, same habits.

---

## Part 12 — Five years of deals, and who ran them

The tracker now covers **July 2021 through July 2026** — a complete market cycle — and shows **which investment banks worked each deal**. Both editions got the upgrade: the one-file version (tech-deal-tracker.html, still works by double-clicking) and your live site.

### What's new on the deals page

- **~40 more deals** from 2021–2023: Microsoft/Activision, Musk/Twitter, the Adobe/Figma deal regulators killed, the 2022 take-private wave, the Rivian IPO mania, and the 2022 "IPO desert" (exactly one notable listing all year — Mobileye).
- **The chart tells the cycle's story.** The quarterly bars now span 20 quarters with three shaded eras behind them: **ZIRP BOOM → THE FREEZE → AI RECOVERY**. Toggle between $ Value and # Count and you can literally see the market close and reopen.
- **Banks on every deal that disclosed them.** Click open a deal and an "Advisors / bookrunners (as reported)" line appears. There's also a new **All banks** dropdown — pick Qatalyst Partners and see why it's called the tech-M&A boutique, or Goldman Sachs to see the breadth of a bulge bracket. The search box finds bank names too.
- **Dead deals don't inflate the totals.** Terminated deals (Figma, iRobot, Tower, Five9, Core Scientific) show with a struck-through value and are excluded from the headline dollar figures — the graveyard is visible but never counted as money that moved.
- **The League page got much better** automatically — 48 deals now carry advisor data, so the rankings actually mean something.

### Three honest footnotes

1. **Advisor coverage is partial by nature.** IPO bookrunners are always disclosed, so that data is near-complete; M&A advisors often aren't reported, especially on smaller deals. Where nothing was publicly reported, the field is simply blank — never guessed.
2. **A few famous 2021 names are missing on purpose.** Coupang, Roblox, and Coinbase all listed in early 2021 — just *before* the five-year window starts in July. Strict window, honestly applied.
3. **Under the hood,** the robot's "keep deals for N years" setting moved from 3 to 5 — without that one-line change, the next automatic run would have quietly deleted all the new history. (Already done; mentioned so you know it matters if you ever change the window yourself.)

**To deploy:** re-upload the folder to GitHub as usual. The standalone file needs nothing — just open it.

---

## Part 12 — Five years of history, and who ran the deals

The tracker now covers a **full market cycle: July 2021 to today** — about 110 deals — and shows **which investment banks advised each one**.

What you'll see:

- **The chart tells a story now.** The quarterly chart has three shaded eras: the ZIRP boom (cheap-money mania — Rivian's giant IPO, Microsoft/Activision), the freeze (2022's take-private wave, when the IPO market produced essentially one deal in 20 months), and the AI recovery you've been tracking live. That arc is the single most useful mental model for understanding today's market — and now you can literally see it.
- **A new "All banks" dropdown** next to the filters. Pick Qatalyst Partners and see every sale mandate they ran; pick Goldman Sachs and see their whole footprint. The search box also finds banks now. Before an interview or a coffee chat, filter to that bank — you'll know their recent deals better than most candidates.
- **Advisors in the deal details.** Click open any deal and, where roles were publicly reported, you'll see the banks — labeled honestly as "(as reported)" because advisor rosters are only ever partially public, especially on smaller M&A. Roughly 45 of the 110 deals have them; the pipeline captures advisors on new deals automatically, so coverage grows.
- **Terminated deals count differently.** Dead deals (Adobe/Figma, Zoom/Five9, Amazon/iRobot, Intel/Tower, CoreWeave/Core Scientific) stay visible — they're some of the best learning material — but their value is now excluded from the headline totals so the stats never count money that never changed hands.
- **The League Tables page got much better** automatically — five years of bookrunner data instead of three makes the rankings meaningful.
- **Some deals now pair up.** HashiCorp's 2021 IPO at $14B and its 2025 sale to IBM at $6.4B are both in the file. So are Figma's blocked $20B sale and its later $19.3B IPO. Full corporate lifecycles, in one tracker — gold for interview stories.

**To deploy:** re-upload the folder as usual. One under-the-hood change matters: the robot's memory window was widened from three years to five — without that, the next automatic run would have deleted the new history. Already handled in the files.

**The standalone file** (tech-deal-tracker.html) was regenerated with all five years and the bank filter built in — still works with a double-click, no server needed.

One honest note: values are announced figures from public reporting and solid; advisor lists are only as complete as public disclosure, so treat the league view as directional, and verify any specific mandate before citing it in a serious setting.

---

## Part 13 — The whole picture: six deal types (and where UBS was)

The tracker now covers what investment banking actually does, not just the equity slice. Three new deal types join M&A, IPO, and Follow-on — about 34 new events, 144 total:

- **Debt** (steel blue): the bond offerings, buyout loans, private credit, and data-center financings behind the headlines — Meta's record $30B bond, the Twitter buyout's $13B "hung debt" saga and its 2025 resolution, JPMorgan single-handedly underwriting ~$20B for the EA buyout, and the new breed of AI-infrastructure financings. Debt is where much of banking's money is actually made, and it was invisible before.
- **SPAC** (plum): the boom era's parallel stock market — Grab's $40B record, Lucid, WeWork's cautionary tale, and Circle's failed SPAC that made its later IPO look brilliant. The chart's "ZIRP boom" band finally shows what actually happened in it. One honest note: de-SPAC values were announced valuations, aspirational by nature — the legend says so.
- **Private** (green): the mega-rounds that replaced IPOs — OpenAI's $40B raise (the largest private financing ever), Anthropic's rounds, Stripe's famous down-round. Arguably *the* capital-markets story of this era.

**Reading the new numbers:** the headline boxes now keep things apples-to-apples — M&A + de-SPAC value, equity raised, and debt raised are shown *separately*, because mixing a purchase price with a bond raise in one total is the kind of thing that makes bankers wince.

**So — where was UBS?** Two answers, both true. Partly my earlier data skewed toward the US headline names (fixed: UBS now appears via its eToro IPO mandate, alongside newly added Jefferies, expanded Citi and BofA coverage — 15 banks total). And partly the market itself: UBS simply isn't a top-tier US tech franchise; its strength is Europe and Asia, and it spent these years digesting Credit Suisse — whose 2023 collapse sits inside your window, and which now appears in the tracker as a bookrunner on the 2022 Citrix debt sale, a small monument to a vanished bank. The bank filter and League page are where all of this becomes visible: the bond desks bring in exactly the names the M&A league tables leave out.

**Nothing to configure.** The pipeline's robot now recognizes all six types automatically (its rulebook and test cases were updated), the cleaning robot knows the plausible value ranges for each, and the standalone file has everything built in. Just re-upload as usual.

---

## Part 14 — Importing data from Dealytics (or any deal database)

Professional platforms like Dealytics know about mandates that never make press releases. You can now feed their exports into your tracker — carefully.

**The one rule first:** data you export from a paid platform is licensed *to you*. Your tracker website is public, so republishing their data there could break their terms. The importer reminds you of this every single time and won't run until you type `--acknowledge-license`. The safe plays: keep your GitHub repository private if you import licensed data wholesale, or use the platform only to *discover* facts (like "UBS was on the Ambiq deal") that you then confirm from public press releases — which is exactly what we did in this chat.

**How to use it:**

1. In Dealytics, build your deal list (tech deals, your date range) and export it as a CSV file.
2. Open the CSV once and check the column headers. If they differ from what's in `config/import_mappings.json` (things like "Announced Date", "Financial Advisors"), edit that file so the names match exactly — it's a settings file, not code.
3. In your terminal (Part 2, Step 3), run a rehearsal first — `--dry-run` shows what *would* happen without changing anything:
```
python pipeline/import_deals.py export.csv --source dealytics --mode enrich --acknowledge-license --dry-run
```
4. Happy with the preview? Run it again without `--dry-run`.

**The two modes, in plain words:** `--mode enrich` is the gentle one — it only fills in missing bank names on deals you already track, never adds anything, and never overwrites banks you already have. Start here. `--mode import` adds new deals too; they arrive with the usual yellow "needs review" badge plus a record of where they came from, and they go through the same duplicate-detection as everything else, so importing the same file twice is harmless.

✅ **Checkpoint:** the dry run prints something like "5 rows → 4 normalized, 1 skipped" and "matched 4, filled advisors on 2." Skipped rows are usually broken data (missing dates or parties) — the importer refuses to guess.

**Free alternative needing no export at all:** Dealytics publishes free league-table reports on their site. Compare their bank rankings against your League page — any bank they rank that you barely show is your next research prompt, the same way the UBS question found Ambiq.

---

## Part 15 — Using S&P Capital IQ and FactSet (your school access)

You have the professional-grade sources through Columbia. Here's how to use them with your tracker, click by click. **The rule from Part 14 applies double here:** academic licenses are strictly personal-use — never automate extraction, never republish their data on your public site. Use them to *find and fill*, at human speed, and keep the "verify from a public source before publishing" habit.

### Which platform for which job

- **Capital IQ** = M&A gold. Its transaction screens carry the deal economics your tracker wants most: offer premiums, EV/Revenue and EV/EBITDA multiples, price per share, and — better than anything you have — advisors *split by side* (who advised the target vs. the buyer). One export can fill the "Comps" line on most of your M&A deals in an afternoon.
- **FactSet** = syndicate gold. Its ECM screens list the full bookrunner group on IPOs and follow-ons — the systematic fix for gaps like the UBS one, instead of finding them one Ambiq at a time.

### The Capital IQ workflow (one afternoon, repeat monthly)

1. **Build a screen.** In Capital IQ, go to the Screening area and start a *Transactions* screen. Filter to: M&A transactions, target in Information Technology / Semiconductors, announced date from July 2021, deal value above ~$1B (keeps the list manageable).
2. **Choose your columns.** Add display columns for: announced date, transaction type, buyer, target, total transaction value, status, industry, financial advisors to target, financial advisors to buyers, offer premium (1-day prior), implied EV/Revenue, implied EV/EBITDA, offer price per share. (Exact column names in CIQ's menus may differ slightly from this list — pick the closest ones; you'll align names in step 4.)
3. **Export** the screen to Excel, then in Excel do File → Save As → **CSV**.
4. **Align the headers — the one careful step.** Open the CSV and look at row 1. Then open `config/import_mappings.json`, find the `"capiq"` section, and make every column name there match your CSV's headers *exactly*, character for character. This is editing a settings file, not coding. Do it once; your saved screen exports the same headers every time after.
5. **Rehearse:**
```
python pipeline/import_deals.py your_export.csv --source capiq --mode enrich --acknowledge-license --dry-run
```
6. Read the preview. Then run it again without `--dry-run`.

✅ **Checkpoint:** it prints something like "matched 41, filled advisors on 23," and clicking open an enriched M&A deal in your tracker now shows a Comps line with the premium and multiples.

**If it prints a WARNING about columns not found** — stop and trust it. It means a header name doesn't match (or a comma inside a header confused the file). Fix the name in the mapping file and re-run the dry-run. This warning exists because the alternative — silently shifted columns putting the wrong numbers in the wrong fields — is the one failure you'd never notice on your own. (It caught exactly that during testing.)

**If some deals show as "unmatched":** usually a naming difference — Capital IQ says "Alphabet," your tracker says "Google." That's expected and safe; nothing wrong happened. Either rename in the CSV to match your tracker's name, or use `--mode import` to review them as potential new deals.

### The FactSet workflow (same shape)

Build a deals/ECM screen for tech IPOs and follow-ons since July 2021 with columns for announce date, deal type, issuer, deal value, status, industry, and bookrunners/co-managers. Export → CSV → align the `"factset"` block in the mapping file → dry-run with `--source factset`. The bookrunner columns merge automatically, and enrich mode fills syndicates only where your tracker has none.

### The third mode: let the pros audit you

```
python pipeline/import_deals.py your_export.csv --source capiq --mode reconcile --acknowledge-license
```

This changes *nothing* — it compares the professional data against yours and prints discrepancies: "your Wiz value is $3.2B, Capital IQ says $32B — check units" or "this deal you show as Pending has closed." Run it after each export; it's the licensed data quality-checking your public-source data, which is exactly the direction trust should flow. Findings also land in a small report file.

### Monthly rhythm (15 minutes)

Refresh both saved screens → export → `reconcile` first (fix anything it flags) → `enrich` (fill new advisor/comps gaps) → glance at League Tables, which just got better. That habit alone will keep your tracker closer to professional-grade than anything a student typically walks into interviews with.

### Part 15 addendum — what happened with a real Capital IQ file

We ran your actual Transaction Screening Report (.xls, 210 deals ≥$1B, Jul 2023–Jun 2026) end to end. What it proved, and what to do:

- **The importer reads CapIQ's .xls directly now** — no CSV conversion needed; it finds the header row under the branding automatically, cleans tickers out of names ("Synaptics Incorporated (NasdaqGS:SYNA)" → "Synaptics"), keeps only the *financial* advisors (law firms dropped), and normalizes bank names ("J.P. Morgan Securities LLC" → "JPMorgan").
- **Reconcile found real news:** Google/Wiz and Adobe/Semrush have *closed* — your tracker said Pending. The pros caught what the news feed hadn't yet. Two value differences (Informatica, Core Scientific) are just announced-equity vs. implied-total measurement — yours stand.
- **The import added 188 deals** (now 335 total, 94 banks), each with the yellow review badge and premiums/multiples/break fees where CapIQ had them. Spot-check a dozen (`python pipeline/review.py`), then `python pipeline/review.py approve-all` when satisfied.
- **The licensing reality, one more time:** those 188 records are tagged `licensed: true`. They're fine in your personal tracker and the standalone file on your laptop. If your GitHub repository is public, **make it private before pushing this data** (repo Settings → General → Danger Zone → change visibility) — GitHub Pages works on private repos on paid plans, or keep the public site on the pre-import data. Your call, but make it consciously.
- **Small skips are normal:** 5 rows skipped (missing buyer or unparseable fields) and a few janitor duplicate flags on similar-sounding Asian display-industry deals — reviewed and legitimate distinct transactions.

---

## Part 16 — The July upgrade: two new rooms in the building

Two new pages appeared in the top navigation. Nothing to install — if the app runs, they run.

### Comps (comps.html) — "what do deals like this cost?"

This is the page a banker would call **precedent transactions**: for every deal where the numbers were disclosed, it shows what the buyer paid *relative to the target's business* — and lets you slice it.

Quick translations of the column names:

- **TV ($B)** = total transaction value, in billions.
- **EV/Rev** = enterprise value ÷ the target's yearly revenue. "They paid 6x revenues."
- **EV/EBITDA** = price relative to cash-flow-ish profits. The most-quoted M&A multiple.
- **Prem 1D** = how far above the target's stock price (one day before the news) the offer was. A 30% premium means shareholders got paid 30% more than the market thought the company was worth the day before.
- **Cons.** = consideration — did the buyer pay in cash, stock, or a mix.

Things to try:

1. Click a **year chip** to see how expensive deals were in 2024 vs 2026.
2. Use the **sector dropdown** — semiconductor deals and software deals live in different price universes.
3. Click any **column header** to sort. Sorting by Prem 1D descending shows the most desperate buyers.
4. Scroll to **Broken deals** at the bottom: terminated transactions, each with a one-line story of why it died. Every one is an interview anecdote.

✅ **Checkpoint:** open Comps, click "2026", and the "Median multiples by year" table highlights how this year compares to the last three.

### Audit Room (audit.html) — "can I trust this data?"

The tracker now writes itself an inspection report every time data changes. The Audit Room shows:

- **Pending review** — deals a robot added or changed that no human has approved yet, each with a number. That number is how you refer to it when approving (Part 18).
- **Data-quality flags** — the janitor's findings: possible duplicates, deals stuck on "Pending" suspiciously long, values that look like typos, records missing fields. These are *prompts to look*, not verdicts.
- **Coverage** — how much of the data has multiples, advisors, and provider IDs attached.
- **Licensing exposure** — how many records came from a licensed database and what would have to be stripped before publishing publicly (Part 19).
- **Recent human verdicts** — a log of every approve/reject you've ever made. This is also what teaches the pipeline (Part 8's self-improving loop reads it).

✅ **Checkpoint:** the Audit Room shows 2 pending deals and a "generated" timestamp from today.

---

## Part 17 — The drop-box: import a Cap IQ report with zero typing

This is the new fully-automated way to refresh your data. The old way (Part 15) used the terminal. The new way is: **download a file, drag it into a folder on a website.** That's the whole procedure.

It only works if you did Part 4 (the project lives on GitHub). One-time note: the robot needs nothing new — no extra accounts, no extra secrets.

### The routine (2 minutes, do it whenever you refresh your screen)

1. In Capital IQ, open your saved screen and **re-run it** (same criteria — the dates roll forward automatically if you saved it with a relative date range). Export as Excel.
2. Go to your repository on **github.com** and click into the **inbox** folder.
3. Click **Add file → Upload files** (top right).
4. **Drag your downloaded .xls into the box**, then click the green **Commit changes** button. Don't rename anything, don't edit anything.
5. That's it. Within a minute, the robot wakes up.

### What the robot does with it

1. Reads every deal in the file.
2. **New deals** get added. **Deals you already track** get updated — a deal that closed since your last export flips from Pending to Closed, and any newly disclosed numbers (premiums, multiples, break fees) get filled in. It can never create a duplicate: each Cap IQ deal carries a permanent ID card, and the tracker checks IDs before names.
3. Regenerates the audit report and the public-safe data file.
4. **Deletes your uploaded file.** This is on purpose — the licensed export shouldn't live on GitHub. The *facts* it contained are now in your data; the file itself is gone.
5. Commits everything. Your app picks it up automatically.

✅ **Checkpoint:** the Actions tab shows a green check next to "Import screening report", the inbox folder is empty again, and the Audit Room's "generated" timestamp is fresh.

**If the run shows a red X:** click it, click the "Import every report in the inbox" step, and read the last few lines. The most common message is the column-mismatch warning — it means Cap IQ changed a column header in your export. Copy the log text and paste it to Claude; it's a one-line fix in `config/import_mappings.json`.

---

## Part 18 — Approving and rejecting deals without a terminal

The review queue used to require typing commands on your computer. Now there's a button on GitHub.

### When to review

Deals from your Cap IQ imports arrive **pre-approved** — they're structured data from a professional database, not guesses. What lands in the queue is the risky stuff: deals the *news-reading robot* extracted from articles and filings. Those genuinely deserve 30 seconds of your attention, because a language model reading a press release can mix up "raised $500M" and "valued at $500M".

### The routine

1. Open the **Audit Room** page. Look at the Pending review table. Each deal has a **number** and shows the note and (when available) a link to the source article — click it and check the deal value and the parties.
2. On GitHub: **Actions → Review deals → Run workflow** (a small form appears).
3. In the command box, type one of:
   - `approve 1` — deal #1 is correct, remove its badge.
   - `reject 2 value is the valuation not the amount raised` — deal #2 is wrong; delete it, and the reason you typed becomes a lesson the pipeline learns from (Part 8). Always write a reason — you're training your own analyst.
   - `approve-all capiq` — bulk-approve everything from one source.
   - `list` — just print the queue into the run's log.
4. Click the green **Run workflow** button. Twenty seconds later the queue is updated, and the Audit Room reflects it.

✅ **Checkpoint:** after approving both pending deals, the Audit Room shows "queue clear" in green.

**The habit that keeps quality high:** once a week, open the Audit Room, clear the pending queue, and skim the quality flags. Five minutes. The "Recent human verdicts" table at the bottom is your own audit trail — every decision, dated.

---

## Part 19 — One-click start, staying in sync, and the licensing question

### One-click start (no more typing the server command)

The folder now contains two small files:

- **Mac:** double-click **start-mac.command**. (First time only: if Mac complains it's from an unidentified developer, right-click it → Open → Open.)
- **Windows:** double-click **start-windows.bat**.

Either one starts the mini web server *and* opens the tracker in your browser. To stop it, close the black window.

✅ **Checkpoint:** double-click → browser opens by itself → tracker appears.

### Staying in sync with the robots (the missing piece)

Here's the one thing nobody tells beginners: the robots update the data **on GitHub**, but the copy **on your laptop** doesn't know about it. You need to pull the updates down. The no-terminal way:

1. Install **GitHub Desktop** (desktop.github.com) — a free app with buttons instead of commands.
2. File → Clone repository → pick your deal-tracker repo → Clone. (Do this once. From now on, *this* cloned folder is the one you open; you can delete the old copy.)
3. Whenever you want the latest data: open GitHub Desktop and click **Fetch origin**, then **Pull origin**. Then double-click your start file.

That's the entire maintenance loop: robots update in the cloud on schedule, you drop in a Cap IQ file occasionally, and one click syncs it all to your laptop.

### The licensing question, decided once

Your data is now a blend: public facts (fine anywhere) and licensed analytics from Cap IQ — the multiples, premiums, and financials columns (fine *for you*, not fine on a public website). The system now handles this automatically, but you have to make one decision:

- **Recommended: make the repository private.** Repo Settings → General → scroll to Danger Zone → Change visibility → Private. Everything keeps working — the robots, the drop-box, the review button, GitHub Desktop — you just view the tracker on your laptop instead of a public web address. This is the zero-worry option.
- **If you keep it public:** every robot run now also writes `data/deals.public.json` — a scrubbed copy with all licensed analytics removed. A public website must point at that file, not the full one. If you go this route, tell Claude "switch my pages to the public data file" and it's a five-minute change. Until then, treat the public URL as off.

✅ **Checkpoint:** you've either made the repo private, or you've consciously decided to do the public-file switch. Not deciding is the only wrong answer.

---

## The updated map of the whole machine

```
 You, occasionally:                       Robots, on schedule:
 ┌──────────────────────┐                 ┌─────────────────────────────┐
 │ drop .xls in inbox/  │──► import ──►   │ every 6h: read EDGAR + news │
 │ click Review button  │──► approve ──►  │ extract deals with Claude   │
 └──────────────────────┘                 │ merge · dedupe by ID · flag │
            ▲                             └──────────────┬──────────────┘
            │                                            ▼
     Audit Room shows you              deals.json ── audit.json ── deals.public.json
     what needs a human                     │
                                            ▼
                       Deals · Comps · League · News · Digest · Ask
```

Everything above the line is your job — maybe ten minutes a week. Everything below happens whether you're paying attention or not.
