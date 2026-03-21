# Onboarding

Onboarding collects your professional profile and job preferences.
It runs once at first launch, and can be re-run any time to update your profile.

---

## How to start

Send `/start` to the Telegram bot.

---

## What happens

### 1. Profile intake
The agent asks you to paste your LinkedIn profile.

**What to paste:** Go to your LinkedIn profile and copy the text from:
- The "About" section
- All "Experience" entries
- The "Skills" section

You can also paste a raw CV in any format — plain text works best.

**What happens with it:**
1. The raw text is sent to **Qwen2.5:7b running locally on your machine**
2. Qwen extracts structured data: name, title, experience, skills, education
3. The raw text is never stored in a readable file and never sent to any cloud service
4. You see a summary and confirm it before anything is saved

### 2. Confirmation
The agent shows you what was extracted:
```
Here's what I extracted:
Name: Jane Doe
Current title: Senior Backend Developer
Experience: 4 roles, most recent: Lead Developer at Acme Corp
Skills: Python, FastAPI, PostgreSQL, Docker, React, TypeScript, Redis, AWS
Location: Odense, Denmark
```

Reply **YES** to save, or tell the agent what to correct.

### 3. Preferences
Four quick questions:
1. What job titles are you looking for?
2. Minimum monthly salary (DKK)?
3. Location(s) and remote preference?
4. Any keywords to always exclude (e.g. "junior, unpaid")?

### 4. Done
Profile is saved to `config/profile.json` and the database.
Scraping queries are built from your job title preferences.

---

## Re-running onboarding

Send `/start` again at any time to update your profile.
Useful after a promotion, a new skill, or changing job preferences.

Re-running onboarding will **re-score all existing jobs** against your updated profile.

---

## Privacy notes

- Your raw LinkedIn paste is processed by **Qwen2.5:7b on your own machine**
- The free cloud model (OpenRouter) **never sees** your raw profile
- Together.ai sees `profile.json` (structured data) only when generating a CV/cover letter
- The raw input is stored in the `profile.raw_input` DB column (for re-parsing if needed)
  but is never displayed in chat or logs
