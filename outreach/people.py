"""Named-person discovery hints from current official pages; never buyer/ownership approvals."""
import json
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from .web import crawl_url

NAME = r"[A-Z][a-zA-ZÀ-ž'’-]{1,35}(?:\s+[A-Z][a-zA-ZÀ-ž'’-]{1,35}){1,3}"
ROLE = r"(?i:\b(?:co[- ]?founder|founder|owner|CEO|chief executive officer|president|managing director|director|principal|(?:managing |founding )?partner|head of (?:marketing|growth|ecommerce|e-commerce|customer experience)|marketing manager)\b)"


def indexed_person_name(value):
    """Normalize a title's name hint; never a source-approved identity."""
    if not isinstance(value, str):
        return ''
    # Localized index titles can wrap a Latin name in direction markers.
    # Normalize only boundary marks; preserve unexpected internal formatting
    # for the existing strict name validator to reject.
    words = value.strip().strip('\u200e\u200f').strip().split()
    credentials = {'MCIAT', 'FCIAT', 'RIBA', 'ARB', 'FRSA', 'AIA', 'FAIA', 'MCIM', 'FCIM', 'MBA', 'PhD', 'MSc', 'BSc'}
    while len(words) > 2 and words[-1].strip(',') in credentials:
        words.pop()
    name = ' '.join(words)
    return person_name(name.title() if name.islower() or name.isupper() else name)


def person_name(value):
    if not isinstance(value, str):
        return ''
    value = ' '.join(value.split())
    value = re.sub(r"^(?:Hi[,!]?\s+(?:I'm|I am)|Hello[,!]?\s+(?:I'm|I am)|My name is|Meet)\s+", '', value)
    if (not re.fullmatch(NAME, value) or len(value) > 120
            or re.search(r'\b(?:Contact|About|Customer|Team|Privacy|Company|Founder|Director|Marketing|Coffee|Shop|Services|Read|Learn|Meet|United|London|Bristol|Our|Your|Mission|Vision|Story|Values|Welcome|Who|What|Why|How)\b', value)):
        return ''
    return value


