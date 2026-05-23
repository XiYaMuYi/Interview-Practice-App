"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { EmptyState, LoadingState } from "@/components/states";
import TaskStatusBadge from "@/components/TaskStatusBadge";

// ─── Types ───────────────────────────────────────────────────────────

interface InterviewStartResponse {
  session_id: string;
  first_question: string;
  domain: string;
  difficulty: string;
  max_turns: number;
}

interface AnswerResponse {
  feedback: string;
  score: number;
  next_question: string | null;
  follow_up: string | null;
  is_done: boolean;
  summary: string | null;
  overall_score: number | null;
  total_turns: number;
}

interface StructuredSummary {
  name?: string;
  title?: string;
  years_of_experience?: number;
  top_skills?: string[];
  summary?: string;
}

interface ResumeItem {
  id: string;
  file_name: string;
  parse_status: string;
  structured_summary: StructuredSummary | null;
}

type Phase = "setup" | "interview" | "done";
type InterviewMode = "general" | "resume";

const LLM_MODEL = process.env.NEXT_PUBLIC_LLM_MODEL ?? "qwen3-vl-plus";
const domains = ["RAG检索增强", "Agent智能体", "LangGraph工作流", "LLM应用开发", "模型微调", "Prompt工程", "向量数据库", "多模态处理", "Text-to-SQL", "OCR文档解析", "MCP协议", "Function Calling", "vLLM部署", "FastAPI后端"];
const difficulties = [
  { value: "easy", label: "简单" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "困难" },
];

// ─── Page ────────────────────────────────────────────────────────────

