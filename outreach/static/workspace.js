/* A focused prospect workspace; existing research and sales tools remain available. */
window.WorkbenchWorkspace = {
  initialize() {
    const writer = document.querySelector('#writer-settings-form');
    const column = writer.parentElement;
    column.prepend(writer);
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
    advanced.innerHTML = '<summary>Research details & advanced tools<span>Sources, qualification, audits and history</span></summary><div class="advanced-content"></div>';
    const advancedBody = advanced.querySelector('div');
    const sources = document.createElement('details');
    sources.className = 'saved-sources';
    sources.innerHTML = `<summary>Saved source pages (${data.evidence.length})</summary>`;
    const intro = document.createElement('section');
    intro.className = 'prospect-header';
    const l = data.lead;
    intro.innerHTML = `<div><span class="eyebrow">PROSPECT WORKSPACE</span><h2>${esc(l.company)}</h2>${link(l.website || l.profile_url)}</div><span class="workspace-pill">${l.country ? esc(l.country) : 'Market needs review'} · ${l.campaign === 'B' ? 'Ecommerce' : 'Business enquiries'}</span>`;
    const steps = document.createElement('ol');
    steps.className = 'workspace-steps';
    const hasSource = data.evidence.some(e => e.current_for_review && e.business_for_review !== false);
    const hasEmail = data.messages.some(m => m.step === 0);
    steps.innerHTML = [['Research', hasSource], ['Match an offer', !!data.offer_workflow?.selected_service], ['Review email', hasEmail]].map(([label,done],i) => `<li class="${done ? 'done' : ''}"><span>${done ? '✓' : i+1}</span>${label}</li>`).join('');
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
    if (audits) {
      const labels = {performance:'PageSpeed lab test',screenshot:'Desktop / mobile capture'};
      const states = {not_run:'Not run',stale:'Outdated for current research',target_unverified:'Capture target not recorded',failed:'Failed',partial:'Partial capture',complete:'Completed'};
      const owner = data.contacts.find(c => data.messages.some(m => m.contact_id === c.id && m.step === 0));
      brief.insertAdjacentHTML('beforeend', `<div class="audit-basis"><strong>${audits.observations.length ? audits.observations.length+' measured observation(s) available' : 'No measured technical issue established yet'}</strong><p>Client impact and business pain are unconfirmed. We can propose an opportunity; we cannot claim a problem without evidence.</p><details><summary>Audit coverage & observations</summary><ul>${audits.reports.map(r => `<li>${labels[r.kind] || esc(r.kind)}: ${states[r.state] || esc(r.state)}${r.quota_limited ? '; last request quota limited (HTTP 429), no score from that failed run' : ''}${r.event_id ? ' · report #'+Number(r.event_id) : ''}</li>`).join('')}</ul>${audits.observations.map(o=>`<p>${esc(o.fact)}<br><small>Report ${esc(o.ref)} · ${new Date(o.captured_at*1000).toLocaleDateString()}</small></p>`).join('')}<p class="small">Captures do not test form submission, conversion loss or every chatbot state. Partial rendering cannot establish missing features.</p></details>${owner && !owner.draft_origin?.audit_context ? '<p class="small">This existing draft predates structured audit inputs. Its saved wording has been preserved.</p>' : ''}</div>`);
    }
    // Existing buttons retain their listeners and IDs; only their placement changes.
    const prepare = detail.querySelector('#prepare-emails');
    if (prepare && preparation) {
      prepare.textContent = 'Create email';
      if (!hasEmail) {
        const control = !hasSource ? detail.querySelector('#research-again') : !data.contacts.length ? detail.querySelector('#contact-research') : prepare;
        if (control) {
          control.classList.add('primary');
          control.textContent = !hasSource ? 'Research business' : !data.contacts.length ? 'Find a contact' : 'Create email';
          preparation.querySelector('.next-action-controls').append(control);
        }
      }
      else prepare.hidden = true;
    }
    for (const node of original) {
      if (node === preparation || node === marker || node === primary) continue;
      if (node.hasAttribute('data-evidence-id')) {
        if (!sources.parentElement) advancedBody.append(sources);
        sources.append(node);
        continue;
      }
      advancedBody.append(node);
    }
    if (heading) {
      heading.querySelector('h2')?.remove();
      heading.querySelector('.eyebrow')?.remove();
      heading.classList.add('research-tools');
    }
    detail.replaceChildren(intro, steps);
    if (preparation) detail.append(preparation);
    detail.append(brief);
    if (proof || data.offer_workflow?.selected_service) detail.append(proofPanel);
    if (marker) {
      marker.className = 'email-section-heading';
      marker.innerHTML = '<span class="eyebrow">ONE PROSPECT · ONE INITIAL EMAIL</span><h3>Your email</h3><p>Review the recipient and wording. Saving a draft does not send it.</p>';
      detail.append(marker);
    }
    if (primary) detail.append(primary);
    else {
      const empty = document.createElement('div');
      empty.className = 'email-empty';
      empty.innerHTML = '<span class="empty-mail-icon">✉</span><h3>No email yet</h3><p>We need current business evidence and a published contact before creating a personalized draft.</p>';
      detail.append(empty);
    }
    detail.append(advanced);
    // A direct email link opens the prospect workspace without making the user find it.
    if (location.hash === '#email-sequence' && hasEmail) marker?.scrollIntoView({block:'start'});
  }
};
