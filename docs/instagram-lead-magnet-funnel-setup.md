# Instagram Lead Magnet Funnel — Complete Setup Guide
*For Aeloria AI Influencer*

---

## HOW THE FUNNEL WORKS

```
Post (Problem) → Reader comments "WORKFLOW" → ManyChat auto-DMs PDF → Follow-up sequence
```

---

## PART 1 — MANYCHAT SETUP (30-45 minutes)

### Step 1.1 — Create ManyChat Account
1. Go to **manychat.com**
2. Click **"Start for Free"**
3. Connect your Instagram account via OAuth
   - Grant: manage_messages, comments, automated_comments, instagram_basic, instagram_content_publish
4. Select your Aeloria Instagram Business account

### Step 1.2 — Set Up the Comment Trigger
1. In ManyChat sidebar: **Automation → Instagram Comments → New Rule**
2. Configure:
   - **Trigger type:** Comment contains keyword
   - **Keyword:** `WORKFLOW` (uppercase, no quotes)
   - **Platform:** Instagram
   - **Apply to:** All posts (or specific post IDs)

### Step 1.3 — Create the DM Flow
1. In ManyChat: **Automation → Flows → New Flow**
2. Name it: `Lead Magnet: AI Workflow Blueprint`

**FLOW CONTENT:**

```
[TRIGGER: User commented "WORKFLOW"]

↓

Message 1 (instant):
"Hey! 👋 Here's the AI Workflow Blueprint — everything I cover in my posts, in one guide.

↓ Save it, share it with someone who needs it."

[ATTACHMENT: PDF file — https://pub-01988be0618644a68aedd677bfa464a9.r2.dev/lead-magnets/ai-workflow-blueprint.pdf]

↓

Message 2 (delay: 30 min, only if no reply):
"P.S. I post daily breakdowns of real AI workflows — follow @[AELORIA_INSTAGRAM_USERNAME] for more."

↓

Message 3 (delay: 24 hrs, only if no reply):
"One more thing — if you tried the 5-day sprint in the blueprint and got stuck, comment PROBLEM and I'll help."

[END FLOW]
```

### Step 1.4 — Set Growth Tool (for the PDF link)
1. **Growth → New Growth Tool → Link to File/URL**
2. Name: `AI Workflow Blueprint PDF`
3. URL: `https://pub-01988be0618644a68aedd677bfa464a9.r2.dev/lead-magnets/ai-workflow-blueprint.pdf`
4. This is what ManyChat attaches in the DM

