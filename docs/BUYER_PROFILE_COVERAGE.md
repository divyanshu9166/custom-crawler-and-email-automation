# Fresh buyer-role profile coverage

13 October 2026. The previous turn established repeatable known-profile recovery
and improved community X extraction. This turn tested fresh sector/role queries
instead of counting those controls as representative client acquisition.

## Sample and actual results

`scripts/verify_profile_buyer_coverage_live.py` fixes four cohorts before search,
with up to two eligible profiles per cohort. No names or company URLs are supplied:

| Market hint | Source | Fixed query terms | Indexed rows | Initially selected |
| --- | --- | --- | ---: | ---: |
| UK | LinkedIn `/in/` | dental, owner, United Kingdom | 2 | 1 |
| US | LinkedIn `/in/` | skincare, founder, United States | 0 | 0 |
| UK | X | skincare, founder, UK | 0 | 0 |
| US | X | ecommerce, founder, USA | 0 | 0 |

The configured free engines reported rate-limit, timeout, access-denied and
CAPTCHA issues. Eight planned slots did **not** yield eight available profiles.
The corrected run retained normal official-site rendering and market language
selection. The initial HTTP-only pass is not normal-renderer coverage.

Rakesh Patel's result supplied a UK education reference, not proof of a UK
business. It did not pass current person/profile matching or produce an accepted
email. Another result, Nik Kotecha, describes an SEO business helping dental
clinics rather than establishing that he is a dental-practice owner. Neither
market nor buyer fit is approved by the query terms.

## Actual implementation bugs corrected

- The declared-employer parser truncated `Dental Care of Corona` to `Dental Care`.
  It now preserves bounded internal name connectors and stops before ordinary
  trailing prose. The corrected live pass found the actual indexed staff route
  `https://www.dentalcareofcorona.com/about-us/dr-rakesh-patel/30109`, but its
  capture was unavailable. Finding that route did not establish source acceptance.
- Boundary direction markers around `Nik Kotecha` made the usable Latin name
  fail validation. Boundary marks now normalize; unexpected internal marks still
  fail. Original indexed titles remain in evidence. A live replay of that saved
  row recovered the name hint but no exact current staff/profile match or email.

These are extraction/research fixes, not a native LinkedIn restriction bypass.
Neither absent source data nor a same-name person at another employer passes the
existing exact-profile/publication requirements.

## Evidence and verification

Private measured report pointers:

- `data/profile-buyer-coverage-latest.json`
- `data/profile-buyer-name-recovery-latest.json`

The combined community, LinkedIn recovery, platform discovery and failover set
passed **91 tests in 36.23 seconds** after the employer fix. After the boundary-name
fix, the person/recovery set passed **61 tests in 32.97 seconds**. These sets
overlap and are not a combined unique test count. Ruff passed. The previous
full-suite baseline remains separately documented; no new full-suite result is
claimed here.

Operational data stayed unchanged. No recipients were imported, mailbox probes
performed or messages sent. The current fresh buyer-role sample has zero
accepted emails and zero qualified buyers. It therefore does not establish
representative US/UK coverage, native LinkedIn access or Apollo/Apify parity.
The full goal remains active and incomplete.
