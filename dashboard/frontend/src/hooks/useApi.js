const API = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export const OPERATOR_TOKEN_KEY = 'dummy_operator_token';

export function apiUrl(path) {
  return `${API}${path}`;
}

export function getOperatorToken() {
  return (
    window.sessionStorage?.getItem(OPERATOR_TOKEN_KEY) ||
    window.localStorage?.getItem(OPERATOR_TOKEN_KEY) ||
    ''
  );
}

export function storeOperatorToken(token, persist = false) {
  const value = String(token || '').trim();
  window.sessionStorage?.removeItem(OPERATOR_TOKEN_KEY);
  window.localStorage?.removeItem(OPERATOR_TOKEN_KEY);
  if (!value) return false;
  const storage = persist ? window.localStorage : window.sessionStorage;
  storage?.setItem(OPERATOR_TOKEN_KEY, value);
  return true;
}

export function clearOperatorToken() {
  window.sessionStorage?.removeItem(OPERATOR_TOKEN_KEY);
  window.localStorage?.removeItem(OPERATOR_TOKEN_KEY);
}

function operatorHeaders() {
  const token = getOperatorToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiError(response, path) {
  let detail = '';
  try {
    const payload = await response.json();
    detail = typeof payload?.detail === 'string' ? payload.detail : '';
  } catch {
    detail = '';
  }
  let guidance = '';
  if (response.status === 503) {
    guidance =
      'Configure DUMMY_OPERATOR_TOKEN in the backend process, then enter the matching token in Operator Control.';
  } else if (response.status === 403) {
    guidance = 'The operator token is missing or does not match the backend token.';
  }
  return new Error(
    [`${path}: ${response.status}`, detail, guidance].filter(Boolean).join(' — '),
  );
}

export async function fetchJson(path) {
  const r = await fetch(apiUrl(path), { headers: operatorHeaders() });
  if (!r.ok) throw await apiError(r, path);
  return r.json();
}

export async function postJson(path, body = {}) {
  const r = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...operatorHeaders() },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await apiError(r, path);
  return r.json();
}
