# CI browser sandbox failure

The 17 October 2026 GitHub Actions run for `367be15` failed in pytest with
17 failures and 1,083 passes. This was a GitHub Actions test failure, not a
GitGuardian secret-detection result. Its separate Reacher build and smoke check
passed. The failing render/browser cases reported `No usable sandbox` on the
GitHub-hosted Ubuntu 24.04 runner, with downstream missing-render assertions.

The application explicitly enables Chromium's sandbox. Playwright's downloaded
browser executables need user-namespace permission under Ubuntu's AppArmor
restrictions. The workflow now loads `deploy/ci/playwright-chromium.apparmor`
for `/home/runner/.cache/ms-playwright/**/chrome{,-headless-shell}` before testing.
This follows [Chromium's per-path AppArmor guidance](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md).

This profile is installed only on the disposable CI runner. It does not alter
the VPS, disable the host's global user-namespace restriction, pass `--no-sandbox`
to Chromium, skip failing tests, or change crawler/credential/send behavior.
Docker deployment retains its existing non-root user and seccomp configuration.

Both jobs explicitly select `ubuntu-24.04`, avoiding an implicit move when the
`ubuntu-latest` label changes. Checkout/setup-python use their current v7 actions
with Node 24 rather than the deprecated Node 20 versions. Workflow tokens have
read-only contents permission and checkout credentials are not persisted.

Validation must include a fresh Linux Actions run: local Windows browser tests
cannot validate Ubuntu AppArmor. A green health endpoint on a deployed app also
does not prove that Chromium rendering can start on that host. Keep these
acceptance results separate from deployment, provider coverage and secret-scan
results.
