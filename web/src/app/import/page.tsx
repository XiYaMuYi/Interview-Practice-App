"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import { LoadingState, ErrorState, EmptyState } from "@/components/states";
import TaskStatusBadge from "@/components/TaskStatusBadge";

interface ImportResult {
  status: string;
  questions_extracted: number;
  knowledge_nodes: number;
  question_ids: string[];
}

interface StructuredSummary {
  name?: string;
  title?: string;
  years_of_experience?: number;
  top_skills?: string[];
  summary?: string;
  project_experience?: Array<{
    project_name?: string;
    role?: string;
    description?: string;
    technologies?: string[];
  }>;
  [key: string]: unknown;
}

interface ResumeRead {
  id: string;
  file_name: string;
  file_path: string;
  source_type: string;
  parse_status: string;
  raw_text: string | null;
  structured_summary: StructuredSummary | null;
  created_at: string;
  updated_at: string;
}

interface ResumeParseResponse {
  resume_id: string;
  parse_status: string;
  structured_summary: StructuredSummary | null;
  experiences_count: number;
  model_version: string | null;
  prompt_version: string | null;
  error?: string;
}

const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
];

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

function isAllowedFile(file: File) {
  if (ALLOWED_TYPES.includes(file.type)) return true;
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  return ALLOWED_EXTENSIONS.includes(ext);
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type TabKey = "questions" | "resume" | "custom";

export default function ImportPage() {
  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>("resume");

  // ── Text import (questions tab) ──────────────────────────────────

  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ── Streaming import state ───────────────────────────────────────

  const [streaming, setStreaming] = useState(false);
  const [streamProgress, setStreamProgress] = useState(0);
  const [streamPhase, setStreamPhase] = useState<string | null>(null);
  const [streamMessage, setStreamMessage] = useState<string | null>(null);
  const [streamTotalGenerated, setStreamTotalGenerated] = useState(0);
  const [streamElapsed, setStreamElapsed] = useState(0);
  const [streamDone, setStreamDone] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Resume streaming parse state ─────────────────────────────────

  const [resumeStreaming, setResumeStreaming] = useState(false);
  const [resumeStreamProgress, setResumeStreamProgress] = useState(0);
  const [resumeStreamPhase, setResumeStreamPhase] = useState<string | null>(null);
  const [resumeStreamMessage, setResumeStreamMessage] = useState<string | null>(null);
  const [resumeStreamElapsed, setResumeStreamElapsed] = useState(0);
  const [resumeStreamDone, setResumeStreamDone] = useState(false);
  const [resumeStreamError, setResumeStreamError] = useState<string | null>(null);
  const [resumeStreamSavedChunks, setResumeStreamSavedChunks] = useState<Array<{type: string, label: string}>>([]);
  const [resumeStreamQuestionsGenerated, setResumeStreamQuestionsGenerated] = useState(0);
  const [resumeStreamResumeId, setResumeStreamResumeId] = useState<string | null>(null);
  const resumeAbortRef = useRef<AbortController | null>(null);

  // ── File upload (resume tab) ─────────────────────────────────────

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<ResumeParseResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // ── Custom question import (custom tab) ──────────────────────────

  const [jsonText, setJsonText] = useState("");
  const [customLoading, setCustomLoading] = useState(false);
  const [customError, setCustomError] = useState<string | null>(null);
  const [customResult, setCustomResult] = useState<{
    total: number;
    success: number;
    failed: number;
    results: Array<{
      index: number;
      status: string;
      id?: string;
      title?: string;
      error?: string;
      content_preview?: string;
    }>;
  } | null>(null);
  const [validateMsg, setValidateMsg] = useState<string | null>(null);

  // Saved resumes list
  const [savedResumes, setSavedResumes] = useState<ResumeRead[]>([]);
  const [listLoading, setListLoading] = useState(true);

  // ── Resume list ──────────────────────────────────────────────────

  const fetchResumes = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await axios.get<{ items: ResumeRead[] }>("/api/v1/resumes");
      setSavedResumes(res.data.items);
    } catch {
      // silently ignore — list is optional
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

  // ── Text import ──────────────────────────────────────────────────

  const handleImport = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("text", text);
      const res = await axios.post("/api/v1/import/text", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch {
      setError("导入失败，请检查文本格式或后端服务状态");
    } finally {
      setLoading(false);
    }
  };

  const handleImportStream = async () => {
    if (!text.trim()) return;
    setStreaming(true);
    setStreamProgress(0);
    setStreamPhase("chunking");
    setStreamMessage("正在切分文本...");
    setStreamTotalGenerated(0);
    setStreamElapsed(0);
    setStreamDone(false);
    setStreamError(null);
    setResult(null);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const formData = new FormData();
      formData.append("text", text);
      const res = await fetch("/api/v1/import/text-stream", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error("Stream request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5).trim();
            if (dataStr && eventType) {
              try {
                const data = JSON.parse(dataStr);
                if (data.progress != null) setStreamProgress(data.progress);
                if (data.phase) setStreamPhase(data.phase);
                if (data.current) setStreamMessage(data.current);
                if (data.elapsed != null) setStreamElapsed(Math.round(data.elapsed));
                if (data.total_generated != null) setStreamTotalGenerated(data.total_generated);

                if (eventType === "done") {
                  setStreamDone(true);
                  setStreamPhase("done");
                } else if (eventType === "error") {
                  setStreamError(data.error || "提取失败");
                  if (!data.recoverable) {
                    setStreamDone(true);
                  }
                }
              } catch {
                // ignore parse errors
              }
              eventType = "";
              dataStr = "";
            }
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setStreamError("导入已取消");
      } else {
        setStreamError("导入失败，请检查网络连接或后端服务状态");
      }
      setStreamDone(true);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const cancelStream = () => {
    abortRef.current?.abort();
  };

  // ── Custom question import ───────────────────────────────────────

  const handleValidateJson = () => {
    setValidateMsg(null);
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) {
        setValidateMsg("格式错误: 根节点必须是一个数组");
        return;
      }
      if (parsed.length === 0) {
        setValidateMsg("格式错误: 数组不能为空");
        return;
      }
      if (parsed.length > 200) {
        setValidateMsg("格式错误: 单次最多导入 200 道题目");
        return;
      }
      const errors: string[] = [];
      for (let i = 0; i < parsed.length; i++) {
        const item = parsed[i];
        if (typeof item !== "object" || item === null || Array.isArray(item)) {
          errors.push(`索引 ${i}: 必须是一个对象`);
          continue;
        }
        if (!item.content || typeof item.content !== "string" || !item.content.trim()) {
          errors.push(`索引 ${i}: 缺少必填字段 content（字符串）`);
        }
        if (item.content && item.content.length > 5000) {
          errors.push(`索引 ${i}: content 长度不能超过 5000 字符`);
        }
        if (item.category !== undefined && typeof item.category !== "string") {
          errors.push(`索引 ${i}: category 必须是字符串`);
        }
        if (item.difficulty !== undefined && (typeof item.difficulty !== "number" || item.difficulty < 1 || item.difficulty > 5)) {
          errors.push(`索引 ${i}: difficulty 必须是 1-5 的整数`);
        }
        if (item.reference_answer !== undefined && typeof item.reference_answer !== "string") {
          errors.push(`索引 ${i}: reference_answer 必须是字符串`);
        }
      }
      if (errors.length > 0) {
        setValidateMsg(`验证失败（${errors.length} 条错误）:\n${errors.slice(0, 10).join("\n")}${errors.length > 10 ? "\n..." : ""}`);
      } else {
        setValidateMsg(`✅ 格式验证通过，共 ${parsed.length} 道题目`);
      }
    } catch (e: unknown) {
      if (e instanceof SyntaxError) {
        setValidateMsg(`JSON 解析失败: ${e.message}`);
      } else {
        setValidateMsg("JSON 解析失败，请检查格式");
      }
    }
  };

  const handleCustomImport = async () => {
    if (!jsonText.trim()) return;
    setCustomLoading(true);
    setCustomError(null);
    setCustomResult(null);
    try {
      const parsed = JSON.parse(jsonText);
      const res = await axios.post("/api/v1/questions/import", { questions: parsed });
      if (res.data.status === "validation_error") {
        setCustomError(`参数校验失败: ${JSON.stringify(res.data.errors)}`);
      } else {
        setCustomResult({
          total: res.data.total,
          success: res.data.success,
          failed: res.data.failed,
          results: res.data.results || [],
        });
      }
    } catch (e: unknown) {
      if (e instanceof SyntaxError) {
        setCustomError("JSON 格式无效，请先点击「格式验证」检查");
      } else if (axios.isAxiosError(e)) {
        setCustomError(e.response?.data?.detail ?? "导入失败，请检查网络连接或后端服务状态");
      } else {
        setCustomError("导入失败，请重试");
      }
    } finally {
      setCustomLoading(false);
    }
  };

  // ── File upload helpers ──────────────────────────────────────────

  const triggerParseStream = useCallback(async (resumeId: string) => {
    setResumeStreaming(true);
    setResumeStreamProgress(0);
    setResumeStreamPhase("reading");
    setResumeStreamMessage("正在读取简历...");
    setResumeStreamElapsed(0);
    setResumeStreamDone(false);
    setResumeStreamError(null);
    setResumeStreamSavedChunks([]);
    setResumeStreamQuestionsGenerated(0);
    setResumeStreamResumeId(resumeId);
    setUploadError(null);
    setUploadResult(null);

    const controller = new AbortController();
    resumeAbortRef.current = controller;

    try {
      const res = await fetch(`/api/v1/resumes/${resumeId}/parse-stream`, {
        method: "POST",
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error("Stream request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5).trim();
            if (dataStr && eventType) {
              try {
                const data = JSON.parse(dataStr);
                if (data.progress != null) setResumeStreamProgress(data.progress);
                if (data.phase) setResumeStreamPhase(data.phase);
                if (data.current) setResumeStreamMessage(data.current);
                if (data.elapsed != null) setResumeStreamElapsed(Math.round(data.elapsed));

                if (eventType === "chunk_saved") {
                  setResumeStreamSavedChunks(prev => [
                    ...prev,
                    { type: data.chunk_type || "section", label: data.label || data.chunk_type || "section" },
                  ]);
                }

                if (eventType === "done") {
                  setResumeStreamDone(true);
                  setResumeStreamPhase("done");
                  if (data.questions_generated != null) setResumeStreamQuestionsGenerated(data.questions_generated);
                } else if (eventType === "error") {
                  setResumeStreamError(data.error || "解析失败");
                  if (!data.recoverable) {
                    setResumeStreamDone(true);
                  }
                }
              } catch {
                // ignore parse errors
              }
              eventType = "";
              dataStr = "";
            }
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setResumeStreamError("解析已取消");
      } else {
        setResumeStreamError("解析失败，请检查网络连接或后端服务状态");
      }
      setResumeStreamDone(true);
    } finally {
      setResumeStreaming(false);
      resumeAbortRef.current = null;
    }
  }, []);

  const cancelResumeStream = () => {
    resumeAbortRef.current?.abort();
  };

  const processFile = useCallback(
    async (file: File) => {
      if (!isAllowedFile(file)) {
        setUploadError("不支持的文件类型，请上传 PDF、DOCX、TXT 或 MD 文件");
        return;
      }

      setUploading(true);
      setUploadError(null);
      setUploadResult(null);

      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await axios.post<ResumeRead>("/api/v1/resumes/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        const resumeId = res.data.id;
        await fetchResumes();
        // Use streaming parse instead of blocking
        await triggerParseStream(resumeId);
        await fetchResumes();
      } catch (e: unknown) {
        if (axios.isAxiosError(e)) {
          setUploadError(
            e.response?.data?.detail ?? "文件上传失败，请检查网络连接或后端服务状态"
          );
        } else {
          setUploadError("文件上传失败，请检查网络连接或后端服务状态");
        }
      } finally {
        setUploading(false);
      }
    },
    [triggerParseStream, fetchResumes]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) processFile(file);
      e.target.value = "";
    },
    [processFile]
  );

  // ── Resume actions ───────────────────────────────────────────────

  const handleDelete = useCallback(
    async (resumeId: string) => {
      if (!confirm("确定要删除这份简历吗？此操作不可撤销。")) return;
      try {
        await axios.delete(`/api/v1/resumes/${resumeId}`);
        setSavedResumes((prev) => prev.filter((r) => r.id !== resumeId));
        if (uploadResult?.resume_id === resumeId) {
          setUploadResult(null);
        }
      } catch {
        setUploadError("删除失败，请重试");
      }
    },
    [uploadResult]
  );

  const handleReparse = useCallback(
    async (resumeId: string) => {
      setUploadError(null);
      await triggerParseStream(resumeId);
      await fetchResumes();
    },
    [triggerParseStream, fetchResumes]
  );

  // ── Tab definitions ──────────────────────────────────────────────

  const tabs: { key: TabKey; label: string; icon: string; description: string }[] = [
    {
      key: "questions",
      label: "题目导入",
      icon: "file-text",
      description: "粘贴面经文本，AI 自动提取题目",
    },
    {
      key: "resume",
      label: "简历导入",
      icon: "user",
      description: "上传简历文件，AI 解析并生成针对性题目",
    },
    {
      key: "custom",
      label: "自定义批量导入",
      icon: "code",
      description: "JSON 格式批量导入自定义题目",
    },
  ];

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="page-frame-tight">
      <h1 className="page-title">导入</h1>
      <p className="page-subtitle">
        通过文本粘贴或简历上传，快速构建你的面试题库
      </p>

      {/* Tab Navigation */}
      <div className="tab-bar w-full mb-8">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key);
              // Clear tab-specific state on switch
              if (tab.key === "questions") {
                setUploadResult(null);
                setUploadError(null);
                setCustomResult(null);
                setCustomError(null);
                if (streaming) cancelStream();
                setStreaming(false);
                setStreamDone(false);
                setStreamError(null);
                setStreamProgress(0);
                setStreamPhase(null);
                setStreamMessage(null);
                setStreamTotalGenerated(0);
                setStreamElapsed(0);
              } else if (tab.key === "resume") {
                setResult(null);
                setError(null);
                setCustomResult(null);
                setCustomError(null);
              } else {
                setResult(null);
                setError(null);
                setUploadResult(null);
                setUploadError(null);
                if (resumeStreaming) cancelResumeStream();
                setResumeStreaming(false);
                setResumeStreamDone(false);
                setResumeStreamError(null);
                setResumeStreamProgress(0);
                setResumeStreamPhase(null);
                setResumeStreamMessage(null);
                setResumeStreamElapsed(0);
                setResumeStreamSavedChunks([]);
                setResumeStreamQuestionsGenerated(0);
                setResumeStreamResumeId(null);
              }
            }}
            className={`flex-1 flex flex-col items-center gap-1 py-3 px-4 rounded-lg text-sm font-medium transition-all tab-pill ${
              activeTab === tab.key
                ? "tab-pill-active"
                : "tab-pill-inactive"
            }`}
          >
            <span>{tab.label}</span>
            <span className="text-xs text-slate-400 font-normal">{tab.description}</span>
          </button>
        ))}
      </div>

      {/* ── Tab: 题目导入 ──────────────────────────────────────── */}
      {activeTab === "questions" && (
        <div className="space-y-6">
          <div className="soft-card p-6">
            <h2 className="section-title mb-3">文本导入</h2>
            <label
              htmlFor="import-text"
              className="block text-sm font-medium text-slate-700 mb-2"
            >
              题目文本
            </label>
            <textarea
              id="import-text"
              rows={8}
              className="form-textarea font-mono"
              placeholder={`在此粘贴题目文本...\n\n示例格式：\n题目：什么是闭包？\n难度：3\n分类：Frontend\n\n题目：请解释 React 的虚拟 DOM\n难度：3\n分类：Frontend`}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div className="mt-4 flex items-center gap-4">
              <button
                onClick={handleImportStream}
                disabled={streaming || !text.trim()}
                className="btn-primary"
              >
                {streaming ? "提取中..." : "智能导入（流式）"}
              </button>
              <button
                onClick={handleImport}
                disabled={loading || streaming || !text.trim()}
                className="btn-secondary"
              >
                {loading ? "导入中..." : "普通导入"}
              </button>
              {streaming && (
                <button
                  onClick={cancelStream}
                  className="btn-ghost text-red-500"
                >
                  取消
                </button>
              )}
              <button
                onClick={() => setText("")}
                className="btn-ghost"
                disabled={streaming}
              >
                清空
              </button>
            </div>
          </div>

          {/* ── Streaming progress UI ──────────────────────────── */}
          {streaming && (
            <div className="soft-card p-6 space-y-4">
              <div className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5 text-cyan-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-800">
                    {streamPhase === "chunking" ? "切分文本" : streamPhase === "extracting" ? "提取题目" : "处理中"}
                  </p>
                  {streamMessage && (
                    <p className="text-xs text-slate-500">{streamMessage}</p>
                  )}
                </div>
                <span className="text-xs text-slate-400">{streamElapsed}s</span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round(streamProgress * 100)}%` }}
                />
              </div>

              {/* Stats */}
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-600">
                  进度 <span className="font-semibold text-slate-900">{Math.round(streamProgress * 100)}%</span>
                </span>
                {streamTotalGenerated > 0 && (
                  <span className="text-green-600 font-medium">
                    已提取 {streamTotalGenerated} 道题目
                  </span>
                )}
              </div>
            </div>
          )}

          {/* ── Stream done ────────────────────────────────────── */}
          {streamDone && !streamError && streamTotalGenerated > 0 && (
            <div className="soft-card p-6 space-y-4">
              <div className="success-banner">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold">流式导入完成</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">提取题目</span>
                  <p className="font-semibold text-lg text-green-600">{streamTotalGenerated} 道</p>
                </div>
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">耗时</span>
                  <p className="font-semibold text-lg text-slate-900">{streamElapsed}s</p>
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <Link href="/questions" className="btn-primary">
                  查看题目列表 &rarr;
                </Link>
                <Link href="/study" className="btn-secondary">
                  开始模拟面试
                </Link>
              </div>
            </div>
          )}

          {streamError && !streaming && (
            <ErrorState message={streamError} onRetry={handleImportStream} />
          )}

          {error && <ErrorState message={error} onRetry={handleImport} />}

          {result && (
            <div className="soft-card p-6 space-y-4">
              <div className="success-banner">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold">文本导入成功</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">提取题目</span>
                  <p className="font-semibold text-lg text-slate-900">{result.questions_extracted} 道</p>
                </div>
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">知识节点</span>
                  <p className="font-semibold text-lg text-slate-900">{result.knowledge_nodes} 个</p>
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <Link href="/questions" className="btn-primary">
                  查看题目列表 &rarr;
                </Link>
                <Link href="/study" className="btn-secondary">
                  开始模拟面试
                </Link>
              </div>
            </div>
          )}

          <EmptyState
            title="提示"
            description="你也可以从简历中自动提取针对性题目，切换到「简历导入」标签即可。"
          />
        </div>
      )}

      {/* ── Tab: 自定义批量导入 ────────────────────────────────── */}
      {activeTab === "custom" && (
        <div className="space-y-6">
          <div className="soft-card p-6">
            <h2 className="section-title mb-3">JSON 批量导入</h2>
            <p className="text-sm text-slate-500 mb-4">
              以 JSON 数组格式提交题目，每道题目需包含 <code className="bg-slate-100 px-1 rounded text-xs">content</code> 字段，
              可选字段：<code className="bg-slate-100 px-1 rounded text-xs">category</code>、<code className="bg-slate-100 px-1 rounded text-xs">difficulty</code>（1-5）、<code className="bg-slate-100 px-1 rounded text-xs">reference_answer</code>
            </p>
            <textarea
              id="custom-json"
              rows={12}
              className="form-textarea font-mono text-sm"
              placeholder={`[
  {
    "content": "什么是 React 的 Fiber 架构？",
    "category": "Frontend",
    "difficulty": 4,
    "reference_answer": "Fiber 是 React 16 引入的新一代协调算法..."
  },
  {
    "content": "解释一下 Python 的 GIL",
    "category": "Backend",
    "difficulty": 3,
    "reference_answer": "GIL 是全局解释器锁..."
  }
]`}
              value={jsonText}
              onChange={(e) => {
                setJsonText(e.target.value);
                setValidateMsg(null);
              }}
            />

            <div className="mt-4 flex items-center gap-4">
              <button
                onClick={handleValidateJson}
                disabled={!jsonText.trim()}
                className="btn-secondary"
              >
                格式验证
              </button>
              <button
                onClick={handleCustomImport}
                disabled={customLoading || !jsonText.trim()}
                className="btn-primary"
              >
                {customLoading ? "导入中..." : "批量导入"}
              </button>
              <button
                onClick={() => {
                  setJsonText("");
                  setValidateMsg(null);
                  setCustomResult(null);
                  setCustomError(null);
                }}
                className="btn-ghost"
              >
                清空
              </button>
            </div>
          </div>

          {/* Validation message */}
          {validateMsg && (
            <div className={`rounded-lg border p-4 text-sm whitespace-pre-wrap ${
              validateMsg.startsWith("✅")
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-red-200 bg-red-50 text-red-800"
            }`}>
              {validateMsg}
            </div>
          )}

          {/* Error */}
          {customError && <ErrorState message={customError} onRetry={handleCustomImport} />}

          {/* Result */}
          {customResult && (
            <div className="soft-card p-6 space-y-4">
              <div className="success-banner">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold">批量导入完成</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">总计</span>
                  <p className="font-semibold text-lg text-slate-900">{customResult.total} 道</p>
                </div>
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">成功</span>
                  <p className="font-semibold text-lg text-green-600">{customResult.success} 道</p>
                </div>
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">失败</span>
                  <p className="font-semibold text-lg text-red-600">{customResult.failed} 道</p>
                </div>
              </div>

              {/* Detail list */}
              {customResult.results.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-slate-700 mb-2">导入明细</h3>
                  <ul className="space-y-2 max-h-64 overflow-y-auto">
                    {customResult.results.map((item) => (
                      <li
                        key={item.index}
                        className={`flex items-start justify-between rounded-lg border px-3 py-2 text-sm ${
                          item.status === "success"
                            ? "border-green-200 bg-green-50"
                            : "border-red-200 bg-red-50"
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <span className="text-xs text-slate-400">#{item.index + 1}</span>
                          {item.status === "success" ? (
                            <span className="ml-2 text-sm text-slate-800 truncate">{item.title}</span>
                          ) : (
                            <span className="ml-2 text-xs text-red-600">{item.error}</span>
                          )}
                        </div>
                        <span className={`ml-2 shrink-0 text-xs font-medium ${
                          item.status === "success" ? "text-green-600" : "text-red-600"
                        }`}>
                          {item.status === "success" ? "成功" : "失败"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <Link href="/questions" className="btn-primary">
                  查看题目列表 &rarr;
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: 简历导入 ──────────────────────────────────────── */}
      {activeTab === "resume" && (
        <div className="space-y-6">
          {/* File upload zone */}
          <div className="soft-card p-6">
            <h2 className="section-title mb-1">上传简历</h2>
            <p className="text-sm text-slate-500 mb-4">
              支持 PDF、DOCX、TXT、MD 格式，上传后将自动解析并生成针对性面试题
            </p>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
                transition-all duration-200
                ${
                  dragActive
                    ? "border-sky-400 bg-sky-50/60 scale-[1.01]"
                    : "border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50"
                }
                ${(uploading || resumeStreaming) ? "pointer-events-none opacity-60" : ""}
              `}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={handleFileSelect}
                className="hidden"
              />
              {uploading || resumeStreaming ? (
                <div className="flex flex-col items-center gap-3">
                  <svg
                    className="animate-spin h-8 w-8 text-sky-600"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  <div className="text-center">
                    {resumeStreaming ? (
                      <>
                        <TaskStatusBadge status="parsing" />
                        <p className="text-slate-500 text-sm mt-1">{resumeStreamMessage || "简历解析中，请稍候..."}</p>
                      </>
                    ) : (
                      <>
                        <TaskStatusBadge status="uploading" />
                        <p className="text-slate-500 text-sm mt-1">文件上传中，请稍候...</p>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <svg
                    className={`h-10 w-10 transition-colors ${
                      dragActive ? "text-sky-500" : "text-slate-400"
                    }`}
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3"
                    />
                  </svg>
                  <span className={`font-medium transition-colors ${
                    dragActive ? "text-sky-700" : "text-slate-700"
                  }`}>
                    拖拽文件到此处，或点击选择文件
                  </span>
                  <span className="text-sm text-slate-400">PDF, DOCX, TXT, MD</span>
                </div>
              )}
            </div>
          </div>

          {/* ── Resume streaming progress UI ─────────────────────── */}
          {resumeStreaming && (
            <div className="soft-card p-6 space-y-4">
              <div className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5 text-cyan-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-800">
                    {resumeStreamPhase === "reading" ? "读取简历" : resumeStreamPhase === "chunking" ? "切分内容" : resumeStreamPhase === "parsing" ? "解析经历" : resumeStreamPhase === "generating_questions" ? "生成题目" : "处理中"}
                  </p>
                  {resumeStreamMessage && (
                    <p className="text-xs text-slate-500">{resumeStreamMessage}</p>
                  )}
                </div>
                <span className="text-xs text-slate-400">{resumeStreamElapsed}s</span>
                <button
                  onClick={cancelResumeStream}
                  className="btn-ghost text-red-500 text-xs"
                >
                  取消
                </button>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round(resumeStreamProgress * 100)}%` }}
                />
              </div>

              {/* Saved chunks */}
              {resumeStreamSavedChunks.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-600 mb-1">已解析区块</p>
                  <ul className="space-y-1 max-h-40 overflow-y-auto">
                    {resumeStreamSavedChunks.map((chunk, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-green-600">
                        <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        <span>{chunk.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* ── Resume stream done ───────────────────────────────── */}
          {resumeStreamDone && !resumeStreamError && (
            <div className="soft-card p-6 space-y-4">
              <div className="success-banner">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold">简历解析完成</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">解析区块</span>
                  <p className="font-semibold text-lg text-green-600">{resumeStreamSavedChunks.length} 个</p>
                </div>
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">生成题目</span>
                  <p className="font-semibold text-lg text-green-600">{resumeStreamQuestionsGenerated} 道</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="soft-card px-3 py-2">
                  <span className="text-sm text-slate-500">耗时</span>
                  <p className="font-semibold text-lg text-slate-900">{resumeStreamElapsed}s</p>
                </div>
              </div>
              {resumeStreamSavedChunks.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-600 mb-1">已解析区块</p>
                  <ul className="space-y-1 max-h-40 overflow-y-auto">
                    {resumeStreamSavedChunks.map((chunk, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-green-600">
                        <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        <span>{chunk.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-3 pt-1">
                <Link
                  href={resumeStreamResumeId ? `/questions?source_type=resume&source_ref=${resumeStreamResumeId}` : "/questions?source_type=resume"}
                  className="btn-primary"
                >
                  查看简历生成的题目 &rarr;
                </Link>
                <Link href="/study" className="btn-secondary">
                  开始模拟面试
                </Link>
              </div>
            </div>
          )}

          {/* ── Resume stream error ─────────────────────────────── */}
          {resumeStreamDone && resumeStreamError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <svg className="mx-auto h-10 w-10 text-red-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-900 mb-1">简历解析失败</h3>
              <p className="text-sm text-gray-600 mb-4">{resumeStreamError}</p>
              <button
                onClick={() => {
                  setResumeStreamDone(false);
                  setResumeStreamError(null);
                  setResumeStreamSavedChunks([]);
                  setResumeStreamQuestionsGenerated(0);
                  setResumeStreamResumeId(null);
                }}
                className="px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
              >
                重试
              </button>
            </div>
          )}

          {/* Upload result with parse summary */}
          {uploadError && !resumeStreamDone && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <svg className="mx-auto h-10 w-10 text-red-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <h3 className="text-lg font-semibold text-gray-900 mb-1">简历解析失败</h3>
              <p className="text-sm text-gray-600 mb-4">{uploadError}</p>
              {uploadResult?.resume_id && (
                <button
                  onClick={() => handleReparse(uploadResult!.resume_id)}
                  disabled={uploading || resumeStreaming}
                  className="px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  重试
                </button>
              )}
            </div>
          )}

          {uploadResult && !resumeStreamDone && (
            <div className="soft-card p-6 space-y-4">
              <div className="success-banner">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold">简历上传并解析成功</p>
                </div>
              </div>

              {/* Summary cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {uploadResult.structured_summary?.name && (
                  <div className="soft-card px-4 py-3">
                    <span className="text-xs text-slate-500">姓名</span>
                    <p className="font-semibold text-slate-900">{uploadResult.structured_summary.name}</p>
                  </div>
                )}
                {uploadResult.structured_summary?.title && (
                  <div className="soft-card px-4 py-3">
                    <span className="text-xs text-slate-500">目标职位</span>
                    <p className="font-semibold text-slate-900">{uploadResult.structured_summary.title}</p>
                  </div>
                )}
                {uploadResult.structured_summary?.years_of_experience != null && (
                  <div className="soft-card px-4 py-3">
                    <span className="text-xs text-slate-500">工作年限</span>
                    <p className="font-semibold text-slate-900">{uploadResult.structured_summary.years_of_experience} 年</p>
                  </div>
                )}
                <div className="soft-card px-4 py-3">
                  <span className="text-xs text-slate-500">解析状态</span>
                  <p className="mt-0.5"><TaskStatusBadge status={uploadResult.parse_status} /></p>
                </div>
              </div>

              {/* Top skills */}
              {uploadResult.structured_summary?.top_skills && uploadResult.structured_summary.top_skills.length > 0 && (
                <div className="soft-card px-4 py-3">
                  <span className="text-xs text-slate-500">核心技能</span>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {uploadResult.structured_summary.top_skills.map((skill) => (
                      <span
                        key={skill}
                        className="primary-chip"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Project experience summary */}
              {uploadResult.structured_summary?.project_experience && uploadResult.structured_summary.project_experience.length > 0 && (
                <div className="soft-card px-4 py-3">
                  <span className="text-xs text-slate-500">项目经历</span>
                  <div className="mt-2 space-y-2">
                    {uploadResult.structured_summary.project_experience.slice(0, 3).map((proj, i) => (
                      <div key={i} className="border-l-2 border-sky-200 pl-3 py-1">
                        <p className="text-sm font-medium text-slate-800">
                          {proj.project_name || "未命名项目"}
                          {proj.role && (
                            <span className="text-xs text-slate-500 font-normal ml-2">{proj.role}</span>
                          )}
                        </p>
                        {proj.description && (
                          <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{proj.description}</p>
                        )}
                        {proj.technologies && proj.technologies.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {proj.technologies.slice(0, 5).map((tech) => (
                              <span key={tech} className="secondary-chip">
                                {tech}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Experiences count */}
              <div className="soft-card px-4 py-3">
                <span className="text-xs text-slate-500">提取经历</span>
                <p className="font-semibold text-slate-900">{uploadResult.experiences_count} 条</p>
              </div>

              {/* Next steps */}
              <div className="flex flex-wrap gap-3 pt-1">
                <Link
                  href={uploadResult.resume_id ? `/questions?source_type=resume&source_ref=${uploadResult.resume_id}` : "/questions?source_type=resume"}
                  className="btn-primary"
                >
                  查看简历生成的题目 &rarr;
                </Link>
                <Link
                  href="/study"
                  className="btn-secondary"
                >
                  开始模拟面试
                </Link>
                <button
                  onClick={() => handleReparse(uploadResult.resume_id)}
                  disabled={uploading || resumeStreaming}
                  className="btn-secondary disabled:opacity-50"
                >
                  重新解析
                </button>
              </div>
            </div>
          )}

          {/* Saved resumes list */}
          <div className="soft-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="section-title">已上传简历</h2>
              <button
                onClick={fetchResumes}
                className="btn-ghost"
              >
                刷新
              </button>
            </div>

            {listLoading ? (
              <LoadingState variant="spinner" message="加载简历列表中..." />
            ) : savedResumes.length === 0 ? (
              <EmptyState
                title="暂无简历"
                description="上传你的第一份简历，AI 将自动解析并生成针对性面试题"
              />
            ) : (
              <ul className="space-y-3">
                {savedResumes.map((resume) => (
                  <li
                    key={resume.id}
                    className="soft-card soft-card-hover p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-900 truncate">
                          {resume.file_name}
                        </span>
                        <TaskStatusBadge status={resume.parse_status} />
                      </div>
                      {resume.structured_summary && (
                        <div className="mt-1.5 text-xs text-slate-500 space-y-0.5">
                          {resume.structured_summary.title && (
                            <span>{resume.structured_summary.title}</span>
                          )}
                          {resume.structured_summary.top_skills && resume.structured_summary.top_skills.length > 0 && (
                            <span className="ml-2">
                              · {resume.structured_summary.top_skills.slice(0, 4).join("、")}
                            </span>
                          )}
                        </div>
                      )}
                      <p className="mt-0.5 text-xs text-slate-400">
                        {formatDate(resume.updated_at)}
                      </p>
                    </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Link
                          href={`/import/${resume.id}`}
                          className="btn-ghost"
                        >
                          查看详情
                        </Link>
                        <button
                          onClick={() => handleReparse(resume.id)}
                          disabled={uploading || resumeStreaming}
                          className="btn-ghost disabled:opacity-50"
                        >
                          重新解析
                        </button>
                        <button
                          onClick={() => handleDelete(resume.id)}
                          className="btn-ghost"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
