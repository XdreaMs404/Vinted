/**
 * Multi-account OAuth + persistent credential backoff for GSD.
 *
 * Core already supports:
 * - multiple API keys per provider
 * - session-sticky selection
 * - retry / fallback on usage-limit errors
 *
 * This extension adds:
 * - multiple OAuth credentials for the same provider
 * - in-place refresh of the selected OAuth credential
 * - persistent credential/provider backoff across restarts
 * - inventory / removal helpers for user-facing commands
 */

import { AuthStorage } from "@gsd/pi-coding-agent";
import { getOAuthProvider } from "@gsd/pi-ai/oauth";
import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const PATCH_FLAG = Symbol.for("gsd.llmCredentialFailover.patch.v2");
const LOOKUP_CONTEXT = Symbol.for("gsd.llmCredentialFailover.lookupContext");
const RUNTIME_STATE = Symbol.for("gsd.llmCredentialFailover.runtimeState");

const OAUTH_ID_FIELD = "_gsdCredentialId";
const OAUTH_ADDED_AT_FIELD = "_gsdAddedAt";
const OAUTH_LAST_REFRESH_AT_FIELD = "_gsdLastRefreshAt";

const RATE_LIMIT_BACKOFF_MS = 30_000;
const QUOTA_BACKOFF_MS = 30 * 60_000;
const SERVER_ERROR_BACKOFF_MS = 20_000;
const DEFAULT_BACKOFF_MS = 60_000;

const gsdHome = process.env.GSD_HOME || join(homedir(), ".gsd");
const BACKOFF_FILE_PATH = process.env.GSD_LLM_CREDENTIAL_BACKOFF_FILE
  || join(gsdHome, "agent", "llm-credential-backoff.json");

const OAUTH_IDENTITY_FIELDS = [
  "accountId",
  "account_id",
  "chatgpt_account_id",
  "userId",
  "user_id",
  "sub",
  "email",
  "login",
  "enterpriseUrl",
  "enterprise_url",
  "workspaceId",
  "workspace_id",
  "tenantId",
  "tenant_id",
  "organizationId",
  "organization_id",
];

const OPENAI_AUTH_CLAIM_PATH = "https://api.openai.com/auth";
const OPENAI_PROFILE_CLAIM_PATH = "https://api.openai.com/profile";

const backoffStores = new Map();

function now() {
  return Date.now();
}

function isObject(value) {
  return !!value && typeof value === "object";
}

