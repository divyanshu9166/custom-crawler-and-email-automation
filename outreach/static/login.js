document.querySelector('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  const error = document.querySelector('#login-error');
  button.disabled = true;
  error.textContent = '';
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    if (response.status >= 500) {
      throw new Error(`Sign-in service unavailable (HTTP ${response.status}). Check that the app is running and the Cloudflare tunnel can reach it.`);
    }
    const type = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
    if (type !== 'application/json' && !type.endsWith('+json')) {
      throw new Error(`Sign-in received an unexpected page (HTTP ${response.status}). Check the app/tunnel connection and reload this page.`);
    }
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Sign-in received an invalid response (HTTP ${response.status}). Check the app/tunnel connection and reload this page.`);
    }
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail.slice(0, 400) : '';
      throw new Error(detail || `Sign in failed (HTTP ${response.status}). Check the sign-in details and configured workspace URL.`);
    }
    if (data?.signed_in !== true) {
      throw new Error('The server did not confirm sign-in. Check the app/tunnel connection and reload this page.');
    }
    location.replace('/');
  } catch (failure) {
    error.textContent = failure instanceof TypeError
      ? 'Cannot reach the sign-in service. Check your connection and the Cloudflare tunnel, then try again.'
      : failure.message || 'Sign in failed. Please try again.';
  } finally {
    button.disabled = false;
  }
});
