/* A focused prospect workspace; existing research and sales tools remain available. */
window.WorkbenchWorkspace = {
  researchLabel(job) {
    const names = {research:'Research',screenshot:'Screenshots',performance:'PageSpeed audit',contact_research:'Contact research',professional_research:'Profile research',social_research:'Post research'};
    return (names[job.kind] || 'Research')+' '+(job.state === 'running' ? 'running' : 'queued');
  },
  updateResearchActivity(activity, {esc, reload, refreshNeeded=false}) {
    const panel = document.querySelector('#prospect-research-status');
    if (!panel || !activity) return;
    const job = activity.job, busy = activity.active_jobs.length > 0;
    const inconsistent = !busy && activity.lead_status === 'researching';
    const failed = !busy && (job?.state === 'failed' || activity.lead_status === 'research_failed' || inconsistent);
    const cancelled = !busy && job?.state === 'cancelled';
    const title = busy ? this.researchLabel(job) : failed ? 'Research needs attention' : cancelled ? 'Research cancelled' : activity.saved_pages ? 'Research saved' : 'Not researched yet';
    const waiting = busy && job.state === 'pending';
    const note = busy ? !activity.worker_enabled ? 'Research automation is OFF. This work is saved in the queue; turn Research ON in Settings to continue.' : waiting ?
      (job.due_at*1000 > Date.now()+2000 ? 'Waiting for the next attempt at '+new Date(job.due_at*1000).toLocaleString()+'. No need to start research again.' : 'Waiting for an available worker. No action needed; you can continue collecting prospects.') :
      'This prospect is being processed. No action needed; saved results and screenshots update here.' : failed ? job?.error || (inconsistent ? 'No active source job is recorded for this prospect. Saved sources are preserved; inspect Research & audits before retrying.' : 'The latest research pass could not finish. Existing sources are preserved; inspect Research & audits before retrying.') : cancelled ? 'This research job was cancelled. Saved sources are preserved.' :
      activity.saved_pages ? 'Results from the saved research pass are available. Saved pages do not imply complete website coverage or a verified business problem.' : 'Start business research to collect source pages and published contact details.';
    const capture = activity.screenshots;
    const labels = {pending:'Screenshots queued',running:'Capturing desktop & mobile',waiting_for_research:'Screenshots waiting for website research',complete:'Screenshots ready',partial:'Screenshots saved · partial capture',stale:'Older screenshots · refresh needed',target_unverified:'Screenshot website match needs review',failed:'Screenshot capture failed',cancelled:'Screenshot capture cancelled',disabled:'Automatic screenshots OFF',unavailable:'Screenshot files unavailable',not_applicable:'Website screenshots not applicable',not_run:'Screenshots not captured yet'};
    const old = ['pending','running','waiting_for_research','failed','cancelled'].includes(capture.state) || ['stale','target_unverified'].includes(capture.report_state);
    panel.className = 'research-progress '+(failed || cancelled ? 'needs-attention' : busy ? 'in-progress' : '');
    panel.innerHTML = `<div class="research-progress-heading"><div><span class="eyebrow">DATA COLLECTION</span><h3>${esc(title)}</h3></div><span class="workspace-pill">${activity.worker_enabled ? 'Research ON' : 'Research OFF'}</span></div><p role="status">${esc(note)}</p><div class="research-progress-facts"><span><strong>${activity.saved_pages}</strong> saved page contents</span><span><strong>${activity.contacts}</strong> contact records</span></div><div class="research-capture-status"><strong>${esc(labels[capture.state] || 'Screenshot status unavailable')}</strong><p class="small">${capture.state === 'waiting_for_research' ? 'Desktop/mobile capture follows a successful website research pass.' : capture.state === 'partial' ? 'Images are saved, but rendering was incomplete. This alone does not prove a website defect.' : 'Page contents and screenshot images are separate records.'}</p>${Object.entries(capture.files).map(([device,name])=>`<a href="/api/screenshots/${encodeURIComponent(name)}" target="_blank" rel="noopener noreferrer">View ${esc(device)} screenshot${old ? ' (previous capture)' : ''}</a>`).join(' · ')}${capture.state === 'failed' && capture.error ? `<p class="error">${esc(capture.error)}</p>` : ''}</div><p class="small">${activity.auto_prepare_enabled ? 'Automatic email preparation is ON. An eligible prospect can proceed to one unsent draft after research.' : 'Data collection mode · automatic email preparation is OFF. Create email is optional when research is ready.'} Nothing is sent by research.</p>${refreshNeeded ? '<p class="small">New results are saved. Your open form has been preserved.</p><button type="button" data-refresh-research>View updated research</button>' : ''}`;
    panel.querySelector('[data-refresh-research]')?.addEventListener('click',async event=>{
      event.currentTarget.disabled=true;
      try {await reload();} catch (error) {window.WorkbenchFeedback.notice('Research refresh failed: '+error.message,true);panel.querySelector('[data-refresh-research]').disabled=false;}
    });
    const step = document.querySelector('[data-research-step]');
    if (step) {const done = !busy && !failed && !cancelled && activity.saved_pages > 0;step.classList.toggle('done',done);step.innerHTML = `<span>${done ? '✓' : '1'}</span>${busy ? esc(this.researchLabel(job)) : 'Research'}`;}
    const preparation = document.querySelector('[aria-label="Email preparation"]');
    if (preparation) preparation.hidden = busy && preparation.dataset.preparationActive !== 'true' && !document.querySelector('[data-edit]');
    for (const id of ['research-again','continue-research','screenshot','performance','prepare-emails']) {
      const button = document.getElementById(id); if (!button) continue;
      const blocked = id === 'prepare-emails' ? busy : id === 'research-again' || id === 'continue-research' ? busy : activity.active_jobs.some(j=>j.kind === 'research' || j.kind === (id === 'screenshot' ? 'screenshot' : 'performance'));
      if (blocked) {if (!button.dataset.researchBlocked) button.dataset.researchWasDisabled=String(button.disabled);button.dataset.researchBlocked='true';button.disabled=true;button.title='This prospect already has work queued or running. Status updates above.';}
      else if (button.dataset.researchBlocked && id !== 'prepare-emails') {button.disabled=button.dataset.researchWasDisabled === 'true';delete button.dataset.researchBlocked;button.removeAttribute('title');}
    }
  },
  initialize() {
    const writer = document.querySelector('#writer-settings-form');
    const column = writer.parentElement;
    column.prepend(writer);
    writer.after(document.getElementById('pagespeed-settings-form'));
    for (const [id, title, note] of [
      ['mail-settings-form', 'Connect a sending mailbox', 'Only needed when you are ready to send'],
      ['research-settings-form', 'Research sources & automation preferences', 'Advanced source controls'],
      ['credentials-form', 'Sign-in & account security', 'Change your workspace username or password']
    ]) {
      const form = document.getElementById(id);
      const section = document.createElement('details');
      section.className = 'settings-group';
      section.id = id+'-details';
      section.innerHTML = `<summary>${title}<span>${note}</span></summary>`;
      form.before(section);
      section.append(form);
    }
  },
  organize(data, finding, {esc, link, api, reload}) {
    const detail = document.querySelector('#detail');
    const original = [...detail.children];
    const heading = detail.querySelector('.lead-heading');
    const preparation = detail.querySelector('[aria-label="Email preparation"]');
    const contacts = [...detail.querySelectorAll(':scope > .contact')];
    const marker = detail.querySelector('#email-sequence');
    const primary = contacts.find(c => c.querySelector('[data-edit]')) || contacts[0];
    const advanced = document.createElement('details');
    advanced.className = 'advanced-workspace';
    advanced.id = 'advanced-research';
    advanced.innerHTML = '<summary>Advanced tools & evidence<span>Optional research, source history, qualification and sending checks</span></summary><div class="advanced-content"></div>';
    const advancedBody = advanced.querySelector('div');
    const group = (title, note, id) => {
      const section = document.createElement('details');
      section.className = 'advanced-group';
      section.id = id;
      section.innerHTML = `<summary>${title}<span>${note}</span></summary><div class="advanced-group-content"></div>`;
      advancedBody.append(section);
      return section.querySelector('div');
    };
    const researchTools = group('Research & audits', 'Refresh website research, run audits and inspect reports', 'research-tools-group');
    const peopleTools = group('People & public profiles', 'Published contacts, LinkedIn/X observations and ownership checks', 'people-tools-group');
    const qualificationTools = group('Qualification & service selection', 'Correct the automatic business review only when needed', 'qualification-tools-group');
    const recipientTools = group('Recipient & sending checks', 'Mailbox status, contact details and final sending approval', 'recipient-tools-group');
    const guide = document.createElement('details');
    guide.className = 'tool-guide';
    const uses = [
      ['Save draft', 'Save your edited subject and email. This does not send it.'],
      ['Rewrite from research / Regenerate email', 'Replace an unapproved email with fresh AI wording from the current reviewed finding. Saved edits can be replaced.'],
      ['Check mailbox', 'Queue technical mailbox verification. Syntax or MX records alone do not prove a working inbox.'],
      ['Do not contact', 'Suppress this address so the system does not send outreach to it.'],
      ['Name, Role & Save contact', 'Correct the person and job role associated with a published address. This does not prove buying authority.'],
      ['Technical verification response', 'Raw checker diagnostics for troubleshooting. VerificationUnavailable means the checker failed, not that the address is valid or invalid.'],
      ['Research again', 'Start a fresh research pass. Reviewed findings can return to review; the displayed old email is not automatically rewritten.'],
      ['Continue crawl', 'Resume the existing crawl and eligible bounded retries; it does not restart every page.'],
      ['Find public contacts', 'Research published business contact routes using public sources; it does not guess addresses.'],
      ['Check verifier', 'Check whether the verification service is available. This is separate from checking a real mailbox.'],
      ['Desktop & mobile audit', 'Capture the website at desktop/mobile sizes and inspect bounded layout observations. A partial render is not a proven website defect.'],
      ['PageSpeed audit', 'Queue a Lighthouse lab performance test. Provider access/quota must work; a failed request creates no score.'],
      ['Review priority', 'Order prospects by evidence and readiness. The score is not a probability of winning a client.'],
      ['Public professional profiles', 'Inspect public LinkedIn/X profile observations and official team-page evidence for a relevant buyer.'],
      ['Known public profile URL', 'Optionally target a particular public profile. Leave blank for the configured discovery search.'],
      ['Research public professional profiles', 'Queue that profile research; review source ownership and current company relevance afterward.'],
      ['LinkedIn / X post research', 'Collect accessible public posts for business context; posts alone do not prove buying intent.'],
      ['Discovery sources', 'Show where the company or profile candidate came from. A search match still needs identity review.'],
      ['Saved source pages', 'Inspect saved page excerpts, URLs and capture dates. Search or filter current research and historical captures.'],
      ['Historical capture', 'An older saved page that was not refreshed in the latest research pass; retained for reference.'],
      ['Use this sourced idea', 'Fill the manual review form with a suggested service and source quote. It does not approve or send anything.'],
      ['Company, country & timezone', 'Confirm which business and market the research concerns and the time zone used for scheduling.'],
      ['Country source & exact location quote', 'Link the country decision to words actually captured on the business source.'],
      ['Business type', 'Record the reviewed entity category used by contact eligibility checks; it is not inferred from a lab score.'],
      ['Primary service & reviewed goal', 'Choose one offer and the matching inquiry or ecommerce goal.'],
      ['AI calling agent / call flow', 'A proposed qualification, booking or support phone workflow based on a published phone process. The preview does not make calls or connect a live calendar.'],
      ['Save qualification', 'Save the source-backed business and offer decision. A changed qualification invalidates unsent drafts.'],
      ['Supporting preview', 'A local proposed audit/concept/FAQ/workflow to review. It is not automatically delivered to the prospect.'],
      ['Recipient & sending approval', 'Review recipient relevance, eligibility and messages before allowing scheduling. Global sending controls still apply.']
    ];
    guide.innerHTML = `<summary>What does each tool do?</summary><p>These tools are for exceptions and deeper review. You do not need to open every section for each prospect.</p><div class="tool-reference"><table><thead><tr><th>Tool</th><th>Purpose</th></tr></thead><tbody>${uses.map(([name,use])=>`<tr><td>${esc(name)}</td><td>${esc(use)}</td></tr>`).join('')}</tbody></table></div>`;
    advancedBody.prepend(guide);
    const sources = document.createElement('details');
    sources.className = 'saved-sources';
    sources.innerHTML = `<summary>Saved source pages (${data.evidence.length})</summary><p>Saved page text and metadata, separate from screenshot images. Current captures can support the review. Historical captures are retained for reference.</p><div class="source-filters"><input type="search" aria-label="Search saved pages" placeholder="Search saved pages"><select aria-label="Source capture period"><option value="current">Current research</option><option value="history">Historical captures</option><option value="all">All saved pages</option></select></div><p class="source-count" role="status"></p><div class="source-results"></div><button type="button" class="source-more">Show more pages</button>`;
    const intro = document.createElement('section');
    intro.className = 'prospect-header';
    const l = data.lead;
    intro.innerHTML = `<div><span class="eyebrow">PROSPECT WORKSPACE</span><h2>${esc(l.company)}</h2>${link(l.website || l.profile_url)}</div><span class="workspace-pill">${l.country ? esc(l.country) : 'Market needs review'} · ${l.campaign === 'B' ? 'Ecommerce' : 'Business enquiries'}</span>`;
    const mapsReport = data.crawl ? JSON.parse(data.crawl.report) : {};
    const maps = mapsReport.signal?.public_snapshot;
    if (maps?.capture_method === 'google_business_visible_listing') {
      intro.insertAdjacentHTML('beforeend', `<div class="google-business-summary"><strong>Google Business Profile</strong><p>${esc(maps.business_category || '')}${maps.address ? ' · '+esc(maps.address) : ''}</p><p>${maps.public_phone ? 'Public phone: '+esc(maps.public_phone) : 'No public phone captured'} · ${esc(l.website_status.replaceAll('_',' '))}</p><p class="small">A missing Website field is a research clue. The website lookup and published-email checks still apply; phone-only records do not generate guessed email addresses.</p></div>`);
    }
    const steps = document.createElement('ol');
    steps.className = 'workspace-steps';
    const hasSource = data.evidence.some(e => e.current_for_review && e.business_for_review !== false);
    const hasEmail = data.messages.some(m => m.step === 0);
    steps.innerHTML = [['Research', hasSource], ['Match an offer', !!data.offer_workflow?.selected_service], ['Review email', hasEmail]].map(([label,done],i) => `<li ${i === 0 ? 'data-research-step' : ''} class="${done ? 'done' : ''}"><span>${done ? '✓' : i+1}</span>${label}</li>`).join('');
    const brief = document.createElement('section');
    brief.className = 'business-brief';
    const evidence = data.evidence.find(e => e.id === finding.evidence_id && e.current_for_review);
    brief.innerHTML = `<div class="brief-title"><span class="eyebrow">RESEARCH SUMMARY</span><h3>Why this prospect?</h3></div><div class="brief-facts"><div><span>Business fit</span><p>${esc(l.fit_notes || 'Research will establish whether this business matches your target.')}</p></div><div><span>Proposed approach</span><p>${esc(finding.suggestion || 'No supported offer yet. Prepare the email after research is available.')}</p></div></div>${evidence && finding.quote ? `<details class="brief-source"><summary>View supporting source</summary><blockquote>${esc(finding.quote)}</blockquote>${link(evidence.url)}<p class="small">Captured ${new Date(evidence.fetched_at*1000).toLocaleDateString()}. The proposed approach is an idea to review, not a confirmed client requirement.</p></details>` : ''}`;
    const basis = data.offer_workflow?.evidence_basis;
    if (basis) {
      const labels = {measured_observation:'Measured observation',exploratory_opportunity:'Exploratory opportunity',insufficient_evidence:'More evidence needed'};
      brief.insertAdjacentHTML('afterbegin', `<div class="audit-basis offer-evidence-basis"><strong>${esc(labels[basis.classification] || 'Evidence review')}</strong><p>${esc(basis.note)}</p></div>`);
    }
    const proofIds = data.offer_workflow?.prepared_current_artifact_ids || [];
    const proof = data.deliverables.find(a => proofIds.includes(a.id));
    const proofPanel = document.createElement('section');
    proofPanel.className = 'panel proof-preview';
    proofPanel.setAttribute('aria-label','Proof of value preview');
    proofPanel.innerHTML = '<h3>Supporting preview</h3><p>Review alongside the email. A local concept or test plan is not a completed client implementation.</p>';
    if (proof) {
      proofPanel.insertAdjacentHTML('beforeend', `<details><summary>${esc(proof.title)} · ${proof.state === 'draft' ? 'Draft for review' : 'Reviewed'}</summary><iframe title="Proof of value preview" sandbox="" style="width:100%;height:430px;border:0" srcdoc="${esc(proof.body)}"></iframe></details>`);
    } else if (data.offer_workflow?.selected_service) {
      const button = document.createElement('button');
      button.textContent = 'Prepare supporting preview';
      const result = document.createElement('p');
      result.setAttribute('role','status');
      button.onclick = async () => {
        button.disabled = true;
        result.textContent = 'Preparing a source-backed preview; your email will be preserved…';
        try { await api(`/api/leads/${l.id}/proof-preview`,'POST',{}); await reload(); }
        catch (e) { result.textContent = e.message; button.disabled = false; }
      };
      proofPanel.append(button,result);
    } else proofPanel.insertAdjacentHTML('beforeend','<p>Available automatically after a supported offer is selected.</p>');
    const audits = data.diagnostics;
    const conclusion = audits?.conclusion;
    const best = conclusion?.findings[0];
    const calling = data.offer_workflow?.calling_plan;
    const pitch = document.createElement('section');
    pitch.className = 'pitch-summary';
    pitch.setAttribute('aria-label', 'Research conclusion');
    const assessmentHeld = !hasEmail && data.preparation?.result?.state === 'needs_evidence' && l.lead_kind !== 'profile' && !best;
    const held = conclusion && (!conclusion.draft_allowed || assessmentHeld);
    const performanceReport = audits?.reports.find(r=>r.kind==='performance');
    const gapExplanation = assessmentHeld ? 'Research is saved, but no current reproducible website problem supports this offer. '+
      (performanceReport?.quota_limited ? 'PageSpeed was blocked by provider quota; configure working PageSpeed access before retrying.' :
       performanceReport?.state === 'not_run' ? 'PageSpeed has not been measured. Run the PageSpeed audit to check loading performance.' :
       ['failed','stale','target_unverified'].includes(performanceReport?.state) ? 'The PageSpeed report is unavailable or not current. Resolve the audit issue before retrying.' :
       'The available checks have not established a suitable problem-led offer. Further business evidence is needed; a draft is not guaranteed.') : '';
    pitch.innerHTML = `<div class="pitch-heading"><span class="eyebrow">THE OFFER AT A GLANCE</span><span class="workspace-pill">${held ? 'More evidence needed' : best ? 'Measured finding' : 'Proposed opportunity'}</span></div><h3>${held ? 'Improvement pitch on hold' : 'What we found & how we can help'}</h3><div class="pitch-points"><div><span>01 · What we found</span><p>${esc(best?.fact || (held ? conclusion.summary : evidence && finding.quote ? finding.quote : 'Research is still establishing a relevant offer.'))}</p></div><div><span>02 · What we can do</span><p>${esc(best?.proposed_fix || (held ? 'Wait for a current, reproducible finding before proposing a website fix.' : finding.suggestion || 'Select a source-backed service after research.'))}</p></div><div><span>03 · Intended benefit</span><p>${esc(best?.intended_benefit || 'Confirm the business goal and usefulness of the proposed change before implementation. No client result has been measured.')}</p></div></div><details class="quick-evidence"><summary>View supporting evidence</summary>${best ? `<p>${esc(best.fact)}</p>${link(best.report_url || best.url)}<p class="small">${new Date(best.captured_at*1000).toLocaleString()} · Lab/capture evidence; customer impact is unconfirmed.</p>` : evidence && finding.quote ? `<blockquote>${esc(finding.quote)}</blockquote>${link(evidence.url)}` : '<p>No current evidence supports this pitch yet.</p>'}</details>${held && hasEmail ? '<p class="small">Your existing email is preserved. A saved draft is not proof of an identified problem.</p>' : ''}`;
    if (calling?.proposed_work) {
      const points = pitch.querySelectorAll('.pitch-points p');
      points[1].textContent = calling.proposed_work;
      points[2].textContent = calling.intended_benefit;
    }
    if (best?.screenshot) {
      const captureLink = document.createElement('a');
      captureLink.textContent = 'View saved screenshot';
      captureLink.href = '/api/screenshots/'+encodeURIComponent(best.screenshot);
      captureLink.target = '_blank';
      captureLink.rel = 'noopener';
      pitch.querySelector('.quick-evidence').append(captureLink);
    }
    const solution = data.offer_workflow?.prospect_solution;
    if (solution && !held) {
      if (solution.project_scope) pitch.querySelectorAll('.pitch-points p')[1].textContent = solution.project_scope;
      const names = {chatbot:'Chatbot with human handoff', ai_calling_agent:'AI calling agent'};
      const additions = solution.optional_services || [];
      const note = document.createElement('p');
      note.className = 'small';
      note.textContent = (solution.chatbot_status === 'present' ? 'Existing chatbot: preserve it. ' : '') +
        (additions.length ? 'Optional additions: '+additions.map(o => names[o.service]+(o.status === 'optional_fit_check' ? ' (confirm fit)' : '')).join(' · ')+'.' : '');
      if (note.textContent) pitch.querySelector('.quick-evidence').before(note);
    }
    if (hasEmail) {
      const reviewLink = preparation?.querySelector('a[href="#email-sequence"]');
      if (reviewLink) { reviewLink.className = 'text-control'; pitch.querySelector('.pitch-heading').append(reviewLink); }
    }
    if (conclusion) {
      const approach = brief.querySelector('.brief-facts > div:last-child p');
      if (approach && conclusion.problem_led_required && conclusion.findings.length) approach.textContent = conclusion.findings[0].proposed_fix;
      if (held) {
        steps.children[1]?.classList.remove('done');
        const number = steps.children[1]?.querySelector('span');
        if (number) number.textContent = '2';
        if (approach) approach.textContent = 'No problem-led fix selected until a current finding is available.';
        if (preparation) {
          preparation.classList.add('is-attention');
          preparation.classList.remove('is-ready');
          preparation.querySelector('h3').textContent = 'Improvement pitch needs evidence';
          preparation.querySelector('p').textContent = gapExplanation || 'Complete a current audit before creating a problem-led email. Any existing draft is preserved for inspection.';
          preparation.querySelector('.eyebrow').textContent = 'FINDING NEEDED';
        }
      }
      const section = document.createElement('section');
      section.className = 'panel research-conclusion';
      section.setAttribute('aria-label','Diagnostic details');
      section.innerHTML = `<span class="eyebrow">RESEARCH CONCLUSION</span><h3>${conclusion.state === 'finding_ready' ? 'Finding → proposed fix' : conclusion.problem_led_required ? 'Improvement pitch on hold' : 'No verified website problem'}</h3><p>${esc(conclusion.summary)}</p>${conclusion.findings.slice(0,1).map(f => `<p><strong>Proposed fix:</strong> ${esc(f.proposed_fix)}</p><p><strong>How to verify:</strong> ${esc(f.verification)}</p><details><summary>Evidence & reproduction steps</summary>${link(f.url)}<p>${esc(f.fact)} · ${new Date(f.captured_at*1000).toLocaleString()}</p><p>${esc(f.reproduce)}</p>${f.screenshot ? `<a href="/api/screenshots/${encodeURIComponent(f.screenshot)}" target="_blank" rel="noopener">View capture</a>` : '<p>Evidence: saved lab/capture report; no screenshot linked to this finding.</p>'}<p>${esc(f.limitations)}</p></details>`).join('')}<p>${esc(conclusion.next_action)}</p>${hasEmail && !conclusion.draft_allowed ? '<p>Your existing email is preserved. It is not evidence of an identified problem; do not use it as a problem-led pitch.</p>' : ''}`;
      if (held) {
        const actions = document.createElement('div');
        actions.className = 'actions';
        for (const id of ['screenshot', 'performance']) {
          const button = detail.querySelector('#'+id);
          if (button) actions.append(button);
        }
        pitch.append(actions);
      }
      const proofDetails = section.querySelector('details');
      if (proofDetails && conclusion.findings[0]?.report_url) proofDetails.insertAdjacentHTML('beforeend', `<p>Original PageSpeed report: ${link(conclusion.findings[0].report_url)}</p>`);
      for (const metric of conclusion.findings[0]?.supporting_measurements || []) {
        const line = document.createElement('p');
        line.textContent = `${metric.metric}: ${metric.numericValue} ${metric.numericUnit}`;
        proofDetails?.append(line);
      }
      brief.prepend(section);
    }
    if (audits) {
      const journey = audits.reports.find(r=>r.kind==='screenshot')?.journey;
      if (journey && journey.state !== 'not_run') {
        const note = document.createElement('p');
        note.className = 'small';
        note.textContent = `Enquiry journey: ${journey.checked_pages} page(s) sampled · ${journey.checked_links} link(s) checked · ${journey.state}. Form submission and conversion impact are not tested.`;
        pitch.querySelector('.quick-evidence').before(note);
      }
      const labels = {performance:'PageSpeed lab test',screenshot:'Desktop / mobile capture'};
      const states = {not_run:'Not run',stale:'Outdated for current research',target_unverified:'Capture target not recorded',failed:'Failed',partial:'Partial capture',complete:'Completed'};
      const owner = data.contacts.find(c => data.messages.some(m => m.contact_id === c.id && m.step === 0));
      brief.insertAdjacentHTML('beforeend', `<div class="audit-basis"><strong>${audits.observations.length ? audits.observations.length+' measured observation(s) available' : 'No measured technical issue established yet'}</strong><p>Client impact and business pain are unconfirmed. We can propose an opportunity; we cannot claim a problem without evidence.</p><details><summary>Audit coverage & observations</summary><ul>${audits.reports.map(r => `<li>${labels[r.kind] || esc(r.kind)}: ${states[r.state] || esc(r.state)}${r.quota_limited ? '; last request quota limited (HTTP 429), no score from that failed run' : ''}${r.event_id ? ' · report #'+Number(r.event_id) : ''}</li>`).join('')}</ul>${audits.observations.map(o=>`<p>${esc(o.fact)}<br><small>Report ${esc(o.ref)} · ${new Date(o.captured_at*1000).toLocaleDateString()}</small></p>`).join('')}<p class="small">Captures do not test form submission, conversion loss or every chatbot state. Partial rendering cannot establish missing features.</p></details>${owner && !owner.draft_origin?.audit_context ? '<p class="small">This existing draft predates structured audit inputs. Its saved wording has been preserved.</p>' : ''}</div>`);
    }
    // Existing buttons retain their listeners and IDs; only their placement changes.
    const prepare = detail.querySelector('#prepare-emails');
    if (prepare && preparation) {
      prepare.textContent = 'Create email';
      if (conclusion && !conclusion.draft_allowed) {
        prepare.disabled = !audits?.journey_audit_available || data.preparation?.research_pending ||
          ['pending','running'].includes(data.preparation?.job?.state);
        prepare.textContent = audits?.journey_audit_available ? 'Check journey & prepare email' : 'Finding needed before email';
        prepare.title = conclusion.summary;
      }
      if (!hasEmail) {
        const control = !hasSource ? detail.querySelector('#research-again') : !data.contacts.length ? detail.querySelector('#contact-research') : prepare;
        if (control) {
          control.classList.add('primary');
          control.textContent = !hasSource ? 'Research business' : !data.contacts.length ? 'Find a contact' : held && audits?.journey_audit_available ? 'Check journey & prepare email' : assessmentHeld ? 'Retry offer assessment' : 'Create email';
          preparation.querySelector('.next-action-controls').append(control);
        }
      }
      else prepare.hidden = true;
      if (data.preparation?.research_pending) {
        prepare.disabled = true;
        prepare.textContent = 'Checking enquiry journey…';
      }
    }
    for (const node of original) {
      if (node === preparation || node === marker || node === primary) continue;
      if (node.hasAttribute('data-evidence-id')) {
        if (!sources.parentElement) advancedBody.append(sources);
        sources.querySelector('.source-results').append(node);
        continue;
      }
      if (node.classList.contains('step-label')) continue;
      if (node.querySelector('#review-form') || node.classList.contains('offer-review')) qualificationTools.append(node);
      else if (node.classList.contains('contact') || node.querySelector('#contact-form')) recipientTools.append(node);
      else if (/professional profiles|LinkedIn \/ X|Public contact research|Platform research|Published inboxes|Browser-observed|Public X post/i.test(node.querySelector('summary')?.textContent || '')) peopleTools.append(node);
      else researchTools.append(node);
    }
    if (heading) {
      heading.querySelector('h2')?.remove();
      heading.querySelector('.eyebrow')?.remove();
      heading.classList.add('research-tools');
    }
    detail.replaceChildren(intro, steps);
    if (data.research_activity) {
      const progress = document.createElement('section');progress.id='prospect-research-status';progress.setAttribute('aria-label','Research progress');detail.append(progress);
    }
    if (preparation && !hasEmail) detail.append(preparation);
    else if (preparation) researchTools.append(preparation);
    detail.append(pitch);
    researchTools.append(brief);
    if (proof || data.offer_workflow?.selected_service) researchTools.append(proofPanel);
    if (marker) {
      marker.className = 'email-section-heading';
      marker.innerHTML = '<span class="eyebrow">ONE PROSPECT · ONE INITIAL EMAIL</span><h3>Your email</h3><p>Review the recipient and wording. Saving a draft does not send it.</p>';
      detail.append(marker);
    }
    if (primary) {
      const tools = primary.querySelector('.contact-tools');
      const contact = data.contacts.find(c => String(c.id) === primary.dataset.contact);
      if (tools) {
        const rewrite = tools.querySelector('[data-draft]');
        if (rewrite && hasEmail) {
          rewrite.type = 'button';
          rewrite.disabled = rewrite.disabled || held || !data.offer_workflow?.selected_service;
          rewrite.textContent = 'Rewrite from research';
          rewrite.title = 'Replaces this unapproved draft with new AI wording based on current research.';
          primary.querySelector('.composer-footer')?.append(rewrite);
        }
        recipientTools.append(tools);
      }
      const readiness = document.createElement('p');
      readiness.className = 'sending-readiness';
      let verification = {};
      try { verification = JSON.parse(contact?.verification_raw || '{}'); } catch (_) {}
      const unavailable = verification.error === 'VerificationUnavailable' || verification.provider_status?.ready === false;
      const label = !contact?.source_eligible ? 'Publication or inbox ownership needs review.' : unavailable ? 'Mailbox checker unavailable. This inbox has not been verified.' : contact.verification !== 'safe' || contact.verification_fresh === false ? 'Mailbox verification is still required.' : 'Mailbox check passed. Buyer relevance and final sending approval still need review.';
      readiness.innerHTML = `<span>${esc(label)}</span><button type="button" class="text-control">View sending checks</button>`;
      readiness.querySelector('button').onclick = () => {
        advanced.open = true;
        recipientTools.parentElement.open = true;
        if (tools) tools.open = true;
        recipientTools.parentElement.scrollIntoView({block:'start'});
      };
      primary.querySelector('.recipient-bar')?.after(readiness);
      detail.append(primary);
    }
    else {
      const empty = document.createElement('div');
      empty.className = 'email-empty';
      empty.innerHTML = '<span class="empty-mail-icon">✉</span><h3>No email yet</h3><p>We need current business evidence and a published contact before creating a personalized draft.</p>';
      detail.append(empty);
    }
    detail.append(advanced);
    this.updateResearchActivity(data.research_activity, {esc,reload});
    let sourceLimit = 12;
    const sourceNodes = [...sources.querySelectorAll('[data-evidence-id]')];
    const sourceById = new Map(data.evidence.map(e => [String(e.id),e]));
    sourceNodes.sort((a,b) => {
      const left = sourceById.get(a.dataset.evidenceId), right = sourceById.get(b.dataset.evidenceId);
      return Number(!!right.current_for_review)-Number(!!left.current_for_review) ||
        Number(right.id === finding.evidence_id)-Number(left.id === finding.evidence_id) || right.fetched_at-left.fetched_at;
    });
    for (const node of sourceNodes) sources.querySelector('.source-results').append(node);
    const filterSources = () => {
      const query = sources.querySelector('input').value.trim().toLowerCase();
      const period = sources.querySelector('select').value;
      const matching = sourceNodes.filter(node => {
        const page = sourceById.get(node.dataset.evidenceId);
        return (period === 'all' || (period === 'current') === !!page.current_for_review) &&
          `${page.title} ${page.url}`.toLowerCase().includes(query);
      });
      const visible = new Set(matching.slice(0,sourceLimit));
      for (const node of sourceNodes) { node.hidden = !visible.has(node); if (node.hidden) node.open = false; }
      sources.querySelector('.source-count').textContent = `${Math.min(sourceLimit,matching.length)} of ${matching.length} matching pages`;
      sources.querySelector('.source-more').hidden = matching.length <= sourceLimit;
    };
    for (const control of sources.querySelectorAll('input,select')) control.addEventListener('input', event => { event.stopPropagation(); sourceLimit = 12; filterSources(); });
    sources.querySelector('.source-more').onclick = () => { sourceLimit += 12; filterSources(); };
    filterSources();
    // A direct email link opens the prospect workspace without making the user find it.
    if (location.hash === '#email-sequence' && hasEmail) marker?.scrollIntoView({block:'start'});
  }
};
