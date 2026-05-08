"use client";

import { useState, useRef } from "react";
import axios from "axios";

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

type Phase = "setup" | "interview" | "done";

const domains = ["RAG", "Backend", "Frontend", "Database", "DevOps", "Algorithm", "ML"];
const difficulties = [
  { value: "easy", label: "简单" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "困难" },
];

// ─── Page ────────────────────────────────────────────────────────────

export default function InterviewPage() {
  // Setup
  const [selectedDomain, setSelectedDomain] = useState("");
  const [selectedDifficulty, setSelectedDifficulty] = useState("medium");

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

  // ── Start Interview ────────────────────────────────────────────────

  const startInterview = async () => {
    if (!selectedDomain) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post<InterviewStartResponse>("/api/v1/ai/interview/start", {
        domain: selectedDomain,
        difficulty: selectedDifficulty,
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

  // ── Submit Answer ──────────────────────────────────────────────────

  const submitAnswer = async () => {
    if (!currentQuestion || !userAnswer.trim() || !sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post<AnswerResponse>("/api/v1/ai/interview/answer", {
        session_id: sessionId,
        user_answer: userAnswer.trim(),
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

  // ── Render: Setup ──────────────────────────────────────────────────

  if (phase === "setup") {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">模拟面试</h1>
        <p className="text-gray-600 mb-8">选择领域和难度，开始沉浸式 AI 面试体验</p>

        <div className="bg-white rounded-xl shadow-sm border p-8 space-y-6">
          {/* Domain */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">面试领域</label>
            <div className="flex flex-wrap gap-2">
              {domains.map((d) => (
                <button
                  key={d}
                  onClick={() => setSelectedDomain(d)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedDomain === d
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">难度</label>
            <div className="flex gap-2">
              {difficulties.map((d) => (
                <button
                  key={d.value}
                  onClick={() => setSelectedDifficulty(d.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedDifficulty === d.value
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
          )}

          <button
            onClick={startInterview}
            disabled={loading || !selectedDomain}
            className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-lg"
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
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">模拟面试</h1>
            <p className="text-sm text-gray-500 mt-1">
              领域: <span className="font-medium text-gray-700">{selectedDomain}</span>
              {" · "}难度: <span className="font-medium text-gray-700">{selectedDifficulty}</span>
              {" · "}第 {turns.length + 1} 轮
            </p>
          </div>
          <button
            onClick={resetInterview}
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            退出面试
          </button>
        </div>

        {/* Question */}
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{currentQuestion}</h2>
          <textarea
            ref={answerRef}
            rows={6}
            className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
            placeholder="在此输入你的回答..."
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            disabled={loading}
          />
          <button
            onClick={submitAnswer}
            disabled={loading || !userAnswer.trim()}
            className="mt-3 px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "提交中..." : "提交回答"}
          </button>
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
          )}
        </div>

        {/* Previous turns */}
        {turns.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">历史对话</h3>
            {turns.map((turn, i) => (
              <div key={i} className="bg-white rounded-lg shadow-sm border p-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium text-gray-500">第 {i + 1} 轮</span>
                  <span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span>
                </div>
                <p className="text-sm text-gray-700 mb-2 font-medium">{turn.question}</p>
                <details className="mb-2">
                  <summary className="text-xs text-gray-400 cursor-pointer">查看你的回答</summary>
                  <p className="mt-1 text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded p-2">{turn.answer}</p>
                </details>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm text-blue-900">{turn.feedback}</p>
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
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-8">
        <div className="text-5xl mb-4">&#127881;</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">面试结束</h1>
        <p className="text-gray-600">共 {totalTurns} 轮问答</p>
      </div>

      {/* Overall score */}
      {overallScore != null && (
        <div className="bg-white rounded-xl shadow-sm border p-8 mb-6 text-center">
          <div className={`text-6xl font-bold ${scoreColor(overallScore)} mb-2`}>{overallScore}</div>
          <div className="text-lg text-gray-600">综合评分</div>
          <div className="w-48 mx-auto mt-4 bg-gray-200 rounded-full h-3">
            <div
              className={`h-3 rounded-full ${scoreBarColor(overallScore)}`}
              style={{ width: `${overallScore}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold text-indigo-900 mb-3">面试总结</h3>
          <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{summary}</p>
        </div>
      )}

      {/* All turns */}
      <div className="space-y-4 mb-8">
        <h3 className="text-lg font-semibold text-gray-900">完整对话记录</h3>
        {turns.map((turn, i) => (
          <div key={i} className="bg-white rounded-lg shadow-sm border p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-500">第 {i + 1} 轮</span>
              <span className={`text-sm font-bold ${scoreColor(turn.score)}`}>{turn.score} 分</span>
            </div>
            <p className="text-sm text-gray-900 font-medium mb-1">{turn.question}</p>
            <details className="mb-2">
              <summary className="text-xs text-gray-400 cursor-pointer">查看回答</summary>
              <p className="mt-1 text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded p-2">{turn.answer}</p>
            </details>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-900">{turn.feedback}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-4 justify-center">
        <button
          onClick={resetInterview}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          再来一次
        </button>
        <a
          href="/stats"
          className="px-6 py-2.5 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
        >
          查看统计
        </a>
      </div>
    </div>
  );
}