function hashString(input) {
  const text = String(input ?? "");
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function normalizeCredentials(entry) {
  if (!entry) return [];
  return Array.isArray(entry) ? [...entry] : [entry];
}

function denormalizeCredentials(credentials) {
  if (!Array.isArray(credentials) || credentials.length === 0) return undefined;
  return credentials.length === 1 ? credentials[0] : credentials;
}

function readStringField(value, field) {
  if (!isObject(value)) return undefined;
  const result = value[field];
  return typeof result === "string" && result.trim() ? result.trim() : undefined;
}

function getBackoffDuration(errorType) {
  switch (errorType) {
    case "rate_limit":
      return RATE_LIMIT_BACKOFF_MS;
    case "quota_exhausted":
      return QUOTA_BACKOFF_MS;
    case "server_error":
      return SERVER_ERROR_BACKOFF_MS;
    default:
      return DEFAULT_BACKOFF_MS;
  }
}

function getRuntimeState(auth) {
  if (!auth[RUNTIME_STATE]) {
    auth[RUNTIME_STATE] = {
      selectedCredentialByContext: new Map(),
    };
  }
  return auth[RUNTIME_STATE];
}

function getContextKey(provider, sessionId) {
  return `${provider}::${sessionId ?? "__roundrobin__"}`;
}

function decodeJwtPayload(token) {
  if (typeof token !== "string" || !token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    return JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
  } catch {
    return null;
  }
}

function getOpenAiCodexIdentity(provider, credential) {
  const payload = decodeJwtPayload(readStringField(credential, "access"));
  const auth = isObject(payload?.[OPENAI_AUTH_CLAIM_PATH]) ? payload[OPENAI_AUTH_CLAIM_PATH] : null;
  const profile = isObject(payload?.[OPENAI_PROFILE_CLAIM_PATH]) ? payload[OPENAI_PROFILE_CLAIM_PATH] : null;

  const candidates = [
    ["chatgpt_account_user_id", readStringField(auth, "chatgpt_account_user_id")],
    ["chatgpt_user_id", readStringField(auth, "chatgpt_user_id")],
    ["user_id", readStringField(auth, "user_id")],
    ["sub", typeof payload?.sub === "string" && payload.sub.trim() ? payload.sub.trim() : undefined],
    ["email", typeof profile?.email === "string" && profile.email.trim() ? profile.email.trim() : undefined],
    ["accountId", readStringField(credential, "accountId")],
  ];

  for (const [field, value] of candidates) {
    if (value) {
      return `${provider}:${field}:${value}`;
    }
  }

  return null;
}

function getLegacyOpenAiCodexCredentialId(provider, credential) {
  const accountId = readStringField(credential, "accountId");
  if (!accountId) return undefined;
  return `oauth:${hashString(`${provider}:accountId:${accountId}`)}`;
}

function getPreferredOAuthIdentity(provider, credential) {
  if (provider === "openai-codex") {
    const openAiIdentity = getOpenAiCodexIdentity(provider, credential);
    if (openAiIdentity) return openAiIdentity;
  }

  for (const field of OAUTH_IDENTITY_FIELDS) {
    const value = readStringField(credential, field);
    if (value) {
      return `${provider}:${field}:${value}`;
    }
  }

  const refresh = readStringField(credential, "refresh");
  if (refresh) return `${provider}:refresh:${hashString(refresh)}`;

  const access = readStringField(credential, "access");
  if (access) return `${provider}:access:${hashString(access)}`;

  return `${provider}:oauth:anonymous`;
}

function getStableOAuthIdentity(provider, credential) {
  return getPreferredOAuthIdentity(provider, credential);
}

function getStableCredentialId(provider, credential) {
  if (!credential) return undefined;

  if (credential.type === "api_key") {
    return `api:${provider}:${hashString(credential.key ?? "")}`;
  }

  const preferredId = `oauth:${hashString(getPreferredOAuthIdentity(provider, credential))}`;
  const storedId = readStringField(credential, OAUTH_ID_FIELD);

  if (provider === "openai-codex") {
    const legacyId = getLegacyOpenAiCodexCredentialId(provider, credential);
    if (storedId && legacyId && storedId === legacyId && preferredId !== legacyId) {
      return preferredId;
    }
  }

  return storedId || preferredId;
}

function ensureOAuthMetadata(provider, credential, previous) {
  const stableId = getStableCredentialId(provider, previous)
    || getStableCredentialId(provider, credential)
    || `oauth:${hashString(getPreferredOAuthIdentity(provider, credential))}`;

  const addedAt = Number(previous?.[OAUTH_ADDED_AT_FIELD] ?? credential?.[OAUTH_ADDED_AT_FIELD] ?? now());
  const lastRefreshAt = Number(previous?.[OAUTH_LAST_REFRESH_AT_FIELD] ?? credential?.[OAUTH_LAST_REFRESH_AT_FIELD] ?? 0);

  return {
    ...credential,
    [OAUTH_ID_FIELD]: stableId,
    [OAUTH_ADDED_AT_FIELD]: Number.isFinite(addedAt) ? addedAt : now(),
    ...(lastRefreshAt > 0 ? { [OAUTH_LAST_REFRESH_AT_FIELD]: lastRefreshAt } : {}),
  };
}

function isSameOAuthCredential(provider, left, right) {
  const leftId = getStableCredentialId(provider, left);
  const rightId = getStableCredentialId(provider, right);
  if (leftId && rightId) return leftId === rightId;
  return getStableOAuthIdentity(provider, left) === getStableOAuthIdentity(provider, right);
}

export function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return "expired";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function maskEmail(email) {
  if (typeof email !== "string" || !email.includes("@")) return email;
  const [local, domain] = email.split("@", 2);
  if (!local || !domain) return email;
  if (local.length <= 2) return `${local[0] ?? "*"}*@${domain}`;
  return `${local[0]}${"*".repeat(Math.max(1, local.length - 2))}${local.slice(-1)}@${domain}`;
}

function getOpenAiCodexMaskedEmail(credential) {
  const payload = decodeJwtPayload(readStringField(credential, "access"));
  const profile = isObject(payload?.[OPENAI_PROFILE_CLAIM_PATH])
    ? payload[OPENAI_PROFILE_CLAIM_PATH]
    : null;
  const email = typeof profile?.email === "string" ? profile.email : undefined;
  return email ? maskEmail(email) : undefined;
}

function getCredentialLabel(provider, credential) {
  if (!credential) return "unknown";

  if (credential.type === "api_key") {
    const key = String(credential.key ?? "");
    if (!key) return "API key (empty)";
    if (key.length <= 8) return `API key ${key.slice(0, 2)}***${key.slice(-2)}`;
    return `API key ${key.slice(0, 4)}***${key.slice(-4)}`;
  }

  if (provider === "openai-codex") {
    const email = getOpenAiCodexMaskedEmail(credential);
    if (email) return `OAuth email=${email}`;
  }

  for (const field of OAUTH_IDENTITY_FIELDS) {
    const value = readStringField(credential, field);
    if (value) return `OAuth ${field}=${value}`;
  }

  const id = getStableCredentialId(provider, credential);
  return `OAuth ${String(id ?? "unknown").slice(-10)}`;
}

class PersistentBackoffStore {
  constructor(filePath) {
    this.filePath = filePath;
    this.data = { version: 1, providers: {} };
    this.loaded = false;
  }

  ensureLoaded() {
    if (this.loaded) return;
    this.loaded = true;

    try {
      if (!existsSync(this.filePath)) {
        this.data = { version: 1, providers: {} };
        return;
      }

      const raw = readFileSync(this.filePath, "utf-8");
      const parsed = JSON.parse(raw);
      const providers = isObject(parsed?.providers) ? parsed.providers : {};
      this.data = {
        version: 1,
        providers,
      };
      this.pruneExpired(false);
    } catch {
      this.data = { version: 1, providers: {} };
    }
  }

  persist() {
    this.ensureLoaded();
    mkdirSync(dirname(this.filePath), { recursive: true, mode: 0o700 });

    const tmpPath = `${this.filePath}.tmp-${process.pid}`;
    try {
      writeFileSync(tmpPath, JSON.stringify(this.data, null, 2), "utf-8");
      chmodSync(tmpPath, 0o600);
      renameSync(tmpPath, this.filePath);
      try {
        chmodSync(this.filePath, 0o600);
      } catch {
        // best effort
      }
    } finally {
      try {
        if (existsSync(tmpPath)) unlinkSync(tmpPath);
      } catch {
        // ignore cleanup failure
      }
    }
  }

  getProviderEntry(provider) {
    this.ensureLoaded();
    if (!isObject(this.data.providers[provider])) {
      this.data.providers[provider] = { providerBackoffUntil: 0, credentials: {} };
    }

    const entry = this.data.providers[provider];
    if (!isObject(entry.credentials)) {
      entry.credentials = {};
    }
    return entry;
  }

  pruneExpired(save = true) {
    this.ensureLoaded();
    const current = now();
    let changed = false;

    for (const [provider, entry] of Object.entries(this.data.providers)) {
      if (!isObject(entry)) {
        delete this.data.providers[provider];
        changed = true;
        continue;
      }

      if (!isObject(entry.credentials)) {
        entry.credentials = {};
        changed = true;
      }

      if (Number(entry.providerBackoffUntil ?? 0) <= current) {
        if (entry.providerBackoffUntil) changed = true;
        entry.providerBackoffUntil = 0;
      }

      for (const [credentialId, expiresAt] of Object.entries(entry.credentials)) {
        if (Number(expiresAt) <= current) {
          delete entry.credentials[credentialId];
          changed = true;
        }
      }

      if (!entry.providerBackoffUntil && Object.keys(entry.credentials).length === 0) {
        delete this.data.providers[provider];
        changed = true;
      }
    }

    if (changed && save) {
      this.persist();
    }
  }

  getProviderRemaining(provider) {
    this.pruneExpired(false);
    const entry = this.data.providers[provider];
    if (!entry) return 0;
    return Math.max(0, Number(entry.providerBackoffUntil ?? 0) - now());
  }

  setProviderBackoff(provider, expiresAt) {
    const entry = this.getProviderEntry(provider);
    entry.providerBackoffUntil = Math.max(Number(entry.providerBackoffUntil ?? 0), Number(expiresAt ?? 0));
    this.persist();
  }

  clearProviderBackoff(provider) {
    this.ensureLoaded();
    const entry = this.data.providers[provider];
    if (!entry) return;
    entry.providerBackoffUntil = 0;
    if (Object.keys(entry.credentials ?? {}).length === 0) {
      delete this.data.providers[provider];
    }
    this.persist();
  }

  clearProvider(provider) {
    this.ensureLoaded();
    if (!(provider in this.data.providers)) return;
    delete this.data.providers[provider];
    this.persist();
  }

  getCredentialRemaining(provider, credentialId) {
    this.pruneExpired(false);
    const entry = this.data.providers[provider];
    if (!entry || !credentialId) return 0;
    return Math.max(0, Number(entry.credentials?.[credentialId] ?? 0) - now());
  }

  setCredentialBackoff(provider, credentialId, expiresAt) {
    if (!credentialId) return;
    const entry = this.getProviderEntry(provider);
    entry.credentials[credentialId] = Math.max(Number(entry.credentials?.[credentialId] ?? 0), Number(expiresAt ?? 0));
    this.persist();
  }

  clearCredentialBackoff(provider, credentialId) {
    this.ensureLoaded();
    const entry = this.data.providers[provider];
    if (!entry || !credentialId || !(credentialId in (entry.credentials ?? {}))) return;
    delete entry.credentials[credentialId];
    if (!entry.providerBackoffUntil && Object.keys(entry.credentials).length === 0) {
      delete this.data.providers[provider];
    }
    this.persist();
  }

  clearAllCredentialBackoffs(provider) {
    this.ensureLoaded();
    const entry = this.data.providers[provider];
    if (!entry) return;
    entry.credentials = {};
    if (!entry.providerBackoffUntil) {
      delete this.data.providers[provider];
    }
    this.persist();
  }
}

function getBackoffStore() {
  if (!backoffStores.has(BACKOFF_FILE_PATH)) {
    backoffStores.set(BACKOFF_FILE_PATH, new PersistentBackoffStore(BACKOFF_FILE_PATH));
  }
  return backoffStores.get(BACKOFF_FILE_PATH);
}

function hasAvailableCredential(auth, provider) {
  const store = getBackoffStore();
  const credentials = auth.getCredentialsForProvider(provider);
  if (credentials.length === 0) return false;

  return credentials.some((credential) => {
    const credentialId = getStableCredentialId(provider, credential);
    return store.getCredentialRemaining(provider, credentialId) <= 0;
  });
}

function rememberCredentialSelection(auth, provider, sessionId, credential) {
  const credentialId = getStableCredentialId(provider, credential);
  if (!credentialId) return;

  const runtimeState = getRuntimeState(auth);
  runtimeState.selectedCredentialByContext.set(getContextKey(provider, sessionId), credentialId);
}

function resolveLastUsedCredential(auth, provider, sessionId, credentials) {
  const runtimeState = getRuntimeState(auth);
  const rememberedId = runtimeState.selectedCredentialByContext.get(getContextKey(provider, sessionId));
  if (rememberedId) {
    const remembered = credentials.find((credential) => getStableCredentialId(provider, credential) === rememberedId);
    if (remembered) return remembered;
  }

  if (credentials.length === 0) return undefined;
  if (credentials.length === 1) return credentials[0];

  if (sessionId) {
    const hashedIndex = Number.parseInt(hashString(sessionId), 36);
    const index = Number.isFinite(hashedIndex) ? hashedIndex % credentials.length : 0;
    return credentials[index];
  }

  const current = auth.providerRoundRobinIndex?.get?.(provider) ?? 0;
  const index = ((current - 1) % credentials.length + credentials.length) % credentials.length;
  return credentials[index];
}

function getPerCredentialBackoffRemaining(provider, credential) {
  const store = getBackoffStore();
  return store.getCredentialRemaining(provider, getStableCredentialId(provider, credential));
}

function getProviderBackoffRemaining(auth, provider) {
  const store = getBackoffStore();
  const remaining = store.getProviderRemaining(provider);
  if (remaining > 0 && hasAvailableCredential(auth, provider)) {
    store.clearProviderBackoff(provider);
    return 0;
  }
  return remaining;
}

function buildProviderSummary(auth, provider) {
  const credentials = auth.getCredentialsForProvider(provider);
  const lines = [`${provider} — ${credentials.length} credential${credentials.length > 1 ? "s" : ""}`];

  const providerBackoffRemaining = getProviderBackoffRemaining(auth, provider);
  if (providerBackoffRemaining > 0) {
    lines.push(`  provider backoff: ${formatDuration(providerBackoffRemaining)}`);
  }

  if (credentials.length === 0) {
    lines.push("  (none)");
    return lines.join("\n");
  }

  credentials.forEach((credential, index) => {
    const parts = [`  [${index + 1}] ${getCredentialLabel(provider, credential)}`];

    if (credential.type === "oauth") {
      const expiresIn = Number(credential.expires ?? 0) - now();
      parts.push(expiresIn > 0 ? `expires in ${formatDuration(expiresIn)}` : "expired");
      const addedAt = Number(credential[OAUTH_ADDED_AT_FIELD] ?? 0);
      if (addedAt > 0) {
        parts.push(`added ${new Date(addedAt).toISOString()}`);
      }
    }

    const backoffRemaining = getPerCredentialBackoffRemaining(provider, credential);
    if (backoffRemaining > 0) {
      parts.push(`backed off ${formatDuration(backoffRemaining)}`);
    }

    const credentialId = getStableCredentialId(provider, credential);
    if (credentialId) {
      parts.push(`id=${String(credentialId).slice(-10)}`);
    }

    lines.push(parts.join(" · "));
  });

  return lines.join("\n");
}

async function refreshSpecificOAuthCredential(storage, providerId, credential) {
  const provider = getOAuthProvider(providerId);
  if (!provider) return null;

  const targetId = getStableCredentialId(providerId, credential);
  if (!targetId) return null;

  const result = await storage.storage.withLockAsync(async (current) => {
    const currentData = storage.parseStorageData(current);
    storage.data = currentData;
    storage.loadError = null;

    const credentials = normalizeCredentials(currentData[providerId]);
    const credentialIndex = credentials.findIndex((entry) => {
      return entry?.type === "oauth" && getStableCredentialId(providerId, entry) === targetId;
    });

    if (credentialIndex === -1) {
      return { result: null };
    }

    const currentCredential = credentials[credentialIndex];
    if (!currentCredential || currentCredential.type !== "oauth") {
      return { result: null };
    }

    const decoratedCurrent = ensureOAuthMetadata(providerId, currentCredential, currentCredential);
    if (now() < Number(decoratedCurrent.expires ?? 0)) {
      return {
        result: {
          apiKey: provider.getApiKey(decoratedCurrent),
          newCredentials: decoratedCurrent,
        },
      };
    }

    const refreshed = await provider.refreshToken(decoratedCurrent);
    const decoratedRefreshed = ensureOAuthMetadata(
      providerId,
      {
        ...decoratedCurrent,
        ...refreshed,
        [OAUTH_LAST_REFRESH_AT_FIELD]: now(),
      },
      decoratedCurrent,
    );

    credentials[credentialIndex] = decoratedRefreshed;
    const nextEntry = denormalizeCredentials(credentials);
    const merged = {
      ...currentData,
      [providerId]: nextEntry,
    };

    storage.data = merged;
    storage.loadError = null;

    return {
      result: {
        apiKey: provider.getApiKey(decoratedRefreshed),
        newCredentials: decoratedRefreshed,
      },
      next: JSON.stringify(merged, null, 2),
    };
  });

  if (result) {
    queueMicrotask(() => {
      try {
        storage.notifyCredentialChange?.();
      } catch {
        // best effort
      }
    });
  }

  return result;
}

export function getBackoffFilePath() {
  return BACKOFF_FILE_PATH;
}

export async function ensureFreshCredential(auth, provider, credential) {
  if (!credential || credential.type !== "oauth") {
    return credential;
  }

  const decorated = ensureOAuthMetadata(provider, credential, credential);
  if (now() + 30_000 < Number(decorated.expires ?? 0)) {
    return decorated;
  }

  try {
    const refreshed = await refreshSpecificOAuthCredential(auth, provider, decorated);
    if (refreshed?.newCredentials) {
      return refreshed.newCredentials;
    }
  } catch {
    // best effort
  }

  try {
    auth.reload?.();
  } catch {
    // best effort
  }

  const match = auth.getCredentialsForProvider(provider).find((entry) => {
    return entry?.type === "oauth" && getStableCredentialId(provider, entry) === getStableCredentialId(provider, decorated);
  });

  return match ?? decorated;
}

export function getCredentialId(provider, credential) {
  return getStableCredentialId(provider, credential);
}

export function getCredentialBackoffRemaining(provider, credential) {
  return getPerCredentialBackoffRemaining(provider, credential);
}

export function getProviderBackoffRemainingMs(auth, provider) {
  return getProviderBackoffRemaining(auth, provider);
}

export function getProviderSessionSelection(auth, provider, sessionId) {
  const credentials = auth.getCredentialsForProvider(provider);
  const runtimeState = getRuntimeState(auth);
  const rememberedId = runtimeState.selectedCredentialByContext.get(getContextKey(provider, sessionId));

  const selected = rememberedId
    ? credentials.find((credential) => getStableCredentialId(provider, credential) === rememberedId)
    : resolveLastUsedCredential(auth, provider, sessionId, credentials);

  return {
    sessionId: sessionId ?? null,
    selectedCredentialId: getStableCredentialId(provider, selected) ?? null,
    source: rememberedId ? "remembered" : selected ? "predicted" : "none",
  };
}

export function listConfiguredProviders(auth) {
  return auth.list()
    .filter((provider) => auth.getCredentialsForProvider(provider).length > 0)
    .sort();
}

export function formatCredentialInventory(auth, filterProvider) {
  const providers = filterProvider
    ? [filterProvider]
    : listConfiguredProviders(auth);

  if (providers.length === 0) {
    return [
      "LLM credential inventory",
      "",
      "No stored credentials found in auth.json.",
      "Use /gsd setup llm or /llm-accounts setup to add OAuth accounts or API keys.",
      `Persistent backoff file: ${getBackoffFilePath()}`,
    ].join("\n");
  }

  return [
    "LLM credential inventory",
    "",
    ...providers.map((provider) => buildProviderSummary(auth, provider)),
    "",
    `Persistent backoff file: ${getBackoffFilePath()}`,
    "Notes:",
    "- Repeat /login or use /llm-accounts login to add another OAuth account for the same provider.",
    "- When one account hits rate/quota limits, GSD rotates to the next credential for that provider.",
    "- /logout still removes the whole provider. Use /llm-accounts remove to remove one credential only.",
  ].join("\n");
}

export function removeCredential(auth, provider, selector) {
  const credentials = auth.getCredentialsForProvider(provider);
  if (credentials.length === 0) {
    throw new Error(`No credentials stored for provider \"${provider}\".`);
  }

  let targetIndex = -1;
  const numeric = Number(selector);
  if (Number.isInteger(numeric) && numeric >= 1 && numeric <= credentials.length) {
    targetIndex = numeric - 1;
  } else if (selector) {
    targetIndex = credentials.findIndex((credential) => {
      const credentialId = getStableCredentialId(provider, credential);
      return credentialId === selector || String(credentialId).endsWith(selector);
    });
  }

  if (targetIndex < 0 || targetIndex >= credentials.length) {
    throw new Error(`Credential selector \"${selector}\" did not match a stored credential for \"${provider}\".`);
  }

  const removed = credentials[targetIndex];
  const remaining = credentials.filter((_, index) => index !== targetIndex);
  const removedId = getStableCredentialId(provider, removed);

  auth.remove(provider);
  for (const credential of remaining) {
    auth.set(provider, credential);
  }

  if (removedId) {
    const store = getBackoffStore();
    store.clearCredentialBackoff(provider, removedId);
    if (remaining.length > 0) {
      store.clearProviderBackoff(provider);
    }
  }

  return {
    removed,
    remainingCount: remaining.length,
  };
}

export function clearCredentialBackoff(auth, provider, selector) {
  const credentials = auth.getCredentialsForProvider(provider);
  if (credentials.length === 0) {
    throw new Error(`No credentials stored for provider \"${provider}\".`);
  }

  const store = getBackoffStore();

  if (!selector || selector === "all") {
    store.clearAllCredentialBackoffs(provider);
    store.clearProviderBackoff(provider);
    return { clearedProvider: true, clearedCount: credentials.length };
  }

  const numeric = Number(selector);
  let targetIndex = -1;
  if (Number.isInteger(numeric) && numeric >= 1 && numeric <= credentials.length) {
    targetIndex = numeric - 1;
  } else {
    targetIndex = credentials.findIndex((credential) => {
      const credentialId = getStableCredentialId(provider, credential);
      return credentialId === selector || String(credentialId).endsWith(selector);
    });
  }

  if (targetIndex < 0) {
    throw new Error(`Credential selector \"${selector}\" did not match a stored credential for \"${provider}\".`);
  }

  const credentialId = getStableCredentialId(provider, credentials[targetIndex]);
  store.clearCredentialBackoff(provider, credentialId);
  if (hasAvailableCredential(auth, provider)) {
    store.clearProviderBackoff(provider);
  }

  return { clearedProvider: false, clearedCount: 1 };
}

export function applyMultiOAuthPatches() {
  const proto = AuthStorage.prototype;
  if (proto[PATCH_FLAG]) return;

  const requiredMethods = [
    "set",
    "remove",
    "getApiKey",
    "resolveCredentialApiKey",
    "markUsageLimitReached",
    "markProviderExhausted",
    "isProviderAvailable",
    "getProviderBackoffRemaining",
    "isCredentialBackedOff",
  ];
  for (const methodName of requiredMethods) {
    if (typeof proto[methodName] !== "function") {
      throw new Error(`AuthStorage patch failed: expected AuthStorage.${methodName}().`);
    }
  }

  const originalSet = proto.set;
  const originalRemove = proto.remove;
  const originalGetApiKey = proto.getApiKey;
  const originalResolveCredentialApiKey = proto.resolveCredentialApiKey;

  proto.set = function patchedSet(provider, credential) {
    if (!credential || credential.type !== "oauth") {
      const result = originalSet.call(this, provider, credential);
      if (hasAvailableCredential(this, provider)) {
        getBackoffStore().clearProviderBackoff(provider);
      }
      return result;
    }

    const existing = this.getCredentialsForProvider(provider);
    const apiKeys = existing.filter((entry) => entry.type === "api_key");
    const oauths = existing.filter((entry) => entry.type === "oauth");

    const incoming = ensureOAuthMetadata(provider, credential);
    const matchingIndex = oauths.findIndex((entry) => isSameOAuthCredential(provider, entry, incoming));
    const nextOauths = [...oauths];

    if (matchingIndex >= 0) {
      nextOauths[matchingIndex] = ensureOAuthMetadata(
        provider,
        { ...nextOauths[matchingIndex], ...incoming },
        nextOauths[matchingIndex],
      );
    } else {
      nextOauths.push(incoming);
    }

    const updated = [...apiKeys, ...nextOauths];
    const nextEntry = denormalizeCredentials(updated);
    this.data[provider] = nextEntry;
    this.persistProviderChange(provider, nextEntry);

    getBackoffStore().clearProviderBackoff(provider);
  };

  proto.remove = function patchedRemove(provider) {
    const result = originalRemove.call(this, provider);
    getBackoffStore().clearProvider(provider);
    return result;
  };

  proto.getApiKey = async function patchedGetApiKey(providerId, sessionId, options) {
    this[LOOKUP_CONTEXT] = { providerId, sessionId };
    try {
      return await originalGetApiKey.call(this, providerId, sessionId, options);
    } finally {
      delete this[LOOKUP_CONTEXT];
    }
  };

  proto.resolveCredentialApiKey = async function patchedResolveCredentialApiKey(providerId, credential) {
    if (!credential || credential.type !== "oauth") {
      const resolved = await originalResolveCredentialApiKey.call(this, providerId, credential);
      if (resolved) {
        rememberCredentialSelection(this, providerId, this[LOOKUP_CONTEXT]?.sessionId, credential);
      }
      return resolved;
    }

    const provider = getOAuthProvider(providerId);
    if (!provider) return undefined;

    const decorated = ensureOAuthMetadata(providerId, credential, credential);
    const needsRefresh = now() >= Number(decorated.expires ?? 0);

    if (!needsRefresh) {
      rememberCredentialSelection(this, providerId, this[LOOKUP_CONTEXT]?.sessionId, decorated);
      return provider.getApiKey(decorated);
    }

    try {
      const refreshed = await refreshSpecificOAuthCredential(this, providerId, decorated);
      if (refreshed?.apiKey) {
        rememberCredentialSelection(this, providerId, this[LOOKUP_CONTEXT]?.sessionId, refreshed.newCredentials);
        return refreshed.apiKey;
      }
    } catch (error) {
      try {
        this.recordError?.(error);
      } catch {
        // best effort
      }
      this.reload?.();
      const credentials = this.getCredentialsForProvider(providerId);
      const match = credentials.find((entry) => {
        return entry?.type === "oauth" && getStableCredentialId(providerId, entry) === getStableCredentialId(providerId, decorated);
      });
      if (match?.type === "oauth" && now() < Number(match.expires ?? 0)) {
        rememberCredentialSelection(this, providerId, this[LOOKUP_CONTEXT]?.sessionId, match);
        return provider.getApiKey(match);
      }
      return undefined;
    }

    return undefined;
  };

  proto.isCredentialBackedOff = function patchedIsCredentialBackedOff(provider, index) {
    const credentials = this.getCredentialsForProvider(provider);
    const credential = credentials[index];
    if (!credential) return false;
    return getPerCredentialBackoffRemaining(provider, credential) > 0;
  };

  proto.getProviderBackoffRemaining = function patchedGetProviderBackoffRemaining(provider) {
    return getProviderBackoffRemaining(this, provider);
  };

  proto.isProviderAvailable = function patchedIsProviderAvailable(provider) {
    return getProviderBackoffRemaining(this, provider) <= 0;
  };

  proto.markProviderExhausted = function patchedMarkProviderExhausted(provider, errorType) {
    const expiresAt = now() + getBackoffDuration(errorType);
    getBackoffStore().setProviderBackoff(provider, expiresAt);
  };

  proto.markUsageLimitReached = function patchedMarkUsageLimitReached(provider, sessionId, options) {
    const credentials = this.getCredentialsForProvider(provider);
    if (credentials.length === 0) return false;

    const errorType = options?.errorType ?? "rate_limit";
    if (errorType === "unknown" && credentials.length === 1) {
      return false;
    }

    const usedCredential = resolveLastUsedCredential(this, provider, sessionId, credentials);
    if (!usedCredential) return false;

    const expiresAt = now() + getBackoffDuration(errorType);
    const credentialId = getStableCredentialId(provider, usedCredential);
    getBackoffStore().setCredentialBackoff(provider, credentialId, expiresAt);

    const hasAlternate = credentials.some((credential) => {
      if (getStableCredentialId(provider, credential) === credentialId) return false;
      return getPerCredentialBackoffRemaining(provider, credential) <= 0;
    });

    if (hasAlternate) {
      getBackoffStore().clearProviderBackoff(provider);
    }

    return hasAlternate;
  };

  Object.defineProperty(proto, PATCH_FLAG, {
    value: true,
    enumerable: false,
    configurable: false,
    writable: false,
  });
}
