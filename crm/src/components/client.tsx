"use client";

import { createContext, startTransition, useActionState, useContext, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { useRouter } from "next/navigation";
import type { FormState } from "@/app/actions";

const PendingContext = createContext(false);

export function Submit({
  children,
  className = "btn",
  pendingText,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { pendingText?: string }) {
  const status = useFormStatus();
  const pending = useContext(PendingContext) || status.pending;
  return (
    <button type="submit" className={className} {...rest} disabled={pending || rest.disabled}>
      {pending ? (pendingText ?? "Un instant…") : children}
    </button>
  );
}

/** Formulaire dont l'action peut renvoyer une erreur a afficher sur place. */
export function ActionForm({
  action,
  children,
  className,
}: {
  action: (state: FormState, fd: FormData) => Promise<FormState>;
  children: React.ReactNode;
  className?: string;
}) {
  const [state, formAction, pending] = useActionState(action, undefined);
  return (
    <form
      action={formAction}
      className={className}
      aria-busy={pending}
      // Soumission a la main : React viderait sinon les champs apres une erreur.
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        startTransition(() => formAction(data));
      }}
    >
      {state?.error && (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {state.error}
        </p>
      )}
      <PendingContext value={pending}>{children}</PendingContext>
    </form>
  );
}

/** Rafraichit la page tant qu'un travail de l'agent est en cours. */
export function AutoRefresh({ active, everyMs = 4000 }: { active: boolean; everyMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => router.refresh(), everyMs);
    return () => clearInterval(id);
  }, [active, everyMs, router]);
  return null;
}

export function CopyButton({ text, label = "Copier" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="btn-ghost"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? "Copié" : label}
    </button>
  );
}

/** Demande confirmation avant une action irreversible. */
export function ConfirmSubmit({ children, message, className = "btn-danger" }: { children: React.ReactNode; message: string; className?: string }) {
  return (
    <button
      type="submit"
      className={className}
      onClick={(e) => {
        if (!confirm(message)) e.preventDefault();
      }}
    >
      {children}
    </button>
  );
}

/** Coche ou decoche toutes les cases d'un meme nom dans le formulaire. */
export function CheckAll({ name }: { name: string }) {
  return (
    <input
      type="checkbox"
      aria-label="Tout sélectionner"
      onChange={(e) => {
        const form = e.currentTarget.form;
        if (!form) return;
        form.querySelectorAll<HTMLInputElement>(`input[name="${name}"]`).forEach((box) => (box.checked = e.currentTarget.checked));
      }}
    />
  );
}
