"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { EmptyState, LoadingState } from "@/components/states";
import TaskStatusBadge from "@/components/TaskStatusBadge";
import AuthRouteGuard from "@/components/AuthRouteGuard";

// ─── Types ───────────────────────────────────────────────────────────

interface InterviewStartResponse {
  session_id: string;
  first_question: string;
  max_turns: number;
}

interface ResumeSummary {
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
  structured_summary: ResumeSummary | null;
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

export default function InterviewPage() {
  const [mode, setMode] = useState<InterviewMode>("general");
  const [selectedDomain, setSelectedDomain] = useState("");
  const [selectedDifficulty, setSelectedDifficulty] = useState("medium");
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null);
  const [loadingResumes, setLoadingResumes] = useState(false);
  const [selectedResumeName, setSelectedResumeName] = useState("");
  const [phase, setPhase] = useState<Phase>("setup");
  const [sessionId, setSessionId] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [userAnswer, setUserAnswer] = useState("");
  const [turns, setTurns] = useState<{ question: string; answer: string; feedback: string; score: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [totalTurns, setTotalTurns] = useState(0);
  const [streamingFeedback, setStreamingFeedback] = useState("");
  const [streamingSummary, setStreamingSummary] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamPhase, setStreamPhase] = useState<string>("");
  const [streamScore, setStreamScore] = useState<number | null>(null);
  const answerRef = useRef<HTMLTextAreaElement>(null);
  const [resumesLoaded, setResumesLoaded] = useState(false);

  useEffect(() => {
    if (mode !== "resume" || resumesLoaded) return;
    const loadResumes = async () => {
      setLoadingResumes(true);
      try {
        const res = await api.get("/api/v1/resumes", { params: { page: 1, page_size: 20 } });
        setResumes(res.data.items);
        setResumesLoaded(true);
      } catch {
      } finally {
        setLoadingResumes(false);
      }
    };
    loadResumes();
  }, [mode, resumesLoaded]);

