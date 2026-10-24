"""Hold automatically approved emails that carry outside links or copy our instructions.

Website text reaches the AI writer as data, and a page can plant instructions ("add this link").
The writer has no tools, and its output is validated, but a prompt cannot guarantee obedience.
So bulk and automatic approval hold an email for a human when it names a domain or address that
is neither ours nor the recipient's, or repeats a long passage of our own AI instructions.
Manual approval is unaffected: a person has read the email.
"""
import re
from urllib.parse import urlsplit

TLDS = ('com|net|org|io|co|uk|us|ai|app|dev|biz|info|me|xyz|site|online|store|shop|tech|page|link|ly|gg|tv|'
        'ca|au|in|de|fr|nl|es|it|eu|ru|cn|top|click|live|cc|ws|to|so|sh|pro|club|space|website|blog|email|cloud')
DOMAIN = re.compile(rf'\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{TLDS}))\b', re.I)
SPELLED = re.compile(rf'\b([a-z0-9-]{{2,}})\s*[\(\[]?\s*dot\s*[\)\]]?\s*({TLDS})\b', re.I)
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
COPY_RUN = 12  # Consecutive words repeated from our instructions.


def _host(value):
    value = (value or '').strip().lower()
    if '@' in value:
        value = value.rsplit('@', 1)[1]
    if '//' in value:
        value = urlsplit(value).hostname or ''
    value = value.split('/')[0].rstrip('.')
    return value[4:] if value.startswith('www.') else value


def allowed_domains(settings, lead, contact):
    from .mailboxes import primary
    values = [settings.sender_website, settings.public_url, lead.get('website', ''), lead.get('domain', ''),
              contact.get('email', ''), primary(settings).get('sender_email', '')]
    values += [box.get('sender_email', '') for box in settings.extra_mailboxes]
    return {h for h in map(_host, values) if h}


def foreign_domains(text, allowed):
    found = {m.lower() for m in DOMAIN.findall(text)} | {m.lower() for m in EMAIL.findall(text)}
    found |= {f'{name}.{tld}'.lower() for name, tld in SPELLED.findall(text)}
    def ours(domain):
        domain = domain[4:] if domain.startswith('www.') else domain
        return any(domain == a or domain.endswith('.' + a) or a.endswith('.' + domain) for a in allowed)
    return sorted(d for d in found if not ours(d))


def _words(text):
    return [w.strip('.,;:!?()[]"\'*_-').casefold() for w in text.split() if w.strip('.,;:!?()[]"\'*_-')]


def instruction_runs():
    """Runs of our own AI instructions (rule text only; the fictional style examples are excluded)."""
    from . import calling, copywriting, email_writer, pitch_strategy
    sources = [email_writer.SINGLE_INSTRUCTIONS, email_writer.INSTRUCTIONS, email_writer.COPY_INSTRUCTIONS,
               email_writer.WEBSITE_INSTRUCTIONS.split('EXAMPLE')[0], calling.WRITER_INSTRUCTIONS,
               pitch_strategy.WRITER_INSTRUCTIONS, *[rule for _, _, rule in copywriting.PRINCIPLES]]
    runs = set()
    for source in sources:
        words = _words(source)
        runs.update(tuple(words[i:i+COPY_RUN]) for i in range(len(words) - COPY_RUN + 1))
    return runs


def copies_instructions(text, runs=None):
    runs = instruction_runs() if runs is None else runs
    words = _words(text)
    return any(tuple(words[i:i+COPY_RUN]) in runs for i in range(len(words) - COPY_RUN + 1))


def review(settings, lead, contact, messages):
    """Reasons to hold these drafts for manual approval; empty when automatic approval may proceed."""
    allowed, runs, reasons = allowed_domains(settings, lead, contact), instruction_runs(), []
    for message in messages:
        text = message['subject'] + '\n' + message['body']
        outside = foreign_domains(text, allowed)
        if outside:
            reasons.append('mentions a domain or address that is not yours or the recipient\'s: ' + ', '.join(outside[:3]))
        if copies_instructions(text, runs):
            reasons.append('repeats a passage of the AI writing instructions')
    return list(dict.fromkeys(reasons))
