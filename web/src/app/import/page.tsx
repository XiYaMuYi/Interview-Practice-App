"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import LoadingState from "@/components/LoadingState";
import ErrorState from "@/components/ErrorState";
import EmptyState from "@/components/EmptyState";
import TaskStatusBadge from "@/components/TaskStatusBadge";

// ── Types ────────────────────────────────────────────────────────────

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

type TabKey = "questions" | "resume";

export default function ImportPage() {
  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>("resume");

  // ── Text import (questions tab) ──────────────────────────────────

  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ── File upload (resume tab) ─────────────────────────────────────

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<ResumeParseResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Saved resumes list
  const [savedResumes, setSavedResumes] = useState<ResumeRead[]>([]);
  const [listLoading, setListLoading] = useState(true);

  // ── Resume list ──────────────────────────────────────────────────

  const fetchResumes = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await axios.get<ResumeRead[]>("/api/v1/resumes");
      setSavedResumes(res.data);
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

  // ── File upload helpers ──────────────────────────────────────────

  const triggerParse = useCallback(async (resumeId: string) => {
    try {
      const res = await axios.post<ResumeParseResponse>(
        `/api/v1/resumes/${resumeId}/parse`
      );
      setUploadResult(res.data);
    } catch {
      setUploadError("简历解析失败，请检查后端服务状态");
    }
  }, []);

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
        await triggerParse(resumeId);
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
    [triggerParse, fetchResumes]
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
      setUploading(true);
      setUploadError(null);
      try {
        await triggerParse(resumeId);
        await fetchResumes();
      } finally {
        setUploading(false);
      }
    },
    [triggerParse, fetchResumes]
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
  ];

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">导入</h1>
      <p className="text-gray-600 mb-6">
        通过文本粘贴或简历上传，快速构建你的面试题库
      </p>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-8">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key);
              // Clear tab-specific state on switch
              if (tab.key === "questions") {
                setUploadResult(null);
                setUploadError(null);
              } else {
                setResult(null);
                setError(null);
              }
            }}
            className={`flex-1 flex flex-col items-center gap-1 py-3 px-4 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <span>{tab.label}</span>
            <span className="text-xs text-gray-400 font-normal">{tab.description}</span>
          </button>
        ))}
      </div>

      {/* ── Tab: 题目导入 ──────────────────────────────────────── */}
      {activeTab === "questions" && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">文本导入</h2>
            <label
              htmlFor="import-text"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              题目文本
            </label>
            <textarea
              id="import-text"
              rows={8}
              className="w-full border border-gray-300 rounded-lg p-3 font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
              placeholder={`在此粘贴题目文本...\n\n示例格式：\n题目：什么是闭包？\n难度：3\n分类：Frontend\n\n题目：请解释 React 的虚拟 DOM\n难度：3\n分类：Frontend`}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div className="mt-4 flex items-center gap-4">
              <button
                onClick={handleImport}
                disabled={loading || !text.trim()}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "导入中..." : "导入"}
              </button>
              <button
                onClick={() => setText("")}
                className="px-4 py-2.5 text-gray-600 hover:text-gray-900 transition-colors"
              >
                清空
              </button>
            </div>
          </div>

          {error && <ErrorState message={error} onRetry={handleImport} />}

          {result && (
            <div className="p-5 bg-green-50 border border-green-200 rounded-lg space-y-3">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-green-700 font-semibold">文本导入成功</p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-green-100/60 rounded px-3 py-2">
                  <span className="text-green-600">提取题目</span>
                  <p className="text-green-800 font-semibold text-lg">{result.questions_extracted} 道</p>
                </div>
                <div className="bg-green-100/60 rounded px-3 py-2">
                  <span className="text-green-600">知识节点</span>
                  <p className="text-green-800 font-semibold text-lg">{result.knowledge_nodes} 个</p>
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <Link
                  href="/questions"
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  查看题目列表 &rarr;
                </Link>
                <Link
                  href="/study"
                  className="px-4 py-2 border border-green-300 text-green-700 rounded-lg text-sm font-medium hover:bg-green-100 transition-colors"
                >
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

      {/* ── Tab: 简历导入 ──────────────────────────────────────── */}
      {activeTab === "resume" && (
        <div className="space-y-6">
          {/* File upload zone */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">上传简历</h2>
            <p className="text-sm text-gray-500 mb-4">
              支持 PDF、DOCX、TXT、MD 格式，上传后将自动解析并生成针对性面试题
            </p>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                transition-colors
                ${
                  dragActive
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-300 hover:border-gray-400 bg-gray-50"
                }
                ${uploading ? "pointer-events-none opacity-60" : ""}
              `}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={handleFileSelect}
                className="hidden"
              />
              {uploading ? (
                <div className="flex flex-col items-center gap-3">
                  <svg
                    className="animate-spin h-8 w-8 text-blue-600"
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
                    <TaskStatusBadge status="uploading" />
                    <p className="text-gray-500 text-sm mt-1">文件上传中，请稍候...</p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <svg
                    className="h-10 w-10 text-gray-400"
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
                  <span className="text-gray-700 font-medium">
                    拖拽文件到此处，或点击选择文件
                  </span>
                  <span className="text-sm text-gray-400">PDF, DOCX, TXT, MD</span>
                </div>
              )}
            </div>
          </div>

          {/* Upload result with parse summary */}
          {uploadError && (
            <ErrorState
              title="简历解析失败"
              message={uploadError}
              onRetry={() => {
                if (uploadResult?.resume_id) {
                  handleReparse(uploadResult.resume_id);
                }
              }}
            />
          )}

          {uploadResult && (
            <div className="p-5 bg-green-50 border border-green-200 rounded-lg space-y-4">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-green-700 font-semibold">简历上传并解析成功</p>
              </div>

              {/* Summary cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {uploadResult.structured_summary?.name && (
                  <div className="bg-white/70 rounded-lg px-4 py-3">
                    <span className="text-xs text-gray-500">姓名</span>
                    <p className="font-semibold text-gray-900">{uploadResult.structured_summary.name}</p>
                  </div>
                )}
                {uploadResult.structured_summary?.title && (
                  <div className="bg-white/70 rounded-lg px-4 py-3">
                    <span className="text-xs text-gray-500">目标职位</span>
                    <p className="font-semibold text-gray-900">{uploadResult.structured_summary.title}</p>
                  </div>
                )}
                {uploadResult.structured_summary?.years_of_experience != null && (
                  <div className="bg-white/70 rounded-lg px-4 py-3">
                    <span className="text-xs text-gray-500">工作年限</span>
                    <p className="font-semibold text-gray-900">{uploadResult.structured_summary.years_of_experience} 年</p>
                  </div>
                )}
                <div className="bg-white/70 rounded-lg px-4 py-3">
                  <span className="text-xs text-gray-500">解析状态</span>
                  <p className="mt-0.5"><TaskStatusBadge status={uploadResult.parse_status} /></p>
                </div>
              </div>

              {/* Top skills */}
              {uploadResult.structured_summary?.top_skills && uploadResult.structured_summary.top_skills.length > 0 && (
                <div className="bg-white/70 rounded-lg px-4 py-3">
                  <span className="text-xs text-gray-500">核心技能</span>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {uploadResult.structured_summary.top_skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-full text-xs font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Project experience summary */}
              {uploadResult.structured_summary?.project_experience && uploadResult.structured_summary.project_experience.length > 0 && (
                <div className="bg-white/70 rounded-lg px-4 py-3">
                  <span className="text-xs text-gray-500">项目经历</span>
                  <div className="mt-2 space-y-2">
                    {uploadResult.structured_summary.project_experience.slice(0, 3).map((proj, i) => (
                      <div key={i} className="border-l-2 border-indigo-200 pl-3 py-1">
                        <p className="text-sm font-medium text-gray-800">
                          {proj.project_name || "未命名项目"}
                          {proj.role && (
                            <span className="text-xs text-gray-500 font-normal ml-2">{proj.role}</span>
                          )}
                        </p>
                        {proj.description && (
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{proj.description}</p>
                        )}
                        {proj.technologies && proj.technologies.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {proj.technologies.slice(0, 5).map((tech) => (
                              <span key={tech} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
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
              <div className="bg-white/70 rounded-lg px-4 py-3">
                <span className="text-xs text-gray-500">提取经历</span>
                <p className="font-semibold text-gray-900">{uploadResult.experiences_count} 条</p>
              </div>

              {/* Next steps */}
              <div className="flex flex-wrap gap-3 pt-1">
                <Link
                  href="/questions?source=resume"
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  查看简历生成的题目 &rarr;
                </Link>
                <Link
                  href="/study"
                  className="px-4 py-2 border border-green-300 text-green-700 rounded-lg text-sm font-medium hover:bg-green-100 transition-colors"
                >
                  开始模拟面试
                </Link>
                <button
                  onClick={() => handleReparse(uploadResult.resume_id)}
                  disabled={uploading}
                  className="px-4 py-2 border border-green-300 text-green-700 rounded-lg text-sm font-medium hover:bg-green-100 transition-colors disabled:opacity-50"
                >
                  重新解析
                </button>
              </div>
            </div>
          )}

          {/* Saved resumes list */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">已上传简历</h2>
              <button
                onClick={fetchResumes}
                className="text-sm text-blue-600 hover:underline"
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
                    className="flex items-start justify-between gap-4 border border-gray-100 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 truncate">
                          {resume.file_name}
                        </span>
                        <TaskStatusBadge status={resume.parse_status} />
                      </div>
                      {resume.structured_summary && (
                        <div className="mt-1.5 text-xs text-gray-500 space-y-0.5">
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
                      <p className="mt-0.5 text-xs text-gray-400">
                        {formatDate(resume.updated_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link
                        href={`/import/${resume.id}`}
                        className="px-3 py-1 text-xs text-indigo-600 border border-indigo-300 rounded hover:bg-indigo-50 transition-colors"
                      >
                        查看详情
                      </Link>
                      <button
                        onClick={() => handleReparse(resume.id)}
                        disabled={uploading}
                        className="px-3 py-1 text-xs text-blue-600 border border-blue-300 rounded hover:bg-blue-50 disabled:opacity-50 transition-colors"
                      >
                        重新解析
                      </button>
                      <button
                        onClick={() => handleDelete(resume.id)}
                        className="px-3 py-1 text-xs text-red-600 border border-red-300 rounded hover:bg-red-50 transition-colors"
                      >
                        删除
                      </button>
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
