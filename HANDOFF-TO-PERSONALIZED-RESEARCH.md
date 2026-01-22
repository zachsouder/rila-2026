# Handoff: RILA → Personalized Research Integration

## Context

I've been building a conference prep tool for RILA LINK 2026 (`/Users/zachsouder/projects/_outpost/rila`). It has:

- **535 companies** with pre-researched data
- **~1800 attendees** with contact info (name, email, LinkedIn, job title, ticket type)
- **Research data per company**: DC count, truck count, fit scores, sourced bullets, conversation hooks

The research uses **Gemini 3 Flash with Google Search grounding** - one API call per company that returns structured JSON with sourced facts. Much faster than the multi-prompt Discovery stage here.

---

### Files I've handed off
 - this handoff doc
 - an adjacent rila.db file with all of the research

---

## What I Need for RILA

**Goal**: Generate personalized "meet with me at the conference" emails for high-fit prospects.

**Data I already have**:
- Company research (overview, DC count, truck count, sourced bullets, hook)
- Attendee contact info (name, title, email, LinkedIn, company)
- Fit scores (gate_fit_score, truck_fit_score) to prioritize outreach

**What I'm missing**:
- Email generation (your P11 equivalent)
- Structured email extraction
- Gmail integration for sending

---

## Recommended Quick Path: Standalone Email Generator

Just build the email generation piece:
1. Accept: company research + list of contacts
2. Run P11-style prompt - BUT MODIFIED FOR CONFERENCES. WE NEED TO SORT OUT WHAT THIS LOOKS LIKE FOR DIFFERENT PEOPLE. I HAVE IDEAS. We'll want to iterate on this to make sure it matches what I think it needs to do.
3. Extract emails with Gemini structured output
4. Create Gmail drafts (proabably just send the email, as long as we BCC a hubspot email address so it's tracked)

This could be a separate route/page that doesn't touch the workflow system.

---

## Future Development - Incorporating our Learnings
 - we need to scheme a UI and workflow that much more closely resembles this. The full research takes me too long.
 - Potential steps
 1) Go out and use Gemini 3 Fast with Grounding with Google to find potential customers with DCs
 2) Check a google sheet file that's updated daily with our hubspot account owners - see if it's been claimed by anyone or by me
 3) If unclaimed, or not in database give me a list (at a regular interval - to be determined) to tell me to create it in hubspot or claim it in hubspot
 4) Complete simpler version of research - or kick off multi stage research, just keep the outputs smaller / more maneagable
 5) Prepare initial highly personalized email and send it (we'll figure out time of day stuff)
 6) Send follow up emails if they don't reply
 6a) I have an existing Hubspot flow we could replicate
 6b) This will require email tracking. Right now it's in Hubspot but we can use our own tracking tools. I want more visibility and granularity/reportability here. I'd love link tracking too but sometimes it's tough to ask someone to click a link of it's actually using a different link than the one shown.
 7) Probably more smart things we could do. Who's clicking on emails? Sort it smartly so I can cold call them. What time do we re-enroll if they never respond? etc.


---

## RILA Research Approach (for reference)

The RILA project uses this simpler research prompt with Gemini + Google Search grounding:

```python
COMPANY_RESEARCH_PROMPT = """Research "{company_name}" for B2B sales...

Return JSON:
{
    "overview": "1-2 sentence description",
    "dc_count": <number>,
    "dc_source": "where you found this",
    "truck_count": <number>,
    "truck_source": "where you found this",
    "gate_fit_score": <0-100>,
    "truck_fit_score": <0-100>,
    "hook": "Recent news or key insight for conversation starter",
    "company_bullets": [
        "Key fact (source)",
        "Recent news (source, date)",
        "Another detail (source)"
    ]
}
"""
```

**Pros**: One call, sourced facts, fast (~1.5s per company)
**Cons**: Less depth than 5-stage workflow, no people research

Could consider offering this as an alternative "quick research" option alongside the full workflow.

---

## Questions to Decide

