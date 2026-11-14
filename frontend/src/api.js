import { categoryChoices, mockAnalyze, mockGenerate } from './mockApi';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_PREFIX = '/api/v1';
const ANALYSIS_POLL_INTERVAL_MS = 1000;
const ANALYSIS_TIMEOUT_MS = 120000;
const DRAFT_POLL_INTERVAL_MS = 750;
const DRAFT_TIMEOUT_MS = 60000;

export const isDemo = !BASE_URL;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function request(path, { method = 'GET', body, token, responseType = 'json' } = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    let payload;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const message = payload?.error?.message || `Ошибка сервера (${response.status}). Попробуйте ещё раз.`;
    const error = new Error(message);
    error.code = payload?.error?.code;
    error.status = response.status;
    error.details = payload?.error?.details;
    throw error;
  }

  if (responseType === 'text') return response.text();
  if (response.status === 204) return null;
  return response.json();
}

function confidenceLabel(value) {
  if (value >= 0.8) return 'high';
  if (value >= 0.5) return 'medium';
  return 'low';
}

function normalizeDraft(draft, service, analysisId) {
  const classification = service?.classification || {};
  return {
    id: draft.id,
    serviceId: draft.serviceId || service?.id,
    analysisId,
    service: service?.service || service?.name,
    category: draft.category?.name || service?.category || classification.categoryName || '',
    microcategory: draft.microcategory?.name || service?.microcategory || classification.microcategoryName || '',
    title: draft.title,
    description: draft.description,
    status: draft.status === 'generated' || draft.status === 'edited' ? 'Черновик' : (draft.status || 'Черновик'),
    apiStatus: draft.status,
    createdAt: draft.createdAt,
    updatedAt: draft.updatedAt,
  };
}

function normalizeService(service, analysisId) {
  const classification = service.classification || {};
  const normalized = {
    id: service.id,
    analysisId,
    service: service.name,
    sourceFragment: service.sourceFragment,
    categoryId: classification.categoryId,
    category: classification.categoryName,
    microcategoryId: classification.microcategoryId,
    microcategory: classification.microcategoryName,
    confidenceScore: classification.confidence,
    confidence: confidenceLabel(classification.confidence),
    confirmed: classification.confirmed,
    classificationDirty: false,
    selected: true,
  };
  normalized.drafts = (service.drafts || []).map(draft => normalizeDraft(draft, normalized, analysisId));
  return normalized;
}

function processingErrorMessage(analysis) {
  const messages = (analysis.errors || [])
    .map(item => item.message || item.code)
    .filter(Boolean);
  return messages.length ? messages.join('. ') : 'Не удалось обработать текст.';
}

async function waitForAnalysis(analysisId, token) {
  const deadline = Date.now() + ANALYSIS_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const analysis = await request(`${API_PREFIX}/analyses/${analysisId}`, { token });
    if (analysis.status === 'completed' || analysis.status === 'partially_completed') return analysis;
    if (analysis.status === 'failed') throw new Error(processingErrorMessage(analysis));
    await sleep(ANALYSIS_POLL_INTERVAL_MS);
  }
  throw new Error('Обработка заняла слишком много времени. Попробуйте повторить запрос.');
}

export async function analyzeText(text, token) {
  if (isDemo) {
    return { analysisId: null, services: await mockAnalyze(text) };
  }

  const created = await request(`${API_PREFIX}/analyses`, {
    method: 'POST',
    body: { text, source: 'manual', draftsPerService: 1 },
    token,
  });
  const analysis = await waitForAnalysis(created.id, token);
  return {
    analysisId: analysis.id,
    normalizedText: analysis.normalizedText,
    services: (analysis.services || []).map(service => normalizeService(service, analysis.id)),
  };
}

export async function searchCategories(query, token) {
  const normalizedQuery = query.trim();
  if (normalizedQuery.length < 2) return [];

  if (isDemo) {
    return categoryChoices
      .filter(name => name.toLowerCase().includes(normalizedQuery.toLowerCase()))
      .map(name => ({ id: name, parentId: 'Ремонт и отделка', name, path: ['Ремонт и отделка', name] }));
  }

  const params = new URLSearchParams({ query: normalizedQuery, limit: '10' });
  const data = await request(`${API_PREFIX}/catalog/categories?${params}`, { token });
  return (data.items || []).filter(item => item.type === 'microcategory');
}

async function confirmClassification(analysisId, service, token) {
  if (!service.categoryId || !service.microcategoryId) {
    throw new Error(`Для услуги «${service.service}» необходимо выбрать категорию из справочника.`);
  }
  return request(`${API_PREFIX}/analyses/${analysisId}/services/${service.id}/classification`, {
    method: 'PATCH',
    body: {
      categoryId: service.categoryId,
      microcategoryId: service.microcategoryId,
      confirmed: true,
    },
    token,
  });
}

async function loadServiceDrafts(analysisId, service, token) {
  const data = await request(`${API_PREFIX}/analyses/${analysisId}/services/${service.id}/drafts`, { token });
  return (data.items || []).map(draft => normalizeDraft(draft, service, analysisId));
}

async function regenerateServiceDrafts(analysisId, service, token) {
  const previousDrafts = new Map(
    (service.drafts || []).map(draft => [draft.id, draft.updatedAt || draft.createdAt]),
  );
  await request(`${API_PREFIX}/analyses/${analysisId}/services/${service.id}/drafts/regenerate`, {
    method: 'POST',
    body: { variantsCount: 1, replaceExisting: true },
    token,
  });

  const deadline = Date.now() + DRAFT_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const drafts = await loadServiceDrafts(analysisId, service, token);
    const hasNewOrUpdatedDraft = drafts.some(draft =>
      !previousDrafts.has(draft.id)
      || previousDrafts.get(draft.id) !== (draft.updatedAt || draft.createdAt),
    );
    if (drafts.length && (previousDrafts.size === 0 || hasNewOrUpdatedDraft)) return drafts;
    await sleep(DRAFT_POLL_INTERVAL_MS);
  }
  throw new Error(`Не удалось дождаться нового черновика для услуги «${service.service}».`);
}

export async function generateDrafts(analysisId, services, token) {
  if (isDemo) return mockGenerate(services);
  if (!analysisId) throw new Error('Сначала выполните новый анализ текста.');

  const results = await Promise.all(services.map(async service => {
    const confirmation = await confirmClassification(analysisId, service, token);
    const shouldRegenerate = service.classificationDirty
      || confirmation?.draftRequiresRegeneration
      || !(service.drafts || []).length;
    if (shouldRegenerate) return regenerateServiceDrafts(analysisId, service, token);
    return loadServiceDrafts(analysisId, service, token);
  }));

  return results.flat();
}

export async function updateDraft(draft, token) {
  if (isDemo) return { ...draft, status: 'Черновик', apiStatus: 'edited', updatedAt: new Date().toISOString() };
  const updated = await request(`${API_PREFIX}/drafts/${draft.id}`, {
    method: 'PATCH',
    body: { title: draft.title, description: draft.description },
    token,
  });
  return normalizeDraft(updated, draft, draft.analysisId);
}

export async function exportDraft(draft, token) {
  if (isDemo || !draft.analysisId) {
    return `${draft.title}\n\n${draft.description}\n\nКатегория: ${draft.category} → ${draft.microcategory}`;
  }
  const params = new URLSearchParams({ format: 'text', draftIds: draft.id });
  return request(`${API_PREFIX}/analyses/${draft.analysisId}/export?${params}`, {
    token,
    responseType: 'text',
  });
}
