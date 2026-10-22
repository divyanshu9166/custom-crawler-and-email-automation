"""Copywriting playbook as code, so email quality does not depend on one model.

Principles from five classic books, restated in our own words. They drive:
1. copy_plan(): what each email must do for this reader (deterministic input), and
2. score(): a deterministic grade of ANY model's draft against the same principles.
Truth rules live in email_writer; nothing here permits an unsupported claim.
"""
import re

# (id, source, rule). Shown to the model and documented in docs/COPYWRITING_PLAYBOOK.md.
PRINCIPLES = [
    ('market_first', 'The Boron Letters',
     'The right reader beats clever words: write to the one owner this research is about, nobody else.'),
    ('awareness', 'Breakthrough Advertising',
     'A cold reader is not thinking about our service yet. Enter through something they already know is '
     'true about their business, then move one believable step at a time.'),
    ('channel_desire', 'Breakthrough Advertising',
     'Copy cannot create desire; it can only connect the offer to a goal the business already has.'),
    ('hero', 'Building a StoryBrand',
     'The owner is the hero and we are the guide: talk about their business, customers and goal, not about us.'),
    ('plan', 'Building a StoryBrand',
     'Make the next step so simple and low-risk that saying yes is easier than ignoring it.'),
    ('benefit', "The Copywriter's Handbook",
     'Turn every feature into what it means for them; keep asking "so what?" until it reaches their goal.'),
    ('specific', "The Copywriter's Handbook",
     'Specific beats general: a page, a number, their own words. Vague praise and generic claims are ignored.'),
    ('subject', "The Copywriter's Handbook",
     'The subject line only has to get the email opened: specific and relevant to them, never clever or hyped.'),
    ('desire', 'Cashvertising',
     'Tie the benefit to a core business desire: winning customers, saving time, earning more, removing worry.'),
    ('fear_solution', 'Cashvertising',
     'A risk only persuades when it is paired with a specific, easy fix the reader can say yes to.'),
    ('readability', 'Cashvertising',
     'Short words, short sentences, short paragraphs. Easy reading is what gets read.'),
    ('personal', 'The Boron Letters',
     'Look like a note from one person, not an advert: plain words, no hype, no exclamation marks.'),
    ('slide', 'The Boron Letters',
     'Every sentence must earn the next one; cut anything that does not move the reader forward.'),
]

