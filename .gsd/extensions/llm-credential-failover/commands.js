import { Input, Key, matchesKey, truncateToWidth, wrapTextWithAnsi } from "@gsd/pi-tui";
import {
  formatOpenAiCodexAccountsText,
  showOpenAiCodexAccountsDashboard,
} from "./openai-accounts.js";
import {
  applyMultiOAuthPatches,
  clearCredentialBackoff,
  formatCredentialInventory,
  getBackoffFilePath,
  getCredentialId,
  listConfiguredProviders,
  removeCredential,
} from "./multi-oauth.js";

const SETUP_NOTIFY_PATCH = Symbol.for("gsd.llmCredentialFailover.setupNotifyPatch.v1");
const SETUP_NOTIFY_MESSAGE = "Use /login to configure LLM authentication.";
const OAUTH_LABEL_FIELDS = ["email", "accountId", "account_id", "chatgpt_account_id", "userId", "user_id", "sub", "login"];

function tokenize(input) {
  return String(input ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function printInfo(ctx, text, level = "info") {
  if (ctx.hasUI) {
    ctx.ui.notify(text, level);
    return;
  }

  const stream = level === "error" ? process.stderr : process.stdout;
  stream.write(`${text}\n`);
}

function displayText(pi, ctx, text) {
  if (ctx.hasUI) {
    pi.sendMessage({
      customType: "llm-accounts-report",
      content: text,
      display: true,
    });
    return;
  }

  process.stdout.write(`${text}\n`);
}

function usage() {
  return [
    "Usage: /llm-accounts [setup|wizard|list [provider]|login [provider]|remove <provider> <index|id>|clear-backoff <provider> [index|id|all]|help]",
    "",
    "Examples:",
    "  /llm-accounts setup",
    "  /llm-accounts login openai-codex",
    "  /llm-accounts list openai-codex",
    "  /llm-accounts remove openai-codex 2",
    "  /llm-accounts clear-backoff openai-codex all",
    "",
    "Notes:",
    "  - /gsd setup llm opens the same assistant.",
    "  - /llm-accounts list ouvre un tableau OpenAI/Codex avec compte actif + limites 5h / hebdo quand openai-codex est configuré.",
    "  - Repeat login on the same provider to add another OAuth account.",
    `  - Persistent backoff file: ${getBackoffFilePath()}`,
  ].join("\n");
}

function codexHowToText(auth) {
  const count = auth.getCredentialsForProvider("openai-codex").length;
  return [
    "Ajouter plusieurs OAuth Codex (OpenAI) — mode d'emploi",
    "",
    `État actuel: ${count} credential${count > 1 ? "s" : ""} stocké${count > 1 ? "s" : ""} pour openai-codex.`,
    "",
    "La façon la plus simple:",
    "1. Lance /gsd setup llm",
    "2. Choisis \"Ajouter un compte OAuth\"",
    "3. Choisis \"openai-codex\"",
    "4. Termine le login dans le navigateur ouvert automatiquement",
    "5. Pour un deuxième compte, utilise de préférence un autre profil navigateur ou une fenêtre privée",
    "6. Recommence pour chaque compte ChatGPT/Codex supplémentaire",
    "",
    "Alternative directe:",
    "- /llm-accounts login openai-codex",
    "- répéter la commande autant de fois que nécessaire",
    "",
    "Important:",
    "- si la page du navigateur affiche \"State mismatch\", tu as généralement terminé un ancien onglet OAuth; ferme-le et recommence avec l'URL la plus récente",
    "- si le login finit mais que l'inventaire reste à 1 credential, tu as très probablement reconnecté le même compte Codex/OpenAI",
    "- /llm-accounts list openai-codex permet de vérifier immédiatement le nombre de comptes stockés",
    "",
    "Une fois plusieurs comptes ajoutés:",
    "- si un compte prend une limite d'usage / quota / rate limit reconnue par GSD, la rotation se fait vers le credential suivant du même provider",
    "- le backoff est persistant entre redémarrages",
    "",
    "Gestion:",
    "- /logout supprime tout le provider openai-codex",
    "- pour supprimer un seul compte: /llm-accounts remove openai-codex <index>",
  ].join("\n");
}

function nonInteractiveSetupText(auth) {
  return [
    "LLM setup",
    "",
    usage(),
    "",
    codexHowToText(auth),
    "",
    formatCredentialInventory(auth),
  ].join("\n");
}

function sortOAuthProviders(auth, preferredProvider) {
  const providers = [...auth.getOAuthProviders()];

  return providers.sort((left, right) => {
    const leftRank = left.id === preferredProvider ? 0 : left.id === "openai-codex" ? 1 : 2;
    const rightRank = right.id === preferredProvider ? 0 : right.id === "openai-codex" ? 1 : 2;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.name.localeCompare(right.name);
  });
}

function readStringField(value, field) {
  if (!value || typeof value !== "object") return undefined;
  const result = value[field];
  return typeof result === "string" && result.trim() ? result.trim() : undefined;
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
  const visible = local.length <= 2 ? local[0] ?? "*" : `${local[0]}${"*".repeat(Math.max(1, local.length - 2))}${local.slice(-1)}`;
  return `${visible}@${domain}`;
}

function getCodexMaskedEmail(credential) {
  const payload = decodeJwtPayload(readStringField(credential, "access"));
  const profile = payload && typeof payload === "object" ? payload["https://api.openai.com/profile"] : null;
  const email = profile && typeof profile === "object" ? profile.email : undefined;
  return typeof email === "string" && email ? maskEmail(email) : undefined;
}

function describeCredential(provider, credential) {
  if (!credential) return "credential";
  if (credential.type === "api_key") {
    return `API key (${provider})`;
  }

  if (provider === "openai-codex") {
    const email = getCodexMaskedEmail(credential);
    if (email) return `OAuth email=${email}`;
  }

  for (const field of OAUTH_LABEL_FIELDS) {
    const value = readStringField(credential, field);
    if (!value) continue;
    return field === "email" ? `OAuth email=${maskEmail(value)}` : `OAuth ${field}=${value}`;
  }

  const credentialId = getCredentialId(provider, credential);
  return credentialId ? `OAuth id=${String(credentialId).slice(-10)}` : "OAuth credential";
}

function snapshotProviderCredentials(auth, provider) {
  return auth.getCredentialsForProvider(provider).map((credential) => ({
    id: getCredentialId(provider, credential),
    description: describeCredential(provider, credential),
  }));
}

function summarizeLoginOutcome(providerId, providerName, before, after) {
  const beforeIds = new Set(before.map((entry) => entry.id).filter(Boolean));
  const afterIds = new Set(after.map((entry) => entry.id).filter(Boolean));
  const added = after.filter((entry) => entry.id && !beforeIds.has(entry.id));
  const removed = before.filter((entry) => entry.id && !afterIds.has(entry.id));

  if (added.length > 0 && removed.length === 0) {
    const addedLabel = added[0]?.description ?? "new credential";
    return {
      level: "success",
      text: `${providerName}: added ${addedLabel}. ${after.length} credential${after.length > 1 ? "s" : ""} now available for ${providerId}.`,
    };
  }

  if (added.length === 0 && removed.length === 0) {
    const existingLabel = after[0]?.description ?? "existing credential";
    const extraHint = providerId === "openai-codex"
      ? " If you intended to add another Codex account, complete the OAuth in a different browser profile or private window so OpenAI authenticates a different account."
      : "";
    return {
      level: "warning",
      text: `${providerName}: login completed, but it matched the already stored ${existingLabel}. Inventory stayed at ${after.length} credential${after.length > 1 ? "s" : ""}.${extraHint}`,
    };
  }

  if (added.length > 0 && removed.length > 0) {
    return {
      level: "warning",
      text: `${providerName}: login changed stored credentials for ${providerId}, but the total stayed at ${after.length}. Inventory: ${after.map((entry) => entry.description).join(", ")}.`,
    };
  }

  return {
    level: "success",
    text: `${providerName}: login stored successfully. ${after.length} credential${after.length > 1 ? "s" : ""} now available for ${providerId}.`,
  };
}

class OAuthLoginDialog {
  constructor(tui, theme, providerName, done) {
    this.tui = tui;
    this.theme = theme;
    this.providerName = providerName;
    this.done = done;
    this.input = new Input();
    this.abortController = new AbortController();
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
    this.authUrl = null;
    this.instructions = null;
    this.browserStatus = null;
    this.notes = [];
    this.promptMessage = null;
    this.placeholder = null;
    this.inputVisible = false;
    this.inputResolver = null;
    this.inputRejecter = null;
    this.finished = false;
    this.focused = false;

    this.input.onSubmit = () => {
      if (!this.inputResolver) return;
      const resolve = this.inputResolver;
      this.inputResolver = null;
      this.inputRejecter = null;
      resolve(this.input.getValue());
    };

    this.input.onEscape = () => {
      this.cancel();
    };
  }

  get signal() {
    return this.abortController.signal;
  }

  invalidate() {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
    if (typeof this.input.invalidate === "function") {
      this.input.invalidate();
    }
  }

  dispose() {
    this.rejectPending("Login dialog disposed");
    if (!this.abortController.signal.aborted) {
      this.abortController.abort();
    }
    this.finished = true;
  }

  requestRender() {
    this.invalidate();
    this.tui.requestRender();
  }

  finish(value) {
    if (this.finished) return;
    this.finished = true;
    this.done(value);
  }

  cancel() {
    this.rejectPending("Login cancelled");
    if (!this.abortController.signal.aborted) {
      this.abortController.abort();
    }
    this.finish({ ok: false, error: "Login cancelled" });
  }

  rejectPending(reason) {
    if (!this.inputRejecter) return;
    const reject = this.inputRejecter;
    this.inputResolver = null;
    this.inputRejecter = null;
    reject(new Error(reason));
  }

  showAuth(url, instructions) {
    this.authUrl = url;
    this.instructions = instructions ?? null;
    this.browserStatus = "Opening browser...";
    this.notes = [];
    this.requestRender();
  }

  setBrowserStatus(opened) {
    this.browserStatus = opened
      ? "Browser opened with the full OAuth URL."
      : "Could not open the browser automatically. Open the URL below manually.";
    this.requestRender();
  }

  setNote(message) {
    this.notes = message ? [message] : [];
    this.requestRender();
  }

  showProgress(message) {
    this.notes = [...this.notes, message].slice(-4);
    this.requestRender();
  }

  showManualInput(prompt) {
    this.rejectPending("Superseded by new input prompt");
    this.inputVisible = true;
    this.promptMessage = prompt;
    this.placeholder = "Paste the full redirect URL or code";
    this.input.setValue("");
    this.requestRender();

    return new Promise((resolve, reject) => {
      this.inputResolver = resolve;
      this.inputRejecter = reject;
    });
  }

  showPrompt(message, placeholder) {
    this.rejectPending("Superseded by new input prompt");
    this.inputVisible = true;
    this.promptMessage = message;
    this.placeholder = placeholder ?? null;
    this.input.setValue("");
    this.requestRender();

    return new Promise((resolve, reject) => {
      this.inputResolver = resolve;
      this.inputRejecter = reject;
    });
  }

  wrapLine(text, width, color = "text") {
    return wrapTextWithAnsi(this.theme.fg(color, text), Math.max(1, width));
  }

  render(width) {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }

    const innerWidth = Math.max(20, width);
    const lines = [];
    const pushWrapped = (text, color = "text") => {
      lines.push(...this.wrapLine(text, innerWidth, color));
    };

    lines.push(this.theme.fg("accent", "─".repeat(innerWidth)));
    lines.push(truncateToWidth(this.theme.fg("accent", this.theme.bold(` OAuth login — ${this.providerName}`)), innerWidth));
    lines.push("");

    if (this.browserStatus) {
      pushWrapped(this.browserStatus, "dim");
      lines.push("");
    }

    if (this.authUrl) {
      pushWrapped(this.authUrl, "accent");
      lines.push("");
    }

    if (this.instructions) {
      pushWrapped(this.instructions, "warning");
      lines.push("");
    }

    for (const note of this.notes) {
      pushWrapped(note, "dim");
      lines.push("");
    }

    if (this.inputVisible) {
      pushWrapped(this.promptMessage ?? "Paste the redirect URL or authorization code.", "text");
      if (this.placeholder) {
        pushWrapped(`e.g. ${this.placeholder}`, "dim");
      }
      lines.push("");
      for (const line of this.input.render(Math.max(1, innerWidth - 2))) {
        lines.push(truncateToWidth(` ${line}`, innerWidth));
      }
      lines.push("");
    }

    pushWrapped("Enter to submit · Esc to cancel", "dim");
    lines.push(this.theme.fg("accent", "─".repeat(innerWidth)));

    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }

  handleInput(data) {
    if (this.finished) return;
    if (matchesKey(data, Key.escape)) {
      this.cancel();
      return;
    }
    if (!this.inputVisible) return;
    this.input.handleInput(data);
    this.requestRender();
  }
}

async function selectProviderFromList(ctx, items, prompt) {
  if (!ctx.hasUI) return null;
  const choice = await ctx.ui.select(prompt, items.map((item) => item.label));
  if (!choice || typeof choice !== "string") return null;
  const found = items.find((item) => item.label === choice);
  return found?.id ?? null;
}

async function selectConfiguredProvider(ctx, auth, prompt) {
  const providers = listConfiguredProviders(auth);
  if (providers.length === 0) {
    printInfo(ctx, "No stored credentials found.", "warning");
    return null;
  }

  return selectProviderFromList(
    ctx,
    providers.map((provider) => ({
      id: provider,
      label: `${provider} (${auth.getCredentialsForProvider(provider).length})`,
    })),
    prompt,
  );
}

async function selectCredential(ctx, auth, provider, prompt) {
  const credentials = auth.getCredentialsForProvider(provider);
  if (credentials.length === 0) {
    printInfo(ctx, `No credentials stored for ${provider}.`, "warning");
    return null;
  }

  if (!ctx.hasUI) {
    printInfo(ctx, usage(), "error");
    return null;
  }

  const choice = await ctx.ui.select(
    prompt,
    credentials.map((credential, index) => {
      const credentialId = getCredentialId(provider, credential);
      const shortId = credentialId ? String(credentialId).slice(-10) : "unknown";
      const kind = credential.type === "oauth" ? "OAuth" : "API key";
      return `[${index + 1}] ${kind} (${shortId})`;
    }),
  );

  if (!choice || typeof choice !== "string") return null;
  const match = choice.match(/^\[(\d+)\]/);
  return match?.[1] ?? null;
}

async function bestEffortOpenUrl(pi, url) {
  try {
    if (process.platform === "win32") {
      const escaped = String(url).replace(/'/g, "''");
      await pi.exec("powershell", ["-NoProfile", "-Command", `Start-Process '${escaped}'`]);
      return true;
    }
    if (process.platform === "darwin") {
      await pi.exec("open", [url]);
      return true;
    }
    await pi.exec("xdg-open", [url]);
    return true;
  } catch {
    return false;
  }
}

async function runInteractiveOAuthLogin(pi, ctx, auth, providerId, providerInfo) {
  const usesCallbackServer = providerInfo?.usesCallbackServer ?? false;

  return ctx.ui.custom((tui, theme, _kb, done) => {
    const dialog = new OAuthLoginDialog(tui, theme, providerInfo.name, done);

    void (async () => {
      try {
        await auth.login(providerId, {
          onAuth: (info) => {
            dialog.showAuth(info.url, info.instructions);
            if (usesCallbackServer) {
              dialog.setNote(
                "If the browser page says 'State mismatch', you almost certainly completed an older OAuth tab. Close old tabs and use only the newest login attempt.",
              );
            }
            void bestEffortOpenUrl(pi, info.url)
              .then((opened) => dialog.setBrowserStatus(opened))
              .catch(() => dialog.setBrowserStatus(false));
          },
          onPrompt: async (prompt) => dialog.showPrompt(prompt.message, prompt.placeholder),
          onProgress: (message) => dialog.showProgress(message),
          onManualCodeInput: usesCallbackServer
            ? () => dialog.showManualInput("Paste the final redirect URL below, or finish login in the browser.")
            : undefined,
          signal: dialog.signal,
        });
        dialog.finish({ ok: true });
      } catch (error) {
        dialog.finish({
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        });
      } finally {
        dialog.dispose();
      }
    })();

    return dialog;
  });
}

export async function loginOAuthProvider(pi, ctx, providerId) {
  applyMultiOAuthPatches();

  const auth = ctx.modelRegistry.authStorage;
  const providerInfo = auth.getOAuthProviders().find((provider) => provider.id === providerId);
  if (!providerInfo) {
    throw new Error(`Provider OAuth inconnu: ${providerId}`);
  }

  const before = snapshotProviderCredentials(auth, providerId);
  let authUrl = null;

  if (ctx.hasUI) {
    const result = await runInteractiveOAuthLogin(pi, ctx, auth, providerId, providerInfo);
    if (!result?.ok) {
      const errorMessage = result?.error ?? "Login cancelled";
      if (errorMessage === "Login cancelled") {
        printInfo(ctx, `${providerInfo.name}: login cancelled.`, "info");
        return {
          providerId,
          providerName: providerInfo.name,
          authUrl,
          credentialCount: before.length,
          cancelled: true,
        };
      }

      if (errorMessage === "State mismatch") {
        throw new Error(
          `${providerInfo.name}: OAuth state mismatch. This usually means an older auth tab was completed, or Windows opened a malformed URL. Use only the newest login attempt; for multiple Codex accounts, prefer a separate browser profile/private window.`,
        );
      }

      throw new Error(errorMessage);
    }
  } else {
    await auth.login(providerId, {
      onAuth: (info) => {
        authUrl = info.url;
        void (async () => {
          const opened = await bestEffortOpenUrl(pi, info.url);
          const lines = [
            `${providerInfo.name}: ${opened ? "browser opened" : "open this URL in your browser"}`,
            info.url,
            ...(info.instructions ? [info.instructions] : []),
          ];
          printInfo(ctx, lines.join("\n"), "info");
        })();
      },
      onPrompt: async (prompt) => {
        if (!ctx.hasUI) {
          throw new Error(
            `${providerInfo.name}: interactive input required. Re-run in interactive mode and paste the authorization code or redirect URL when prompted.`,
          );
        }

        const value = await ctx.ui.input(
          prompt.message,
          prompt.placeholder ?? "Paste the authorization code or full redirect URL",
        );
        if (value == null) {
          throw new Error("Login cancelled");
        }
        return value;
      },
      onProgress: (message) => {
        printInfo(ctx, `${providerInfo.name}: ${message}`, "info");
      },
    });
  }

  ctx.modelRegistry.refresh();
  const after = snapshotProviderCredentials(auth, providerId);
  const outcome = summarizeLoginOutcome(providerId, providerInfo.name, before, after);
  printInfo(ctx, outcome.text, outcome.level);

  return {
    providerId,
    providerName: providerInfo.name,
    authUrl,
    credentialCount: after.length,
    cancelled: false,
    outcome,
  };
}

async function chooseOAuthProviderForLogin(ctx, auth) {
  const preferred = ctx.model?.provider;
  const providers = sortOAuthProviders(auth, preferred).map((provider) => ({
    id: provider.id,
    label: `${provider.name}${provider.id === preferred ? " (current provider)" : provider.id === "openai-codex" ? " (recommended)" : ""}`,
  }));
  return selectProviderFromList(ctx, providers, "Add an OAuth account for which provider?");
}

async function handleList(pi, ctx, auth, provider) {
  const configuredProviders = listConfiguredProviders(auth);
  const hasOpenAiCodex = auth.getCredentialsForProvider("openai-codex").length > 0;
  const shouldShowOpenAiCodex = provider === "openai-codex"
    || (!provider && hasOpenAiCodex && (configuredProviders.length === 1 || ctx.model?.provider === "openai-codex"));

  if (shouldShowOpenAiCodex) {
    if (ctx.hasUI) {
      await showOpenAiCodexAccountsDashboard(ctx, auth);
      return;
    }

    displayText(
      pi,
      ctx,
      await formatOpenAiCodexAccountsText(
        auth,
        ctx.sessionManager.getSessionId?.() ?? null,
        ctx.model,
      ),
    );
    return;
  }

  displayText(pi, ctx, formatCredentialInventory(auth, provider));
}

async function handleRemove(ctx, auth, providerArg, selectorArg) {
  let provider = providerArg ?? null;
  if (!provider) {
    provider = await selectConfiguredProvider(ctx, auth, "Remove a credential from which provider?");
    if (!provider) return;
  }

  let selector = selectorArg ?? null;
  if (!selector) {
    selector = await selectCredential(ctx, auth, provider, `Remove which credential from ${provider}?`);
    if (!selector) return;
  }

  const result = removeCredential(auth, provider, selector);
  ctx.modelRegistry.refresh();
  const removedId = getCredentialId(provider, result.removed);
  printInfo(
    ctx,
    `Removed ${provider} credential ${removedId ? String(removedId).slice(-10) : selector}. ${result.remainingCount} remaining.`,
    "success",
  );
}

async function handleClearBackoff(ctx, auth, providerArg, selectorArg) {
  let provider = providerArg ?? null;
  if (!provider) {
    provider = await selectConfiguredProvider(ctx, auth, "Clear backoff for which provider?");
    if (!provider) return;
  }

  let selector = selectorArg ?? null;
  if (!selector && ctx.hasUI) {
    const credentials = auth.getCredentialsForProvider(provider);
    if (credentials.length > 1) {
      const choice = await ctx.ui.select(`Clear backoff for ${provider}:`, [
        "All credentials for this provider",
        "One specific credential",
      ]);
      if (!choice || typeof choice !== "string") return;
      if (choice === "One specific credential") {
        selector = await selectCredential(ctx, auth, provider, `Clear backoff for which credential in ${provider}?`);
        if (!selector) return;
      }
    }
  }

  selector = selector ?? "all";
  const result = clearCredentialBackoff(auth, provider, selector);
  if (result.clearedProvider) {
    printInfo(ctx, `Cleared provider backoff for ${provider}.`, "success");
  } else {
    printInfo(
      ctx,
      `Cleared ${result.clearedCount} credential backoff entr${result.clearedCount === 1 ? "y" : "ies"} for ${provider}.`,
      "success",
    );
  }
}

export async function openLlmSetupWizard(pi, ctx, options = {}) {
  applyMultiOAuthPatches();

  const auth = ctx.modelRegistry.authStorage;
  if (!ctx.hasUI) {
    displayText(pi, ctx, nonInteractiveSetupText(auth));
    return;
  }

  while (true) {
    const action = await ctx.ui.select("LLM setup", [
      "Add an OAuth account (Recommended)",
      "Show stored accounts & backoffs",
      "Remove one account / key",
      "Clear a backoff",
      "How to add multiple Codex OAuth accounts",
      "Close",
    ]);

    if (!action || typeof action !== "string" || action === "Close") {
      return;
    }

    if (action === "Add an OAuth account (Recommended)") {
      const providerId = await chooseOAuthProviderForLogin(ctx, auth);
      if (!providerId) continue;
      const result = await loginOAuthProvider(pi, ctx, providerId);
      if (result?.cancelled) {
        continue;
      }

      const showInventory = await ctx.ui.confirm(
        "Show inventory?",
        `Display stored credentials for ${providerId}?`,
      );
      if (showInventory) {
        await handleList(pi, ctx, auth, providerId);
      }
      continue;
    }

    if (action === "Show stored accounts & backoffs") {
      await handleList(pi, ctx, auth);
      continue;
    }

    if (action === "Remove one account / key") {
      await handleRemove(ctx, auth, null, null);
      continue;
    }

    if (action === "Clear a backoff") {
      await handleClearBackoff(ctx, auth, null, "all");
      continue;
    }

    if (action === "How to add multiple Codex OAuth accounts") {
      displayText(pi, ctx, codexHowToText(auth));
      continue;
    }
  }
}

export function installSetupLlmIntercept(pi) {
  pi.on("session_start", async (_event, ctx) => {
    const ui = ctx.ui;
    if (ui[SETUP_NOTIFY_PATCH]) {
      return;
    }

    const originalNotify = typeof ui.notify === "function" ? ui.notify.bind(ui) : null;
    if (!originalNotify) {
      return;
    }

    let running = false;

    ui.notify = (message, level) => {
      if (message !== SETUP_NOTIFY_MESSAGE) {
        return originalNotify(message, level);
      }

      if (running) {
        return;
      }

      running = true;
      void (async () => {
        try {
          await openLlmSetupWizard(pi, ctx, { source: "gsd-setup-llm" });
        } catch (error) {
          originalNotify(
            `LLM setup assistant failed: ${error instanceof Error ? error.message : String(error)}`,
            "warning",
          );
        } finally {
          running = false;
        }
      })();
    };

    Object.defineProperty(ui, SETUP_NOTIFY_PATCH, {
      value: true,
      enumerable: false,
      configurable: false,
      writable: false,
    });
  });
}

export function registerLlmAccountsCommand(pi) {
  applyMultiOAuthPatches();

  pi.registerCommand("llm-accounts", {
    description: "Inspect, add, rotate, and clean up LLM credentials / OAuth accounts",
    getArgumentCompletions: (prefix) => {
      const parts = tokenize(prefix);
      const subcommands = ["setup", "wizard", "list", "login", "remove", "clear-backoff", "help"];

      if (parts.length <= 1) {
        const first = parts[0] ?? "";
        return subcommands
          .filter((item) => item.startsWith(first))
          .map((item) => ({ value: item, label: item }));
      }

      return [];
    },
    handler: async (args, ctx) => {
      applyMultiOAuthPatches();

      const auth = ctx.modelRegistry.authStorage;
      const parts = tokenize(args);
      const subcommand = parts[0] ?? (ctx.hasUI ? "setup" : "list");

      if (subcommand === "help") {
        displayText(pi, ctx, usage());
        return;
      }

      if (subcommand === "setup" || subcommand === "wizard") {
        await openLlmSetupWizard(pi, ctx, { source: "llm-accounts" });
        return;
      }

      if (subcommand === "list") {
        await handleList(pi, ctx, auth, parts[1]);
        return;
      }

      if (subcommand === "login") {
        let providerId = parts[1] ?? null;
        if (!providerId) {
          providerId = await chooseOAuthProviderForLogin(ctx, auth);
          if (!providerId) return;
        }
        await loginOAuthProvider(pi, ctx, providerId);
        return;
      }

      if (subcommand === "remove") {
        await handleRemove(ctx, auth, parts[1], parts[2]);
        return;
      }

      if (subcommand === "clear-backoff") {
        await handleClearBackoff(ctx, auth, parts[1], parts[2] ?? "all");
        return;
      }

      displayText(pi, ctx, usage());
    },
  });
}
