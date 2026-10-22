# Copywriting playbook — 22 October 2026

Cold-email quality now comes from the application, not from whichever language model is
configured. Principles from five classic copywriting books are restated in our own words in
`outreach/copywriting.py` and applied in three model-independent places:

1. **Copy plan** (`copy_plan`): a deterministic brief per email, sent to the model with the
   research. It names the reader, their awareness stage, the entry point, the business desire the
   offer serves, the benefit to reach, the structure and low-risk calls to action for the service.
2. **Pitch brief** (`outreach/stakes.py`): for measured website findings, the exact plain-English
   fact, a verified reason it matters (published benchmark or direct consequence) and the fix.
3. **Copy score** (`score`): every draft from any model is graded 0-100 against the same rules.
   Below `COPY_MIN_SCORE` (default 75) the writer asks the model for one rewrite naming the failed
   checks, then keeps the better valid draft. A failed rewrite never replaces a valid draft.
   The score and its notes are saved with the draft and shown under the email as **Copy check**.

Truth validators in `outreach/email_writer.py` always win over style: no invented pain, lost
customers, visitor behaviour, statistics, past clients or completed work.

## Principles and where they are enforced

| Principle (our wording) | Source | Plan / prompt | Scored check |
|---|---|---|---|
| Write to the one owner the research is about | The Boron Letters | `reader` | — (targeting happens in research) |
| Cold readers are unaware: enter through something they know is true | Breakthrough Advertising | `awareness_stage`, `entry_point`, pitch brief hook | `specific` |
| Channel an existing desire; copy cannot create one | Breakthrough Advertising | `their_desire` per service | `benefit` |
| The owner is the hero, we are the guide | Building a StoryBrand | prompt rule | `hero` (you/your ≥ I/we/our) |
| A simple, low-risk next step | Building a StoryBrand | `next_step`, `cta_options` | `single_cta` |
| Features become benefits ("so what?") | The Copywriter's Handbook | `benefit_to_reach` | `benefit` |
| Specific beats general | The Copywriter's Handbook | pitch brief numbers/quotes | `specific` |
| Subject lines only need to get the email opened | The Copywriter's Handbook | pitch brief `subject_ideas` | `subject` (2-7 words, no hype) |
| Tie the benefit to a core desire | Cashvertising | `their_desire` | `benefit` |
| A risk persuades only with a specific easy fix | Cashvertising | brief `why_it_matters` + `plain_fix` | `fear_solution` |
| Short words, sentences and paragraphs | Cashvertising | prompt rule | `readability`, `length`, `paragraphs` |
| Look like a personal note, not an advert | The Boron Letters | prompt rule | `personal` (no hype, "!" or filler) |
| Every sentence earns the next | The Boron Letters | prompt rule | `length`, `one_offer` |

## Services

Each Campaign A/B service has a desire, benefit, outcome words and calls to action in
`SERVICES`. Benefits are goals, never claims; calling-agent wording avoids the "never miss"
and lost-lead promises that its validator rejects. Adding a service means adding one entry.

## Changing the model

Switching `DRAFT_MODEL` keeps the same plan, brief, truth rules and quality bar. A weaker model
may need its one rewrite more often; check the Copy check scores on a sample after switching.
Set `COPY_MIN_SCORE=0` to disable rewrites (scores are still recorded).

## Limits

The score measures structure and clarity, not persuasion in the real world. Reply rates are
the real test: compare them in Learning before and after this change. Drafts still need human
review before approval; scores are calculated on the AI version, before manual edits.
