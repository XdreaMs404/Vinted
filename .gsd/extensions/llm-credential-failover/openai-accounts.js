import { Key, matchesKey, truncateToWidth, wrapTextWithAnsi } from "@gsd/pi-tui";
import {
  ensureFreshCredential,
  formatDuration,
  getCredentialBackoffRemaining,
  getCredentialId,
  getProviderBackoffRemainingMs,
  getProviderSessionSelection,
} from "./multi-oauth.js";

const OPENAI_PROVIDER_ID = "openai-codex";
const OPENAI_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage";
const OPENAI_USAGE_CACHE_TTL_MS = 30_000;
const OPENAI_USAGE_ERROR_CACHE_TTL_MS = 5_000;
const OPENAI_AUTH_CLAIM_PATH = "https://api.openai.com/auth";
const OPENAI_PROFILE_CLAIM_PATH = "https://api.openai.com/profile";
const SESSION_SELECTION_TEXT = {
  remembered: "actif dans cette session",
  predicted: "prochain compte pour cette session",
  none: "aucune sélection de session",
};

const usageCache = new Map();

function now() {
  return Date.now();
}

function isObject(value) {
  return !!value && typeof value === "object";
}

function readStringField(value, field) {
  if (!isObject(value)) return undefined;
  const result = value[field];
  return typeof result === "string" && result.trim() ? result.trim() : undefined;
}

function readNumberField(value, field) {
  if (!isObject(value)) return undefined;
  const result = value[field];
  return Number.isFinite(result) ? Number(result) : undefined;
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

function maskEmail(email) {
  if (typeof email !== "string" || !email.includes("@")) return email;
  const [local, domain] = email.split("@", 2);
  if (!local || !domain) return email;
  const visible = local.length <= 2
    ? `${local[0] ?? "*"}*`
    : `${local[0]}${"*".repeat(Math.max(1, local.length - 2))}${local.slice(-1)}`;
  return `${visible}@${domain}`;
}

function tail(value, size = 8) {
  if (typeof value !== "string" || !value) return undefined;
  return value.slice(-size);
}

function getCredentialAccountId(credential) {
  const direct = readStringField(credential, "accountId");
  if (direct) return direct;
  const payload = decodeJwtPayload(readStringField(credential, "access"));
  return readStringField(payload?.[OPENAI_AUTH_CLAIM_PATH], "chatgpt_account_id");
}

function getCredentialMaskedEmail(credential) {
  const payload = decodeJwtPayload(readStringField(credential, "access"));
  const profile = isObject(payload?.[OPENAI_PROFILE_CLAIM_PATH]) ? payload[OPENAI_PROFILE_CLAIM_PATH] : null;
  const email = typeof profile?.email === "string" ? profile.email : undefined;
  return email ? maskEmail(email) : undefined;
}

function padRight(text, width) {
  const value = String(text ?? "");
  if (width <= 0) return "";
  if (value.length >= width) return value.slice(0, width);
  return value + " ".repeat(width - value.length);
}

function formatClock(resetAtMs) {
  if (!Number.isFinite(resetAtMs) || resetAtMs <= 0) return "?";
  const target = new Date(resetAtMs);
  const current = new Date();
  const sameDay = target.toDateString() === current.toDateString();
  const formatter = sameDay
    ? new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" })
    : new Intl.DateTimeFormat("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" });
  return formatter.format(target);
}

function formatWindowMinutes(windowMinutes) {
  if (!Number.isFinite(windowMinutes) || windowMinutes <= 0) return undefined;
  if (Math.abs(windowMinutes - 300) < 1) return "5h";
  if (Math.abs(windowMinutes - 10_080) < 1) return "hebdo";
  if (windowMinutes < 60) return `${Math.round(windowMinutes)}m`;
  const hours = Math.round(windowMinutes / 60);
  return `${hours}h`;
}