export default function InterviewPage() {
  // Mode
  const [mode, setMode] = useState<InterviewMode>("general");

  // Setup
  const [selectedDomain, setSelectedDomain] = useState("");
  const [selectedDifficulty, setSelectedDifficulty] = useState("medium");

  // Resume mode
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null);
  const [loadingResumes, setLoadingResumes] = useState(false);
  const [selectedResumeName, setSelectedResumeName] = useState("");

  // Interview
  const [phase, setPhase] = useState<Phase>("setup");
  const [sessionId, setSessionId] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [userAnswer, setUserAnswer] = useState("");
  const [turns, setTurns] = useState<{ question: string; answer: string; feedback: string; score: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Done
  const [summary, setSummary] = useState("");
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [totalTurns, setTotalTurns] = useState(0);

  const answerRef = useRef<HTMLTextAreaElement>(null);

  const [resumesLoaded, setResumesLoaded] = useState(false);

  // Load resumes when switching to resume mode
  useEffect(() => {
    if (mode !== "resume" || resumesLoaded) return;
    const loadResumes = async () => {
      setLoadingResumes(true);
      try {
        const res = await axios.get("/api/v1/resumes", { params: { page: 1, page_size: 20 } });
        setResumes(res.data.items);
        setResumesLoaded(true);
      } catch {
        // silently ignore — EmptyState will handle it
      } finally {
        setLoadingResumes(false);
      }
    };
    loadResumes();
  }, [mode, resumesLoaded]);

  // ── Start Interview ────────────────────────────────────────────────

  const startInterview = async () => {
    if (!selectedDomain) return;
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, string> = {
        domain: selectedDomain,
        difficulty: selectedDifficulty,
      };
      if (mode === "resume" && selectedResumeId) {
        body.resume_id = selectedResumeId;
      }
      const res = await axios.post<InterviewStartResponse>("/api/v1/ai/interview/start", body);
      setSessionId(res.data.session_id);
      setCurrentQuestion(res.data.first_question);
      setTurns([]);
      setPhase("interview");
      setUserAnswer("");
      setTimeout(() => answerRef.current?.focus(), 100);
    } catch {
      setError("开始面试失败，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  };

  // ── Submit Answer ──────────────────────────────────────────────────

  const submitAnswer = async () => {
    if (!currentQuestion || !userAnswer.trim() || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post<AnswerResponse>("/api/v1/ai/interview/answer", {
        session_id: sessionId,
        answer: userAnswer.trim(),
      });

      const newTurn = {
        question: currentQuestion,
        answer: userAnswer.trim(),
        feedback: res.data.feedback,
        score: res.data.score,
      };

      if (res.data.is_done) {
        setTurns((prev) => [...prev, newTurn]);
        setSummary(res.data.summary || "");
        setOverallScore(res.data.overall_score ?? null);
        setTotalTurns(res.data.total_turns);
        setPhase("done");
      } else {
        setTurns((prev) => [...prev, newTurn]);
        setCurrentQuestion(res.data.next_question || res.data.follow_up || "");
        setUserAnswer("");
        setTimeout(() => answerRef.current?.focus(), 100);
      }
    } catch {
      setError("提交回答失败，请检查网络连接");
    } finally {
      setLoading(false);
    }
  };

  // ── Reset ──────────────────────────────────────────────────────────

  const resetInterview = () => {
    setPhase("setup");
    setSessionId("");
    setCurrentQuestion("");
    setUserAnswer("");
    setTurns([]);
    setSummary("");
    setOverallScore(null);
    setTotalTurns(0);
    setError(null);
    setSelectedResumeId(null);
    setSelectedResumeName("");
  };

  const switchMode = (newMode: InterviewMode) => {
    setMode(newMode);
    if (phase !== "setup") resetInterview();
  };

  // ── Score helpers ──────────────────────────────────────────────────

  function scoreColor(score: number) {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  }

  function scoreBarColor(score: number) {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-500";
    return "bg-red-500";
  }

  // ── Resume mode badge ──────────────────────────────────────────────

  const resumeBadge = mode === "resume" && phase !== "setup" && (
    <div className="mb-4">
      <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 border border-rose-200">
        <span className="w-2 h-2 rounded-full bg-rose-500" />
        简历模式：{selectedResumeName}
      </span>
    </div>
  );

  // ── Render: Setup ──────────────────────────────────────────────────

  if (phase === "setup") {
    return (
      <div className="page-frame-tight">
        <h1 className="page-title">模拟面试</h1>
        <p className="page-subtitle">选择领域和难度，开始沉浸式 AI 面试体验</p>

        <div className="soft-card p-8 space-y-6">
          {/* Mode selector */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">面试模式</label>
            <div className="flex gap-2">
              <button
                onClick={() => switchMode("general")}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                  mode === "general"
                    ? "bg-sky-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                通用模式
              </button>
              <button
                onClick={() => switchMode("resume")}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                  mode === "resume"
                    ? "bg-sky-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                简历模式
              </button>
            </div>
          </div>

          {/* Resume selection */}
          {mode === "resume" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">选择简历</label>
              {loadingResumes ? (
                <LoadingState variant="spinner" message="加载简历中..." />
              ) : resumes.length === 0 ? (
                <EmptyState
                  title="暂无简历"
                  description="请先上传简历，才能使用简历模式进行面试"
                  actionLabel="去导入简历"
                  actionHref="/import"
                />
              ) : (
                <ul className="space-y-2 max-h-64 overflow-y-auto">
                  {resumes.map((r) => (
                    <li
                      key={r.id}
                      onClick={() => {
                        setSelectedResumeId(r.id);
                        setSelectedResumeName(r.file_name);
                      }}
                      className={`flex items-center justify-between gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        selectedResumeId === r.id
                          ? "border-sky-400 bg-sky-50"
                          : "border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-900 truncate">{r.file_name}</p>
                        {r.structured_summary?.top_skills && r.structured_summary.top_skills.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {r.structured_summary.top_skills.slice(0, 4).map((s) => (
                              <span key={s} className="primary-chip">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0">
                        <TaskStatusBadge status={r.parse_status} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Domain */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">面试领域</label>
            <div className="flex flex-wrap gap-2">
              {domains.map((d) => (
                <button
                  key={d}
                  onClick={() => setSelectedDomain(d)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                    selectedDomain === d
                      ? "bg-sky-600 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">难度</label>
            <div className="flex gap-2">
              {difficulties.map((d) => (
                <button
                  key={d.value}
                  onClick={() => setSelectedDifficulty(d.value)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                    selectedDifficulty === d.value
                      ? "bg-sky-600 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="error-banner">{error}</div>
          )}

          <button
            onClick={startInterview}
            disabled={loading || !selectedDomain || (mode === "resume" && !selectedResumeId)}
            className="btn-primary-lg w-full"
          >
            {loading ? "准备中..." : "开始面试"}
          </button>
        </div>
      </div>
    );
  }

  // ── Render: Interview ──────────────────────────────────────────────

  if (phase === "interview") {
    return (
      <div className="page-frame-tight">
        {resumeBadge}

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="page-title">模拟面试</h1>
            <p className="section-hint mt-1">
              {mode === "resume" && <span>简历模式 · </span>}
              领域: <span className="font-medium text-slate-700">{selectedDomain}</span>
              {" · "}难度: <span className="font-medium text-slate-700">{selectedDifficulty}</span>
              {" · "}模型: <span className="font-medium text-slate-700">{LLM_MODEL}</span>
              {" · "}第 {turns.length + 1} 轮
            </p>
          </div>
          <button
            onClick={resetInterview}
            className="btn-ghost text-sm"
          >
            退出面试
          </button>
        </div>

        {/* Question */}
        <div className="soft-card p-6 mb-6">
          <h2 className="section-title mb-4">{currentQuestion}</h2>
          <textarea
            ref={answerRef}
            rows={6}
            className="form-textarea disabled:bg-gray-100 disabled:cursor-not-allowed"
            placeholder="在此输入你的回答..."
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            disabled={loading}
          />
          <button
            onClick={submitAnswer}
            disabled={loading || !userAnswer.trim()}
            className="btn-primary mt-3 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                提交中...
              </>
            ) : (
              "提交回答"
            )}
          </button>
          {error && (
            <div className="mt-3 error-banner">{error}</div>
          )}
        </div>

        {/* Previous turns */}
        {turns.length > 0 && (
          <div className="space-y-4">
            <h3 className="section-hint uppercase tracking-wide">历史对话</h3>
            {turns.map((turn, i) => (
              <div key={i} className="soft-card p-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium text-slate-500">第 {i + 1} 轮</span>
                  <span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span>
                </div>
                <p className="text-sm text-slate-700 mb-2 font-medium">{turn.question}</p>
                <details className="mb-2">
                  <summary className="text-xs text-slate-400 cursor-pointer">查看你的回答</summary>
                  <p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap bg-slate-50/70 rounded-xl p-3">{turn.answer}</p>
                </details>
                <div className="bg-sky-50/70 border border-sky-200 rounded-xl p-3">
                  <p className="text-sm text-sky-900">{turn.feedback}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Render: Done ───────────────────────────────────────────────────

  return (
    <div className="page-frame-tight">
      {resumeBadge}

      <div className="text-center mb-8">
        <div className="text-5xl mb-4">&#127881;</div>
        <h1 className="page-title">面试结束</h1>
        <p className="section-hint">共 {totalTurns} 轮问答</p>
      </div>

      {/* Overall score */}
      {overallScore != null && (
        <div className="soft-card p-8 mb-6 text-center">
          <div className={`text-6xl font-bold ${scoreColor(overallScore)} mb-2`}>{overallScore}</div>
          <div className="text-lg text-slate-600">综合评分</div>
          <div className="w-48 mx-auto mt-4 progress-track h-3">
            <div
              className={`h-3 rounded-full transition-all ${scoreBarColor(overallScore)}`}
              style={{ width: `${overallScore}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="bg-violet-50/80 border border-violet-200 rounded-xl p-6 mb-6">
          <h3 className="section-title text-violet-900 mb-3">面试总结</h3>
          <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{summary}</p>
        </div>
      )}

      {/* All turns */}
      <div className="space-y-4 mb-8">
        <h3 className="section-title">完整对话记录</h3>
        {turns.map((turn, i) => (
          <div key={i} className="soft-card p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-slate-500">第 {i + 1} 轮</span>
              <span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span>
            </div>
            <p className="text-sm text-slate-900 font-medium mb-1">{turn.question}</p>
            <details className="mb-2">
              <summary className="text-xs text-slate-400 cursor-pointer">查看回答</summary>
              <p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap bg-slate-50/70 rounded-xl p-2">{turn.answer}</p>
            </details>
            <div className="bg-sky-50/70 border border-sky-200 rounded-xl p-3">
              <p className="text-sm text-sky-900">{turn.feedback}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-4 justify-center">
        <button
          onClick={resetInterview}
          className="btn-primary"
        >
          再来一次
        </button>
        <a
          href="/stats"
          className="btn-secondary"
        >
          查看统计
        </a>
      </div>
    </div>
  );
}
