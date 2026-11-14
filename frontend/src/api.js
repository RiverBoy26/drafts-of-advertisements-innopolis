const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080').replace(/\/$/, '');
const API_PREFIX = '/api/v1';
const ANALYSIS_POLL_INTERVAL_MS = 1000;
const ANALYSIS_TIMEOUT_MS = 180000;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function request(path, { method = 'GET', body, token } = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = new Error(payload?.error?.message || `Ошибка сервера (${response.status}).`);
    error.code = payload?.error?.code;
    error.status = response.status;
    error.details = payload?.error?.details;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function normalizeDraft(draft) {
  return {
    ...draft,
    title: draft.title || '',
    text: draft.text || '',
  };
}

export const register = credentials => request(`${API_PREFIX}/auth/register`, {
  method: 'POST', body: credentials,
});

export const login = credentials => request(`${API_PREFIX}/auth/login`, {
  method: 'POST', body: credentials,
});

export const refresh = refreshToken => request(`${API_PREFIX}/auth/refresh`, {
  method: 'POST', body: { refreshToken },
});

export const logout = refreshToken => request(`${API_PREFIX}/auth/logout`, {
  method: 'POST', body: { refreshToken },
});

export const getProfile = token => request(`${API_PREFIX}/auth/me`, { token });

export async function getMicrocategories() {
  const data = await request(`${API_PREFIX}/catalog/microcategories`);
  return data.items || [];
}

export async function searchCategories(query) {
  const categories = await getMicrocategories();
  const normalizedQuery = query.trim().toLocaleLowerCase('ru-RU');
  return categories.filter(item => item.name.toLocaleLowerCase('ru-RU').includes(normalizedQuery));
}

async function waitForAnalysis(analysisId, token) {
  const deadline = Date.now() + ANALYSIS_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const analysis = await request(`${API_PREFIX}/analyses/${analysisId}`, { token });
    if (analysis.status === 'completed') return analysis;
    if (analysis.status === 'failed') {
      const errors = await request(`${API_PREFIX}/analyses/${analysisId}/errors`, { token });
      throw new Error(errors.items?.map(item => item.message).filter(Boolean).join('. ') || 'Не удалось обработать текст.');
    }
    await sleep(ANALYSIS_POLL_INTERVAL_MS);
  }
  throw new Error('Обработка заняла слишком много времени. Проверьте результат позже.');
}

export async function analyzeText(description, mcId, token) {
  const created = await request(`${API_PREFIX}/analyses`, {
    method: 'POST', body: { description, mcId }, token,
  });
  const analysis = await waitForAnalysis(created.id, token);
  const drafts = await getAnalysisDrafts(analysis.id, token);
  return { id: analysis.id, description, mcId, drafts };
}

export async function getAnalysisDrafts(analysisId, token) {
  const data = await request(`${API_PREFIX}/analyses/${analysisId}/drafts`, { token });
  return (data.items || []).map(normalizeDraft);
}

// Предложения уже создаются бэкендом при успешном анализе.
export const generateDrafts = getAnalysisDrafts;

export async function listDrafts(state, token) {
  const params = state ? `?${new URLSearchParams({ state })}` : '';
  const data = await request(`${API_PREFIX}/drafts${params}`, { token });
  return (data.items || []).map(normalizeDraft);
}

export async function changeDraftState(draftId, state, token) {
  const updated = await request(`${API_PREFIX}/drafts/${draftId}/state`, {
    method: 'PATCH', body: { state }, token,
  });
  return normalizeDraft(updated);
}

export const saveProposal = (draftId, token) => changeDraftState(draftId, 'draft', token);
export const markReady = (draftId, token) => changeDraftState(draftId, 'ready', token);
export const moveToDrafts = (draftId, token) => changeDraftState(draftId, 'draft', token);

export async function updateDraft(draft, token) {
  const updated = await request(`${API_PREFIX}/drafts/${draft.id}`, {
    method: 'PATCH',
    body: { title: draft.title, text: draft.text },
    token,
  });
  return normalizeDraft(updated);
}

export const deleteDraft = (draftId, token) => request(`${API_PREFIX}/drafts/${draftId}`, {
  method: 'DELETE', token,
});

export function exportDraft(draft) {
  return `${draft.title || ''}\n\n${draft.text || ''}`;
}