function normalizeWindow(window) {
  if (!isObject(window)) return null;
  const usedPercent = Math.max(0, Math.min(100, Number(window.used_percent ?? window.usedPercent ?? 0)));
  const remainingPercent = Math.max(0, Math.min(100, 100 - usedPercent));
  const limitWindowSeconds = readNumberField(window, "limit_window_seconds")
    ?? (readNumberField(window, "windowDurationMins") != null ? readNumberField(window, "windowDurationMins") * 60 : undefined)
    ?? (readNumberField(window, "window_minutes") != null ? readNumberField(window, "window_minutes") * 60 : undefined);
  const resetAfterSeconds = readNumberField(window, "reset_after_seconds");
  const resetAtSeconds = readNumberField(window, "reset_at") ?? (readNumberField(window, "resetsAt") != null
    ? Math.floor(readNumberField(window, "resetsAt") / 1000)
    : undefined);
  const resetAtMs = resetAtSeconds != null
    ? resetAtSeconds * 1000
    : resetAfterSeconds != null
      ? now() + resetAfterSeconds * 1000
      : undefined;
  const resetAfterMs = resetAfterSeconds != null
    ? resetAfterSeconds * 1000
    : resetAtMs != null
      ? Math.max(0, resetAtMs - now())
      : undefined;
  const windowMinutes = limitWindowSeconds != null ? limitWindowSeconds / 60 : undefined;

  return {
    usedPercent,
    remainingPercent,
    windowMinutes,
    windowLabel: formatWindowMinutes(windowMinutes),
    resetAtMs,
    resetAfterMs,
    resetText: resetAtMs ? formatClock(resetAtMs) : "?",
    remainingText: resetAfterMs != null ? formatDuration(resetAfterMs) : "?",
  };
}

function normalizeRateBucket(bucket) {
  if (!isObject(bucket)) return null;
  return {
    allowed: bucket.allowed !== false,
    limitReached: bucket.limit_reached === true || bucket.limitReached === true,
    primary: normalizeWindow(bucket.primary_window ?? bucket.primary),
    secondary: normalizeWindow(bucket.secondary_window ?? bucket.secondary),
  };
}

function summarizeCredits(credits) {
  if (!isObject(credits)) return null;
  return {
    hasCredits: credits.has_credits === true,
    unlimited: credits.unlimited === true,
    balance: credits.balance != null ? String(credits.balance) : null,
    approxLocalMessages: credits.approx_local_messages != null ? String(credits.approx_local_messages) : null,
    approxCloudMessages: credits.approx_cloud_messages != null ? String(credits.approx_cloud_messages) : null,
  };
}

function normalizeUsagePayload(payload) {
  const emailMasked = maskEmail(readStringField(payload, "email") || "");
  const additionalRateLimitsRaw = isObject(payload.additional_rate_limits) ? payload.additional_rate_limits : {};
  const additionalRateLimits = Object.entries(additionalRateLimitsRaw)
    .map(([key, value]) => ({ key, bucket: normalizeRateBucket(value) }))
    .filter((entry) => entry.bucket);

  return {
    emailMasked: emailMasked || null,
    planType: readStringField(payload, "plan_type") || null,
    userIdTail: tail(readStringField(payload, "user_id"), 10) || null,
    accountIdTail: tail(readStringField(payload, "account_id"), 8) || null,
    main: normalizeRateBucket(payload.rate_limit),
    codeReviews: normalizeRateBucket(payload.code_review_rate_limit),
    additionalRateLimits,
    credits: summarizeCredits(payload.credits),
    spendControlReached: payload?.spend_control?.reached === true,
    promo: isObject(payload.promo) ? payload.promo : null,
  };
}

function buildUsageError(status, payload, fallbackText) {
  const detail = isObject(payload?.detail) ? payload.detail : null;
  const detailCode = readStringField(detail, "code") || readStringField(payload, "code") || null;
  const detailMessage = readStringField(detail, "message") || readStringField(payload, "message") || null;

  if (status === 402 && detailCode === "deactivated_workspace") {
    return { status, detailCode, message: "workspace désactivé pour Codex" };
  }
  if (status === 401) {
    return { status, detailCode, message: "auth OpenAI expirée ou invalide" };
  }
  if (status === 403) {
    return { status, detailCode, message: "accès refusé par OpenAI" };
  }
  if (detailMessage) {
    return { status, detailCode, message: detailMessage };
  }
  return { status, detailCode, message: fallbackText || `HTTP ${status}` };
}

