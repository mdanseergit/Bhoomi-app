"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { Farm } from "@/lib/types";

interface Source {
  domain: string | null;
  provider: string | null;
  status: string | null;
}

interface ToolCall {
  tool: string;
  status: string;
  summary: string;
  duration_ms: number;
  reason?: string | null;
}

interface Phase {
  step_number: number;
  phase: string;
  status: string;
  summary: string | null;
  duration_ms: number | null;
}

interface Budget {
  steps_used: number;
  max_steps: number;
  tool_calls_used: number;
  max_tool_calls: number;
  elapsed_seconds: number;
  limit_reason: string | null;
}

interface ChatReply {
  task_id: string;
  session_id: string;
  status: string;
  answer: string;
  confidence: number;
  model_used: string | null;
  provider_used: string | null;
  fallback_used: boolean;
  requires_approval: boolean;
  evidence: Array<Record<string, unknown>>;
  sources: Source[];
  missing_data: string[];
  tool_calls: ToolCall[];
  phases: Phase[];
  budget: Budget;
  warning: string | null;
}

interface Turn {
  id: string;
  question: string;
  reply: ChatReply | null;
  error: string | null;
}

const SUGGESTIONS = [
  "How is my farm doing?",
  "Will it rain in the next 3 days?",
  "Check my soil health",
  "What advisories apply to my crop?",
];

/** Confidence is a model judgement, so it is shown as a bounded range rather
 *  than an implied measurement. */
function confidenceLabel(confidence: number): { label: string; tone: string } {
  if (confidence >= 0.75) return { label: "high", tone: "text-success" };
  if (confidence >= 0.45) return { label: "moderate", tone: "text-warning" };
  return { label: "low", tone: "text-muted" };
}

function availabilityTone(status: string | null): string {
  if (status === "available") return "text-success";
  if (status === "unavailable" || status === "error") return "text-muted";
  return "text-text-secondary";
}

