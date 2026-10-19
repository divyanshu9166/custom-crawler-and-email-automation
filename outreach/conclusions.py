"""Turn validated diagnostics into a bounded problem / proposal / test brief.

This is deliberately deterministic: raw copy, render errors and failed searches
must never become invented customer problems.
"""

IMPROVEMENTS = {'website_improvement', 'store_improvement'}


def build(audit, service):
    findings = []
    reports = {r.get('event_id'): r for r in audit.get('reports', [])}
    for observation in audit.get('observations', []):
        ref = observation['ref']
        parts = ref.split(':')
        report = reports.get(int(parts[1])) if len(parts) == 3 and parts[1].isdigit() else None
        if not report:
            continue
        device = ref.split(':')[-1]
        supporting_measurements = []
        if observation['kind'] == 'lab_measurement':
            measurement = next((m for m in report.get('measurements', []) if m['strategy'] == device), {})
            metrics = measurement.get('metrics', {})
            lcp = metrics.get('largest-contentful-paint', {})
            supporting_measurements = [{'metric': key, **value} for key, value in metrics.items()]
            if lcp.get('numericUnit') == 'millisecond' and lcp.get('numericValue', 0) > 2500:
                fix = 'Trace the largest visible element in a repeat lab run; inspect its loading priority and dependencies, then optimise the confirmed bottleneck.'
                test = 'Compare largest-contentful-paint before and after the change under the same lab settings; aim for 2,500 ms or less.'
            else:
                fix = 'Profile the page under the same Lighthouse settings, identify the largest measured loading or scripting bottleneck, and optimise that bottleneck.'
                test = 'Repeat the same device lab test before and after implementation and compare its score and underlying timings.'
            reproduce = f'Run Lighthouse performance on the exact source URL using the {device} strategy. Results may vary between runs.'
            limit = 'This is a lab performance finding. Its root cause, visitor experience and business impact still need confirmation.'
        elif observation['kind'] == 'render_observation':
            fix = 'Identify the element wider than the viewport and adjust its width, wrapping or overflow rules; retain intentional carousels.'
            test = f'Repeat the capture at {observation["anchor"]}px and confirm the document fits without hiding required content.'
            reproduce = f'Open the exact source URL at {observation["anchor"]}px width and compare document scroll width with viewport width.'
            limit = 'Overflow was observed in this capture. Whether it affects a real customer task must still be checked.'
        else:
            continue
        findings.append({**observation, 'proposed_fix': fix, 'verification': test,
                         'reproduce': reproduce, 'limitations': limit,
                         'supporting_measurements': supporting_measurements,
                         'screenshot': report.get('screenshots', {}).get(device)})
    required = service in IMPROVEMENTS
    ready = bool(findings)
    return {'state': 'finding_ready' if ready else 'needs_evidence' if required else 'opportunity_only',
            'problem_led_required': required, 'draft_allowed': ready or not required,
            'summary': findings[0]['fact'] if ready else
                'No current, reproducible website problem has been established. Hold the improvement pitch; a business description or quote button is not a defect.',
            'findings': findings, 'next_action': 'Review the finding and its matching proposed fix before approving the email.' if ready else
                'Complete a current performance or desktop/mobile audit. Failed or partial captures need investigation, not a claim about the prospect.',
            'business_pain_confirmed': False}


def require_finding(audit, service):
    conclusion = build(audit or {}, service)
    if not conclusion['draft_allowed']:
        raise ValueError('Improvement email held: no current reproducible finding. Complete a valid audit first; existing drafts are preserved.')
    return conclusion
