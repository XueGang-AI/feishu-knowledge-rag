"use client";

import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowDownToLine,
  Bell,
  BookOpen,
  Bot,
  Brain,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  Gauge,
  HardDrive,
  HelpCircle,
  History,
  Home as HomeIcon,
  Layers,
  Loader2,
  MessageCircle,
  Plus,
  RefreshCw,
  RotateCw,
  Search,
  Send,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Square,
  Upload,
  X
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type View =
  | "dashboard"
  | "chat"
  | "library"
  | "import"
  | "memory"
  | "retrieval"
  | "settings"
  | "search"
  | "health"
  | "alerts"
  | "document";

type ModalView = "qa-settings" | null;

type SourceRef = {
  source_id?: string;
  chunk_id: string;
  account_id: string;
  space_id: string;
  node_token: string;
  doc_token: string;
  tenant_name?: string | null;
  title: string;
  section_path: string;
  source_url?: string | null;
  block_ids: string[];
  score?: number | null;
  rerank_score?: number | null;
  updated_time?: number | null;
  content_preview: string;
};

type SearchHit = {
  chunk_id: string;
  account_id: string;
  space_id: string;
  node_token: string;
  doc_token: string;
  tenant_name?: string | null;
  title: string;
  section_path: string;
  source_url?: string | null;
  block_ids: string[];
  content: string;
  score?: number | null;
  rerank_score?: number | null;
  updated_time?: number | null;
};

type SearchResponse = {
  query: string;
  hits: SearchHit[];
};

type ChatResponse = {
  answer: string;
  sources: SourceRef[];
  mode?: "direct" | "rag";
  retrieval_used?: boolean;
};

type HealthCheck = {
  name?: string;
  ok: boolean;
  status_code?: number;
  url?: string;
  path?: string;
  configured?: boolean;
  accounts?: AccountStatus[];
  error?: string;
};

type HealthResponse = {
  status: string;
  checks: Record<string, HealthCheck>;
};