### Step 1.5 — Test
1. From a personal account (not Aeloria's), comment "WORKFLOW" on the latest post
2. You should receive the DM within 60 seconds
3. Check the PDF attachment arrives correctly

---

## PART 2 — POST CAPTION FORMAT

**Every post follows this structure:**

```
[PROBLEM opener — 1-2 lines]

[Body — 3-5 lines, tells the story]

↓ Comment "WORKFLOW" and I'll send you the free blueprint — all my workflows, in one guide.

#[Hashtags]
```

**Do NOT write "DM me" or "Message me" — ManyChat only triggers on comments, not DMs.**

---

## PART 3 — UPLOAD PDF TO R2

**Before the funnel goes live:**
1. Convert `docs/lead-magnet-ai-workflow-blueprint.md` to PDF
2. Upload to R2: `posts/lead-magnets/ai-workflow-blueprint.pdf`
3. Get the public URL
4. Update ManyChat Growth Tool with the correct URL

---

## PART 4 — UPDATED CAPTIONS (all 7 days)

### MONDAY — Home Office
```
I stopped doing busywork 6 months ago.

Now an AI workflow handles my emails, scheduling, client follow-ups, and half my content — while I sleep. My 'office' is wherever I want it to be, and it runs itself.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — all my workflows, step by step.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #RemoteWork #AIWorkflows
```

### TUESDAY — Text Carousel (no photo)
```
Most of what you've heard about AI entrepreneurship is wrong.

Five myths I believed at the start:

1/ You need to be a tech genius — you don't. You need to know what you want.
2/ You need a big budget — you don't. You need focus.
3/ AI replaces humans entirely — it doesn't. It handles the stuff you hate.
4/ Set it up once and forget it — you can't. Systems need tending.
5/ Overnight success is real — it isn't. Consistency is unglamorous and that's fine.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — the 5-day sprint I used to automate my business.

#AIAutomation #FounderMyths #WomenInTech #Solopreneur #AIEntrepreneur
```

### WEDNESDAY — Cafe Reel
```
This café has become my second office.

Yesterday I sat here and mapped out an entire client onboarding automation in one afternoon. The flat white was decent. The workflow was better — it's been running on autopilot ever since.

One coffee. One diagram. A business that runs itself.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — my exact onboarding flow, downloadable.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #ClientWorkflow #StartupLife
```

### THURSDAY — London Street
```
I can run my business from a London street, a park bench, or my actual sofa.

The freedom isn't the money. It's that my time is actually mine again. That's what AI gave me — not the income, but the hours back.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — 5 automations you can set up this week.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #WorkFromAnywhere #FinancialFreedom
```

### FRIDAY — Behind the Scenes
```
Fridays are for testing.

I went through every AI tool that landed in my mentions this week. Most were noise. Three were genuinely worth it.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — the tools I actually use, with what they cost.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #AITools #TechStack
```

### SATURDAY — Whiteboard Carousel
```
Every business hits the same wall: there's only one of you.

You can't clone yourself. But you can build systems that scale beyond your own hours.

That's the shift. Stop thinking about how to do more yourself. Start thinking about what you can hand off.

This is what changed everything for me.

↓ Comment "WORKFLOW" and I'll send you the free blueprint — the exact 5-day sprint that got me here.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #BusinessGrowth #StartupStrategy
```

### SUNDAY — Cozy Evening
```
If I could go back and talk to myself when I started, I'd say one thing:

Stop waiting to feel ready. The systems don't need to be perfect. The AI doesn't need to be finished. You just need to start before you're comfortable.

What's one thing you wish you'd known at the start?

↓ Comment "WORKFLOW" and I'll send you the free blueprint — my whole system, laid out.

#AIAutomation #FounderLife #WomenInTech #Solopreneur #SundayThoughts #FounderJourney
```

---

## PART 5 — COMPLIANCE NOTES

**Meta/TOS rules to follow:**
- ✅ ManyChat is an official Meta Marketing Partner — safe to use
- ✅ Comment keyword trigger is fully compliant
- ✅ Auto-DM is compliant when using ManyChat (they handle the API auth)
- ❌ Never say "DM me" in post captions — always say "comment [keyword]"
- ❌ Don't send more than 1-2 follow-up DMs per user per week
- ❌ Don't use the word "free" misleadingly — the blueprint IS free
- ❌ Don't automate DMs to people who don't follow you — ManyChat defaults to followers-only

**Shadowban triggers to avoid:**
- Posting the same caption word-for-word across multiple posts
- Commenting on your own posts from multiple accounts
- Using the same keyword trigger in every single caption (vary it: WORKFLOW, AUTOMATE, BLUEPRINT, etc.)
- Asking users to "comment below" repeatedly in every post

**Recommended keyword rotation:**
| Day | Keyword |
|-----|---------|
| Mon | WORKFLOW |
| Tue | AUTOMATE |
| Wed | BLUEPRINT |
| Thu | WORKFLOW |
| Fri | AUTOMATE |
| Sat | WORKFLOW |
| Sun | BLUEPRINT |

Update the ManyChat rule to listen for all three keywords.

---

## PART 6 — WHAT STILL NEEDS TO BE DONE (Manual)

- [ ] Create ManyChat account and connect Instagram
- [ ] Set up ManyChat DM flow (use the template above)
- [ ] Convert `docs/lead-magnet-ai-workflow-blueprint.md` to PDF
- [ ] Upload PDF to R2: `r2://lead-magnets/ai-workflow-blueprint.pdf`
- [ ] Update ManyChat Growth Tool with the R2 public URL
- [ ] Add the comment trigger rule to each new post
- [ ] Test the flow from a personal account before going live
