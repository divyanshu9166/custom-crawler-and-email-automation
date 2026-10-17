"""Preserve independent public HTTP/DOM contact evidence and contact navigation."""
import copy
import hashlib
import json


def retain_http_publications(rendered, http):
    """Enrich only same-URL captures; complete person records never cross scopes.

    The evidence digest commits both original document hashes, so an HTTP-only
    publication disappearing invalidates its proof even if the DOM is unchanged.
    HTTP text is labelled as publication, never claimed as rendered visibility.
    """
    if rendered['url'] != http['url'] or rendered['sha256'] == http['sha256']:
        return rendered
    keys = ('contacts', 'review_candidates', 'named_people')
    extra = any(any(item not in rendered.get(key, []) for item in http.get(key, [])) for key in keys)
    from .professionals import sourced_profile_links
    extra = extra or bool(set(sourced_profile_links(http))-set(sourced_profile_links(rendered)))
    # A JS replacement can remove contact/team navigation on an otherwise
    # email-free homepage. Preserve these explicitly published routes now;
    # waiting for an email on this page loses the route to the email itself.
    # Targets still pass the crawler's robots/depth/page/network gates later.
    from .contact_recovery import contact_route
    from .web import domain_of
    dom_links = set(rendered.get('links', []))
    navigation_seen = set(dom_links)
    domain = domain_of(rendered['url'])
    navigation = []
    for link in http.get('links', []):
        try:
            route = contact_route(link, domain)
        except ValueError:
            continue
        if route and route not in navigation_seen:
            navigation_seen.add(route)
            navigation.append(route)
    if not extra and not navigation:
        return rendered
    versions = [('rendered_dom', rendered), ('public_html', http)]

    def tag(person, method, page):
        return {**copy.deepcopy(person), 'source_capture_method': method, 'source_sha256': page['sha256']}

    people = [tag(person, method, page) for method, page in versions for person in page.get('named_people', [])]
    # Keep mail-bearing complete records before records with no publication;
    # this does not attach an email/profile/role from one record to another.
    people.sort(key=lambda p: not bool(p.get('email_publications')))

    def contacts(kind):
        groups = {}
        for method, page in versions:
            for item in page.get(kind, []):
                groups.setdefault(item['email'], []).append((method, page, item))
        result = []
        for email, records in groups.items():
            entry = copy.deepcopy(records[0][2])
            entry['methods'] = list(dict.fromkeys(m for _, _, p in records for m in p.get('methods', [])))
            entry['named_associations'] = [tag(p, method, page) for method, page, item in records
                for p in item.get('named_associations', [])]
            entry['publication_captures'] = [{'capture_method': method, 'source_sha256': page['sha256'],
                'name': item.get('name', ''), 'role': item.get('role', '')} for method, page, item in records]
            names = {p.get('name') for _, _, p in records if p.get('name')}
            names.update(p['name'] for p in entry['named_associations'] if p.get('name'))
            roles = {p.get('role') for _, _, p in records if p.get('role')}
            roles.update(p['role'] for p in entry['named_associations'] if p.get('role'))
            entry['name'] = next(iter(names)) if len(names) == 1 else ''
            entry['role'] = next(iter(roles)) if len(names) == len(roles) == 1 else ''
            entry['identity_ambiguous'] = len(names) > 1
            result.append(entry)
        return result

    sources = [{'capture_method': method, 'sha256': page['sha256']} for method, page in versions]
    digest = hashlib.sha256(json.dumps({'schema': 'public_contact_bundle_v1', 'sources': sources},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {**rendered, 'sha256': digest, 'rendered_sha256': rendered['sha256'],
        'text': rendered['text']+'\n\nAdditional current public HTML capture (not rendered visibility):\n'+http['text'],
        'emails': sorted(set(rendered['emails']) | set(http['emails'])),
        'contacts': contacts('contacts'), 'review_candidates': contacts('review_candidates'),
        'named_people': people, 'links': list(dict.fromkeys(rendered['links']+http['links'])),
        'http_publication_retained': True, 'capture_sources': sources,
        'http_navigation_retained': bool(navigation), 'http_navigation_links': navigation}
