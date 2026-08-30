'use strict';
const TOKEN_KEY = 'mh_token';
const USER_KEY = 'mh_user';
function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (e) { return null; } }
function setAuth(token, user) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); }
function clearAuth() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }

function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  const t = getToken();
  if (t) h['Authorization'] = 'Bearer ' + t;
  return h;
}

async function authFetch(path, opts) {
  opts = opts || {};
  opts.headers = authHeaders(opts.headers);
  const r = await fetch(path, opts);
  if (r.status === 401) {
    clearAuth();
    if (!location.pathname.endsWith('login.html')) location.href = 'login.html';
    throw new Error('No autenticado');
  }
  return r;
}

function requireAuth() {
  if (!getToken()) { location.href = 'login.html'; return false; }
  return true;
}
function logout() { clearAuth(); location.href = 'login.html'; }

function renderUser() {
  const u = getUser();
  const el = document.getElementById('user-chip');
  if (el && u) el.innerHTML = '<span class="side-link" style="cursor:pointer" title="Cerrar sesión" onclick="logout()"><svg class="icon"><use href="#i-lead"/></svg> ' + u.username + ' · ' + u.role + '</span>';
}
function isReadOnly() { const u = getUser(); return !u || u.role === 'viewer'; }