type SyncJob = {
  job_id: string;
  account_id?: string | null;
  scope_type: string;
  scope_id: string | null;
  status: string;
  total_items: number;
  processed_items: number;
  failed_items: number;
  error_message: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

type AccountStatus = {
  account_id: string;
  tenant_name: string;
  enabled: boolean;
  configured: boolean;
  spaces: number;
  nodes: number;
  documents: number;
  blocks: number;
  chunks: number;
  last_scan_at?: string | null;
  failed_items: number;
  latest_error?: string | null;
};

type SyncStatus = {
  counts: {
    spaces: number;
    nodes: number;
    documents: number;
    blocks: number;
    chunks: number;
    sync_jobs: number;
  };
  accounts: AccountStatus[];
  latest_job: SyncJob | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceRef[];
  mode?: "direct" | "rag";
  retrievalUsed?: boolean;
  createdAt: string;
};

type MemoryItem = {
  id: string;
  content: string;
  type: string;
  source: string;
  confidence: "高" | "中" | "低";
  updatedAt: string;
};

type QaSettings = {
  answerLength: "简短" | "适中" | "详细";
  answerFormat: "结构化段落" | "要点列表";
  onlyKnowledge: boolean;
  showCitations: boolean;
  saveMemory: boolean;
  semanticSearch: boolean;
  topK: number;
  topN: number;
  accountId: string;
};

const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3301";
const STORAGE_SETTINGS = "feishu-rag-ui-settings-v3";
const STORAGE_MEMORY = "feishu-rag-local-memory-v1";
const STORAGE_SEARCHES = "feishu-rag-saved-searches-v1";

const serviceLabels: Record<string, string> = {
  sqlite: "SQLite",
  feishu: "飞书",
  embedding: "Embedding bge-m3",
  reranker: "Reranker",
  llm: "Gemma LLM",
  milvus: "Milvus"
};

const navigation = [
  { id: "dashboard" as const, label: "首页总览", icon: HomeIcon },
  { id: "chat" as const, label: "智能问答", icon: MessageCircle },
  { id: "library" as const, label: "知识库管理", icon: Square },
  { id: "import" as const, label: "导入文档", icon: ArrowDownToLine },
  { id: "memory" as const, label: "长期记忆", icon: Brain },
  { id: "retrieval" as const, label: "检索测试", icon: Activity },
  { id: "settings" as const, label: "本地设置", icon: Settings }
];

const defaultSettings: QaSettings = {
  answerLength: "适中",
  answerFormat: "结构化段落",
  onlyKnowledge: false,
  showCitations: true,
  saveMemory: true,
  semanticSearch: false,
  topK: 8,
  topN: 5,
  accountId: "all"
};

const suggestionSets = [
  ["文搜图是什么", "Milvus 是什么", "当前知识库同步状态如何", "6.28 周报讲了什么？"],
  ["有哪些最近同步失败项", "请总结可检索文档范围", "当前有哪些飞书账号", "如何提升知识库健康度"],
  ["请用一句话介绍你自己", "有哪些来源可以引用", "查找最近的项目记录", "检索 RAG 相关内容"]
];

function nowLabel() {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

function compactNumber(value?: number | null) {
  if (value === null || value === undefined) return "未加载";
  return new Intl.NumberFormat("zh-CN").format(value);
}

function percent(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}

function formatDateTime(value?: string | number | null) {
  if (!value) return "未提供";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function scoreOf(item: SourceRef | SearchHit) {
  return item.rerank_score ?? item.score ?? null;
}

function scoreLabel(item: SourceRef | SearchHit) {
  const score = scoreOf(item);
  return score === null ? "无评分" : score.toFixed(2);
}

function hitToSource(hit: SearchHit): SourceRef {
  return {
    source_id: hit.chunk_id,
    chunk_id: hit.chunk_id,
    account_id: hit.account_id,
    space_id: hit.space_id,
    node_token: hit.node_token,
    doc_token: hit.doc_token,
    tenant_name: hit.tenant_name,
    title: hit.title,
    section_path: hit.section_path,
    source_url: hit.source_url,
    block_ids: hit.block_ids,
    score: hit.score,
    rerank_score: hit.rerank_score,
    updated_time: hit.updated_time,
    content_preview: hit.content.slice(0, 260)
  };
}

function sanitizeError(error: unknown) {
  const raw = error instanceof Error ? error.message : String(error);
  return raw
    .replace(/(app_secret|tenant_access_token|cookie|token)["':=\s]+[^"',\s}]+/gi, "$1=***")
    .slice(0, 500);
}

function serviceStateText(check?: HealthCheck) {
  if (!check) return "未加载";
  if (check.ok) return "正常";
  if (check.configured === false) return "待配置";
  return check.status_code ? `HTTP ${check.status_code}` : check.error ?? "异常";
}

function serviceStateTone(check?: HealthCheck) {
  if (!check) return "amber";
  return check.ok ? "green" : "amber";
}

function serviceProbeText(check?: HealthCheck) {
  if (!check) return "等待健康检查";
  return check.url ?? check.path ?? (check.configured === false ? "缺少配置" : "本地状态");
}

function serviceIssueText(check?: HealthCheck) {
  if (!check) return "未加载";
  if (check.ok) return "无明显问题";
  if (check.configured === false) return "未完成配置";
  if (check.status_code) return `探针返回 HTTP ${check.status_code}`;
  return check.error ?? "服务不可用";
}

function isHealthy(check?: HealthCheck) {
  return check?.ok === true;
}

function jobStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "待执行",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消"
  };
  return labels[status] ?? status;
}

function jobStatusTone(status: string) {
  if (status === "succeeded") return "green";
  if (status === "failed" || status === "cancelled") return "amber";
  return "blue";
}

function jobTime(job: SyncJob) {
  const raw = job.finished_at ?? job.started_at ?? job.created_at;
  const time = new Date(raw).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function jobScopeKey(job: SyncJob) {
  return `${job.account_id ?? "all"}:${job.scope_type}:${job.scope_id ?? ""}`;
}

function isFailedJob(job: SyncJob) {
  return job.failed_items > 0 || job.status === "failed";
}

function chatModeClass(message: ChatMessage) {
  if (message.retrievalUsed === true) return "rag";
  if (message.retrievalUsed === false) return "direct";
  return "unknown";
}

function chatModeLabel(message: ChatMessage) {
  if (message.retrievalUsed === true) return "已使用知识库检索";
  if (message.retrievalUsed === false) return "未使用知识库检索 / 直接由 Gemma 回答";
  return "问答未完成 / 路由状态未知";
}

function emptySourceLabel(message: ChatMessage) {
  if (message.retrievalUsed === true) return "暂无来源";
  if (message.retrievalUsed === false) return "本次没有知识库来源";
  return "本次请求未成功，无法确认来源状态";
}

function documentSyncScopeId(source: SourceRef) {
  if (!source.space_id || !source.node_token) return null;
  return `${source.space_id}:${source.node_token}`;
}

function IconBadge({ children, tone = "blue" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`iconBadge ${tone}`}>{children}</span>;
}

export default function Home() {
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [view, setView] = useState<View>("dashboard");
  const [modal, setModal] = useState<ModalView>(null);
  const [settings, setSettings] = useState<QaSettings>(defaultSettings);
  const [draftSettings, setDraftSettings] = useState<QaSettings>(defaultSettings);
  const [settingsTab, setSettingsTab] = useState<"style" | "scope" | "citation" | "memory">("style");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [globalQuery, setGlobalQuery] = useState("");
  const [libraryQuery, setLibraryQuery] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchFilter, setSearchFilter] = useState<"all" | "docs" | "memory" | "high">("all");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<SourceRef | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [savedSearches, setSavedSearches] = useState<string[]>([]);
  const [scopeType, setScopeType] = useState<"all" | "account" | "space" | "node" | "document">("all");
  const [scopeId, setScopeId] = useState("");
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const globalSearchRef = useRef<HTMLInputElement>(null);

  const checks = health?.checks ?? {};
  const serviceRows = Object.entries(checks);
  const serviceIssueCount = serviceRows.filter(
    ([key, check]) => key !== "sqlite" && check.ok === false
  ).length;
  const visibleServiceRows = ["sqlite", "feishu", "embedding", "reranker", "llm", "milvus"]
    .map((key) => [key, checks[key]] as const)
    .filter(([, check]) => Boolean(check));
  const accounts = useMemo(
    () => syncStatus?.accounts ?? checks.feishu?.accounts ?? [],
    [checks.feishu?.accounts, syncStatus?.accounts]
  );
  const selectedAccount =
    settings.accountId === "all"
      ? null
      : accounts.find((account) => account.account_id === settings.accountId) ?? null;
  const counts = syncStatus?.counts;
  const latestJob = syncStatus?.latest_job ?? jobs[0] ?? null;
  const runningJobs = jobs.filter((job) => job.status === "running" || job.status === "pending");
  const latestSuccessfulJobs = useMemo(() => {
    const latest = new Map<string, number>();
    jobs
      .filter((job) => job.status === "succeeded" && job.failed_items === 0)
      .forEach((job) => {
        const key = jobScopeKey(job);
        latest.set(key, Math.max(latest.get(key) ?? 0, jobTime(job)));
      });
    return latest;
  }, [jobs]);
  const failedJobs = useMemo(
    () =>
      jobs.filter((job) => {
        if (!isFailedJob(job)) return false;
        return jobTime(job) > (latestSuccessfulJobs.get(jobScopeKey(job)) ?? 0);
      }),
    [jobs, latestSuccessfulJobs]
  );
  const healthScore = useMemo(() => {
    const servicesTotal = Math.max(serviceRows.length, 1);
    const servicePart = (serviceRows.filter(([, check]) => check.ok).length / servicesTotal) * 60;
    const knowledgePart = counts && counts.chunks > 0 ? 25 : 0;
    const failurePart = failedJobs.length === 0 ? 15 : Math.max(0, 15 - failedJobs.length * 5);
    return Math.round(servicePart + knowledgePart + failurePart);
  }, [counts, failedJobs.length, serviceRows]);
  const currentSuggestions = suggestionSets[suggestionIndex % suggestionSets.length];
  const latestSources = useMemo(() => {
    const sources = chatMessages.flatMap((message) => message.sources ?? []);
    const fromSearch = (searchResponse?.hits ?? []).map(hitToSource);
    const merged = [...fromSearch, ...sources];
    const seen = new Set<string>();
    return merged.filter((source) => {
      if (seen.has(source.chunk_id)) return false;
      seen.add(source.chunk_id);
      return true;
    });
  }, [chatMessages, searchResponse]);
  const latestAssistantMessage = useMemo(
    () => [...chatMessages].reverse().find((message) => message.role === "assistant") ?? null,
    [chatMessages]
  );
  const visibleSearchHits = useMemo(() => {
    const hits = searchResponse?.hits ?? [];
    if (searchFilter === "memory") return [];
    if (searchFilter === "high") {
      return hits.filter((hit) => (scoreOf(hit) ?? 0) > 0.5 || (hit.rerank_score ?? 0) > 0);
    }
    return hits;
  }, [searchFilter, searchResponse]);
  const alertItems = useMemo(() => {
    const items: { title: string; detail: string; severity: "warn" | "error" | "info"; action: string }[] = [];
    if (!health) {
      items.push({ title: "服务状态未加载", detail: "后端健康接口当前不可用或尚未刷新。", severity: "warn", action: "刷新状态" });
    }
    if (health) {
      visibleServiceRows
        .filter(([key, check]) => key !== "sqlite" && !isHealthy(check))
        .slice(0, 4)
        .forEach(([key, check]) => {
          items.push({
            title: `${serviceLabels[key] ?? key} 异常`,
            detail: serviceIssueText(check),
            severity: key === "feishu" ? "error" : "warn",
            action: "查看健康"
          });
        });
    }
    if (counts && counts.chunks === 0) {
      items.push({ title: "知识库为空", detail: "当前没有可检索向量片段，请确认授权后同步。", severity: "warn", action: "开始同步" });
    }
    failedJobs.slice(0, 4).forEach((job) => {
      items.push({
        title: `${job.scope_type} 同步存在失败项`,
        detail: job.error_message ?? `${job.failed_items} 个条目失败`,
        severity: "warn",
        action: "查看任务"
      });
    });
    accounts
      .filter((account) => !account.enabled || !account.configured || account.latest_error)
      .slice(0, 4)
      .forEach((account) => {
        items.push({
          title: `${account.tenant_name} 账号需要处理`,
          detail: account.latest_error ?? (!account.configured ? "账号未完成配置" : "账号未启用"),
          severity: "info",
          action: "查看账号"
        });
      });
    if (items.length === 0) {
      items.push({ title: "暂无阻塞提醒", detail: "当前未发现健康检查或同步任务中的阻塞项。", severity: "info", action: "导出诊断" });
    }
    return items;
  }, [accounts, counts, failedJobs, health, visibleServiceRows]);

  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
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
  }, [apiBase]);

  const refreshAll = useCallback(async () => {
    setLoading("refresh");
    setError("");
    try {
      const [healthData, statusData, jobsData] = await Promise.all([
        request<HealthResponse>("/health"),
        request<SyncStatus>("/api/sync/status"),
        request<SyncJob[]>("/api/sync/jobs")
      ]);
      setHealth(healthData);
      setSyncStatus(statusData);
      setJobs(jobsData);
      setToast("已刷新真实后端状态");
    } catch (err) {
      setError(`无法加载后端状态：${sanitizeError(err)}`);
    } finally {
      setLoading(null);
    }
  }, [request]);

  useEffect(() => {
    const storedSettings = window.localStorage.getItem(STORAGE_SETTINGS);
    const storedMemory = window.localStorage.getItem(STORAGE_MEMORY);
    const storedSearches = window.localStorage.getItem(STORAGE_SEARCHES);
    if (storedSettings) {
      try {
        const parsed = { ...defaultSettings, ...JSON.parse(storedSettings) } as QaSettings;
        setSettings(parsed);
        setDraftSettings(parsed);
      } catch {
        window.localStorage.removeItem(STORAGE_SETTINGS);
      }
    }
    if (storedMemory) {
      try {
        setMemories(JSON.parse(storedMemory) as MemoryItem[]);
      } catch {
        window.localStorage.removeItem(STORAGE_MEMORY);
      }
    }
    if (storedSearches) {
      try {
        setSavedSearches(JSON.parse(storedSearches) as string[]);
      } catch {
        window.localStorage.removeItem(STORAGE_SEARCHES);
      }
    }
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function persistSettings(next: QaSettings) {
    setSettings(next);
    setDraftSettings(next);
    window.localStorage.setItem(STORAGE_SETTINGS, JSON.stringify(next));
    setToast("问答偏好已保存到本地浏览器");
  }

  function setAccount(accountId: string) {
    persistSettings({ ...settings, accountId });
  }

  function persistMemories(next: MemoryItem[]) {
    setMemories(next);
    window.localStorage.setItem(STORAGE_MEMORY, JSON.stringify(next));
  }

  function persistSavedSearches(next: string[]) {
    setSavedSearches(next);
    window.localStorage.setItem(STORAGE_SEARCHES, JSON.stringify(next));
  }

  function navTo(next: View) {
    setView(next);
    setError("");
    if (next === "chat") {
      window.setTimeout(() => chatInputRef.current?.focus(), 40);
    }
    if (next === "search") {
      window.setTimeout(() => globalSearchRef.current?.focus(), 40);
    }
  }

  async function runSearch(query: string, targetView: View = "search") {
    const trimmed = query.trim();
    if (!trimmed) {
      setToast("请输入检索问题");
      return;
    }
    setLoading("search");
    setError("");
    setSearchQuery(trimmed);
    setView(targetView);
    try {
      const data = await request<SearchResponse>("/api/search", {
        method: "POST",
        body: JSON.stringify({
          query: trimmed,
          top_k: settings.topK,
          top_n: settings.topN,
          account_id: settings.accountId === "all" ? null : settings.accountId
        })
      });
      setSearchResponse(data);
      setSearchFilter("all");
      if (data.hits.length === 0) {
        setToast("真实搜索完成：当前没有命中文档");
      }
    } catch (err) {
      setError(`真实搜索失败：${sanitizeError(err)}`);
      setSearchResponse({ query: trimmed, hits: [] });
    } finally {
      setLoading(null);
    }
  }

  async function askChat(query: string, options?: { fromDocument?: SourceRef }) {
    const trimmed = query.trim();
    if (!trimmed) {
      setToast("请输入问题");
      return;
    }
    const chatMode = options?.fromDocument || settings.onlyKnowledge ? "rag" : "auto";
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: trimmed,
      createdAt: nowLabel()
    };
    setChatMessages((current) => [...current, userMessage]);
    setLoading("chat");
    setError("");
    setView("chat");
    try {
      const data = await request<ChatResponse>("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          query: trimmed,
          mode: chatMode,
          top_k: settings.topK,
          top_n: settings.topN,
          account_id:
            options?.fromDocument?.account_id ??
            (settings.accountId === "all" ? null : settings.accountId),
          doc_token: options?.fromDocument?.doc_token ?? null
        })
      });
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: data.answer,
        sources: data.sources,
        mode: data.mode,
        retrievalUsed: data.retrieval_used,
        createdAt: nowLabel()
      };
      setChatMessages((current) => [...current, assistantMessage]);
      if (settings.saveMemory && data.answer && data.sources.length > 0) {
        const next = [
          {
            id: `mem-${Date.now()}`,
            content: data.answer.slice(0, 140),
            type: "对话",
            source: data.sources[0]?.title ?? "问答",
            confidence: "中" as const,
            updatedAt: nowLabel()
          },
          ...memories
        ].slice(0, 20);
        persistMemories(next);
      }
    } catch (err) {
      const message = `真实问答失败：${sanitizeError(err)}`;
      setError(message);
      setChatMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          text: message,
          sources: [],
          mode: chatMode === "rag" ? "rag" : undefined,
          retrievalUsed: chatMode === "rag" ? true : undefined,
          createdAt: nowLabel()
        }
      ]);
    } finally {
      setLoading(null);
    }
  }

  async function createSyncJob(
    autoStart: boolean,
    override?: { scopeType?: typeof scopeType; scopeId?: string | null; accountId?: string | null }
  ) {
    setLoading("sync");
    setError("");
    try {
      const created = await request<SyncJob>("/api/sync/jobs", {
        method: "POST",
        body: JSON.stringify({
          scope_type: override?.scopeType ?? scopeType,
          scope_id:
            override && "scopeId" in override
              ? override.scopeId
              : scopeId.trim()
                ? scopeId.trim()
                : null,
          account_id:
            override && "accountId" in override
              ? override.accountId
              : settings.accountId === "all"
                ? null
                : settings.accountId,
          auto_start: autoStart
        })
      });
      setToast(autoStart ? `同步任务已创建并启动：${created.job_id}` : `同步任务已创建：${created.job_id}`);
      await refreshAll();
      navTo("import");
    } catch (err) {
      setError(`创建同步任务失败：${sanitizeError(err)}`);
    } finally {
      setLoading(null);
    }
  }

  async function runWeeklyScan() {
    setLoading("weekly");
    setError("");
    try {
      const data = await request<{ job_ids: string[] }>("/api/sync/weekly-scan/run", { method: "POST" });
      setToast(data.job_ids.length ? `已触发 weekly scan：${data.job_ids.length} 个任务` : "没有可启动的 weekly scan 任务");
      await refreshAll();
    } catch (err) {
      setError(`weekly scan 触发失败：${sanitizeError(err)}`);
    } finally {
      setLoading(null);
    }
  }

  function handleGlobalSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runSearch(globalQuery, "search");
  }

  function submitTopSearch(value = globalQuery) {
    void runSearch(value, "search");
  }

  function handleDashboardQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void askChat(chatInput);
    setChatInput("");
  }

  function copyText(text: string, label = "内容") {
    void navigator.clipboard?.writeText(text);
    setToast(`${label}已复制`);
  }

  function saveCurrentSearch() {
    if (!searchQuery) {
      setToast("当前没有可保存的搜索条件");
      return;
    }
    const next = [searchQuery, ...savedSearches.filter((item) => item !== searchQuery)].slice(0, 8);
    persistSavedSearches(next);
    setToast("搜索条件已保存到本地浏览器");
  }

  function exportDiagnostics() {
    const payload = {
      generated_at: new Date().toISOString(),
      health_status: health?.status ?? null,
      counts: syncStatus?.counts ?? null,
      accounts: accounts.map(({ account_id, tenant_name, enabled, configured, spaces, documents, chunks, failed_items }) => ({
        account_id,
        tenant_name,
        enabled,
        configured,
        spaces,
        documents,
        chunks,
        failed_items
      })),
      latest_job: latestJob,
      alerts: alertItems.map(({ title, detail, severity }) => ({ title, detail, severity }))
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `feishu-rag-diagnostics-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setToast("已导出不含 secret/token 的诊断报告");
  }

  function openDocument(source: SourceRef) {
    setSelectedDocument(source);
    navTo("document");
  }

  function unavailable(feature: string) {
    setToast(`${feature} 当前没有后端接口，已保留为明确不可用状态`);
  }

  function renderTopActions() {
    const actionClass = "btn primary";
    if (view === "dashboard") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={() => navTo("import")}>
            <ArrowDownToLine size={16} />
            导入资料库
          </button>
          <button className={actionClass} type="button" onClick={() => navTo("chat")}>
            <Send size={16} />
            开始对话
          </button>
        </>
      );
    }
    if (view === "chat") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={() => navTo("library")}>
            <BookOpen size={16} />
            选择知识库
          </button>
          <button
            className="btn muted"
            type="button"
            onClick={() => {
              setChatMessages([]);
              setChatInput("");
              setToast("已新建本地对话");
              chatInputRef.current?.focus();
            }}
          >
            新建对话
          </button>
        </>
      );
    }
    if (view === "library") {
      return (
        <>
          <button className={actionClass} type="button" onClick={() => unavailable("新建集合")}>
            <Plus size={16} />
            新建集合
          </button>
          <button className="btn subtle" type="button" onClick={() => navTo("import")}>
            <ArrowDownToLine size={16} />
            导入文档
          </button>
        </>
      );
    }
    if (view === "import") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={() => unavailable("连接本地目录")}>
            连接目录
          </button>
          <button className={actionClass} type="button" onClick={() => unavailable("本地文件导入")}>
            选择文件
          </button>
        </>
      );
    }
    if (view === "memory") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={() => unavailable("记忆审查后端")}>
            审查记忆
          </button>
          <button
            className={actionClass}
            type="button"
            onClick={() => {
              persistMemories([
                {
                  id: `mem-${Date.now()}`,
                  content: "用户手动新增的本地记忆，可在本浏览器中用于前端状态展示。",
                  type: "本地",
                  source: "手动新增",
                  confidence: "中",
                  updatedAt: nowLabel()
                },
                ...memories
              ]);
              setToast("已新增本地记忆");
            }}
          >
            新增记忆
          </button>
        </>
      );
    }
    if (view === "retrieval") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={exportDiagnostics}>
            导出报告
          </button>
          <button className={actionClass} type="button" onClick={() => void runSearch(retrievalQuery, "retrieval")}>
            运行测试
          </button>
        </>
      );
    }
    if (view === "settings") {
      return (
        <>
          <button
            className="btn subtle"
            type="button"
            onClick={() => {
              persistSettings(defaultSettings);
              setToast("已恢复前端本地默认设置");
            }}
          >
            恢复默认
          </button>
          <button className={actionClass} type="button" onClick={() => persistSettings(settings)}>
            保存设置
          </button>
        </>
      );
    }
    if (view === "health") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={exportDiagnostics}>
            导出诊断
          </button>
          <button className={actionClass} type="button" onClick={() => void refreshAll()}>
            一键优化
          </button>
        </>
      );
    }
    if (view === "alerts") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={exportDiagnostics}>
            全部忽略
          </button>
          <button className={actionClass} type="button" onClick={() => void refreshAll()}>
            一键处理
          </button>
        </>
      );
    }
    if (view === "document") {
      return (
        <>
          <button className="btn subtle" type="button" onClick={() => selectedDocument && copyText(JSON.stringify(selectedDocument, null, 2), "引用")}>
            复制引用
          </button>
          <button className={actionClass} type="button" onClick={() => selectedDocument && void askChat(`请基于《${selectedDocument.title}》回答：`, { fromDocument: selectedDocument })}>
            用此文档提问
          </button>
        </>
      );
    }
    return (
      <button className="btn subtle" type="button" onClick={() => navTo("dashboard")}>
        清空
      </button>
    );
  }

  function renderDashboard() {
    return (
      <div className="pageGrid dashboardGrid">
        <section className="statCards">
          <MetricCard icon={<FileText size={24} />} label="已索引文档" value={compactNumber(counts?.documents)} hint={counts ? `知识空间 ${compactNumber(counts.spaces)}` : "来自 /api/sync/status"} tone="purple" />
          <MetricCard icon={<Layers size={24} />} label="向量片段" value={compactNumber(counts?.chunks)} hint={counts ? `blocks ${compactNumber(counts.blocks)}` : "来自 /api/sync/status"} tone="blue" />
          <MetricCard icon={<MessageCircle size={24} />} label="今日问答" value={compactNumber(chatMessages.filter((m) => m.role === "user").length)} hint="本浏览器会话真实计数" tone="cyan" />
          <MetricCard icon={<HardDrive size={24} />} label="本地存储" value="未检测" hint="后端未提供容量接口" tone="green" />
        </section>

        <section className="askCard card">
          <div className="sectionHead compact">
            <div>
              <h2>今天想从资料里找什么？</h2>
              <p>普通问题直接由 Gemma 回答；涉及飞书文档、项目资料或来源时才检索知识库。</p>
            </div>
          </div>
          <form className="askForm" onSubmit={handleDashboardQuestion}>
            <div className="promptInput">
              <input
                ref={chatInputRef}
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="输入你的问题，例如：Milvus 是什么"
              />
              <button className="sendIcon" type="submit" aria-label="发送问题" disabled={loading === "chat"}>
                {loading === "chat" ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              </button>
            </div>
            <div className="toggleRow">
              <Toggle checked={settings.onlyKnowledge} label="强制知识库检索" onChange={(checked) => persistSettings({ ...settings, onlyKnowledge: checked })} />
              <Toggle checked={settings.showCitations} label="显示引用来源" onChange={(checked) => persistSettings({ ...settings, showCitations: checked })} />
              <Toggle checked={settings.saveMemory} label="保存到记忆" onChange={(checked) => persistSettings({ ...settings, saveMemory: checked })} />
              <Toggle checked={settings.semanticSearch} label="搜索语义化" onChange={(checked) => persistSettings({ ...settings, semanticSearch: checked })} />
              <button className="inlineButton" type="button" onClick={() => setModal("qa-settings")}>
                <Settings size={14} />
                设置
              </button>
            </div>
          </form>
          <div className="suggestions">
            <span>试试这些问题</span>
            {currentSuggestions.map((item) => (
              <button key={item} type="button" onClick={() => setChatInput(item)}>
                {item}
              </button>
            ))}
            <button type="button" className="linkButton" onClick={() => setSuggestionIndex((current) => current + 1)}>
              换一换 <RotateCw size={14} />
            </button>
          </div>
        </section>

        <HealthCard />
        <RecentActivity />
        <MemoryPreview />
        <AlertPreview />
      </div>
    );
  }

  function HealthCard() {
    const knowledgeRows = [
      { label: "项目概况", value: counts && counts.documents > 0 ? "已索引" : "待同步", tone: counts && counts.documents > 0 ? "green" : "amber" },
      { label: "飞书账号", value: accounts.length ? `${accounts.length} 个` : "未加载", tone: accounts.some((item) => item.configured) ? "green" : "amber" },
      { label: "向量片段", value: counts ? compactNumber(counts.chunks) : "未加载", tone: counts && counts.chunks > 0 ? "blue" : "amber" }
    ];
    return (
      <section className="card healthCard">
        <h2>知识库健康度</h2>
        <div className="ringWrap">
          <div className="healthRing" style={{ "--health": `${healthScore}%` } as React.CSSProperties}>
            <strong>{percent(healthScore)}</strong>
            <span>整体健康度</span>
          </div>
        </div>
        <div className="healthRows">
          {knowledgeRows.map((row) => (
            <div key={row.label} className="healthRow">
              <span>{row.label}</span>
              <b className={`pill ${row.tone}`}>{row.value}</b>
            </div>
          ))}
        </div>
        <button className="linkButton center" type="button" onClick={() => navTo("health")}>
          查看详情
        </button>
      </section>
    );
  }

  function RecentActivity() {
    const rows = jobs.slice(0, 3);
    return (
      <section className="card miniPanel">
        <h2>最近活动</h2>
        {rows.length === 0 ? (
          <EmptyLine text="暂无真实同步任务记录" />
        ) : (
          rows.map((job) => (
            <button className="activityRow" key={job.job_id} type="button" onClick={() => navTo("import")}>
              <span className="activityMain">
                <span className="activityTitle">{job.scope_type} 同步</span>
                <b className={`statusPill ${jobStatusTone(job.status)}`}>{jobStatusLabel(job.status)}</b>
              </span>
              <small>{formatDateTime(job.created_at)}</small>
            </button>
          ))
        )}
      </section>
    );
  }

  function MemoryPreview() {
    return (
      <section className="card miniPanel">
        <h2>近期记忆</h2>
        {memories.length === 0 ? (
          <EmptyLine text="暂无本地记忆，保存回答后会出现在这里" />
        ) : (
          memories.slice(0, 3).map((memory) => (
            <button className="activityRow" key={memory.id} type="button" onClick={() => navTo("memory")}>
              <span>{memory.content}</span>
              <small>{memory.updatedAt}</small>
            </button>
          ))
        )}
      </section>
    );
  }

  function AlertPreview() {
    return (
      <section className="card miniPanel alertPanel">
        <h2>系统提醒</h2>
        {alertItems.slice(0, 3).map((item) => (
          <button className="alertRow" key={`${item.title}-${item.detail}`} type="button" onClick={() => navTo("alerts")}>
            <span className={`dot ${item.severity}`} />
            <span className="alertText">{item.title}</span>
            <b className="alertAction">{item.action}</b>
          </button>
        ))}
      </section>
    );
  }

  function renderChat() {
    const sourcePanel = latestSources.slice(0, 4);
    return (
      <div className="pageGrid twoColumn">
        <section className="card chatMain">
          <div className="chatHeader">
            <strong>{selectedAccount ? selectedAccount.tenant_name : "全部账号"}</strong>
            <span>{settings.onlyKnowledge ? "强制检索" : "自动路由"}</span>
            <select value={settings.accountId} onChange={(event) => setAccount(event.target.value)}>
              <option value="all">全部账号</option>
              {accounts.map((account) => (
                <option key={account.account_id} value={account.account_id}>
                  {account.tenant_name} / {account.account_id}
                </option>
              ))}
            </select>
          </div>
          <div className="messageList">
            {chatMessages.length === 0 ? (
              <div className="emptyChat">
                <Bot size={26} />
                <strong>开始真实问答</strong>
                <p>普通问题会直接由 Gemma 回答；涉及飞书文档、项目资料或来源时才会检索知识库。</p>
              </div>
            ) : (
              chatMessages.map((message) => (
                <article className={`message ${message.role}`} key={message.id}>
                  <div className="avatar">{message.role === "assistant" ? "AI" : "你"}</div>
                  <div className="bubble">
                    <p>{message.text}</p>
                    {message.role === "assistant" && (
                      <span className={`chatModeBadge ${chatModeClass(message)}`}>
                        {chatModeLabel(message)}
                      </span>
                    )}
                    {message.role === "assistant" && settings.showCitations && (
                      <div className="sourceChips">
                        {(message.sources ?? []).length === 0 ? (
                          <span className="emptySource">
                            {emptySourceLabel(message)}
                          </span>
                        ) : (
                          message.sources?.map((source) => (
                            <button key={source.chunk_id} type="button" onClick={() => openDocument(source)}>
                              {source.title}
                              <small>{scoreLabel(source)}</small>
                            </button>
                          ))
                        )}
                      </div>
                    )}
                    <small>{message.createdAt}</small>
                  </div>
                </article>
              ))
            )}
          </div>
          <form className="bottomComposer" onSubmit={handleDashboardQuestion}>
            <input ref={chatInputRef} value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="继续提问，或输入 /summary /cite /memory" />
            <button className="sendIcon" type="submit" aria-label="发送问题" disabled={loading === "chat"}>
              {loading === "chat" ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            </button>
          </form>
        </section>
        <aside className="sideStack">
          <section className="card">
            <h2>引用来源</h2>
            {sourcePanel.length === 0 ? (
              <EmptyLine
                text={
                  latestAssistantMessage?.retrievalUsed === false
                    ? "本次为直接回答，没有知识库来源。"
                    : latestAssistantMessage?.retrievalUsed === undefined
                      ? "最近一次问答未成功，无法确认来源状态。"
                      : "还没有真实 sources。完成一次问答或搜索后会展示来源。"
                }
              />
            ) : (
              sourcePanel.map((source) => (
                <button className="sourceCard" key={source.chunk_id} type="button" onClick={() => openDocument(source)}>
                  <strong>{source.title}</strong>
                  <span>{source.tenant_name ?? source.account_id}</span>
                  <div className="scoreBar"><span style={{ width: `${Math.max(8, (scoreOf(source) ?? 0.3) * 100)}%` }} /></div>
                </button>
              ))
            )}
          </section>
          <section className="card">
            <h2>本次检索</h2>
            {latestAssistantMessage?.retrievalUsed === false ? (
              <EmptyLine text="未使用知识库检索，回答直接来自 Gemma。" />
            ) : latestAssistantMessage?.retrievalUsed === undefined ? (
              <EmptyLine text="最近一次问答未成功，无法确认检索链路状态。" />
            ) : (
              <>
                <ProgressLine label="Top-K" value={settings.topK} max={100} />
                <ProgressLine label="Rerank Top-N" value={settings.topN} max={20} />
                <ProgressLine label="引用数量" value={sourcePanel.length} max={Math.max(settings.topN, 1)} />
              </>
            )}
          </section>
        </aside>
      </div>
    );
  }

  function renderLibrary() {
    const docs = latestSources;
    return (
      <div className="pageGrid">
        <div className="tabRow">
          <button
            className={settings.accountId === "all" ? "active" : ""}
            type="button"
            onClick={() => setAccount("all")}
          >
            全部集合
          </button>
          {accounts.map((account) => (
            <button key={account.account_id} type="button" onClick={() => setAccount(account.account_id)}>
              {account.tenant_name}
            </button>
          ))}
          <button type="button" onClick={() => unavailable("集合创建")}>+ 新集合</button>
        </div>
        <section className="statCards">
          <MetricCard icon={<FileText size={24} />} label="文档总数" value={compactNumber(counts?.documents)} hint="真实 SQLite 统计" tone="blue" />
          <MetricCard icon={<Layers size={24} />} label="向量片段" value={compactNumber(counts?.chunks)} hint={counts ? `平均 ${counts.documents ? Math.round(counts.chunks / counts.documents) : 0} / 文档` : "未加载"} tone="green" />
          <MetricCard icon={<HardDrive size={24} />} label="本地占用" value="未检测" hint="后端未提供容量接口" tone="purple" />
          <MetricCard icon={<AlertTriangle size={24} />} label="待处理" value={compactNumber(failedJobs.length)} hint="失败或含失败项任务" tone="amber" />
        </section>
        <section className="collectionCards">
          {accounts.length === 0 ? (
            <div className="card"><EmptyLine text="没有账号分组，等待 /api/sync/status 返回数据" /></div>
          ) : (
            accounts.map((account) => (
              <button className="collectionCard" key={account.account_id} type="button" onClick={() => setAccount(account.account_id)}>
                <IconBadge tone="blue"><FolderOpen size={20} /></IconBadge>
                <strong>{account.tenant_name}</strong>
                <span>{compactNumber(account.documents)} 文档 · {compactNumber(account.chunks)} chunks · {account.configured ? "已配置" : "待配置"}</span>
              </button>
            ))
          )}
        </section>
        <section className="card tableCard">
          <div className="tableHeader">
            <h2>文档列表</h2>
            <form className="compactSearch" onSubmit={(event) => { event.preventDefault(); void runSearch(libraryQuery, "library"); }}>
              <input value={libraryQuery} onChange={(event) => setLibraryQuery(event.target.value)} placeholder="搜索文档..." />
              <button type="submit">搜索</button>
            </form>
          </div>
          {docs.length === 0 ? (
            <EmptyLine text="请先搜索或问答；文档列表只展示真实 search/chat 返回的来源，不伪造文档。" />
          ) : (
            <div className="dataTable">
              <div className="tableRow head"><span>文档名称</span><span>账号</span><span>类型</span><span>状态</span><span>评分</span><span>操作</span></div>
              {docs.map((doc) => (
                <button className="tableRow" key={doc.chunk_id} type="button" onClick={() => openDocument(doc)}>
                  <span>{doc.title}</span>
                  <span>{doc.tenant_name ?? doc.account_id}</span>
                  <span>{doc.section_path || "未提供"}</span>
                  <span><b className="pill green">已索引</b></span>
                  <span>{scoreLabel(doc)}</span>
                  <span>查看</span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderImport() {
    return (
      <div className="pageGrid importGrid">
        <section className="card uploadCard">
          <h2>把资料变成可检索知识</h2>
          <p>当前后端支持飞书同步任务；本地文件解析导入暂未接入后端。</p>
          <button className="dropZone" type="button" onClick={() => unavailable("本地文件解析导入")}>
            <Upload size={36} />
            <strong>拖入 PDF、Markdown、网页快照或整个文件夹</strong>
            <span>不可假装成功：此入口当前只给出待接入反馈</span>
            <i>PDF</i><i>DOCX</i><i>MD</i><i>HTML</i><i>TXT</i>
          </button>
        </section>
        <section className="card syncCreator">
          <h2>飞书同步任务</h2>
          <label>账号范围</label>
          <select value={settings.accountId} onChange={(event) => setAccount(event.target.value)}>
            <option value="all">全部 enabled 账号</option>
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>{account.tenant_name} / {account.account_id}</option>
            ))}
          </select>
          <label>同步范围</label>
          <select value={scopeType} onChange={(event) => setScopeType(event.target.value as typeof scopeType)}>
            <option value="all">all</option>
            <option value="account">account</option>
            <option value="space">space</option>
            <option value="node">node</option>
            <option value="document">document</option>
          </select>
          <label>scope_id</label>
          <input value={scopeId} onChange={(event) => setScopeId(event.target.value)} placeholder="space/node/document token，可为空" />
          <div className="buttonStack">
            <button className="btn primary block" type="button" onClick={() => void createSyncJob(true)} disabled={loading === "sync"}>
              {loading === "sync" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
              开始同步
            </button>
            <button className="btn subtle block" type="button" onClick={() => void createSyncJob(false)}>只创建任务</button>
            <button className="btn subtle block" type="button" onClick={() => void runWeeklyScan()}>手动触发 weekly scan</button>
          </div>
        </section>
        <section className="card pipelineCard">
          <h2>导入流水线</h2>
          {["创建同步任务", "飞书节点扫描", "正文解析切片", "Embedding 写入", "Milvus 索引"].map((label, index) => (
            <div className="pipelineStep" key={label}>
              <span>{index + 1}</span>
              <strong>{label}</strong>
              <small>{runningJobs.length ? "运行中任务会由后端更新" : "等待任务"}</small>
            </div>
          ))}
        </section>
        <section className="card queueCard">
          <h2>导入队列</h2>
          {jobs.length === 0 ? <EmptyLine text="暂无真实任务" /> : jobs.slice(0, 8).map((job) => <JobRow job={job} key={job.job_id} />)}
        </section>
      </div>
    );
  }

  function renderMemory() {
    return (
      <div className="pageGrid memoryGrid">
        <section className="memoryPrimary">
          <form className="wideSearch" onSubmit={(event) => { event.preventDefault(); setToast("长期记忆搜索当前只搜索本地浏览器记忆"); }}>
            <Search size={16} />
            <input placeholder="搜索长期记忆：偏好、项目、人物、决策、事实..." />
          </form>
          <section className="memoryCards">
            {["回答风格", "项目", "人物", "决策"].map((type) => (
              <article className="card memoryTile" key={type}>
                <b className="pill blue">{type}</b>
                <strong>{type === "回答风格" ? "本地偏好" : `${type}记忆`}</strong>
                <p>当前为前端 localStorage 记忆，未声称来自后端。</p>
              </article>
            ))}
          </section>
        </section>
        <aside className="sideStack memorySideStack">
          <section className="card memoryReviewCard"><h2>记忆审查</h2><InfoRow label="待确认记忆" value="0" /><InfoRow label="可能过期" value="0" /><InfoRow label="冲突项" value="0" /><button className="btn primary block" type="button" onClick={() => unavailable("记忆审查")}>开始审查</button></section>
          <section className="card memoryPolicyCard"><h2>记忆策略</h2><Toggle checked={settings.saveMemory} label="自动保存高置信偏好" onChange={(checked) => persistSettings({ ...settings, saveMemory: checked })} /><Toggle checked={true} label="保存前询问" onChange={() => setToast("该策略当前固定为本地确认模式")} /><Toggle checked={true} label="敏感记忆加密" onChange={() => unavailable("记忆加密后端")} /></section>
        </aside>
        <section className="card tableCard">
          <div className="tableHeader">
            <h2>记忆列表</h2>
            <button className="btn subtle" type="button" onClick={() => unavailable("后端记忆审查")}>新增记忆</button>
          </div>
          {memories.length === 0 ? (
            <EmptyLine text="暂无本地记忆。打开问答设置的保存到记忆后，真实问答回答摘要会保存在本浏览器。" />
          ) : (
            <div className="dataTable">
              <div className="tableRow head"><span>记忆内容</span><span>类型</span><span>置信度</span><span>来源</span><span>更新时间</span></div>
              {memories.map((memory) => (
                <div className="tableRow five" key={memory.id}><span>{memory.content}</span><span>{memory.type}</span><span><b className="pill green">{memory.confidence}</b></span><span>{memory.source}</span><span>{memory.updatedAt}</span></div>
              ))}
            </div>
          )}
        </section>
      </div>
    );
  }

  function renderRetrieval() {
    const hits = searchResponse?.hits ?? [];
    return (
      <div className="pageGrid twoColumn">
        <section className="card retrievalMain">
          <h2>检索测试台</h2>
          <p>调试向量检索、Rerank 和 Context Pack。耗时为前端未提供时的不可用状态，不写死 trace。</p>
          <form className="promptInput" onSubmit={(event) => { event.preventDefault(); void runSearch(retrievalQuery, "retrieval"); }}>
            <input value={retrievalQuery} onChange={(event) => setRetrievalQuery(event.target.value)} placeholder="输入测试问题：最近项目风险点有哪些？" />
            <button className="sendIcon" type="submit" aria-label="运行检索" disabled={loading === "search"}>{loading === "search" ? <Loader2 className="spin" size={18} /> : <Search size={18} />}</button>
          </form>
          <div className="retrievalControls">
            <label>知识集合<select value={settings.accountId} onChange={(event) => setAccount(event.target.value)}><option value="all">全部账号</option>{accounts.map((account) => <option key={account.account_id} value={account.account_id}>{account.tenant_name}</option>)}</select></label>
            <label>Top-K<input type="range" min="1" max="100" value={settings.topK} onChange={(event) => persistSettings({ ...settings, topK: Number(event.target.value) })} /><b>{settings.topK}</b></label>
            <label>Rerank Top-N<input type="range" min="1" max="20" value={settings.topN} onChange={(event) => persistSettings({ ...settings, topN: Number(event.target.value) })} /><b>{settings.topN}</b></label>
            <Toggle checked={true} label="启用 Rerank（由后端检索链路决定）" onChange={() => setToast("Rerank 开关当前未暴露为后端参数")} />
          </div>
          <div className="traceBox">
            <h3>检索 Trace</h3>
            {["Query Rewrite", "Vector Search", "BM25 Match", "Rerank", "Context Pack"].map((item) => (
              <div key={item}><strong>{item}</strong><span>后端未提供 trace</span></div>
            ))}
          </div>
        </section>
        <aside className="card hitPanel">
          <h2>命中结果</h2>
          {hits.length === 0 ? <EmptyLine text="运行真实 /api/search 后展示命中结果" /> : hits.slice(0, 8).map((hit) => (
            <button className="hitCard" key={hit.chunk_id} type="button" onClick={() => openDocument(hitToSource(hit))}>
              <strong>{hit.title}</strong>
              <p>{hit.content.slice(0, 90)}</p>
              <b className="pill green">{scoreLabel(hit)}</b>
            </button>
          ))}
        </aside>
      </div>
    );
  }

  function renderSettings() {
    return (
      <div className="pageGrid settingsGrid">
        <section className="card settingsPanel">
          <h2>模型与索引</h2>
          <SettingRow title="聊天模型" subtitle="用于生成回答和总结" value="Gemma 4 12B / 8040/v1" />
          <SettingRow title="Embedding 模型" subtitle="用于向量化文档" value="bge-m3 / 8010" />
          <SettingRow title="向量数据库" subtitle="本地索引存储" value="Milvus / 19530" />
          <SettingRow title="上下文窗口" subtitle="由后端与模型服务决定" value="后端未公开" />
          <button className="btn primary" type="button" onClick={() => setModal("qa-settings")}>保存模型设置</button>
        </section>
        <section className="card settingsPanel">
          <h2>隐私边界</h2>
          <Toggle checked={settings.onlyKnowledge} label="强制知识库检索" onChange={(checked) => persistSettings({ ...settings, onlyKnowledge: checked })} />
          <Toggle checked={true} label="敏感集合加密" onChange={() => unavailable("敏感集合加密")} />
          <label>日志保留<select defaultValue="未接入"><option>未接入</option></select></label>
          <button className="btn subtle" type="button" onClick={() => unavailable("清空本地日志")}>清空本地日志</button>
        </section>
        <section className="card settingsPanel">
          <h2>数据位置</h2>
          <input readOnly value="SQLite 路径由后端配置管理，前端不可读取 secret 配置" />
          <input readOnly value="Milvus 数据目录未由公开 API 暴露" />
          <input readOnly value="长期记忆：浏览器 localStorage" />
          <button className="btn subtle" type="button" onClick={() => unavailable("更改目录")}>更改目录</button>
        </section>
        <section className="card settingsPanel">
          <h2>备份与恢复</h2>
          <InfoRow label="最近备份" value="未检测" />
          <InfoRow label="备份大小" value="后端未公开" />
          <InfoRow label="自动备份" value="未接入" />
          <button className="btn subtle" type="button" onClick={exportDiagnostics}>导出诊断备份</button>
          <button className="btn subtle" type="button" onClick={() => unavailable("恢复备份")}>恢复</button>
        </section>
      </div>
    );
  }

  function renderSearchResults() {
    const hits = searchResponse?.hits ?? [];
    return (
      <div className="pageGrid searchGrid">
        <section className="card searchPanel">
          <form className="wideSearch" onSubmit={(event) => { event.preventDefault(); void runSearch(searchQuery || globalQuery, "search"); }}>
            <Search size={16} />
            <input ref={globalSearchRef} value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="在文档、记忆、问题记录中搜索" />
            <button type="submit">{loading === "search" ? "搜索中" : "搜索"}</button>
          </form>
          <div className="tabRow">
            <button
              className={searchFilter === "all" ? "active" : ""}
              type="button"
              onClick={() => setSearchFilter("all")}
            >
              全部 {hits.length}
            </button>
            <button
              className={searchFilter === "docs" ? "active" : ""}
              type="button"
              onClick={() => setSearchFilter("docs")}
            >
              文档 {hits.length}
            </button>
            <button
              className={searchFilter === "memory" ? "active" : ""}
              type="button"
              onClick={() => setSearchFilter("memory")}
            >
              记忆 {memories.length}
            </button>
            <button
              className={searchFilter === "high" ? "active" : ""}
              type="button"
              onClick={() => setSearchFilter("high")}
            >
              只看高相关
            </button>
          </div>
          <h2>搜索结果</h2>
          {visibleSearchHits.length === 0 ? (
            <EmptyLine
              text={
                searchFilter === "memory"
                  ? "当前只保存本地记忆；搜索结果页不会伪造后端记忆命中。"
                  : searchResponse
                    ? "真实 /api/search 未返回当前筛选下的命中结果"
                    : "提交搜索后展示真实结果"
              }
            />
          ) : (
            visibleSearchHits.map((hit) => (
              <button className="searchResult" key={hit.chunk_id} type="button" onClick={() => openDocument(hitToSource(hit))}>
                <IconBadge tone="blue"><FileText size={16} /></IconBadge>
                <div><strong>{hit.title}</strong><p>{hit.content.slice(0, 150)}</p><small>{hit.tenant_name ?? hit.account_id}</small></div>
                <b className="pill green">{scoreLabel(hit)}</b>
              </button>
            ))
          )}
        </section>
        <aside className="sideStack">
          <section className="card">
            <h2>快速操作</h2>
            <ActionRow label="用这些结果开始问答" action="问 AI" onClick={() => void askChat(searchQuery || globalQuery)} />
            <ActionRow label="打开所在集合" action="集合" onClick={() => navTo("library")} />
            <ActionRow label="保存搜索条件" action="保存" onClick={saveCurrentSearch} />
          </section>
          <section className="card noticeCard">
            <p>搜索结果来自本地知识库检索接口，不会使用截图里的示例文档或示例评分。</p>
          </section>
          <section className="filterPills">
            {savedSearches.map((item) => <button key={item} type="button" onClick={() => void runSearch(item, "search")}>{item}</button>)}
          </section>
        </aside>
      </div>
    );
  }

  function renderHealthDetail() {
    return (
      <div className="pageGrid healthDetailGrid">
        <section className="card healthWide">
          <div className="largeRing" style={{ "--health": `${healthScore}%` } as React.CSSProperties}>
            <strong>{percent(healthScore)}</strong><span>整体健康度</span>
          </div>
          <div className="healthMetrics">
            <h2>知识库健康度详情</h2>
            <p>从服务健康、知识库是否有 chunks、同步失败项三个维度估算。</p>
            <ProgressLine label="服务覆盖" value={serviceRows.filter(([, check]) => check.ok).length} max={Math.max(serviceRows.length, 1)} />
            <ProgressLine label="内容可检索" value={counts?.chunks ?? 0} max={Math.max(counts?.chunks ?? 1, 1)} />
            <ProgressLine label="失败任务" value={Math.max(0, 10 - failedJobs.length)} max={10} />
            <ProgressLine label="账号配置" value={accounts.filter((account) => account.configured).length} max={Math.max(accounts.length, 1)} />
          </div>
        </section>
        <section className="card tableCard">
          <h2>服务状态</h2>
          <div className="dataTable">
            <div className="tableRow head service"><span>服务</span><span>状态</span><span>诊断</span><span>探针 / 路径</span></div>
            {visibleServiceRows.length === 0 ? (
              <div className="tableRow service"><span>后端健康</span><span>未加载</span><span>等待接口</span><span>{apiBase}/health</span></div>
            ) : (
              visibleServiceRows.map(([key, check]) => (
                <div className="tableRow service" key={key}>
                  <span>{serviceLabels[key] ?? key}</span>
                  <span><b className={`pill ${serviceStateTone(check)}`}>{serviceStateText(check)}</b></span>
                  <span>{serviceIssueText(check)}</span>
                  <span title={serviceProbeText(check)}>{serviceProbeText(check)}</span>
                </div>
              ))
            )}
          </div>
        </section>
        <section className="card tableCard">
          <h2>集合状态</h2>
          <div className="dataTable">
            <div className="tableRow head"><span>集合</span><span>状态</span><span>问题</span><span>建议动作</span></div>
            {accounts.length === 0 ? <div className="tableRow four"><span>账号状态</span><span>未加载</span><span>等待接口</span><span>刷新</span></div> : accounts.map((account) => (
              <div className="tableRow four" key={account.account_id}>
                <span>{account.tenant_name}</span>
                <span><b className={`pill ${account.configured ? "green" : "amber"}`}>{account.configured ? "已配置" : "待配置"}</b></span>
                <span>{account.latest_error ?? (account.chunks ? "无明显问题" : "暂无 chunks")}</span>
                <span>{account.chunks ? "保持同步" : "创建同步任务"}</span>
              </div>
            ))}
          </div>
        </section>
        <aside className="sideStack">
          <section className="card"><h2>优先处理</h2>{alertItems.slice(0, 3).map((item, index) => <ActionRow key={item.title} label={`${index + 1}. ${item.title}`} action={item.action} onClick={() => navTo("alerts")} />)}</section>
          <section className="card"><h2>健康规则</h2><Toggle checked={true} label="低 OCR 质量提醒" onChange={() => setToast("该规则当前只在前端展示")} /><Toggle checked={false} label="重复内容自动合并" onChange={() => unavailable("重复内容合并")} /><Toggle checked={true} label="索引过期自动重建" onChange={() => unavailable("自动重建")} /></section>
        </aside>
      </div>
    );
  }

  function renderAlerts() {
    return (
      <div className="pageGrid alertGrid">
        <section className="statCards">
          <MetricCard icon={<AlertTriangle size={24} />} label="提醒项" value={compactNumber(alertItems.length)} hint="真实状态推导" tone="amber" />
          <MetricCard icon={<FileText size={24} />} label="失败任务" value={compactNumber(failedJobs.length)} hint="sync_jobs 失败项" tone="purple" />
          <MetricCard icon={<RefreshCw size={24} />} label="运行任务" value={compactNumber(runningJobs.length)} hint="pending/running" tone="blue" />
        </section>
        <section className="card tableCard">
          <h2>处理中心</h2>
          {alertItems.map((item, index) => (
            <div className="taskRow" key={`${item.title}-${index}`}>
              <span>{index + 1}</span>
              <div><strong>{item.title}</strong><p>{item.detail}</p></div>
              <button type="button" onClick={() => {
                if (item.action.includes("同步")) navTo("import");
                else if (item.action.includes("设置")) navTo("settings");
                else void refreshAll();
              }}>{item.action}</button>
            </div>
          ))}
        </section>
        <aside className="sideStack">
          <section className="card"><h2>批量操作</h2><button className="btn primary block" type="button" onClick={() => void refreshAll()}>一键处理推荐项</button><button className="btn subtle block" type="button" onClick={exportDiagnostics}>导出诊断报告</button><button className="btn subtle block" type="button" onClick={() => setToast("提醒已在当前前端会话中折叠")}>稍后提醒</button></section>
          <section className="card"><h2>当前任务进度</h2><ProgressLine label="运行任务" value={runningJobs.length} max={Math.max(jobs.length, 1)} /><ProgressLine label="失败任务" value={failedJobs.length} max={Math.max(jobs.length, 1)} /><ProgressLine label="已完成任务" value={jobs.filter((job) => job.status === "succeeded").length} max={Math.max(jobs.length, 1)} /></section>
        </aside>
      </div>
    );
  }

  function renderDocumentDetail() {
    const doc = selectedDocument;
    if (!doc) {
      return (
        <div className="pageGrid">
          <section className="card"><EmptyLine text="还没有选择真实文档。请从搜索结果、引用来源或文档列表进入。" /><button className="btn primary" type="button" onClick={() => navTo("search")}>去搜索</button></section>
        </div>
      );
    }
    return (
      <div className="pageGrid documentGrid">
        <section className="card docMain">
          <h2>{doc.title}</h2>
          <p>来源：{doc.tenant_name ?? doc.account_id} · {doc.section_path || "未提供 section_path"} · 已索引</p>
          <div className="skeletonLines" aria-hidden="true"><span /><span /><span /><span /></div>
          <h3>命中片段预览</h3>
          <article className="chunkPreview">
            <strong>Chunk {doc.chunk_id.slice(0, 10)} · 相似度 {scoreLabel(doc)}</strong>
            <p>{doc.content_preview || "该来源没有返回 content_preview。"}</p>
          </article>
          <h3>文档结构</h3>
          <div className="structureCards">
            <div className="structureCard">来源 <b>{doc.block_ids.length}</b></div>
            <div className="structureCard">section <b>{doc.section_path || "无"}</b></div>
            <div className="structureCard">账号 <b>{doc.account_id}</b></div>
            <div className="structureCard">节点 <b>{doc.node_token ? doc.node_token.slice(0, 8) : "未知"}</b></div>
          </div>
        </section>
        <aside className="sideStack">
          <section className="card">
            <h2>文档信息</h2>
            <InfoRow label="集合" value={doc.tenant_name ?? doc.account_id} />
            <InfoRow label="文件类型" value={doc.section_path || "飞书文档"} />
            <InfoRow label="最近更新" value={formatDateTime(doc.updated_time)} />
            <InfoRow label="索引状态" value="已索引" />
            <InfoRow label="引用次数" value={compactNumber(doc.block_ids.length)} />
            <button
              className="btn primary block"
              type="button"
              onClick={() => {
                const syncScopeId = documentSyncScopeId(doc);
                if (!syncScopeId) {
                  setError("该来源缺少 space_id 或 node_token，无法创建文档级重新索引任务。");
                  return;
                }
                void createSyncJob(true, {
                  scopeType: "document",
                  scopeId: syncScopeId,
                  accountId: doc.account_id
                });
              }}
            >
              重新索引
            </button>
          </section>
          <section className="card">
            <h2>可执行操作</h2>
            <ActionRow label="用此文档提问" action="开始问" onClick={() => void askChat(`请基于《${doc.title}》回答：`, { fromDocument: doc })} />
            <ActionRow label="生成摘要" action="摘要" onClick={() => void askChat(`请总结《${doc.title}》`, { fromDocument: doc })} />
            <ActionRow label="复制引用" action="复制" onClick={() => copyText(JSON.stringify(doc, null, 2), "引用")} />
            <ActionRow
              label="打开飞书原文"
              action={doc.source_url ? "打开" : "无链接"}
              onClick={() => {
                if (doc.source_url) window.open(doc.source_url, "_blank", "noopener,noreferrer");
                else unavailable("打开飞书原文");
              }}
            />
            <Toggle checked={false} label="排除此检索" onChange={() => unavailable("排除检索")} />
          </section>
          <section className="card">
            <h2>相关文档</h2>
            {latestSources.filter((source) => source.chunk_id !== doc.chunk_id).slice(0, 3).map((source) => (
              <button className="relatedDoc" key={source.chunk_id} type="button" onClick={() => openDocument(source)}>
                {source.title}<b>{scoreLabel(source)}</b>
              </button>
            ))}
          </section>
        </aside>
      </div>
    );
  }

  function renderCurrentView() {
    if (view === "dashboard") return renderDashboard();
    if (view === "chat") return renderChat();
    if (view === "library") return renderLibrary();
    if (view === "import") return renderImport();
    if (view === "memory") return renderMemory();
    if (view === "retrieval") return renderRetrieval();
    if (view === "settings") return renderSettings();
    if (view === "search") return renderSearchResults();
    if (view === "health") return renderHealthDetail();
    if (view === "alerts") return renderAlerts();
    return renderDocumentDetail();
  }

  const titles: Record<View, { title: string; subtitle: string }> = {
    dashboard: { title: "首页总览", subtitle: "你的本地知识库与记忆工作台" },
    chat: { title: "智能问答", subtitle: "普通问题直接回答，专有知识自动检索并展示来源" },
    library: { title: "知识库管理", subtitle: "管理你的本地知识库和文档集合" },
    import: { title: "导入文档", subtitle: "把本地资料解析、切片、向量化并写入知识库" },
    memory: { title: "长期记忆", subtitle: "管理偏好、项目事实、人物信息和长期规则" },
    retrieval: { title: "检索测试", subtitle: "调试召回、排序、引用覆盖率和上下文打包策略" },
    settings: { title: "本地设置", subtitle: "控制模型、索引、隐私和数据保存位置" },
    search: { title: "全局搜索", subtitle: "点击顶部搜索框后的真实搜索结果页" },
    health: { title: "知识库健康度", subtitle: "点击「查看详情」后的健康分析页" },
    alerts: { title: "系统提醒", subtitle: "点击「去处理 / 去优化」后的任务处理中心" },
    document: { title: "文档详情", subtitle: "点击最近活动、引用来源或文档表格后的详情页" }
  };

  return (
    <main className="ragShell">
      <div className="windowFrame">
        <aside className="sidebar">
          <div className="brand">
            <div className="brandMark">AI</div>
            <div><strong>Local RAG</strong><span>个人助手</span><b>{health?.status === "ok" ? (serviceIssueCount ? `${serviceIssueCount} 项服务异常` : "本地运行中") : "状态待检测"}</b></div>
          </div>
          <nav className="navList" aria-label="主导航">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <button key={item.id} className={view === item.id ? "active" : ""} type="button" onClick={() => navTo(item.id)}>
                  <Icon size={17} />
                  {item.label}
                </button>
              );
            })}
          </nav>
          <section className="localStatus">
            <strong>本地状态<span /></strong>
            <p>{health?.status === "ok" ? (serviceIssueCount ? "已加载，存在异常项" : "全部服务状态已加载") : "等待健康检查"}</p>
            <dl>
              <div><dt>向量库</dt><dd>{serviceStateText(checks.milvus)}</dd></div>
              <div><dt>Embedding</dt><dd>{serviceStateText(checks.embedding)}</dd></div>
              <div><dt>Reranker</dt><dd>{serviceStateText(checks.reranker)}</dd></div>
              <div><dt>大语言模型</dt><dd>{serviceStateText(checks.llm)}</dd></div>
            </dl>
          </section>
        </aside>
        <section className="workspace">
          <header className="pageHeader">
            <div>
              <h1>{titles[view].title}</h1>
              <p>{titles[view].subtitle}</p>
            </div>
            <form className="topSearch" onSubmit={handleGlobalSearch}>
              <Search size={15} />
              <input
                value={globalQuery}
                onChange={(event) => setGlobalQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    submitTopSearch(event.currentTarget.value);
                  }
                }}
                placeholder="搜索文档、记忆、问题..."
              />
              <kbd>⌘K</kbd>
              <button type="submit" aria-label="提交全局搜索">
                <Search size={15} />
              </button>
            </form>
            <div className="headerActions">{renderTopActions()}</div>
          </header>
          {error && <div className="runtimeError"><AlertTriangle size={16} />{error}</div>}
          {toast && <div className="toast"><CheckCircle2 size={16} />{toast}</div>}
          <div className="pageScroller">{renderCurrentView()}</div>
        </section>
      </div>
      {modal === "qa-settings" && renderQaSettingsModal()}
    </main>
  );

  function renderQaSettingsModal() {
    return (
      <div className="modalLayer" role="dialog" aria-modal="true" aria-label="问答设置">
        <section className="settingsModal">
          <button className="closeButton" type="button" aria-label="关闭设置" onClick={() => setModal(null)}><X size={18} /></button>
          <h2>问答设置</h2>
          <p>点击问答卡片里的「设置」后出现，用来控制回答方式、引用和记忆策略。</p>
          <div className="modalTabs">
            <button className={settingsTab === "style" ? "active" : ""} type="button" onClick={() => setSettingsTab("style")}>回答风格</button>
            <button className={settingsTab === "scope" ? "active" : ""} type="button" onClick={() => setSettingsTab("scope")}>搜索范围</button>
            <button className={settingsTab === "citation" ? "active" : ""} type="button" onClick={() => setSettingsTab("citation")}>引用设置</button>
            <button className={settingsTab === "memory" ? "active" : ""} type="button" onClick={() => setSettingsTab("memory")}>记忆策略</button>
          </div>
          <div className="modalGrid">
            {settingsTab === "style" && (
              <>
                <label>回答长度<select value={draftSettings.answerLength} onChange={(event) => setDraftSettings({ ...draftSettings, answerLength: event.target.value as QaSettings["answerLength"] })}><option>简短</option><option>适中</option><option>详细</option></select></label>
                <label>输出格式<select value={draftSettings.answerFormat} onChange={(event) => setDraftSettings({ ...draftSettings, answerFormat: event.target.value as QaSettings["answerFormat"] })}><option>结构化段落</option><option>要点列表</option></select></label>
                <Toggle checked={draftSettings.semanticSearch} label="搜索语义化" onChange={(checked) => setDraftSettings({ ...draftSettings, semanticSearch: checked })} />
              </>
            )}
            {settingsTab === "scope" && (
              <>
                <label>账号范围<select value={draftSettings.accountId} onChange={(event) => setDraftSettings({ ...draftSettings, accountId: event.target.value })}><option value="all">全部账号</option>{accounts.map((account) => <option key={account.account_id} value={account.account_id}>{account.tenant_name}</option>)}</select></label>
                <label>Top-K<input type="number" min="1" max="100" value={draftSettings.topK} onChange={(event) => setDraftSettings({ ...draftSettings, topK: Number(event.target.value) })} /></label>
                <label>Rerank Top-N<input type="number" min="1" max="20" value={draftSettings.topN} onChange={(event) => setDraftSettings({ ...draftSettings, topN: Number(event.target.value) })} /></label>
              </>
            )}
            {settingsTab === "citation" && (
              <>
                <Toggle checked={draftSettings.onlyKnowledge} label="强制知识库检索" onChange={(checked) => setDraftSettings({ ...draftSettings, onlyKnowledge: checked })} />
                <Toggle checked={draftSettings.showCitations} label="显示引用来源" onChange={(checked) => setDraftSettings({ ...draftSettings, showCitations: checked })} />
                <div className="systemPrompt">默认自动路由：普通问题直接由 Gemma 回答；强制知识库检索开启后，只基于本地来源回答并展示引用。</div>
              </>
            )}
            {settingsTab === "memory" && (
              <>
                <Toggle checked={draftSettings.saveMemory} label="自动保存高置信记忆" onChange={(checked) => setDraftSettings({ ...draftSettings, saveMemory: checked })} />
                <Toggle checked={true} label="低置信度时提醒" onChange={() => setToast("该提醒当前由前端本地状态控制")} />
                <Toggle checked={false} label="回答前先澄清" onChange={() => setToast("澄清策略当前只保存为本地偏好")} />
              </>
            )}
          </div>
          <div className="modalActions">
            <button className="btn subtle" type="button" onClick={() => { setDraftSettings(settings); setModal(null); }}>取消</button>
            <button className="btn primary" type="button" onClick={() => { persistSettings(draftSettings); setModal(null); }}>保存设置</button>
          </div>
        </section>
      </div>
    );
  }
}

function MetricCard({ icon, label, value, hint, tone }: { icon: React.ReactNode; label: string; value: string; hint: string; tone: string }) {
  return (
    <article className="metricCard">
      <IconBadge tone={tone}>{icon}</IconBadge>
      <div><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>
    </article>
  );
}

function Toggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="toggleControl">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span />
      {label}
    </label>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className="emptyLine"><HelpCircle size={16} />{text}</div>;
}

function ProgressLine({ label, value, max }: { label: string; value: number; max: number }) {
  const width = max <= 0 ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="progressLine">
      <span>{label}</span>
      <div><i style={{ width: `${width}%` }} /></div>
      <b>{value}</b>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return <div className="infoRow"><span>{label}</span><strong>{value}</strong></div>;
}

function ActionRow({ label, action, onClick }: { label: string; action: string; onClick: () => void }) {
  return <div className="actionRow"><span>{label}</span><button type="button" onClick={onClick}>{action}</button></div>;
}

function SettingRow({ title, subtitle, value }: { title: string; subtitle: string; value: string }) {
  return (
    <div className="settingRow">
      <div><strong>{title}</strong><span>{subtitle}</span></div>
      <input readOnly value={value} />
    </div>
  );
}

function JobRow({ job }: { job: SyncJob }) {
  return (
    <div className="jobRow">
      <span className={`statusDot ${job.status}`} />
      <div><strong>{job.scope_type} / {job.account_id ?? "all"}</strong><small>{job.job_id}</small></div>
      <b>{job.processed_items}/{job.total_items}</b>
      <em>{job.status}</em>
    </div>
  );
}
