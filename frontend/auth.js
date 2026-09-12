const SPA_JS = 'https://cdn.jsdelivr.net/npm/@auth0/auth0-spa-js@2.25.0/+esm';
const DESK_SCOPES = 'openid profile email offline_access read:scenarios write:scenarios approve:recovery fetch:observations';
const MFA_ACR = 'http://schemas.openid.net/pape/policies/2007/06/multi-factor';

window.flowbetterAuth = {
  enabled: false,
  ready: false,
  user: null,
  permissions: [],
  desk: null,
  getAccessToken: async () => null,
  login: async () => {},
  logout: () => {},
  stepUp: async () => {},
  can: permission => !window.flowbetterAuth.enabled || window.flowbetterAuth.permissions.includes(permission),
};

function el(id) {
  return document.getElementById(id);
}

function paint() {
  const session = el('authSession');
  const auth = window.flowbetterAuth;
  if (!session) return;
  if (!auth.enabled) {
    session.hidden = true;
    return;
  }
  session.hidden = false;
  const signedIn = Boolean(auth.user);
  const identity = el('authIdentity');
  const login = el('authLogin');
  const logout = el('authLogout');
  const stepUp = el('authStepUp');
  const desk = el('desk');
  const switchDesk = el('switchDesk');
  if (identity) {
    identity.textContent = signedIn
      ? `${auth.user.email || auth.user.name || auth.user.sub} · desk ${auth.desk || 'pending'}`
      : 'Sign in to isolate this desk to your airline or airport identity.';
  }
  if (login) login.hidden = signedIn;
  if (logout) logout.hidden = !signedIn;
  if (stepUp) stepUp.hidden = !signedIn;
  if (desk) {
    desk.readOnly = signedIn;
    if (auth.desk) desk.value = auth.desk;
  }
  if (switchDesk) switchDesk.hidden = signedIn;
  const label = el('workspaceLabel');
  const pill = el('workspacePill');
  if (label) label.textContent = signedIn ? 'Signed-in recovery desk' : 'Auth0 required';
  if (pill) pill.textContent = signedIn ? 'AUTH0' : 'SIGN IN';
}

function bindButtons(client, cfg) {
  el('authLogin')?.addEventListener('click', () => client.loginWithRedirect());
  el('authLogout')?.addEventListener('click', () => client.logout({logoutParams: {returnTo: window.location.origin}}));
  el('authStepUp')?.addEventListener('click', () => window.flowbetterAuth.stepUp());
}

async function start() {
  try {
    const cfg = await fetch('/api/auth/config').then(response => response.json());
    window.flowbetterAuth.enabled = Boolean(cfg.enabled);
    if (!cfg.enabled) return;
    const {createAuth0Client} = await import(SPA_JS);
    const params = {
      redirect_uri: window.location.origin,
      audience: cfg.audience,
      scope: DESK_SCOPES,
    };
    if (cfg.organization) params.organization = cfg.organization;
    const client = await createAuth0Client({
      domain: cfg.domain,
      clientId: cfg.client_id,
      useRefreshTokens: true,
      cacheLocation: 'memory',
      authorizationParams: params,
    });
    const query = new URLSearchParams(window.location.search);
    if ((query.has('code') || query.has('error')) && query.has('state')) {
      await client.handleRedirectCallback();
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    window.flowbetterAuth.getAccessToken = async () => {
      try {
        return await client.getTokenSilently();
      } catch (error) {
        if (error.error === 'login_required' || error.error === 'consent_required' || error.error === 'missing_refresh_token') return null;
        throw error;
      }
    };
    window.flowbetterAuth.login = () => client.loginWithRedirect();
    window.flowbetterAuth.logout = () => client.logout({logoutParams: {returnTo: window.location.origin}});
    window.flowbetterAuth.stepUp = () => client.loginWithRedirect({
      authorizationParams: {...params, acr_values: MFA_ACR, max_age: 0},
    });
    bindButtons(client, cfg);
    if (await client.isAuthenticated()) {
      window.flowbetterAuth.user = await client.getUser();
      const token = await client.getTokenSilently();
      const me = await fetch('/api/auth/me', {headers: {Authorization: `Bearer ${token}`}}).then(response => response.json());
      window.flowbetterAuth.permissions = me.permissions || [];
      window.flowbetterAuth.desk = me.desk;
    }
    paint();
  } catch (error) {
    const identity = el('authIdentity');
    if (identity) identity.textContent = error.message || 'Auth0 configuration failed.';
  } finally {
    window.flowbetterAuth.ready = true;
    window.dispatchEvent(new Event('flowbetter-auth-ready'));
  }
}

start();
