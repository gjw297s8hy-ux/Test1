import Anthropic from "@anthropic-ai/sdk";
import { betaZodOutputFormat } from "@anthropic-ai/sdk/helpers/beta/zod";
import type { z } from "zod";

const MODEL = process.env.ANTHROPIC_MODEL || "claude-opus-5-5";
// Si le modele decline une demande, l'API la rejoue sur un modele de repli.
const FALLBACK_BETA = "server-side-fallback-2026-07-01";

export class AgentError extends Error {}

export type Usage = { input: number; output: number };

let client: Anthropic | null = null;

export function agentConfigured(): boolean {
  return Boolean(process.env.ANTHROPIC_API_KEY);
}

function getClient(): Anthropic {
  if (!agentConfigured()) {
    throw new AgentError("L'agent IA n'est pas configuré : ajoutez ANTHROPIC_API_KEY dans les variables d'environnement.");
  }
  client ??= new Anthropic();
  return client;
}

function track(usage: Usage, u: { input_tokens: number; output_tokens: number }) {
  usage.input += u.input_tokens;
  usage.output += u.output_tokens;
}

function translate(err: unknown): never {
  if (err instanceof AgentError) throw err;
  if (err instanceof Anthropic.AuthenticationError) throw new AgentError("Clé API Anthropic refusée. Vérifiez ANTHROPIC_API_KEY.");
  if (err instanceof Anthropic.RateLimitError) throw new AgentError("Limite de débit de l'API atteinte. Réessayez dans une minute.");
  if (err instanceof Anthropic.APIConnectionError) throw new AgentError("Impossible de joindre l'API Anthropic (réseau).");
  if (err instanceof Anthropic.APIError && /credit balance/i.test(err.message)) {
    throw new AgentError("Crédit IA épuisé : rechargez le compte Anthropic (console, Billing) puis relancez.");
  }
  if (err instanceof Anthropic.APIError) throw new AgentError(`Erreur de l'API Anthropic (${err.status ?? "?"}) : ${err.message}`);
  throw err;
}

/** Recherche sur le web et renvoie les notes de l'agent, avec les URL sources. */
export async function research(opts: { system: string; prompt: string; maxSearches: number; usage: Usage }): Promise<string> {
  const anthropic = getClient();
  const messages: Anthropic.Beta.BetaMessageParam[] = [{ role: "user", content: opts.prompt }];
  try {
    // Une recherche longue peut s'interrompre (pause_turn) : on renvoie le tour pour que le serveur continue.
    for (let turn = 0; turn < 6; turn++) {
      const message = await anthropic.beta.messages
        .stream({
          model: MODEL,
          max_tokens: 32000,
          betas: [FALLBACK_BETA],
          fallbacks: "default",
          output_config: { effort: "medium" },
          system: opts.system,
          tools: [
            {
              type: "web_search_20260209",
              name: "web_search",
              max_uses: opts.maxSearches,
              user_location: { type: "approximate", country: "FR", timezone: "Europe/Paris" },
            },
          ],
          messages,
        })
        .finalMessage();
      track(opts.usage, message.usage);
      if (message.stop_reason === "refusal") throw new AgentError("Le modèle a décliné cette demande.");
      if (message.stop_reason === "pause_turn") {
        messages.push({ role: "assistant", content: message.content as Anthropic.Beta.BetaContentBlockParam[] });
        continue;
      }
      const text = message.content
        .filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text")
        .map((b) => b.text)
        .join("");
      if (!text.trim()) throw new AgentError("La recherche n'a renvoyé aucun résultat exploitable.");
      return text;
    }
    throw new AgentError("La recherche a été interrompue trop de fois.");
  } catch (err) {
    translate(err);
  }
}

/** Reponse structuree, validee par le schema. */
export async function structured<S extends z.ZodType>(opts: {
  schema: S;
  system: string;
  prompt: string;
  usage: Usage;
}): Promise<z.infer<S>> {
  const anthropic = getClient();
  try {
    const message = await anthropic.beta.messages.parse({
      model: MODEL,
      max_tokens: 16000,
      betas: [FALLBACK_BETA],
      fallbacks: "default",
      system: opts.system,
      output_config: { effort: "medium", format: betaZodOutputFormat(opts.schema) },
      messages: [{ role: "user", content: opts.prompt }],
    });
    track(opts.usage, message.usage);
    if (message.stop_reason === "refusal") throw new AgentError("Le modèle a décliné cette demande.");
    if (message.stop_reason === "max_tokens") throw new AgentError("Réponse du modèle tronquée. Réduisez le nombre d'éléments demandés.");
    if (message.parsed_output == null) throw new AgentError("Réponse du modèle illisible.");
    return message.parsed_output;
  } catch (err) {
    translate(err);
  }
}