async function fetchUsageForCredential(auth, credential, { force = false } = {}) {
  const refreshedCredential = await ensureFreshCredential(auth, OPENAI_PROVIDER_ID, credential);
  const credentialId = getCredentialId(OPENAI_PROVIDER_ID, refreshedCredential) || getCredentialId(OPENAI_PROVIDER_ID, credential) || "unknown";
  const cached = usageCache.get(credentialId);
  if (!force && cached && cached.expiresAt > now()) {
    return cached.value;
  }

  const token = readStringField(refreshedCredential, "access");
  if (!token) {
    return {
      ok: false,
      error: { status: 0, detailCode: null, message: "credential OAuth sans access token" },
      fetchedAt: now(),
    };
  }

  const accountId = getCredentialAccountId(refreshedCredential);
  let response;
  try {
    response = await fetch(OPENAI_USAGE_URL, {
      headers: {
        Authorization: `Bearer ${token}`,
        ...(accountId ? { "chatgpt-account-id": accountId } : {}),
        "User-Agent": "CodexCLI/0.101.0",
        Accept: "application/json",
      },
    });
  } catch (error) {
    const value = {
      ok: false,
      error: { status: 0, detailCode: null, message: error instanceof Error ? error.message : String(error) },
      fetchedAt: now(),
    };
    usageCache.set(credentialId, { expiresAt: now() + OPENAI_USAGE_ERROR_CACHE_TTL_MS, value });
    return value;
  }

  const text = await response.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const value = {
      ok: false,
      error: buildUsageError(response.status, payload, text.slice(0, 160)),
      fetchedAt: now(),
    };
    usageCache.set(credentialId, { expiresAt: now() + OPENAI_USAGE_ERROR_CACHE_TTL_MS, value });
    return value;
  }

  const value = {
    ok: true,
    payload: normalizeUsagePayload(payload ?? {}),
    fetchedAt: now(),
  };
  usageCache.set(credentialId, { expiresAt: now() + OPENAI_USAGE_CACHE_TTL_MS, value });
  return value;
}

function getAccountLabel(account) {
  if (account.usage?.ok && account.usage.payload.emailMasked) {
    return account.usage.payload.emailMasked;
  }
  if (account.emailMasked) {
    return account.emailMasked;
  }
  return `credential ${String(account.credentialId).slice(-8)}`;
}

function getAccountState(account) {
  if (account.isSelected && account.selectionSource === "remembered") {
    return { label: "ACTIVE", tone: "success" };
  }
  if (account.isSelected) {
    return { label: "NEXT", tone: "accent" };
  }
  if (account.backoffMs > 0) {
    return { label: "BACKOFF", tone: "warning" };
  }
  if (!account.usage?.ok) {
    return { label: "ERROR", tone: "error" };
  }
  if (account.usage.payload.main?.limitReached) {
    return { label: "LIMIT", tone: "error" };
  }
  return { label: "READY", tone: "dim" };
}

function formatPercent(window) {
  if (!window) return "--";
  return `${Math.round(window.remainingPercent)}%`;
}

function buildBar(remainingPercent, width = 18) {
  const safe = Math.max(0, Math.min(100, Number(remainingPercent ?? 0)));
  const filled = Math.max(0, Math.min(width, Math.round((safe / 100) * width)));
  return `[${"█".repeat(filled)}${"░".repeat(Math.max(0, width - filled))}]`;
}

function toneForPercent(remainingPercent) {
  if (!Number.isFinite(remainingPercent)) return "dim";
  if (remainingPercent >= 50) return "success";
  if (remainingPercent >= 20) return "warning";
  return "error";
}

