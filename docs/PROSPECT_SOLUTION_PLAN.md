# Prospect-specific website and automation proposals

Campaign A selects one primary project, with relevant optional features in the same
initial email. One primary service does not forbid a supporting service. This does
not generate separate emails per service.

| Prospect situation | Main project | Supporting options |
| --- | --- | --- |
| Website not found after reviewed search | Website development, retaining search uncertainty until confirmed | Features supported by the published business process |
| Existing website, existing chatbot, supported improvement finding | Website improvement; focused layout review before agreeing full redesign scope | Preserve the chatbot; explore calling where relevant |
| Existing website, assistant status unknown, relevant questions/support content | Website project when supported by findings | Optional chatbot fit check; do not claim the chatbot is absent |
| Published booking/quote/support phone process | Selected main project, or calling as primary when phone work is the focus | Specific qualification, booking or support call flow |
| Only a phone number alongside service enquiries | Existing main project | Conditional calling-agent fit question, not a claimed phone problem |

## Writer context

The writer previously mainly received the reviewed finding and country page. It
now receives compact exact excerpts from up to six prioritized current official
pages plus required review and commerce sources, a structured prospect solution, positive existing-tool
observations, relevant optional additions and their evidence IDs.

An existing chatbot can be established by a positive widget marker or an
authenticated operator review with an inspectable evidence reference. A blog
mention of Intercom is not proof of an installed chatbot. Partial captures and
unmatched searches do not prove absence. Operator observations expire.

Context sources, hashes and timestamps are saved with draft provenance. Source
changes, new relevant context or changed/expired tool reviews require a new review
before approval. Changes during writing preserve existing copy. Saving a tool
observation does not itself overwrite an email.

## Copy requirements

Lead with a relevant business project, cite one useful observation, explain the
proposed change and practical benefit, then mention at most two relevant optional
features briefly. End with one small next step for the overall project.

Website-project instructions are separate from the technical-audit readout prompt.
When relevant optional features are supplied, the initial email must explain the
main project and briefly mention a relevant addition; a font/CSS-only email is
rejected. A helpdesk phone route supports customer support, not an assumed sales
qualification need. Long page bodies are reduced to decisive exact source excerpts
so duplicate website text does not dominate the writing request.

A PageSpeed score is not a complete design/CRO audit. It cannot establish ugly UI,
a necessary full redesign or lost visitors/sales. Layout changes can be proposed
as project scope; diagnosed design faults require their own evidence. The current
screenshot lane records bounded observations, not a comprehensive automated visual
design assessment. Private conversion data still needs client access.

Nemotron remains the configured writer. Context and offer routing are corrected
before attributing weak drafts solely to the model. Controlled tests and a reviewed
live sample do not guarantee good copy for every prospect.

## Optional operator correction

Authenticated `PUT /api/leads/{id}/business-tools` accepts `chatbot_status` as
`present` or `unknown`, `source_url` for a current saved official page and a specific
`evidence_reference`, such as an inspected screenshot. It does not accept an
unverified absence declaration. This is an exception correction, not another
mandatory questionnaire in the normal Pipeline flow.
