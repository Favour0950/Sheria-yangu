# Sheria Yangu — Live Testing Guide (VPS Deployment)

This covers how to access and test the app as it's currently live on the VPS,
for both the citizen-facing app and the admin review dashboard. Branch
deployed: `Cate-Sheria-Yangu`.

---

## 1. Live URLs

| What | URL |
|---|---|
| Citizen app (start here) | http://137.184.204.191/splash.html |
|
| Admin review dashboard | http://137.184.204.191/admin.html |

**Note on the browser warning:** the site shows "Not secure" — this is
expected. The VPS is accessed by raw IP address (no domain name yet), so it
can't have a real SSL certificate. The site still works correctly over
plain HTTP; the warning is just about encryption, not a sign anything is
broken. This can be fixed later once/if a real domain is pointed at the VPS.

---

## 2. Testing the citizen flow

Go to **http://137.184.204.191/splash.html** and click through in order:

1. **Splash** → click "Get Started"
2. **Sign in** → enter a real-looking phone number, e.g. `+254712611409`,
   and optionally a constituency (e.g. "Dandora") → "Send code →"
3. **OTP screen** → since `SMS_DEV_MODE=true` on the VPS, the 6-digit code
   auto-fills — just click "Verify →"
4. **Bill list** → pick any bill. If none show up, the scraper hasn't been
   run on the VPS yet (see Section 4 below).
5. **Bill detail** → choose "Read plain-language summary & vote"
6. **Clauses** → read each clause's AI summary (English/Kiswahili toggle
   available), vote Kubali/Kataa on at least one, reject at least one
7. **Terms** → check all 3 consent boxes → "Draft my memorandum →"
8. **Memo** → review the AI-drafted memorandum, edit if you like, click
   "Tuma kwa Bunge (Send)" — this opens your email client and marks it sent
9. **Settings** → confirm your constituency/notification preferences saved
   correctly
10. **Analytics** → pick the bill you voted on, confirm your vote shows up
    in the constituency breakdown
11. **Profile** → see your own vote/memorandum history
12. **Hamburger menu (☰, top right)** → confirms Bills / Profile / Settings
    / Analytics / Policy / theme toggle / Sign out are all reachable

**Quick backend check (optional, via terminal):**
```bash
curl http://137.184.204.191/api/bills
curl http://137.184.204.191/api/bills/open
```

---

## 3. Testing the admin review flow

Go to **http://137.184.204.191/admin.html**

1. Enter the admin password (set in the VPS's `.env` as `ADMIN_PASSWORD`)
   → "Log In"
2. You'll land on the **Pending Summary Reviews** screen
3. If it says "Nothing pending — all caught up," that means every summary
   generated so far has already been reviewed. To generate a fresh one to
   test with, go through the citizen clause-viewing flow (Section 2, step 6)
   on a clause that hasn't been summarized before — this triggers a live
   DeepSeek call and adds it to the queue.
4. Refresh the admin page — a review card should appear showing:
   - The bill title and clause number
   - The raw original clause text
   - Editable English and Kiswahili summary boxes
   - Three buttons: **✓ Approve**, **💾 Save Edit**, **✗ Reject**

**What each button does:**
- **Approve** — accepts the AI's summary exactly as-is. Citizens now get
  this exact summary instantly (no more AI calls for this clause).
- **Save Edit** — edit the text in the boxes first, then click this to save
  your corrected version instead of the AI's original. Citizens see your
  edited version from now on.
- **Reject** — flags the summary as unusable. It's removed from the citizen
  view and from the pending queue. The next time anyone actually views that
  clause, a fresh AI summary is generated and reappears in the queue for
  review.

5. After clicking any of the three, the card should disappear from the list
   immediately.

**Quick backend check (optional, via terminal):**
```bash
# Log in and grab a token
curl -X POST http://137.184.204.191/api/admin/login -H "Content-Type: application/json" -d '{"password":"YOUR_ADMIN_PASSWORD"}'

# Check the pending queue directly
curl http://137.184.204.191/api/admin/summaries/pending -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 4. If bills aren't showing (empty bill list)

Scraped bill data lives in `data/scraped_bills/` on the VPS, which is
**not** part of the git repo (gitignored — same as locally). If the VPS
was freshly cloned, this folder starts empty and needs to be populated by
actually running the scraper on the VPS itself:

```bash
ssh sheriayangu@137.184.204.191
cd ~/Sheria-yangu
source venv/bin/activate
python src/scraper.py
```

Refresh the citizen app afterward — bills should now appear.

---

## 5. If something looks broken

Check whether the app service is actually running:
```bash
ssh sheriayangu@137.184.204.191
sudo systemctl status sheriayangu
```
Should say `active (running)`. If not:
```bash
sudo journalctl -u sheriayangu -n 50 --no-pager
```
shows the last 50 log lines to diagnose what went wrong.

To restart the app after any code change:
```bash
cd ~/Sheria-yangu
git pull origin Cate-Sheria-Yangu
sudo systemctl restart sheriayangu
```