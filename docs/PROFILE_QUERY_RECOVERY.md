# Bounded public-profile query recovery

13 October 2026. The preceding goal turn fixed employer/name hints but the fresh
sector-role sample still returned insufficient indexed profiles. This follow-up
changes actual discovery behavior rather than treating known contacts as recall.

## Production change

After a zero-result generated public LinkedIn `/company/`, LinkedIn `/in/`, X or
Twitter query, discovery can make one paced retry. It retains the platform/path,
sector terms and buyer-role expression. It removes only a trailing explicit
search-market phrase and phrase quotes. Arbitrary operators and unsupported
sources are left alone. Empty subjects cannot become a generic profile search.

Successful queries do not get an extra retry. Fallbacks cannot recursively retry
or duplicate an existing query. Existing result/signal limits, domain deduplication,
explicit foreign-market exclusions and current identity/publication review remain
in force. A relaxed query is recorded in `relaxed_queries` and engine-report
metadata, including its original query and relaxed market constraint. It does
not approve a source country or restore native platform access.

## Actual separate live pass

`python scripts/verify_profile_buyer_coverage_live.py --relaxed` preserves the
earlier constrained report and tests the four corresponding less restrictive
queries as a separate pass, without operator-supplied names/company URLs.

| Query | Indexed rows | Selected profile hints |
| --- | ---: | ---: |
| `site:linkedin.com/in/ dental owner` | 7 | 2 |
| `site:linkedin.com/in/ skincare founder` | 5 | 2 |
| `site:x.com skincare founder` | 6 | 2 |
| `site:x.com ecommerce founder` | 7 | 2 |

**25 indexed rows, 8 selected profile hints, zero accepted personal emails.**
The four LinkedIn inputs were Dr Mayank Kaurani, Stuart Garton, Allison Evans
Callaway and Ashish Jawa. None passed the exact current staff/profile match.
Four X inputs were YBFSkincare, SchiqueSkincare, Nugennath and thedennis. Three
community bios were returned, one profile was not found, and none published an
email in the returned bio. YBF is a company account, not proof of a personal
decision-maker profile. No missing profile was replaced.

The hints are not eight US/UK buyer leads. YBF's mirror location is Minneapolis
despite the UK query cohort; thedennis reports Dubai despite the US cohort, and
other locations are absent or not a business-location statement. Role words and
profile links do not approve geography, authority, ownership or offer fit. This
diagnostic records the first eligible profile roots without importing them;
production's explicit indexed-market exclusions are separately exercised by
regression tests. Removing a market constraint predictably increases research
noise, which the existing source/country review must reject or hold.

A current independent capture of Stuart's observed dental staff page was also
checked: it had one company email, no extracted named staff record and no exact
LinkedIn link. That company inbox was not substituted for a personal-profile
email or accepted buyer. See `data/dental-staff-person-diagnostic.json`.

Private live pointer: `data/profile-buyer-relaxed-latest.json`. The earlier fixed
sample remains at `data/profile-buyer-coverage-latest.json`; the passes are not a
controlled benchmark of vendor recall or a rate comparison with identical data.
Engine availability and query constraints can change between passes.

No contacts were imported, recipient probes performed or messages sent. The
operational database remained unchanged and sending disabled/paused. The current
change demonstrably broadens indexed discovery; personal-email coverage and the
full original goal remain incomplete.

## Verification

109 focused discovery/person/community checks passed in 36.34 seconds. The full
suite passed **969 tests in 218.48 seconds**, with the existing Starlette/httpx
warning. Ruff passed. The final preview was restarted on current code; health and
authenticated status checks confirmed source-enabled, sending disabled/paused
and unchanged operational data. Focused fixtures and regression tests are not
live native-profile acceptance evidence. The verified source package excludes
credentials and runtime data.

## Resumed goal: fresh founder/employer boundary check

After the goal was resumed, a current free `site:linkedin.com/in/ skincare founder`
query returned six indexed rows. The native control still returned robots-denied.
The first two usable current founder hints, Fatma Shaheen and Sorbi Khattak, were
processed without operator company URLs. Fatma's current company homepage/About
page was captured but no exact staff/profile match was established. Neither
initial input produced an accepted personal email.

Sorbi's actual snippet exposed a parser defect: the declared employer became
`Skincare Scientists I’m` because first-person prose followed the capitalized
business name without punctuation. The company-name reader now stops before
explicit first-person contractions while preserving legitimate apostrophes such
as `O'Neill & Sons`. Quotes remain exact indexed hints, not verified employment.

A live replay of that same saved row produced `Skincare Scientists`, four results
for its person+company query instead of one, and the independent company candidate
`https://skincarescientists.com/`. The source-matching state changed from
`person_company_unconfirmed` to `indexed_employer_company_candidate`. Personal
identity remained held and accepted personal emails remained zero. This is a real
query-resolution fix, not native LinkedIn recovery, buyer qualification or a new
replacement sample.

Private evidence: `data/goal-resumed-source-audit-20261013.json`,
`data/goal-resumed-founders-latest.json`, and
`data/goal-resumed-employer-recheck-latest.json`. Operational data was unchanged,
with zero contacts imported, recipient probes or messages. The full goal remains
active and incomplete. The preceding 969 full-suite result is the baseline before
this follow-up; **63 focused recovery/discovery/failover checks passed in 37.81
seconds** after the fix, and Ruff passed.

### Newly resolved company: current contact-path follow-up

The resolved Skincare Scientists homepage and its observed About link were both
captured using normal Chromium rendering. Neither published an email, extracted
a current named staff/profile association, or linked a public X profile. An
additional bounded index lookup for the sourced founder name on X and Twitter
returned zero accepted profile results. No handle or email was guessed. This
closes the available observed contact branch without claiming identity/contact
acceptance or native LinkedIn recovery. Company discovery remains distinct from
the requested personal-profile email evidence.

Private pointers: `data/resumed-founder-contact-path-latest.json` and
`data/resumed-founder-x-lookup-latest.json`. Both diagnostics preserved operational
data, with zero imports, recipient probes and messages. No implementation changed
in this follow-up; the earlier verification counts remain the same. The full goal
is incomplete, with the source/publication blocker still present.
