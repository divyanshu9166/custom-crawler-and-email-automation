# Find and research review — 22 October 2026

## Reproduced defects and corrections

1. A current VPS professional-research failure came from an observed website
   link whose X path was an encoded business name containing spaces. Profile
   validation accepted that path, whereas the downstream author reader rejected
   it. Business and professional entry points now require the same 1–15 ASCII
   letter/digit/underscore handle shape and exclude platform action routes.
   Invalid observed links are skipped; explicitly supplied invalid profiles are
   rejected. Valid handles retain their original identity and case.
2. Exceptions from optional community profile hints aborted the parent report
   after native captures had already been saved. These errors now produce a
   separate unavailable hint with the exception type, preserving native denials,
   subsequent profiles and the final research report. Cancellation still propagates.
   Community data does not become first-party publication or employer proof.
3. Managed discovery always searched both LinkedIn and X regardless of the
   configured discovery-platform list. It now uses selected supported platforms;
   Twitter selection maps to the X browser. Public fallback behavior is unchanged.
4. Raw URL deduplication let regional LinkedIn/About variants and X/Twitter
   aliases consume separate signal slots. Deduplication now uses validated
   platform identities before resolution and budget allocation. Separate post IDs
   remain separate; Google listing IDs retain their existing identity rules.
5. When a captured Google listing linked an official website, the candidate name
   came from the indexed result title, sometimes "Google Maps". This branch now
   prefers the actual captured listing name, consistent with the no-website branch.

## Validation scope

The initial 16 regression cases all failed against the old implementation and
passed after the fixes. Added valid-handle and distinct-post checks cover the
boundaries of the stricter validation and deduplication. The existing profile
preparation fixture used a 16-character fictitious X handle; it now uses a valid
15-character fixture without weakening any production check.

The combined regression run covers discovery budgets and intent, website/profile
resolution, profile preparation, professional and social sources, community
hints, automatic crawl continuation/recovery, rendering and Google Business.
Desktop/mobile browser fixtures use controlled pages, not live prospect actions.
Final combined result: **402 passed** in 126.73 seconds, including 21 focused
regression cases. Ruff, Python compilation and whitespace checks passed. The
existing Starlette/httpx deprecation warning remains unrelated to these fixes.

These fixes do not establish that every prospect has a verified business problem.
Missing evidence, source access restrictions and incomplete captures remain
explicit limitations. No finding, inbox ownership or website absence is invented.
This review changes no email copy, sending settings or contact approvals.