# Per service: the desire it serves, the plain benefit, words that show the benefit
# reached the copy, and low-risk calls to action. Benefits are goals, never claims.
SERVICES = {
    'website_improvement': {
        'desire': 'more enquiries from the visitors they already get',
        'benefit': 'people who already found them can see what they do and get in touch more easily',
        'outcome_words': ['enquir', 'get in touch', 'contact', 'quote', 'book', 'see what you', 'services appear',
                          'reach', 'read', 'find', 'easier', 'sooner', 'straight away', 'first'],
        'cta': ['Want me to send over the exact changes?', 'Should I send you the fix, step by step?']},
    'store_improvement': {
        'desire': 'more of their current shoppers finishing a purchase',
        'benefit': 'shoppers can go from product to checkout more easily',
        'outcome_words': ['checkout', 'buy', 'order', 'basket', 'cart', 'purchase', 'product', 'easier', 'sooner'],
        'cta': ['Want me to send over the exact changes?', 'Should I send you the fix, step by step?']},
    'website_build': {
        'desire': 'looking credible and being easy to choose when people check them out',
        'benefit': 'one place where people who find them can see their services and work, then contact them',
        'outcome_words': ['see your', 'your services', 'your work', 'contact you', 'get in touch', 'find you',
                          'enquir', 'one place', 'call'],
        'cta': ['Would a one-page outline of the site be useful?', 'Want me to sketch what the first page could look like?']},
    'chatbot': {
        'desire': 'answering customers quickly without more staff time',
        'benefit': 'common questions get answered at any hour, and their team only handles what needs them',
        'outcome_words': ['answer', 'question', 'any hour', 'evening', 'handoff', 'hand off', 'your team',
                          'enquir', 'book', 'time'],
        'cta': ['Would a short outline of the questions it could answer be useful?',
                'Want me to map out how it could work on that page?']},
    'ai_calling_agent': {
        'desire': 'every caller getting a helpful answer while the team stays focused',
        'benefit': 'callers are answered and the details reach their team as a short summary',
        'outcome_words': ['caller', 'call', 'summary', 'details', 'your team', 'answer', 'handoff', 'hand off', 'transfer'],
        'cta': ['Would a sample call flow for your business be useful?', 'Want me to write out how one call could go?']},
    'store_launch': {
        'desire': 'starting to sell online and earn from it',
        'benefit': 'customers can buy directly from them online',
        'outcome_words': ['buy', 'order', 'online', 'shop', 'store', 'sell', 'customers'],
        'cta': ['Would a one-page plan for the store be useful?', 'Want me to outline what the first version could include?']},
    'whatsapp_marketing': {
        'desire': 'bringing customers back for repeat purchases',
        'benefit': 'customers who opted in hear about the right products at the right time',
        'outcome_words': ['customer', 'repeat', 'back', 'opt', 'permission', 'message', 'order'],
        'cta': ['Would it help to check whether WhatsApp fits your customers first?']},
    'whatsapp_automation': {
        'desire': 'keeping customers informed without manual messages',
        'benefit': 'order updates and common questions are handled automatically for customers who opted in',
        'outcome_words': ['update', 'order', 'customer', 'automatic', 'opt', 'permission', 'question'],
        'cta': ['Would it help to check whether WhatsApp fits your customers first?']},
}

SPAM = re.compile(r'\b(?:(?<!feel )free|guarantee[ds]?|risk[- ]free|act now|limited time|urgent|amazing|revolutionary|'
                  r'cutting[- ]edge|world[- ]class|best[- ]in[- ]class|game[- ]changer|skyrocket|synergy|leverage|'
                  r'click here|no obligation|double your|triple your|once in a lifetime)\b|\b100\s?%|\${2,}', re.I)
SECOND_OFFER = re.compile(r'\b(?:optional(?:ly)?|add-on|as an addition|additionally|on top of that|we (?:also|could also) '
                          r'(?:offer|build|add)|as well as (?:an?|our))\b', re.I)
FILLER = re.compile(r"\b(?:just|really|very|actually|basically|simply|quite|truly|literally|honestly)\b", re.I)
YOU = re.compile(r"\b(?:you|your|yours|you['’](?:re|ll|ve|d))\b", re.I)
WE = re.compile(r"\b(?:I|we|our|ours|us|me|my|I['’](?:m|ve|d|ll)|we['’](?:re|ve|d|ll))\b", re.I)
RISK = re.compile(r'\b(?:poor|dead end|harder|blank|slow|wait|error|off-screen|unlabelled|sideways|404)\b', re.I)
FIX = re.compile(r'\b(?:we can|I can|fix|repair|change|adjust|add|load|darken|update)\b', re.I)


def copy_plan(lead, brief=None, name=''):
    """Deterministic strategy for one email; the model only phrases it."""
    service = SERVICES.get(lead.get('service', ''), SERVICES['website_improvement'])
    brief = brief or {}
    measured = bool(brief.get('hook'))
    return {
        'reader': f'the owner or manager of {name or lead.get("company", "")}, reading on a phone between jobs',
        'awareness_stage': 'problem_unaware' if measured else 'unaware',
        'entry_point': ('Open with the measured fact in pitch_brief.hook; it is about their own site, so it is believable.'
                        if measured else
                        "Open with their own words or goal from reviewed_finding.quote, then one believable step toward the offer."),
        'their_desire': service['desire'],
        'benefit_to_reach': service['benefit'],
        'next_step': 'One small, low-risk step: we send something concrete; no call, no commitment.',
        'cta_options': service['cta'],
        'structure': ['their specific fact', 'why it matters to them', 'the fix and what it gives them',
                      'one easy yes/no question'],
        'principles': [rule for _, _, rule in PRINCIPLES],
    }