1. **Research import format**: What structure for importing pre-researched data? What do we need to do to iterate? Maybe work directly with the rila.db, not the main research project db? Probably best.
2. **Email template**: Use conference specific templates. Do we put this in the UI? Or just chat back and forth. I'm leaning UI.
3. **Batch vs individual**: UI for selecting multiple companies for batch email generation? I'm sure we'll test on a small scale, then probably just batch. Not sure if we need UI for these conference one offs.

---

## Email Ideas
- all emails need to bcc: 22778013@bcc.hubspot.com
If someone is a client and is a Retailer/CPG category:
 - Check if they're a good fit based on the data in the database.
 - If they are one of the top 50 targets (based on number of distribution centers or score)
   - send highly personalized email, that varies a little bit from person to person between a company, maybe we need a template for that. That says, "Hey Dave, It looks like we're both going to RILA LINK. I'm sure you're getting a bunch of people reaching out with you to meet already. Add me to the list! I was actually looking at your company and it looks like you have 25+ distribution centers(some number close to the DC number, or the exact one if we're confident) We do gate automation technology. It looks like our technology could be a great fit to make your operations more secure, more streamlined, and more cost-effective. Would you be able to set aside a bit of time to meet during the conference to see if we could really help you out? I'd be happy to set aside time outside of the show floor to show you something more in depth. Here's a teaser trailer video: https://outpost.us/gate-automation/. Love to catch up. By the way, I'm also sending notes to Steve and Dave. Trying to hit up the right folks without blasting emails to everyone (assuming they have more than 3 people going)" - similar to the P11 prompt if you want to read it." (Will need proper paragraph formatting)
  - If they're a good target, but not top 50 send an email, that varies a little bit from person to person between a company, maybe we need a template for that. That says, "Hey Dave, It looks like we're both going to RILA LINK. I'm sure you're getting a bunch of people reaching out with you to meet already. Add me to the list! I was actually looking at your company and it looks like you have 25+ distribution centers(some number close to the DC number, or the exact one if we're confident) We do gate automation technology. It looks like our technology could be a great fit to make your operations more secure, more streamlined, and more cost-effective. I'd love to chat either during expo hour at booth #832 or whatever's convenient for you. Here's a teaser trailer video: https://outpost.us/gate-automation/. Love to catch up. By the way, I'm also sending notes to Steve and Dave. Trying to hit up the right folks without blasting emails to everyone (assuming they have more than 3 people going)" - similar to the P11 prompt if you want to read it." (Will need proper paragraph formatting)
 - Then next week - if the person doesn't reply - we'll want to send a follow up email.
  - We don't need email tracking. Just a list for me to input somewhere of the companies/people that replied
  - Email: "Hey Dave, see you down in Orlando! We're the gate automation company! Teaser video: https://outpost.us/gate-automation See you soon!" (Will need proper paragraph formatting)


If someone is an Exhibitor / Sponsor: (AND THEY'RE A GOOD FIT; NOT FOR THE ONES THAT AREN'T GOOD FITS FOR TRUCKING TERMINAL OR DISTRIBUTION CENTER GUARD SHACK GATE AUTOMATION TECHNOLOGY)
 - Check their title.
   - Are they actually an operations person?
    - then send them a similar email to meeting as the Retailer/CPGs
   - Are they actually a sales person?
    - then send them an email like, "Hey John, I see you're exhibiting at RILA. I am too. Happy hunting! Quick question, I know it's weird to be a sales person selling to another sales person, but we have really cool gate automation technology that could work really well for your operations team and maybe even be a key differentiator on safety, security, and speed for your potential customers. Do you have a couple minutes to meet up at the show? Here's a teaser trailer video: https://outpost.us/gate-automation/. Love to catch up. By the way, I'm also sending notes to Steve and Dave. Trying to hit up the right folks without blasting emails to everyone (assuming they have more than 3 people going)" - similar to the P11 prompt if you want to read it.
      

---

## Reference

Key fields in RILA's Company model:
```python
name, website, primary_industry, num_locations, employees, revenue
overview, dc_count, truck_count, company_bullets (JSON), hook
gate_fit_score, truck_fit_score, combined_score, category
researched_at
```

Key fields in RILA's Attendee model:
```python
first_name, last_name, company_id
job_title, job_function, management_level
email, linkedin_url, ticket_type
gate_fit_score, truck_fit_score, combined_score
```
