import { applyMultiOAuthPatches } from "./multi-oauth.js";
import { installSetupLlmIntercept, registerLlmAccountsCommand } from "./commands.js";

let patchError = null;

try {
  applyMultiOAuthPatches();
} catch (error) {
  patchError = error instanceof Error ? error : new Error(String(error));
}

export default function (pi) {
  registerLlmAccountsCommand(pi);
  installSetupLlmIntercept(pi);

  if (!patchError) {
    return;
  }

  pi.on("session_start", async (_event, ctx) => {
    const message = `llm-credential-failover failed to initialize: ${patchError.message}`;
    if (ctx.hasUI) {
      ctx.ui.notify(message, "warning");
    }
    process.stderr.write(`${message}\n`);
  });
}
