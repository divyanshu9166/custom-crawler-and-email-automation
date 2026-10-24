"""Public DNS readiness of a sending domain: SPF, DKIM, DMARC, MX and domain blocklists.

Reads public DNS only; nothing is sent. The result advises the operator's SPF/DKIM/DMARC
confirmation in Settings; it does not replace it.
"""
import re
import time

import dns.exception
import dns.resolver

# Selectors used by common mailbox providers; the operator can add their own.
COMMON_SELECTORS = ('google', 'selector1', 'selector2', 'default', 'dkim', 'mail', 'k1', 'k2', 's1', 's2',
                    'zoho', 'zmail', 'protonmail', 'pm', 'resend', 'mxvault', 'smtp', 'mailjet', 'sendgrid')
BLOCKLISTS = {'Spamhaus DBL': 'dbl.spamhaus.org', 'SURBL': 'multi.surbl.org', 'URIBL': 'multi.uribl.com'}
MISSING = (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers)
DOMAIN = re.compile(r'^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


class Lookup:
    """DNS lookups with short timeouts; 'error' means the answer is unknown, not absent."""
    def __init__(self, resolver=None):
        self.resolver = resolver or dns.resolver.Resolver()
        self.resolver.lifetime = 6

    def records(self, name, kind):
        try:
            return [r.to_text() for r in self.resolver.resolve(name, kind)], None
        except MISSING:
            return [], None
        except dns.exception.DNSException as exc:
            return [], type(exc).__name__

    def txt(self, name):
        rows, error = self.records(name, 'TXT')
        return [''.join(part.strip('"') for part in re.findall(r'"(?:[^"\\]|\\.)*"', row)) or row for row in rows], error


def blocklist_state(zone, answers):
    """Listed / clean / unknown. Open public resolvers are often refused with special codes."""
    if not answers:
        return 'clean'
    refused = {'dbl.spamhaus.org': {'127.255.255.252', '127.255.255.254', '127.255.255.255'},
               'multi.surbl.org': {'127.0.0.1'}, 'multi.uribl.com': {'127.0.0.1'}}.get(zone, set())
    return 'unknown' if set(answers) <= refused else 'listed'


def check(domain, selectors=(), resolver=None):
    domain = (domain or '').strip().lower().rstrip('.')
    if not DOMAIN.match(domain):
        raise ValueError('Enter a valid sending domain, such as example.com')
    lookup = Lookup(resolver)
    issues = []

    spf_all, spf_error = lookup.txt(domain)
    spf = [t for t in spf_all if t.lower().startswith('v=spf1')]
    spf_ok = len(spf) == 1 and not re.search(r'(?:^|\s)\+?all\b', spf[0].lower()) if spf else False
    if spf_error:
        issues.append(f'SPF lookup failed ({spf_error}); check again')
    elif not spf:
        issues.append('No SPF record: add the TXT record your mailbox provider gives you')
    elif len(spf) > 1:
        issues.append('More than one SPF record: merge them into one, or receivers treat SPF as broken')
    elif not spf_ok:
        issues.append('SPF ends in "+all", which lets anyone send as you: use "~all" or "-all"')
    elif not re.search(r'(?:^|\s)[+~?-]?(?:include:|a\b|a:|mx\b|mx:|ip4:|ip6:|exists:|redirect=)', spf[0].lower()):
        spf_ok = False
        issues.append("SPF authorises no sending servers: add your mailbox provider's include")

    found, dkim_errors = [], set()
    for selector in dict.fromkeys([s.strip().lower() for s in selectors if s and s.strip()] + list(COMMON_SELECTORS)):
        if not re.fullmatch(r'[a-z0-9._-]{1,63}', selector):
            continue
        rows, error = lookup.txt(f'{selector}._domainkey.{domain}')
        if error:
            dkim_errors.add(error)
        if any(re.search(r'(?:^|;)\s*p=[A-Za-z0-9+/=]{20,}', row) for row in rows):
            found.append(selector)
    if not found:
        issues.append('No DKIM key found among common selectors: turn on DKIM at your mailbox provider, or '
                      'enter your selector' + (f' (some lookups failed: {", ".join(sorted(dkim_errors))})' if dkim_errors else ''))

    dmarc_rows, dmarc_error = lookup.txt('_dmarc.' + domain)
    dmarc = next((t for t in dmarc_rows if t.lower().startswith('v=dmarc1')), '')
    policy = (re.search(r'(?:^|;)\s*p\s*=\s*(\w+)', dmarc, re.I) or [None, ''])[1].lower()
    if dmarc_error:
        issues.append(f'DMARC lookup failed ({dmarc_error}); check again')
    elif not dmarc:
        issues.append('No DMARC record: add a TXT record at _dmarc.' + domain + ' (start with "v=DMARC1; p=none")')

    mx, mx_error = lookup.records(domain, 'MX')
    mx = [m for m in mx if m.split()[-1].rstrip('.')]  # "0 ." is a null MX: the domain accepts no mail.
    if mx_error:
        issues.append(f'MX lookup failed ({mx_error}); check again')
    elif not mx:
        issues.append('No MX record: replies and bounces to this domain cannot be delivered')

    listed = []
    for name, zone in BLOCKLISTS.items():
        answers, error = lookup.records(f'{domain}.{zone}', 'A')
        state = 'unknown' if error else blocklist_state(zone, answers)
        listed.append({'list': name, 'state': state})
        if state == 'listed':
            issues.append(f'Domain is listed on {name}: request delisting before sending')
    ready = (spf_ok and bool(found) and bool(dmarc) and bool(mx) and not any(b['state'] == 'listed' for b in listed)
             and not (spf_error or dmarc_error or mx_error))
    return {'domain': domain, 'checked_at': time.time(), 'ready': ready, 'issues': issues,
            'spf': {'ok': spf_ok, 'records': spf}, 'dkim': {'ok': bool(found), 'selectors': found},
            'dmarc': {'ok': bool(dmarc), 'policy': policy, 'record': dmarc},
            'mx': {'ok': bool(mx), 'hosts': [m.split()[-1].rstrip('.') for m in mx][:5]},
            'blocklists': listed,
            'note': 'Public DNS only. DMARC p=none is monitoring only; tighten it once mail authenticates.' if policy == 'none' else
                    'Public DNS only. Blocklist "unknown" means the list refused this server\'s DNS resolver.'}
