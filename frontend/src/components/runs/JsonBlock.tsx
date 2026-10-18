import { useState } from "react";

const COPY_FEEDBACK_MS = 1500;
const JSON_INDENT = 2;

export function JsonBlock({ value, label = "JSON" }: { value: unknown; label?: string }) {
  const [isCopied, setIsCopied] = useState(false);
  const formatted = JSON.stringify(value, null, JSON_INDENT);

  async function copy() {
    await navigator.clipboard.writeText(formatted);
    setIsCopied(true);
    window.setTimeout(() => setIsCopied(false), COPY_FEEDBACK_MS);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={copy}
        aria-label={`Copy ${label}`}
        className="absolute top-2 right-2 rounded bg-panel px-2 py-1 text-xs text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
      >
        {isCopied ? "Copied" : "Copy"}
      </button>
      <pre className="max-h-[32rem] overflow-auto rounded bg-sunken p-4 pr-16 font-mono text-xs leading-[1.5] whitespace-pre-wrap break-words text-ink">
        {formatted}
      </pre>
    </div>
  );
}
