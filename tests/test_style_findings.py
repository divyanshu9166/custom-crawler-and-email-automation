import copy
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from outreach import diagnostics, email_writer, journey

URL='https://bright-demo.com/'
IMAGE='lead-1-1792410725-123abc-mobile.png'


def rendered_samples():
    reader=Path('outreach/static/journey-reader.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':390,'height':844})
        page.set_content('''<html><style>body{background:white}p{font:16px Arial} .low{background:#44c594;color:white}</style>
        <main><p id="service" class="low">Commercial cleaning services for offices nationwide.</p>
        <p id="good" style="color:black;background:white">Request a detailed office cleaning quote.</p>
        <p id="gradient" style="color:white;background:linear-gradient(black,white)">Text over a gradient is outside this check.</p>
        <p id="alpha" style="color:white;background:#44c594;opacity:.6">Semitransparent content requires visual review.</p>
        <p id="shadow" style="color:white;background:#44c594;text-shadow:1px 1px black">Shadowed text is outside the computed check.</p>
        <p id="hidden" class="low" hidden>This hidden service text must not be reported.</p></main></html>''')
        first,second=page.evaluate(reader),page.evaluate(reader)
        browser.close()
    return first,second


def test_actual_dom_styles_produce_repeatable_scoped_contrast_finding():
    first,second=rendered_samples()
    assert [c['selector'] for c in first['contrast']]==['#service']
    assert first['contrast_checked']>=2
    result=journey.capture(first,second,'mobile',IMAGE)
    finding=next(f for f in result['findings'] if f['code']=='text_contrast')
    assert finding['contrast']['ratio']<3 and finding['selector']=='#service'
    changed=copy.deepcopy(second)
    changed['contrast'][0]['background']=[0,0,0]
    assert not journey.capture(first,changed,'mobile',IMAGE)['findings']


@pytest.mark.parametrize('change',['ratio','minimum','foreground','font_size'])
def test_malformed_or_inconsistent_contrast_proof_is_not_citable(change):
    # Supply a known valid ratio from the actual reader, then corrupt one field.
    proof=rendered_samples()[0]['contrast'][0]
    proof[change]={'ratio':1.0,'minimum':3,'foreground':[999,255,255],'font_size':float('nan')}[change]
    assert not journey.contrast_valid(proof)


def test_readability_finding_reaches_conclusion_and_accepts_focused_fix_without_addon(db,prepared):
    first,second=rendered_samples()
    sample=journey.capture(first,second,'mobile',IMAGE)
    lid=prepared['lead_id']
    sample['screenshot']=IMAGE.replace('lead-1-',f'lead-{lid}-')
    sample['url']=URL
    db.event('screenshot',{'lead_id':lid,'url':URL,'complete':False,
        'journey':{'version':1,'state':'checked','captures':[sample],'links':[]}})
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    db.event('performance',{'lead_id':lid,'url':URL,'status':'complete','strategies':{'mobile':{'final_url':URL,'score':51,'metrics':{'largest-contentful-paint':{'numericValue':4800,'numericUnit':'millisecond'}}}}})
    audit=diagnostics.snapshot(db,lead)
    finding=audit['conclusion']['findings'][0]
    packet=email_writer.research_packet(lead,{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'},db.all('SELECT * FROM evidence'),audit_context=audit)
    assert [o['ref'] for o in packet['audit_context']['observations']]==[finding['ref']]

    assert finding['code']=='text_contrast' and 'brand palette' in finding['proposed_fix']
    body=('In two mobile checks on Bright Demo, white service text on green panels had low contrast. '
          'We can adjust those text and background colors while preserving the brand palette, '
          'making the affected cleaning information easier to read. Would a marked-up example of that change be useful?')
    output={'messages':[{'step':0,'subject':'Bright Demo service-panel readability','body':body,
        'diagnostic_refs':[finding['ref']],
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]}
    assert email_writer.validate_output(output,lead,db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],)),
        db.all('SELECT * FROM evidence'),audit_context=audit)
    output['messages'][0]['body']='Your Lighthouse score is low. We can add an AI calling agent. Would a call be useful?'
    with pytest.raises(ValueError):
        email_writer.validate_output(output,lead,db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],)),
            db.all('SELECT * FROM evidence'),audit_context=audit)

def test_greeting_uses_published_domain_matched_homepage_brand_without_renaming_identity():
    lead={'company':'Office Cleaning London – Expert Commercial Cleaners','website':'https://www.skweekykleen.co.uk/'}
    source={'id':1,'url':lead['website'],'title':'Commercial Cleaning Company | Skweeky Kleen',
            'text':'At Skweeky Kleen, we provide commercial cleaning services.'}
    assert email_writer.display_name(lead,[source])=='Skweeky Kleen'
    assert lead['company']=='Office Cleaning London – Expert Commercial Cleaners'
    assert email_writer.display_name(lead,[{**source,'url':'https://other-company.com/'}])==lead['company']
    assert email_writer.display_name(lead,[{**source,'title':'Commercial Cleaning | Other Company'}])==lead['company']
    assert email_writer.display_name(lead,[{**source,'text':'Unrelated imported content'}])==lead['company']
