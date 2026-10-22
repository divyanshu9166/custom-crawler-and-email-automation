"""Turn validated diagnostics into a bounded problem / proposal / test brief.

This is deliberately deterministic: raw copy, render errors and failed searches
must never become invented customer problems.
"""

IMPROVEMENTS = {'website_improvement', 'store_improvement'}


def build(audit, service):
    if service == 'ai_calling_agent':
        return {'state': 'opportunity_only', 'problem_led_required': False, 'draft_allowed': True,
                'summary': 'Assess one source-backed phone workflow; technical website audits do not establish a calling-agent need.',
                'findings': [], 'next_action': 'Review the published phone task and proposed call flow, then agree a small pilot.',
                'business_pain_confirmed': False}
    findings = []
    reports = {r.get('event_id'): r for r in audit.get('reports', [])}
    for observation in audit.get('observations', []):
        ref = observation['ref']
        parts = ref.split(':')
        report = reports.get(int(parts[1])) if len(parts) == 3 and parts[1].isdigit() else None
        if not report:
            continue
        device = observation.get('device', ref.split(':')[-1])
        supporting_measurements = []
        if observation['kind'] == 'lab_measurement':
            measurement = next((m for m in report.get('measurements', []) if m['strategy'] == device), {})
            metrics = measurement.get('metrics', {})
            lcp = metrics.get('largest-contentful-paint', {})
            supporting_measurements = [{'metric': key, **value} for key, value in metrics.items()]
            opportunities = {o['id'] for o in measurement.get('opportunities', [])}
            if opportunities & {'font-display-insight', 'font-display'}:
                fix = 'Review the flagged font loading rules so text can remain visible while fonts load; test an appropriate font-display fallback and check both text and icon rendering.'
                test = 'Repeat the same mobile/desktop lab strategy after the font-loading change; compare paint timings and confirm the flagged font-display issue is resolved without visual regressions.'
            elif opportunities & {'render-blocking-insight', 'render-blocking-resources'}:
                fix = 'Review the flagged blocking CSS and scripts; inline only required critical styles and defer noncritical resources after checking their dependencies.'
                test = 'Repeat the same lab strategy after the loading change; compare paint timings and retest the affected page interactions.'
            elif lcp.get('numericUnit') == 'millisecond' and lcp.get('numericValue', 0) > 2500:
                fix = 'Trace the largest visible element in a repeat lab run; inspect its loading priority and dependencies, then optimise the confirmed bottleneck.'
                test = 'Compare largest-contentful-paint before and after the change under the same lab settings; aim for 2,500 ms or less.'
            elif metrics.get('total-blocking-time', {}).get('numericValue', 0) > 200 and metrics['total-blocking-time'].get('numericUnit') == 'millisecond':
                fix = 'Trace the long main-thread tasks in the repeat lab run, then split or defer confirmed noncritical script work and retest the enquiry controls.'
                test = 'Compare total blocking time under the same lab settings and check keyboard, touch and existing widget interactions after the script changes.'
            elif metrics.get('cumulative-layout-shift', {}).get('numericValue', 0) > .1 and metrics['cumulative-layout-shift'].get('numericUnit') == 'unitless':
                fix = 'Inspect the layout-shift trace to identify moving elements, then stabilise their confirmed sizing or insertion behaviour without hiding required content.'
                test = 'Repeat the same lab layout-shift measurement and check the affected content and controls while the page loads.'
            elif metrics.get('first-contentful-paint', {}).get('numericValue', 0) > 1800 and metrics['first-contentful-paint'].get('numericUnit') == 'millisecond':
                fix = 'Trace the initial rendering path, then improve the confirmed loading dependencies so initial content can be painted sooner.'
                test = 'Repeat first-contentful-paint under the same lab settings and inspect the initial content and existing enquiry controls.'
            else:
                continue  # A low aggregate score alone does not identify an actionable problem.
            reproduce = f'Run Lighthouse performance on the exact source URL using the {device} strategy. Results may vary between runs.'
            limit = 'This is a lab performance finding. Its root cause, visitor experience and business impact still need confirmation.'
        elif observation['kind'] == 'journey_observation':
            code = observation['code']
            if code == 'broken_cta':
                fix = 'Repair the existing enquiry/booking link or restore its destination, then update every matching call to action and check the route on mobile and desktop.'
                test = 'Repeat the two public GET checks and open the same visible link on both viewports; verify the intended destination loads without submitting a form.'
                benefit = 'Give visitors using that existing link a working route to the enquiry step; measure actual enquiries separately.'
            elif code == 'form_labels':
                fix = 'Add clear persistent labels connected to the observed form fields, retaining their existing validation and integration; check the form with keyboard and mobile layouts.'
                test = 'Repeat the same form capture and confirm each observed control has a nonempty associated label or accessible name; do not submit real enquiries.'
                benefit = 'Make the enquiry fields clearer to identify and revisit, including with assistive technology; actual completion improvement remains to be measured.'
            elif code == 'text_contrast':
                fix = 'Adjust the sampled text and background colors to increase contrast while preserving the brand palette; check the service copy on mobile and desktop before applying the change across matching panels.'
                test = 'Repeat the computed-color contrast check at the same selector and font size; inspect the saved screenshots and confirm the text remains readable in the actual layout.'
                benefit = 'Make the affected service information easier to distinguish from its background; customer comprehension and enquiry impact still need testing.'
            else:
                fix = 'Identify the element extending the mobile layout, then adjust its width, wrapping or overflow rules while retaining intentional scrolling components.'
                test = 'Repeat both viewport samples and verify the document fits while the existing enquiry controls remain visible and usable.'
                benefit = 'Keep the enquiry page readable within the captured viewport; verify usability before claiming an improvement.'
            reproduce = f'Open {observation["url"]} in the {device} viewport and inspect {observation["selector"]}; repeat the captured check.'
            limit = observation['scope']
        elif observation['kind'] == 'render_observation':
            fix = 'Identify the element wider than the viewport and adjust its width, wrapping or overflow rules; retain intentional carousels.'
            test = f'Repeat the capture at {observation["anchor"]}px and confirm the document fits without hiding required content.'
            reproduce = f'Open the exact source URL at {observation["anchor"]}px width and compare document scroll width with viewport width.'
            limit = 'Overflow was observed in this capture. Whether it affects a real customer task must still be checked.'
        else:
            continue
        help_plan = [fix, test]
        benefit = benefit if observation['kind'] == 'journey_observation' else ('Aim to make page content visible sooner and keep the next step usable; confirm the improvement with the repeat test.'
                   if observation['kind'] == 'lab_measurement' else
                   'Aim to let visitors read and use the page without unintended sideways scrolling; confirm this on the affected viewport.')
        findings.append({**observation, 'proposed_fix': fix, 'verification': test,
                         'help_plan': help_plan, 'intended_benefit': benefit,
                         'reproduce': reproduce, 'limitations': limit,
                         'supporting_measurements': supporting_measurements,
                         'report_url': report.get('report_url'),
                         'screenshot': observation.get('screenshot') or report.get('screenshots', {}).get(device)})
        primary = observation.get('primary_measurement')
        if primary:
            flags = observation['fact'].split('. Lighthouse flagged ',1)
            findings[-1]['fact'] = f'{device} Lighthouse lab largest-contentful-paint: {primary["anchor"]} seconds.'+(' Lighthouse flagged '+flags[1] if len(flags)>1 else '')
    findings.sort(key=lambda f: f.get('priority', 30), reverse=True)
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