export function AgentChatBar() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [farmId, setFarmId] = useState<string>("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [expandedTurn, setExpandedTurn] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // The widget lives on public pages too, so it only renders for a signed-in
  // user; anonymous visitors get no agent affordance at all. The API client
  // attaches and refreshes the access token itself.
  useEffect(() => {
    if (!open || !user) return;
    let cancelled = false;
    api
      .get<Farm[]>("/api/v1/farms")
      .then((list) => {
        if (cancelled) return;
        setFarms(list);
        setFarmId((current) => current || list[0]?.id || "");
      })
      .catch(() => {
        if (!cancelled) setFarms([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, user]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, sending]);

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || sending) return;
      const turnId = `${Date.now()}-${question.slice(0, 12)}`;
      setTurns((prev) => [...prev, { id: turnId, question, reply: null, error: null }]);
      setInput("");
      setSending(true);
      try {
        const reply = await api.post<ChatReply>("/api/v1/agent/chat", {
          message: question,
          farm_id: farmId || null,
          session_id: sessionId,
        });
        setSessionId(reply.session_id);
        setTurns((prev) =>
          prev.map((turn) => (turn.id === turnId ? { ...turn, reply } : turn))
        );
      } catch (error) {
        // A failed turn keeps the question visible with the reason, rather than
        // pretending the assistant produced an answer with zero confidence.
        setTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? {
                  ...turn,
                  error:
                    error instanceof Error
                      ? error.message
                      : "The assistant could not answer right now.",
                }
              : turn
          )
        );
      } finally {
        setSending(false);
      }
    },
    [farmId, sending, sessionId]
  );

  if (!user) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Close BHOOMI assistant" : "Open BHOOMI assistant"}
        className="fixed bottom-6 right-6 z-[60] flex h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-white shadow-card-hover transition hover:bg-primary-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3c4.4 0 8 2.9 8 6.5 0 3.6-3.6 6.5-8 6.5a9.6 9.6 0 01-2.6-.35L5 17.5l.9-2.6A6.6 6.6 0 014 9.5C4 5.9 7.6 3 12 3z" />
            <path d="M9 9.5h.01M12 9.5h.01M15 9.5h.01" />
          </svg>
        )}
      </button>

      {open && (
        <section
          aria-label="BHOOMI assistant"
          className="fixed bottom-24 right-6 z-[60] flex h-[min(34rem,calc(100vh-8rem))] w-[min(24rem,calc(100vw-3rem))] flex-col overflow-hidden rounded-card border border-border bg-surface shadow-card-hover"
        >
          <header className="flex items-center justify-between gap-2 border-b border-border bg-primary-700 px-4 py-3 text-white">
            <div>
              <p className="text-sm font-semibold">BHOOMI Assistant</p>
              <p className="text-xs text-primary-100">Grounded answers for your farms</p>
            </div>
            {farms.length > 0 && (
              <select
                aria-label="Farm for this conversation"
                value={farmId}
                onChange={(e) => {
                  setFarmId(e.target.value);
                  // A different farm means different data, so the old thread
                  // would misrepresent what the assistant remembers.
                  setSessionId(null);
                  setTurns([]);
                }}
                className="max-w-[9rem] rounded-md border border-primary-600 bg-primary-800 px-2 py-1 text-xs font-medium text-white"
              >
                {farms.map((farm) => (
                  <option key={farm.id} value={farm.id}>
                    {farm.name}
                  </option>
                ))}
              </select>
            )}
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
            {turns.length === 0 && (
              <div className="space-y-2">
                <p className="text-xs text-text-secondary">
                  Ask about weather, soil, crop health, advisories, or disease risk. Answers come from your
                  recorded farm data and name their sources.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => send(suggestion)}
                      className="rounded-full border border-border px-2.5 py-1 text-xs text-text-secondary transition hover:border-primary hover:text-primary-700"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn) => {
              const reply = turn.reply;
              const confidence = reply ? confidenceLabel(reply.confidence) : null;
              const expanded = expandedTurn === turn.id;
              return (
                <article key={turn.id} className="space-y-2">
                  <p className="ml-auto w-fit max-w-[85%] rounded-lg rounded-br-sm bg-primary-600 px-3 py-2 text-sm text-white">
                    {turn.question}
                  </p>

                  {reply && (
                    <div className="space-y-2 rounded-lg rounded-bl-sm border border-border bg-background px-3 py-2">
                      <p className="whitespace-pre-wrap text-sm text-text-primary">{reply.answer}</p>

                      {turn.error && <p className="text-xs text-danger">{turn.error}</p>}

                      {reply.requires_approval && (
                        <p className="rounded-md bg-accent-soft px-2 py-1 text-xs text-accent">
                          This action changes data and needs an agronomist or admin to approve it first.
                        </p>
                      )}

                      {reply.warning && (
                        <p className="rounded-md bg-accent-soft px-2 py-1 text-xs text-accent">{reply.warning}</p>
                      )}

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-muted">
                        {confidence && (
                          <span className={confidence.tone}>confidence: {confidence.label}</span>
                        )}
                        {reply.model_used && <span>model: {reply.model_used}</span>}
                        {reply.fallback_used && <span className="text-warning">fallback used</span>}
                        {reply.budget.limit_reason && (
                          <span className="text-warning">stopped: {reply.budget.limit_reason}</span>
                        )}
                      </div>

                      {reply.missing_data.length > 0 && (
                        <p className="text-[11px] text-text-muted">
                          Not measured: {reply.missing_data.join(", ").replace(/_/g, " ")}
                        </p>
                      )}

                      {(reply.tool_calls.length > 0 || reply.sources.length > 0) && (
                        <button
                          type="button"
                          onClick={() => setExpandedTurn(expanded ? null : turn.id)}
                          aria-expanded={expanded}
                          className="text-[11px] font-medium text-primary-700 hover:underline"
                        >
                          {expanded ? "Hide" : "Show"} evidence ({reply.tool_calls.length} tools,{" "}
                          {reply.sources.length} sources)
                        </button>
                      )}

                      {expanded && (
                        <div className="space-y-1.5 border-t border-border pt-2 text-[11px] text-text-secondary">
                          {reply.tool_calls.map((call) => (
                            <p key={`${call.tool}-${call.duration_ms}`}>
                              <span className="font-medium text-text-primary">{call.tool}</span>{" "}
                              {call.status} &middot; {call.summary} ({call.duration_ms}ms)
                              {call.reason ? ` — ${call.reason}` : ""}
                            </p>
                          ))}
                          {reply.sources.map((source, index) => (
                            <p key={`${source.domain}-${index}`}>
                              {source.domain ?? "source"}{" "}
                              <span className={availabilityTone(source.status)}>
                                {source.status ?? "unknown"}
                              </span>
                              {source.provider ? ` via ${source.provider}` : ""}
                            </p>
                          ))}
                          <p className="text-text-muted">
                            phases {reply.phases.map((phase) => phase.phase).join(" → ")} &middot;{" "}
                            {reply.budget.steps_used}/{reply.budget.max_steps} steps,{" "}
                            {reply.budget.tool_calls_used}/{reply.budget.max_tool_calls} tool calls
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}

            {sending && (
              <p className="text-xs text-text-muted">Checking your farm data&hellip;</p>
            )}
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              void send(input);
            }}
            className="flex items-center gap-2 border-t border-border px-3 py-2"
          >
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about your farm&hellip;"
              aria-label="Message BHOOMI assistant"
              maxLength={2000}
              className="input flex-1"
            />
            <button
              type="submit"
              disabled={sending || input.trim().length === 0}
              className="rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </section>
      )}
    </>
  );
}