function formatCredits(credits) {
  if (!credits) return "aucun crédit";
  if (credits.unlimited) return "illimités";
  if (credits.balance != null) return `${credits.balance} crédits`;
  if (!credits.hasCredits) return "aucun crédit";
  return "crédits disponibles";
}

function formatApproxCredits(credits) {
  if (!credits) return null;
  const parts = [];
  if (credits.approxLocalMessages) parts.push(`~${credits.approxLocalMessages} messages locaux`);
  if (credits.approxCloudMessages) parts.push(`~${credits.approxCloudMessages} tâches cloud`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function wrapLine(theme, text, width, tone = "text") {
  return wrapTextWithAnsi(theme.fg(tone, text), Math.max(1, width));
}

function renderLimitLine(theme, label, window, width) {
  if (!window) {
    return wrapLine(theme, `${label}: indisponible`, width, "dim");
  }
  const tone = toneForPercent(window.remainingPercent);
  const line = `${label}: ${buildBar(window.remainingPercent)} ${Math.round(window.remainingPercent)}% restant · reset ${window.resetText} (${window.remainingText})`;
  return wrapTextWithAnsi(theme.fg(tone, line), Math.max(1, width));
}

export async function collectOpenAiCodexAccountsSnapshot(auth, sessionId, currentModel, { force = false } = {}) {
  const credentials = auth.getCredentialsForProvider(OPENAI_PROVIDER_ID);
  const selection = getProviderSessionSelection(auth, OPENAI_PROVIDER_ID, sessionId);
  const providerBackoffMs = getProviderBackoffRemainingMs(auth, OPENAI_PROVIDER_ID);

  const accounts = await Promise.all(credentials.map(async (credential, index) => {
    const freshCredential = await ensureFreshCredential(auth, OPENAI_PROVIDER_ID, credential);
    const credentialId = getCredentialId(OPENAI_PROVIDER_ID, freshCredential) || getCredentialId(OPENAI_PROVIDER_ID, credential) || `credential-${index + 1}`;
    const usage = await fetchUsageForCredential(auth, freshCredential, { force });
    const tokenExpiresAt = Number(freshCredential?.expires ?? 0) || null;

    return {
      index: index + 1,
      credentialId,
      emailMasked: getCredentialMaskedEmail(freshCredential) || null,
      accountIdTail: tail(getCredentialAccountId(freshCredential), 8) || null,
      tokenExpiresAt,
      tokenExpiresInMs: tokenExpiresAt ? Math.max(0, tokenExpiresAt - now()) : null,
      addedAt: Number(freshCredential?._gsdAddedAt ?? 0) || null,
      backoffMs: getCredentialBackoffRemaining(OPENAI_PROVIDER_ID, freshCredential),
      usage,
      isSelected: selection.selectedCredentialId === credentialId,
      selectionSource: selection.source,
    };
  }));

  return {
    provider: OPENAI_PROVIDER_ID,
    sessionId: sessionId ?? null,
    selection,
    providerBackoffMs,
    accounts,
    otherModelProvider: currentModel?.provider && currentModel.provider !== OPENAI_PROVIDER_ID ? currentModel.provider : null,
    currentModelId: currentModel?.provider === OPENAI_PROVIDER_ID ? currentModel.id : null,
    fetchedAt: now(),
  };
}

export async function formatOpenAiCodexAccountsText(auth, sessionId, currentModel, options = {}) {
  const snapshot = await collectOpenAiCodexAccountsSnapshot(auth, sessionId, currentModel, options);
  const selected = snapshot.accounts.find((account) => account.isSelected);

  const lines = [
    "OpenAI / Codex accounts",
    "",
    `${snapshot.accounts.length} credential${snapshot.accounts.length > 1 ? "s" : ""} · ${selected ? `${SESSION_SELECTION_TEXT[snapshot.selection.source]}: [${selected.index}] ${getAccountLabel(selected)}` : "aucun compte actif"}`,
  ];

  if (snapshot.currentModelId) {
    lines.push(`Modèle actuel: ${OPENAI_PROVIDER_ID}/${snapshot.currentModelId}`);
  } else if (snapshot.otherModelProvider) {
    lines.push(`Modèle actuel: ${snapshot.otherModelProvider}`);
  }

  if (snapshot.providerBackoffMs > 0) {
    lines.push(`Backoff provider: ${formatDuration(snapshot.providerBackoffMs)}`);
  }

  lines.push("");

  for (const account of snapshot.accounts) {
    const state = getAccountState(account);
    const main = account.usage?.ok ? account.usage.payload.main : null;
    const label = getAccountLabel(account);
    const activeSuffix = account.isSelected ? ` ← ${SESSION_SELECTION_TEXT[account.selectionSource]}` : "";
    lines.push(`[${account.index}] ${label} · ${state.label}${activeSuffix}`);

    if (!account.usage?.ok) {
      lines.push(`    usage: ${account.usage?.error?.message ?? "indisponible"}`);
    } else {
      const payload = account.usage.payload;
      const primary = main?.primary ? `${Math.round(main.primary.remainingPercent)}% restant (reset ${main.primary.resetText}, ${main.primary.remainingText})` : "indisponible";
      const secondary = main?.secondary ? `${Math.round(main.secondary.remainingPercent)}% restant (reset ${main.secondary.resetText}, ${main.secondary.remainingText})` : "indisponible";
      lines.push(`    5h: ${primary}`);
      lines.push(`    hebdo: ${secondary}`);
      if (payload.planType) lines.push(`    plan: ${payload.planType}`);
      if (payload.credits) lines.push(`    crédits: ${formatCredits(payload.credits)}`);
    }

    if (account.backoffMs > 0) {
      lines.push(`    backoff: ${formatDuration(account.backoffMs)}`);
    }
    if (account.tokenExpiresInMs != null) {
      lines.push(`    token OAuth: expire dans ${formatDuration(account.tokenExpiresInMs)}`);
    }
    lines.push("");
  }

  lines.push("Rappel: ↑/↓ pour naviguer et r pour rafraîchir dans l’UI interactive.");
  return lines.join("\n");
}

class OpenAiCodexAccountsDashboard {
  constructor(tui, theme, ctx, auth, done) {
    this.tui = tui;
    this.theme = theme;
    this.ctx = ctx;
    this.auth = auth;
    this.done = done;
    this.snapshot = null;
    this.selectedIndex = 0;
    this.loading = true;
    this.refreshing = false;
    this.error = null;
    this.closed = false;
    this.requestSerial = 0;
    this.cachedWidth = undefined;
    this.cachedLines = undefined;

    void this.refresh(false);
  }

  invalidate() {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }

  requestRender() {
    this.invalidate();
    this.tui.requestRender();
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.done(null);
  }

  dispose() {
    this.closed = true;
  }

  async refresh(force) {
    const serial = ++this.requestSerial;
    this.refreshing = true;
    this.loading = !this.snapshot;
    this.error = null;
    this.requestRender();

    try {
      const snapshot = await collectOpenAiCodexAccountsSnapshot(
        this.auth,
        this.ctx.sessionManager.getSessionId?.() ?? null,
        this.ctx.model,
        { force },
      );

      if (this.closed || serial !== this.requestSerial) return;
      this.snapshot = snapshot;
      this.selectedIndex = Math.max(0, Math.min(this.selectedIndex, Math.max(0, snapshot.accounts.length - 1)));
      const activeIndex = snapshot.accounts.findIndex((account) => account.isSelected);
      if (activeIndex >= 0 && this.selectedIndex === 0) {
        this.selectedIndex = activeIndex;
      }
    } catch (error) {
      if (this.closed || serial !== this.requestSerial) return;
      this.error = error instanceof Error ? error.message : String(error);
    } finally {
      if (this.closed || serial !== this.requestSerial) return;
      this.loading = false;
      this.refreshing = false;
      this.requestRender();
    }
  }

  getSelectedAccount() {
    if (!this.snapshot || this.snapshot.accounts.length === 0) return null;
    return this.snapshot.accounts[Math.max(0, Math.min(this.selectedIndex, this.snapshot.accounts.length - 1))] ?? null;
  }

  handleInput(data) {
    if (matchesKey(data, Key.escape) || matchesKey(data, "q")) {
      this.close();
      return;
    }

    if (!this.snapshot || this.snapshot.accounts.length === 0) {
      if (matchesKey(data, "r")) {
        void this.refresh(true);
      }
      return;
    }

    if (matchesKey(data, Key.up) && this.selectedIndex > 0) {
      this.selectedIndex -= 1;
      this.requestRender();
      return;
    }

    if (matchesKey(data, Key.down) && this.selectedIndex < this.snapshot.accounts.length - 1) {
      this.selectedIndex += 1;
      this.requestRender();
      return;
    }

    if (matchesKey(data, "r")) {
      void this.refresh(true);
    }
  }

  render(width) {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }

    const innerWidth = Math.max(60, width);
    const lines = [];
    const border = this.theme.fg("borderAccent", "─".repeat(innerWidth));
    const pushWrap = (text, tone = "text") => {
      lines.push(...wrapLine(this.theme, text, innerWidth, tone));
    };

    lines.push(border);
    lines.push(truncateToWidth(this.theme.fg("accent", this.theme.bold(" OpenAI / Codex accounts ")), innerWidth));

    if (this.loading && !this.snapshot) {
      lines.push("");
      pushWrap("Chargement des comptes et des limites OpenAI…", "dim");
      lines.push("");
      pushWrap("Esc pour fermer", "dim");
      lines.push(border);
      this.cachedWidth = width;
      this.cachedLines = lines;
      return lines;
    }

    if (this.error) {
      lines.push("");
      pushWrap(this.error, "error");
    }

    const snapshot = this.snapshot;
    if (!snapshot) {
      lines.push(border);
      this.cachedWidth = width;
      this.cachedLines = lines;
      return lines;
    }

    const selected = this.getSelectedAccount();
    const active = snapshot.accounts.find((account) => account.isSelected) ?? null;
    const selectionSummary = active
      ? `${SESSION_SELECTION_TEXT[snapshot.selection.source]}: #${active.index} ${getAccountLabel(active)}`
      : "aucun compte sélectionné";
    const modelSummary = snapshot.currentModelId
      ? `${OPENAI_PROVIDER_ID}/${snapshot.currentModelId}`
      : snapshot.otherModelProvider
        ? snapshot.otherModelProvider
        : "aucun";

    lines.push("");
    pushWrap(`${snapshot.accounts.length} comptes · ${selectionSummary}`, "text");
    pushWrap(`Modèle actuel: ${modelSummary}`, "dim");
    pushWrap(
      snapshot.providerBackoffMs > 0
        ? `Backoff provider: ${formatDuration(snapshot.providerBackoffMs)}`
        : "Provider prêt",
      snapshot.providerBackoffMs > 0 ? "warning" : "dim",
    );
    if (this.refreshing) {
      pushWrap("Rafraîchissement des limites…", "dim");
    }

    lines.push("");
    const accountColumnWidth = Math.max(16, innerWidth - 31);
    lines.push(this.theme.fg("dim", truncateToWidth(`  #   ${padRight("Compte", accountColumnWidth)} ${padRight("État", 8)} ${padRight("5h", 6)} ${padRight("Hebdo", 6)}`, innerWidth)));

    for (const account of snapshot.accounts) {
      const state = getAccountState(account);
      const row = `${account === selected ? "▶" : " "} [${account.index}] ${padRight(getAccountLabel(account), accountColumnWidth)} ${padRight(state.label, 8)} ${padRight(formatPercent(account.usage?.ok ? account.usage.payload.main?.primary : null), 6)} ${padRight(formatPercent(account.usage?.ok ? account.usage.payload.main?.secondary : null), 6)}`;
      const truncated = truncateToWidth(row, innerWidth);
      const toned = this.theme.fg(state.tone, truncated);
      lines.push(account === selected ? this.theme.bg("selectedBg", this.theme.fg("text", truncated)) : toned);
    }

    lines.push("");
    if (!selected) {
      pushWrap("Aucun compte openai-codex stocké.", "warning");
    } else {
      const state = getAccountState(selected);
      const payload = selected.usage?.ok ? selected.usage.payload : null;
      lines.push(truncateToWidth(this.theme.fg("accent", this.theme.bold(` Détails — compte #${selected.index} `)), innerWidth));
      pushWrap(`Compte: ${getAccountLabel(selected)} · état ${state.label.toLowerCase()}${selected.isSelected ? ` (${SESSION_SELECTION_TEXT[selected.selectionSource]})` : ""}`, state.tone === "dim" ? "text" : state.tone);

      const detailParts = [];
      if (payload?.planType) detailParts.push(`plan ${payload.planType}`);
      if (payload?.userIdTail) detailParts.push(`user …${payload.userIdTail}`);
      if (payload?.accountIdTail || selected.accountIdTail) detailParts.push(`workspace …${payload?.accountIdTail ?? selected.accountIdTail}`);
      detailParts.push(`credential …${String(selected.credentialId).slice(-8)}`);
      pushWrap(detailParts.join(" · "), "dim");

      if (selected.tokenExpiresInMs != null) {
        pushWrap(`Token OAuth: expire dans ${formatDuration(selected.tokenExpiresInMs)}`, selected.tokenExpiresInMs < 5 * 60_000 ? "warning" : "dim");
      }
      if (selected.backoffMs > 0) {
        pushWrap(`Backoff credential: ${formatDuration(selected.backoffMs)}`, "warning");
      }

      if (!selected.usage?.ok) {
        lines.push("");
        pushWrap(`Usage indisponible: ${selected.usage?.error?.message ?? "erreur inconnue"}`, "error");
      } else {
        lines.push("");
        lines.push(...renderLimitLine(this.theme, "Fenêtre 5h", payload.main?.primary, innerWidth));
        lines.push(...renderLimitLine(this.theme, "Fenêtre hebdo", payload.main?.secondary, innerWidth));

        if (payload.codeReviews?.primary || payload.codeReviews?.secondary) {
          lines.push("");
          pushWrap("Code reviews", "accent");
          if (payload.codeReviews.primary) {
            lines.push(...renderLimitLine(this.theme, "Reviews 5h", payload.codeReviews.primary, innerWidth));
          }
          if (payload.codeReviews.secondary) {
            lines.push(...renderLimitLine(this.theme, "Reviews hebdo", payload.codeReviews.secondary, innerWidth));
          }
        }

        if (payload.additionalRateLimits.length > 0) {
          lines.push("");
          pushWrap("Autres buckets", "accent");
          for (const extra of payload.additionalRateLimits) {
            pushWrap(`${extra.key}: ${extra.bucket?.primary ? `${Math.round(extra.bucket.primary.remainingPercent)}% 5h` : "--"}${extra.bucket?.secondary ? ` · ${Math.round(extra.bucket.secondary.remainingPercent)}% hebdo` : ""}`, "dim");
          }
        }

        if (payload.credits) {
          lines.push("");
          pushWrap(`Crédits: ${formatCredits(payload.credits)}`, payload.credits.unlimited || payload.credits.hasCredits ? "success" : "dim");
          const approx = formatApproxCredits(payload.credits);
          if (approx) {
            pushWrap(approx, "dim");
          }
        }

        if (payload.spendControlReached) {
          pushWrap("Spend control atteint.", "warning");
        }
      }
    }

    lines.push("");
    pushWrap("↑/↓ sélectionner · r rafraîchir · Esc fermer", "dim");
    lines.push(border);

    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }
}

export async function showOpenAiCodexAccountsDashboard(ctx, auth) {
  if (!ctx.hasUI) {
    return null;
  }

  return ctx.ui.custom((tui, theme, _kb, done) => new OpenAiCodexAccountsDashboard(tui, theme, ctx, auth, done));
}
