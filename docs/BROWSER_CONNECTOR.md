# Browser business-reference connector

This is a local Chrome/Edge Manifest V3 connector, prepared in `deploy/browser-connector`. It reduces manual copying from business pages you can normally open. It does **not** remove LinkedIn/X server restrictions, solve challenges, expose private contacts or provide Apollo's dataset.

## PC and VPS deployment

The current connector runs in the operator's normal desktop browser. The Workbench backend and official-website crawler can run on the VPS after deployment. Exported connector JSON can be reviewed/imported through the VPS-hosted dashboard; the extension itself has no localhost URL or direct connection to that server.

Installing this ZIP alongside Docker/Python services on a VPS does not make it a background crawler. `activeTab` requires a user-invoked browser action, and the collector only reads a visible enabled tab. Running it inside a VPS browser would require a usable browser/desktop session and the same manual activation, navigation, export and import. The present connector has not been deployed/tested that way and is not an unattended headless browser worker.

Therefore this assisted connector does not fulfill the original fully automatic VPS platform-discovery requirement. It is an optional input path; no automatic browser-to-VPS synchronization is implemented.

## Install and use

1. In Chrome, open `chrome://extensions`, enable Developer mode and select **Load unpacked → deploy/browser-connector** from this workspace. Pin the extension if useful. These are the [official Chrome loading steps](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world). The connector has not been installed in your normal browser by this task.
2. Open the specific public LinkedIn company **About** page or a public X business profile in your normal browser. Click the connector and **Enable collection on this tab**. You control any normal sign-in. No credentials or sessions are copied into the software.
3. While this tab is visible, the collector observes supported business headers. Visiting other supported business pages on the same origin in the same enabled tab can add references automatically. Hidden/background tabs do not collect. A different origin or closed tab loses the grant; re-enable explicitly if needed. Use **Stop collection** to stop immediately.
4. Click **Export references for Workbench**. Open the dashboard → **Find prospects → Import collected browser references**, select the JSON, review the company/source/website/date list, choose Campaign A/B and US/UK market hint, confirm the review, then import. Inspect successes and errors. New companies receive website research jobs; existing reviews and messages stay intact.

The collector only requests `activeTab`, `scripting` and `storage`. There are no persistent host permissions, cookie/network interception permissions, account tokens, direct HTTP uploads or automatic message sending. Chrome documents [activeTab's user-invoked, temporary same-origin access](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab).

## Capture and provenance

- LinkedIn: specific `/company/<name>/about` route, visible company heading and the **Website** definition field. The current About link must match the page route to avoid capturing an old SPA header after navigation.
- X: specific root profile route, visible heading and the scoped public website/header field. Posts, message routes, notifications, navigation and unrelated links are excluded. Opaque `t.co` links only produce a candidate when their visible label is a complete website address; no redirect is followed and the observation labels this uncertainty.
- Missing/hidden/ambiguous website fields produce no reference. Layout changes may require a reader update; unrecognized layouts stay uncaptured.
- Only business name, website candidate, public source URL without query parameters, observation time, a short scope description and capture method are exported. No full-page text, phone, email, account identity, inbox, password, cookie or private contact field is collected.
- References stay in local extension storage, bounded to 100 and deduplicated by source/name/website. No data is sent to LinkedIn/X or Workbench by the extension. Imports use the existing authenticated dashboard session and source-validation route.
- Imported records are `browser_connector_reference`, with `server_profile_fetched=false`, `identity_verified=false` and `contact_publication_proof=false`. The capture method is a client-reported observation, not cryptographic or first-party proof. Current official-site capture, country/buyer/offer review and published-contact/verification gates still apply. A market hint does not qualify geography.

## Verification limits

The current LinkedIn Fonte About definition layout and X Sonria header structure were inspected live in the normal in-app browser. A read-only DOM check confirmed one matching visible LinkedIn Website definition, the current About route and Fonte's website; the X check confirmed Sonria's visible `.com` website label in a header with no posts. The X link's destination remains opaque `t.co`, so its label supplies an unverified candidate. No browser session or account-navigation content was transferred.

The packaged reader was exercised in isolated Chromium fixtures reproducing these structures, including hidden fields, unrelated/private navigation, spoofed routes, stale headers, ambiguous websites, collector deduplication and stopping. A Chrome API mock checks background arming, origin changes, buffer capacity and serialized duplicate writes. The authenticated dashboard import was exercised with one valid fictional reference and one stale reference, proving partial-import reporting and unchanged contact eligibility.

This is not a live installation or acceptance test of Chrome/Edge extension permissions in the user's browser. No platform account was changed and no message was sent. Chrome installation and site-specific long-run reliability remain unverified; neither the connector nor its tests prove unattended server access, consistent segment discovery or unpublished-email access.

The complete release passed **720 tests**, including fifteen connector/reader/storage cases. Chromium dashboard import and existing workflow/UI checks passed with zero JavaScript errors; Ruff and JavaScript syntax checks passed. The normal preview was restarted with sending disabled/paused. Source and standalone connector ZIPs contain no operational data or credentials.
