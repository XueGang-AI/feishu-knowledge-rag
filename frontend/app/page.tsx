"use client";

import {
  Activity,
  Bot,
  ExternalLink,
  FileSearch,
  Loader2,
  RefreshCw,
  Send,
  Settings,
  Sparkles
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

type SourceRef = {
  source_id: string;
  chunk_id: string;
  title: string;
  section_path: string;
  source_url?: string | null;
  block_ids: string[];
  rerank_score?: number | null;
  content_preview: string;
};

type ChatResponse = {
  answer: string;
  sources: SourceRef[];
};

type HealthResponse = {
  status: string;
  checks: Record<string, { ok: boolean; status_code?: number; configured?: boolean; error?: string }>;
};

type SyncJob = {
  job_id: string;
  scope_type: string;
  scope_id: string | null;
  status: string;
  processed_items: number;
  failed_items: number;
  total_items: number;
  error_message: string | null;
  created_at: string;
};

const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3301";

export default function Home() {
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceRef[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [scopeType, setScopeType] = useState("all");
  const [scopeId, setScopeId] = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState("");

  const serviceRows = useMemo(() => Object.entries(health?.checks ?? {}), [health]);

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return (await response.json()) as T;
  }

  async function loadHealth() {
    setLoading("health");
    setError("");
    try {
      setHealth(await request<HealthResponse>("/health"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  async function loadJobs() {
    setLoading("jobs");
    setError("");
    try {
      setJobs(await request<SyncJob[]>("/api/sync/jobs"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading("chat");
    setError("");
    try {
      const data = await request<ChatResponse>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ query })
      });
      setAnswer(data.answer);
      setSources(data.sources);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  async function createSyncJob(autoStart: boolean) {
    setLoading("sync");
    setError("");
    try {
      await request<SyncJob>("/api/sync/jobs", {
        method: "POST",
        body: JSON.stringify({
          scope_type: scopeType,
          scope_id: scopeId.trim() ? scopeId.trim() : null,
          auto_start: autoStart
        })
      });
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <Bot size={22} />
          <span>Feishu Knowledge RAG</span>
        </div>
        <div className="apiControl">
          <Settings size={16} />
          <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
          <button type="button" onClick={loadHealth} aria-label="刷新健康状态">
            {loading === "health" ? <Loader2 className="spin" size={16} /> : <Activity size={16} />}
          </button>
        </div>
      </header>

      <section className="workspace">
        <div className="chatPane">
          <form className="askBar" onSubmit={submitChat}>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="输入问题"
              rows={3}
            />
            <button type="submit" aria-label="发送问题" disabled={loading === "chat"}>
              {loading === "chat" ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            </button>
          </form>

          {error && <div className="errorLine">{error}</div>}

          <div className="answerPanel">
            <div className="panelTitle">
              <Sparkles size={18} />
              <span>回答</span>
            </div>
            <div className="answerText">{answer || "等待提问"}</div>
          </div>

          <div className="syncBand">
            <div className="syncControls">
              <select value={scopeType} onChange={(event) => setScopeType(event.target.value)}>
                <option value="all">all</option>
                <option value="space">space</option>
                <option value="node">node</option>
                <option value="document">document</option>
              </select>
              <input
                value={scopeId}
                onChange={(event) => setScopeId(event.target.value)}
                placeholder="scope_id"
              />
              <button type="button" onClick={() => createSyncJob(false)}>
                <FileSearch size={16} />
                创建
              </button>
              <button type="button" onClick={() => createSyncJob(true)}>
                <RefreshCw size={16} />
                运行
              </button>
              <button type="button" onClick={loadJobs} aria-label="刷新同步任务">
                {loading === "jobs" ? <Loader2 className="spin" size={16} /> : <Activity size={16} />}
              </button>
            </div>
            <div className="jobTable">
              {jobs.map((job) => (
                <div className="jobRow" key={job.job_id}>
                  <span>{job.status}</span>
                  <span>{job.scope_type}</span>
                  <span>{job.processed_items}/{job.total_items}</span>
                  <span>{job.error_message ?? job.job_id.slice(0, 8)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <aside className="sidePane">
          <section className="sideSection">
            <div className="panelTitle">
              <ExternalLink size={18} />
              <span>来源</span>
            </div>
            <div className="sourceList">
              {sources.map((source) => (
                <a
                  className="sourceItem"
                  key={source.source_id}
                  href={source.source_url ?? "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  <strong>{source.source_id} · {source.title}</strong>
                  <span>{source.section_path}</span>
                  <small>{source.block_ids.join(", ")}</small>
                  <p>{source.content_preview}</p>
                </a>
              ))}
            </div>
          </section>

          <section className="sideSection">
            <div className="panelTitle">
              <Activity size={18} />
              <span>服务</span>
            </div>
            <div className="healthGrid">
              {serviceRows.map(([name, check]) => (
                <div className="healthRow" key={name}>
                  <span className={check.ok ? "dot ok" : "dot bad"} />
                  <span>{name}</span>
                  <small>{check.ok ? "ok" : check.status_code ?? check.error ?? "off"}</small>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
