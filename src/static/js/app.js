/*
 * Sheria Yangu — shared helpers for the new screens (splash, sign-in, OTP,
 * bill-detail, clauses, terms, memo, settings, analytics).
 *
 * Storage keys, all in localStorage (this is real app code running in a real
 * browser, not a sandboxed chat artifact, so localStorage is the right and
 * normal tool here):
 *   sy_access_token   — JWT from /api/auth/verify-otp, sent as Authorization: Bearer
 *   sy_phone_number    — kept ONLY long enough to pair request-otp -> verify-otp
 *                        on the OTP screen; not needed/used after sign-in succeeds
 *   sy_theme           — "light" | "dark"
 *   sy_pending_votes   — { [clause_id]: "kubali"|"kataa" } for the bill currently
 *                        being read, cleared once a memorandum is created/skipped
 *   sy_current_bill_id — the bill id the citizen is currently reading/voting on
 */

const SY = {
  getToken() { return localStorage.getItem('sy_access_token'); },
  setToken(t) { localStorage.setItem('sy_access_token', t); },
  clearSession() {
    localStorage.removeItem('sy_access_token');
    localStorage.removeItem('sy_phone_number');
  },
  isSignedIn() { return !!SY.getToken(); },

  getPhone() { return localStorage.getItem('sy_phone_number') || ''; },
  setPhone(p) { localStorage.setItem('sy_phone_number', p); },

  getBillId() { return localStorage.getItem('sy_current_bill_id') || ''; },
  setBillId(id) { localStorage.setItem('sy_current_bill_id', id); },

  getVotes() {
    try { return JSON.parse(localStorage.getItem('sy_pending_votes') || '{}'); }
    catch (e) { return {}; }
  },
  setVote(clauseId, choice) {
    const votes = SY.getVotes();
    votes[clauseId] = choice;
    localStorage.setItem('sy_pending_votes', JSON.stringify(votes));
  },
  clearVotes() { localStorage.removeItem('sy_pending_votes'); },

  /** fetch() wrapper that attaches the Authorization header automatically.
   *  Redirects to sign-in if a 401 comes back and the caller didn't opt out. */
  async apiFetch(path, options = {}, { redirectOn401 = true } = {}) {
    const headers = Object.assign({}, options.headers || {});
    const token = SY.getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const res = await fetch(path, Object.assign({}, options, { headers }));
    if (res.status === 401 && redirectOn401) {
      SY.clearSession();
      window.location.href = 'signin.html';
      throw new Error('Not signed in — redirecting to sign-in.');
    }
    return res;
  },

  /** Theme: applied as a data-theme attribute on <html>, persisted. */
  initTheme() {
    const saved = localStorage.getItem('sy_theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    return saved;
  },
  toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('sy_theme', next);
    return next;
  },

  /** Guard for pages that require a signed-in session. Call at top of page script. */
  requireSignIn() {
    if (!SY.isSignedIn()) {
      window.location.href = 'signin.html';
      return false;
    }
    return true;
  },

  showError(el, message) {
    el.textContent = message;
    el.classList.add('visible');
  },
  hideError(el) {
    el.textContent = '';
    el.classList.remove('visible');
  },

  /** Human-readable label for a bill's raw status string — never show the
   *  raw enum value ("needs_manual_review") straight to a citizen. */
  friendlyStatus(status) {
    switch (status) {
      case 'open': return 'Open for public participation';
      case 'closed': return 'Participation window closed';
      case 'needs_manual_review': return 'Pending confirmation of an open participation window';
      default: return status || 'Status unknown';
    }
  },

  /**
   * Injects the persistent hamburger + side drawer nav into the current
   * page: Profile, Settings, County analytics, Terms & data policy, a
   * theme toggle, and Sign out — all reachable from every authenticated
   * screen, not just the three pages that happen to have a bottom nav.
   * Call once per page, e.g. SY.injectNav('settings') to highlight the
   * matching drawer item. Safe to call on pages without a .phone wrapper
   * (it just does nothing) so it can be added defensively.
   */
  injectNav(activeId) {
    const phone = document.querySelector('.phone');
    if (!phone || document.querySelector('.sy-hamburger')) return;

    const items = [
      { id: 'bills', label: '📜 Bills', href: 'bill-detail.html' },
      { id: 'profile', label: '👤 Profile', href: 'profile.html' },
      { id: 'settings', label: '⚙️ Settings', href: 'settings.html' },
      { id: 'analytics', label: '📊 County analytics', href: 'analytics.html' },
      { id: 'policy', label: '📄 Terms & data policy', href: 'policy.html' },
    ];

    const hamburger = document.createElement('button');
    hamburger.className = 'sy-hamburger';
    hamburger.setAttribute('aria-label', 'Menu');
    hamburger.textContent = '☰';

    const overlay = document.createElement('div');
    overlay.className = 'sy-drawer-overlay';

    const drawer = document.createElement('div');
    drawer.className = 'sy-drawer';
    drawer.innerHTML = `
      <div class="sy-drawer-header">Sheria Yangu</div>
      <div class="sy-drawer-items">
        ${items.map(it => `
          <button class="sy-drawer-item${it.id === activeId ? ' active' : ''}"
                  data-href="${it.href}">${it.label}</button>
        `).join('')}
      </div>
      <div class="sy-drawer-footer">
        <div class="sy-drawer-theme-row">
          <span>Light</span>
          <label class="switch">
            <input type="checkbox" class="sy-drawer-theme-switch">
            <span class="slider"></span>
          </label>
          <span>Dark</span>
        </div>
        <button class="sy-drawer-signout">Sign out</button>
      </div>
    `;

    phone.appendChild(overlay);
    phone.appendChild(drawer);
    phone.appendChild(hamburger);

    const themeSwitch = drawer.querySelector('.sy-drawer-theme-switch');
    themeSwitch.checked = document.documentElement.getAttribute('data-theme') === 'dark';

    function open() { overlay.classList.add('open'); drawer.classList.add('open'); }
    function close() { overlay.classList.remove('open'); drawer.classList.remove('open'); }

    hamburger.addEventListener('click', open);
    overlay.addEventListener('click', close);
    drawer.querySelectorAll('.sy-drawer-item').forEach(btn => {
      btn.addEventListener('click', () => { window.location.href = btn.dataset.href; });
    });
    themeSwitch.addEventListener('change', () => SY.toggleTheme());
    drawer.querySelector('.sy-drawer-signout').addEventListener('click', () => {
      SY.clearSession();
      window.location.href = 'splash.html';
    });
  },
};

SY.initTheme();