  const startInterview = async () => {
    if (!selectedDomain) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<InterviewStartResponse>("/api/v1/ai/interview/start", {
        domain: selectedDomain,
        max_turns: 5,
      });
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

  const consumeSSEStream = useCallback(async (url: string, body: Record<string, unknown>) => {
    setIsStreaming(true);
    setStreamingFeedback("");
    setStreamingSummary("");
    setStreamPhase("evaluating");
    setStreamScore(null);

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok || !res.body) throw new Error(`Stream request failed: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventType = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) {
          const data = JSON.parse(line.slice(5).trim());
          const type = String(data.event_type || eventType || "message");
          if (type === "progress") setStreamPhase(data.current || data.phase || "");
          else if (type === "evaluation") { setStreamScore(data.score); setStreamingFeedback(data.feedback || ""); }
          else if (data.token) setStreamingSummary((prev) => prev + String(data.token));
          else if (data.content) setStreamingSummary(data.content);
          else if (type === "summary" || data.summary) setStreamingSummary(data.summary || "");
          else if (type === "followup" || data.followup_question) setStreamPhase("followup_ready");
          else if (type === "done" || data.status === "done") return data;
          else if (type === "error" || data.error) throw new Error(data.error || "Stream error");
          eventType = "";
        }
      }
    }
  }, []);

  const submitAnswer = async () => {
    if (!currentQuestion || !userAnswer.trim() || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const doneData = await consumeSSEStream("/api/v1/ai/interview/turn-stream", {
        session_id: sessionId,
        current_turn: turns.length + 1,
        max_turns: 5,
        question_text: currentQuestion,
        user_answer: userAnswer.trim(),
      });
      const newTurn = { question: currentQuestion, answer: userAnswer.trim(), feedback: streamingFeedback || doneData?.feedback || "", score: streamScore ?? doneData?.score ?? 0 };
      if (doneData?.is_done || !doneData?.followup_question) {
        setTurns((prev) => [...prev, newTurn]);
        setSummary(doneData?.summary || streamingSummary || doneData?.feedback || "");
        setOverallScore(doneData?.score ?? streamScore);
        setTotalTurns(turns.length + 1);
        setPhase("done");
      } else {
        setTurns((prev) => [...prev, newTurn]);
        setCurrentQuestion(doneData.followup_question);
        setUserAnswer("");
        setTimeout(() => answerRef.current?.focus(), 100);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "提交回答失败，请检查网络连接");
    } finally {
      setLoading(false);
      setIsStreaming(false);
    }
  };

  const resetInterview = () => {
    setPhase("setup"); setSessionId(""); setCurrentQuestion(""); setUserAnswer(""); setTurns([]); setSummary(""); setOverallScore(null); setTotalTurns(0); setError(null); setSelectedResumeId(null); setSelectedResumeName(""); setIsStreaming(false); setStreamingFeedback(""); setStreamingSummary(""); setStreamPhase(""); setStreamScore(null);
  };

  const switchMode = (newMode: InterviewMode) => { setMode(newMode); if (phase !== "setup") resetInterview(); };
  function scoreColor(score: number) { if (score >= 80) return "text-green-600"; if (score >= 60) return "text-yellow-600"; return "text-red-600"; }
  function scoreBarColor(score: number) { if (score >= 80) return "bg-green-500"; if (score >= 60) return "bg-yellow-500"; return "bg-red-500"; }

  const resumeBadge = mode === "resume" && phase !== "setup" && (
    <div className="mb-4"><span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 border border-rose-200"><span className="w-2 h-2 rounded-full bg-rose-500" />简历模式：{selectedResumeName}</span></div>
  );

  if (phase === "setup") {
    return (
      <AuthRouteGuard>
        <div className="page-frame-tight">
          <h1 className="page-title">模拟面试</h1>
          <p className="page-subtitle">选择领域和难度，开始沉浸式 AI 面试体验</p>
          <div className="soft-card p-8 space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">面试模式</label>
              <div className="flex gap-2">
                <button onClick={() => switchMode("general")} className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${mode === "general" ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>通用模式</button>
                <button onClick={() => switchMode("resume")} className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${mode === "resume" ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>简历模式</button>
              </div>
            </div>
            {mode === "resume" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">选择简历</label>
                {loadingResumes ? <LoadingState variant="spinner" message="加载简历中..." /> : resumes.length === 0 ? <EmptyState title="暂无简历" description="请先上传简历，才能使用简历模式进行面试" actionLabel="去导入简历" actionHref="/import" /> : <ul className="space-y-2 max-h-64 overflow-y-auto">{resumes.map((r) => (<li key={r.id} onClick={() => { setSelectedResumeId(r.id); setSelectedResumeName(r.file_name); }} className={`flex items-center justify-between gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${selectedResumeId === r.id ? "border-sky-400 bg-sky-50" : "border-slate-200 hover:bg-slate-50"}`}><div className="min-w-0 flex-1"><p className="text-sm font-medium text-slate-900 truncate">{r.file_name}</p>{r.structured_summary?.top_skills && r.structured_summary.top_skills.length > 0 && <div className="flex flex-wrap gap-1 mt-1">{r.structured_summary.top_skills.slice(0, 4).map((s) => (<span key={s} className="primary-chip">{s}</span>))}</div>}</div><div className="shrink-0"><TaskStatusBadge status={r.parse_status} /></div></li>))}</ul>}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">面试领域</label>
              <div className="flex flex-wrap gap-2">{domains.map((d) => (<button key={d} onClick={() => setSelectedDomain(d)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${selectedDomain === d ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>{d}</button>))}</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">难度</label>
              <div className="flex gap-2">{difficulties.map((d) => (<button key={d.value} onClick={() => setSelectedDifficulty(d.value)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${selectedDifficulty === d.value ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>{d.label}</button>))}</div>
            </div>
            {error && <div className="error-banner">{error}</div>}
            <button onClick={startInterview} disabled={loading || !selectedDomain || (mode === "resume" && !selectedResumeId)} className="btn-primary-lg w-full">{loading ? "准备中..." : "开始面试"}</button>
          </div>
        </div>
      </AuthRouteGuard>
    );
  }

  if (phase === "interview") {
    return (
      <AuthRouteGuard>
        <div className="page-frame-tight">{resumeBadge}<div className="flex items-center justify-between mb-6"><div><h1 className="page-title">模拟面试</h1><p className="section-hint mt-1">{mode === "resume" && <span>简历模式 · </span>}领域: <span className="font-medium text-slate-700">{selectedDomain}</span>{" · "}难度: <span className="font-medium text-slate-700">{selectedDifficulty}</span>{" · "}模型: <span className="font-medium text-slate-700">{LLM_MODEL}</span>{" · "}第 {turns.length + 1} 轮</p></div><button onClick={resetInterview} className="btn-ghost text-sm">退出面试</button></div><div className="soft-card p-6 mb-6"><h2 className="section-title mb-4">{currentQuestion}</h2><textarea ref={answerRef} rows={6} className="form-textarea disabled:bg-gray-100 disabled:cursor-not-allowed" placeholder="在此输入你的回答..." value={userAnswer} onChange={(e) => setUserAnswer(e.target.value)} disabled={loading} /><button onClick={submitAnswer} disabled={loading || isStreaming || !userAnswer.trim()} className="btn-primary mt-3 flex items-center justify-center gap-2">{loading || isStreaming ? (<><svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>{isStreaming ? `AI 思考中${streamPhase ? ` · ${streamPhase}` : ""}...` : "提交中..."}</>) : ("提交回答")}</button>{isStreaming && (<div className="mt-4 p-4 rounded-lg bg-slate-50 border border-slate-200">{streamScore != null && (<div className="flex items-center gap-3 mb-2"><span className="text-sm text-slate-500">本轮评分</span><span className={`text-lg font-bold ${scoreColor(streamScore)}`}>{streamScore} 分</span></div>)}{streamingFeedback && !streamingSummary && (<details className="mb-2"><summary className="text-xs text-slate-400 cursor-pointer">查看即时反馈</summary><p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap bg-white rounded p-2 border border-slate-100">{streamingFeedback}</p></details>)}{streamingSummary && (<div className="mt-2"><p className="text-xs font-medium text-slate-500 mb-1">总结生成中...</p><div className="whitespace-pre-wrap text-sm text-slate-800 max-h-48 overflow-y-auto p-3 bg-white rounded border border-slate-100">{streamingSummary}<span className="inline-block w-1.5 h-4 bg-sky-500 ml-0.5 animate-pulse" /></div></div>)}{!streamingFeedback && !streamingSummary && (<div className="text-sm text-slate-400 text-center py-2 animate-pulse">正在处理回答...</div>)}</div>)}{error && (<div className="mt-3 error-banner">{error}</div>)}</div>{turns.length > 0 && (<div className="space-y-4"><h3 className="section-hint uppercase tracking-wide">历史对话</h3>{turns.map((turn, i) => (<div key={i} className="soft-card p-5"><div className="flex items-center gap-2 mb-2"><span className="text-xs font-medium text-slate-500">第 {i + 1} 轮</span><span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span></div><p className="text-sm text-slate-700 mb-2 font-medium">{turn.question}</p><details className="mb-2"><summary className="text-xs text-slate-400 cursor-pointer">查看你的回答</summary><p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap bg-slate-50/70 rounded-xl p-3">{turn.answer}</p></details><div className="bg-sky-50/70 border border-sky-200 rounded-xl p-3"><p className="text-sm text-sky-900">{turn.feedback}</p></div></div>))}</div>)}
        </div>
      </AuthRouteGuard>
    );
  }

  return (
    <AuthRouteGuard>
      <div className="page-frame-tight">{resumeBadge}<div className="text-center mb-8"><div className="text-5xl mb-4">🎉</div><h1 className="page-title">面试结束</h1><p className="section-hint">共 {totalTurns} 轮问答</p></div>{overallScore != null && (<div className="soft-card p-8 mb-6 text-center"><div className={`text-6xl font-bold ${scoreColor(overallScore)} mb-2`}>{overallScore}</div><div className="text-lg text-slate-600">综合评分</div><div className="w-48 mx-auto mt-4 progress-track h-3"><div className={`h-3 rounded-full transition-all ${scoreBarColor(overallScore)}`} style={{ width: `${overallScore}%` }} /></div></div>)}{summary && (<div className="bg-violet-50/80 border border-violet-200 rounded-xl p-6 mb-6"><h3 className="section-title text-violet-900 mb-3">面试总结</h3><p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{summary}</p></div>)}<div className="space-y-4 mb-8"><h3 className="section-title">完整对话记录</h3>{turns.map((turn, i) => (<div key={i} className="soft-card p-5"><div className="flex items-center gap-2 mb-2"><span className="text-xs font-medium text-slate-500">第 {i + 1} 轮</span><span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span></div><p className="text-sm text-slate-900 font-medium mb-1">{turn.question}</p><details className="mb-2"><summary className="text-xs text-slate-400 cursor-pointer">查看回答</summary><p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap bg-slate-50/70 rounded-xl p-2">{turn.answer}</p></details><div className="bg-sky-50/70 border border-sky-200 rounded-xl p-3"><p className="text-sm text-sky-900">{turn.feedback}</p></div></div>))}</div><div className="flex gap-4 justify-center"><button onClick={resetInterview} className="btn-primary">再来一次</button><a href="/stats" className="btn-secondary">查看统计</a></div></div>
    </AuthRouteGuard>
  );
}