def people_from_html(url, html):
    from .contact_recovery import contact_route
    parts = urlsplit(crawl_url(url))
    if parts.path not in {'', '/'} and not contact_route(url, parts.hostname.removeprefix('www.')):
        return []  # Article authors, testimonials and unrelated catalog people are not team evidence.
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    def scoped_emails(node):
        from .web import EMAIL_RE
        values = [(v, 'scoped_visible_text') for v in re.findall(EMAIL_RE, node.get_text(' ', strip=True))]
        for anchor in node.select('a[href]'):
            if anchor['href'].lower().startswith('mailto:'):
                values.extend((v, 'scoped_mailto') for v in unquote(anchor['href'][7:]).split('?')[0].split(','))
        for item in node.select('[data-cfemail]'):
            try:
                raw = bytes.fromhex(item['data-cfemail'])
                values.append((bytes(b ^ raw[0] for b in raw[1:]).decode(), 'scoped_cloudflare_obfuscation'))
            except (ValueError, IndexError, UnicodeError):
                pass
        return email_values(values)

    def email_values(values):
        from .web import normalize_email, outreach_email_allowed
        found = {}
        for value, method in values[:30]:
            try:
                email = normalize_email(value.strip())
                if outreach_email_allowed(email):
                    found.setdefault(email, {'email': email, 'method': method})
            except (ValueError, TypeError):
                pass
        return list(found.values())[:5]

    def add(name, role, quote, method, profiles=(), publications=()):
        name = person_name(name)
        if not name or len(quote) > 700 or re.search(r'\b(?:former|previous|ex[- ]|used to|testimonial|review by)\b', quote, re.I):
            return
        from .professionals import professional_target
        links = []
        for link in profiles[:20]:
            try:
                target = professional_target(link)[1]
                if target not in links:
                    links.append(target)
            except (ValueError, TypeError):
                pass
        item = {'name': name, 'role': role[:150], 'quote': quote,
            'method': method, 'source_url': url, 'professional_links': links,
            'email_publications': list(publications), 'inbox_ownership_verified': False,
            'current_employer_verified': False, 'buyer_verified': False}
        # Preserve each candidate's scope. Never merge an email from one card
        # with the LinkedIn link/role in another card bearing the same name.
        if name not in result or publications and not result[name].get('email_publications'):
            result[name] = item

    def walk(value, depth=0):
        if depth > 15:
            return
        if isinstance(value, list):
            for item in value[:100]:
                walk(item, depth + 1)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            if kinds in ('Review', 'Article', 'NewsArticle', 'BlogPosting') or (
                isinstance(kinds, list) and any(k in kinds for k in ('Review', 'Article', 'NewsArticle', 'BlogPosting'))
            ):
                return
            if kinds == 'Person' or isinstance(kinds, list) and 'Person' in kinds:
                name, role = value.get('name', ''), value.get('jobTitle', '')
                if isinstance(role, str) and re.search(ROLE, role, re.I):
                    aliases = value.get('sameAs', [])
                    aliases = [aliases] if isinstance(aliases, str) else aliases
                    # Preserve exact published metadata; do not synthesize a visible quote.
                    email = value.get('email', '')
                    published = email_values([(unquote(email).removeprefix('mailto:'), 'scoped_json_ld_person')]) if isinstance(email, str) else []
                    quote = f'name: {name} | jobTitle: {role}'
                    if published:
                        quote += f' | email: {email}'
                    add(name, role, quote, 'official_json_ld_person',
                        aliases if isinstance(aliases, list) else [], published)
            for key, item in list(value.items())[:100]:
                if key in {'review', 'reviews', 'testimonial', 'testimonials'}:
                    continue
                if isinstance(item, (dict, list)):
                    walk(item, depth + 1)

    for script in soup.select('script[type="application/ld+json"]')[:30]:
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError, RecursionError):
            pass
    for node in list(soup.select('script,style,nav,footer,aside,blockquote,dialog,[role="dialog"],form,[hidden],[aria-hidden="true"]')):
        node.decompose()
    for node in list(soup.select('[style]')):
        if re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', node.get('style', ''), re.I):
            node.decompose()
    # Official team sites often lack semantic <main>. Use their cleaned body
    # while preserving the existing small-card/one-heading identity boundary.
    scopes = soup.select('main,[role="main"]') or [soup.body or soup]
    headings = [h for scope in scopes for h in scope.select('h1,h2,h3,h4,h5,h6')]
    # A heading and explicit buyer-role text in the same small staff card.
    for heading in headings[:100]:
        name = person_name(heading.get_text(' ', strip=True))
        if not name and re.search(ROLE, heading.get_text(' ', strip=True), re.I):
            # Some individual staff pages publish a name and role in separate
            # spans inside one heading. Do not combine two different names.
            heading_parts = [n.get_text(' ', strip=True) for n in heading.find_all(['span', 'strong'], recursive=False)]
            # "Sarah Castle <br> Co-Founding Director" has direct text nodes,
            # not spans. Never split arbitrary prose into a guessed person.
            if heading.find('br', recursive=False):
                heading_parts.extend(str(n).strip() for n in heading.find_all(string=True, recursive=False))
            names = {person_name(part) for part in heading_parts}
            names.discard('')
            if len(names) == 1:
                name = names.pop()
        if not name:
            continue
        card = heading.parent
        for _ in range(3):
            if not card or card.name in {'main', 'body', 'html'}:
                break
            if len(card.select('h1,h2,h3,h4,h5,h6')) > 1:
                break
            text = card.get_text(' ', strip=True)
            if len(text) > 700:
                break
            role = re.search(ROLE, text, re.I)
            if role:
                publications = scoped_emails(card)
                add(name, role[0], text, 'official_staff_card',
                    [a['href'] for a in card.select('a[href]')], publications)
                if publications:
                    break
            card = card.parent
    # Small blocks preserve author proximity; never combine distant page names/roles.
    blocks = [b for scope in scopes for b in scope.select('p,li')]
    for block in blocks[:200]:
        text = block.get_text(' ', strip=True)
        if len(text) > 700:
            continue
        # Some current team layouts use a bold name plus role inside a linked
        # paragraph, not a heading. Keep one explicit name and all publication
        # links inside that same short block; never borrow a footer inbox.
        if parts.path not in {'', '/'}:
            bold_names = {person_name(n.get_text(' ', strip=True)) for n in block.select('strong,b')}
            bold_names.discard('')
            role = re.search(ROLE, text, re.I)
            if len(bold_names) == 1 and role:
                add(next(iter(bold_names)), role[0], text, 'official_bold_staff_block',
                    [a['href'] for a in block.select('a[href]')], scoped_emails(block))
        for match in re.finditer(r'(?P<name>' + NAME + r')\s*[,–—-]\s*(?P<role>' + ROLE + r')\b', text):
            add(match['name'], match['role'], text, 'official_named_role')
        for match in re.finditer(r'\b(?:owned|run|founded) by\s+(?P<name>' + NAME + r')\b', text):
            add(match['name'], '', text, 'official_named_relationship')
        # A common independent-business About statement, with no inferred job title.
        for match in re.finditer(r'\bwork of\s+[^.!?]{0,100}?\b(?P<name>' + NAME + r')(?=\s*[,.;]|\s+and\b|$)', text):
            add(match['name'], '', text, 'official_named_relationship')
    return list(result.values())[:20]