def _sentences(body):
    return [s for s in re.split(r'(?<=[.!?])\s+', body.strip()) if re.search(r'[A-Za-z]', s)]


def _syllables(word):
    word = word.lower().strip(".,!?;:'\"()")
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    groups = re.findall(r'[aeiouy]+', re.sub(r'(?:e|es|ed)$', '', word))
    return max(1, len(groups))


def readability(body):
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", body)
    sentences = _sentences(body) or [body]
    if not words:
        return {'words': 0, 'avg_sentence': 0, 'longest_sentence': 0, 'reading_ease': 0}
    lengths = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.:/-]*", s)) for s in sentences]
    ease = 206.835 - 1.015*(len(words)/len(sentences)) - 84.6*(sum(map(_syllables, words))/len(words))
    return {'words': len(body.split()), 'avg_sentence': round(sum(lengths)/len(lengths), 1),
            'longest_sentence': max(lengths), 'reading_ease': round(ease)}


def score(subject, body, service=''):
    """Grade a draft (without greeting) against the playbook. 0-100 plus named checks."""
    stats = readability(body)
    paragraphs = [p for p in re.split(r'\n\s*\n', body.strip()) if p.strip()]
    questions = body.count('?')
    plan = SERVICES.get(service)
    you, we = len(YOU.findall(body)), len(WE.findall(body))
    subject_words = len(subject.split())
    checks = [
        # (id, weight, passed, note when failed)
        ('hero', 15, you >= we, f'Talk about them more than us ({you} you/your vs {we} I/we/our).'),
        ('readability', 15, stats['avg_sentence'] <= 16 and stats['longest_sentence'] <= 26 and stats['reading_ease'] >= 55,
         f"Shorter sentences and words (average {stats['avg_sentence']} words, longest {stats['longest_sentence']}, "
         f"reading ease {stats['reading_ease']})."),
        ('length', 10, 45 <= stats['words'] <= 110, f"Keep it to 45-110 words (now {stats['words']})."),
        ('paragraphs', 5, 2 <= len(paragraphs) <= 4 and all(len(p.split()) <= 55 for p in paragraphs),
         'Use 2-4 short paragraphs of at most 55 words.'),
        ('specific', 10, bool(re.search(r'\d|["“].{6,}["”]', body)), 'Include a specific number, page or their own words.'),
        ('single_cta', 15, questions == 1 and body.rstrip().endswith('?'), 'End with exactly one easy question.'),
        ('one_offer', 10, not SECOND_OFFER.search(body), 'Pitch one offer only; drop add-ons and extras.'),
        ('benefit', 10, not plan or any(w in body.lower() for w in plan['outcome_words']),
         'Say what the change gives them ({}).'.format(plan['benefit'] if plan else 'their goal')),
        ('fear_solution', 5, not RISK.search(body) or bool(FIX.search(body)), 'Pair the risk with the specific fix.'),
        ('subject', 10, 2 <= subject_words <= 7 and len(subject) <= 55 and '!' not in subject
         and not re.search(r'\b[A-Z]{4,}\b', subject) and not SPAM.search(subject),
         'Subject: 2-7 plain words, specific, no hype or capitals.'),
        ('personal', 5, '!' not in body and not SPAM.search(body) and len(FILLER.findall(body)) <= 1,
         'Plain personal tone: no hype words, exclamation marks or filler words.'),
    ]
    total = sum(weight for _, weight, _, _ in checks)
    earned = sum(weight for _, weight, passed, _ in checks if passed)
    return {'score': round(100*earned/total), 'stats': stats,
            'passed': [cid for cid, _, passed, _ in checks if passed],
            'improve': [{'check': cid, 'note': note} for cid, _, passed, note in checks if not passed]}
