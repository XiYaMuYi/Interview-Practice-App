"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import api from "@/lib/api";
import { authFetch } from "@/lib/auth";

interface Question {
  id: string;
  title: string;
  content: string;
  difficulty_level: number | null;
  domain_type: string | null;
  answered: boolean;
  score: number | null;
  user_answer?: string | null;
  feedback?: string | null;
}

interface ExamSession {
  id: string;
  title: string;
  duration_minutes: number;
  total_questions: number;
  status: string;
  started_at: string | null;
  submitted_at: string | null;
  total_score: number | null;
  questions: Question[];
}

const difficultyLabels: Record<number, string> = {
  1: "入门",
  2: "简单",
  3: "中等",
  4: "困难",
  5: "专家",
};

const difficultyColors: Record<number, string> = {
  1: "bg-green-100 text-green-700",
  2: "bg-blue-100 text-blue-700",
  3: "bg-yellow-100 text-yellow-700",
  4: "bg-orange-100 text-orange-700",
  5: "bg-red-100 text-red-700",
};

export default function ExamSessionPage() {
  const router = useRouter();
  const params = useParams();
  const examId = params?.id as string;

  const [exam, setExam] = useState<ExamSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [timeLeft, setTimeLeft] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [grading, setGrading] = useState(false);
  const [gradingProgress, setGradingProgress] = useState({ graded: 0, total: 0 });
  const [gradingSummary, setGradingSummary] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const gradingAbortRef = useRef<AbortController | null>(null);

  // Load exam
  useEffect(() => {
    const loadExam = async () => {
      try {
        const res = await api.get(`/api/v1/exams/sessions/${examId}`);
        setExam(res.data);

        // Start exam if pending
        if (res.data.status === "pending") {
          await api.post(`/api/v1/exams/sessions/${examId}/start`);
          setExam((prev) => prev ? { ...prev, status: "in_progress" } : null);
        }

        // Initialize answers from existing data
        const initialAnswers: Record<string, string> = {};
        res.data.questions.forEach((q: Question) => {
          initialAnswers[q.id] = "";
        });
        setAnswers(initialAnswers);

        // Set time left
        if (res.data.started_at && res.data.status === "in_progress") {
          const startedAt = new Date(res.data.started_at).getTime();
          const durationMs = res.data.duration_minutes * 60 * 1000;
          const elapsed = Date.now() - startedAt;
          const remaining = Math.max(0, durationMs - elapsed);
          setTimeLeft(Math.floor(remaining / 1000));
        } else if (res.data.status === "submitted" || res.data.status === "graded") {
          setTimeLeft(0);
        } else {
          setTimeLeft(res.data.duration_minutes * 60);
        }

        // If already graded, show results
        if (res.data.status === "graded") {
          setGrading(false);
        }
      } catch {
        setError("加载考试失败");
      } finally {
        setLoading(false);
      }
    };

    if (examId) loadExam();
  }, [examId]);

  // Countdown timer
  useEffect(() => {
    if (timeLeft <= 0 || !exam || (exam.status !== "in_progress" && exam.status !== "pending")) return;

    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          handleSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [timeLeft, exam?.status]);

  // Auto-save answers every 30 seconds (only while exam is in progress)
  useEffect(() => {
    if (!exam || exam.status !== "in_progress") return;

    const saveTimer = setInterval(async () => {
      // Re-check status in case exam was submitted during the interval
      if (exam.status !== "in_progress") return;
      const currentQ = exam.questions[currentQuestionIndex];
      if (!currentQ) return;
      const answer = answers[currentQ.id];
      if (answer && answer.trim()) {
        try {
          await api.post(`/api/v1/exams/sessions/${examId}/answers`, {
            question_id: currentQ.id,
            user_answer: answer,
          });
        } catch (err) {
          // Silently ignore auto-save failures — the submit handler will save all answers
          console.warn("Auto-save skipped:", err);
        }
      }
    }, 30000);

    return () => clearInterval(saveTimer);
  }, [exam, examId, currentQuestionIndex, answers]);

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const currentQuestion = exam?.questions[currentQuestionIndex];

  const handleAnswerChange = useCallback(
    (value: string) => {
      if (!currentQuestion) return;
      setAnswers((prev) => ({ ...prev, [currentQuestion.id]: value }));
    },
    [currentQuestion]
  );

  const handleSaveAnswer = async () => {
    if (!currentQuestion || !exam) return;
    if (exam.status !== "in_progress" && exam.status !== "pending") return;
    const answer = answers[currentQuestion.id];
    if (!answer || !answer.trim()) return;

    try {
      await api.post(`/api/v1/exams/sessions/${examId}/answers`, {
        question_id: currentQuestion.id,
        user_answer: answer,
      });
      // Update local state
      setExam((prev) => {
        if (!prev) return prev;
        const updated = [...prev.questions];
        updated[currentQuestionIndex] = { ...updated[currentQuestionIndex], answered: true };
        return { ...prev, questions: updated };
      });
    } catch {
      setError("保存答案失败");
    }
  };

  const handleSubmit = async () => {
    if (!exam) return;
    setShowSubmitConfirm(false);
    setIsSubmitting(true);

    try {
      // Save current answer first
      await handleSaveAnswer();

      // Submit exam
      await api.post(`/api/v1/exams/sessions/${examId}/submit`);
      setExam((prev) => prev ? { ...prev, status: "submitted" } : null);

      // Start grading with SSE
      setGrading(true);
      setGradingProgress({ graded: 0, total: exam.total_questions });
      setGradingSummary("");

      const controller = new AbortController();
      gradingAbortRef.current = controller;
      const eventSource = {
        readyState: 0,
        close() {
          this.readyState = EventSource.CLOSED;
          controller.abort();
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        addEventListener(_type: string, _listener: any) {},
        onmessage: null as ((event: MessageEvent) => void) | null,
        onerror: null as (() => void) | null,
      };

      // Track if we've received any progress to detect silent failures
      let hasReceivedProgress = false;
      let lastEventTime = Date.now();
      const overallTimeout = setTimeout(() => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close();
          setGrading(false);
          setError("批改超时，请刷新页面查看结果");
        }
      }, 600000); // 10 minute overall timeout

      // Per-event timeout: alert if no progress for 90 seconds (LLM might be slow)
      const eventTimeout = setInterval(() => {
        if (eventSource.readyState === EventSource.CLOSED) {
          clearInterval(eventTimeout);
          return;
        }
        const idle = Date.now() - lastEventTime;
        if (idle > 90000 && hasReceivedProgress) {
          // Still processing but taking a while — user gets feedback
          setGradingSummary((prev) => prev + (prev ? "\n" : "") + "⏳ AI 正在思考中，请稍候...");
        }
      }, 30000);

      const resetEventTimer = () => {
        lastEventTime = Date.now();
      };

      // Handle named events (event: grading_progress, etc.)
      const handleProgress = (event: MessageEvent) => {
        hasReceivedProgress = true;
        resetEventTimer();
        const data = JSON.parse(event.data);
        setGradingProgress({ graded: data.graded, total: data.total });
        setGradingSummary(""); // Clear thinking message on real progress
      };

      const handleComplete = () => {
        clearTimeout(overallTimeout);
        clearInterval(eventTimeout);
        eventSource.close();
        setGrading(false);
        api.get(`/api/v1/exams/sessions/${examId}`).then((res) => {
          setExam(res.data);
        });
      };

      const handleError = (event: MessageEvent) => {
        clearTimeout(overallTimeout);
        clearInterval(eventTimeout);
        eventSource.close();
        setGrading(false);
        setError("批改失败: " + (JSON.parse(event.data).error || "未知错误"));
      };

      // Register named event listeners (for SSE events with `event:` line)
      eventSource.addEventListener("grading_progress", handleProgress);
      eventSource.addEventListener("grading_complete", handleComplete);
      eventSource.addEventListener("error", handleError);

      // Handle unnamed events (data-only, no `event:` line)
      eventSource.onmessage = (event) => {
        hasReceivedProgress = true;
        resetEventTimer();
        const data = JSON.parse(event.data);
        if (data.event === "grading_progress") {
          setGradingProgress({ graded: data.graded, total: data.total });
          setGradingSummary(""); // Clear thinking message on real progress
        } else if (data.event === "token" && data.token) {
          setGradingSummary((prev) => prev + data.token);
        } else if (data.event === "grading_complete") {
          clearTimeout(overallTimeout);
          clearInterval(eventTimeout);
          eventSource.close();
          setGrading(false);
          api.get(`/api/v1/exams/sessions/${examId}`).then((res) => {
            setExam(res.data);
          });
        } else if (data.event === "error") {
          clearTimeout(overallTimeout);
          clearInterval(eventTimeout);
          eventSource.close();
          setGrading(false);
          setError("批改失败: " + data.error);
        }
      };

      eventSource.onerror = () => {
        // Don't treat first error as fatal - EventSource fires onerror on connection open too
        if (eventSource.readyState === EventSource.CLOSED) {
          clearTimeout(overallTimeout);
          clearInterval(eventTimeout);
          // If we received progress before disconnect, grading likely completed
          if (hasReceivedProgress) {
            setGrading(false);
            // Reload to check results
            api.get(`/api/v1/exams/sessions/${examId}`).then((res) => {
              setExam(res.data);
            });
          } else {
            setGrading(false);
            setError("批改连接断开，请稍后刷新查看结果");
          }
        }
      };

      try {
        const streamRes = await authFetch(`/api/v1/exams/sessions/${examId}/grade`, {
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!streamRes.ok || !streamRes.body) {
          throw new Error(`Grading stream failed: ${streamRes.status}`);
        }

        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() || "";

          for (const block of blocks) {
            const dataLines = block
              .split(/\r?\n/)
              .filter((line) => line.startsWith("data:"))
              .map((line) => line.slice(5).trim());
            if (dataLines.length === 0) continue;
            eventSource.onmessage?.({ data: dataLines.join("\n") } as MessageEvent);
          }
        }
      } catch {
        eventSource.close();
        eventSource.onerror?.();
      }
    } catch {
      setError("提交考试失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    );
  }

  if (error && !exam) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-xl shadow-lg p-8 text-center">
          <div className="text-red-500 text-xl mb-4">⚠️</div>
          <div className="text-gray-700">{error}</div>
          <button
            onClick={() => router.push("/exam")}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回考试列表
          </button>
        </div>
      </div>
    );
  }

  if (!exam) return null;

  // Results view
  if (exam.status === "graded") {
    const answeredCount = exam.questions.filter((q) => q.score !== null).length;
    const avgScore = exam.total_score || 0;

    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-xl shadow-lg p-8 mb-6">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">{exam.title}</h1>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-4xl font-bold text-blue-600">{avgScore}</div>
                <div className="text-sm text-gray-500">总分</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-semibold text-gray-700">{answeredCount}/{exam.total_questions}</div>
                <div className="text-sm text-gray-500">已作答</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-semibold text-gray-700">{exam.duration_minutes}分钟</div>
                <div className="text-sm text-gray-500">考试时长</div>
              </div>
            </div>
          </div>

          {/* Question breakdown */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">逐题成绩</h2>
            <div className="space-y-3">
              {exam.questions.map((q, idx) => (
                <div
                  key={q.id}
                  className="p-4 border rounded-lg hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <span className="text-sm font-medium text-gray-500 mr-3">#{idx + 1}</span>
                      <span className="text-gray-800">{q.title}</span>
                      {q.difficulty_level && (
                        <span className={`ml-2 px-2 py-0.5 rounded text-xs ${difficultyColors[q.difficulty_level] || "bg-gray-100 text-gray-600"}`}>
                          {difficultyLabels[q.difficulty_level] || "未知"}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-lg font-semibold ${q.score === null ? "text-gray-400" : q.score >= 60 ? "text-green-600" : "text-red-600"}`}>
                        {q.score === null ? "未评分" : `${q.score}分`}
                      </span>
                    </div>
                  </div>
                  {q.feedback && (
                    <div className="mt-3 rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm text-slate-700 whitespace-pre-wrap">
                      {q.feedback}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 text-center">
            <button
              onClick={() => router.push("/exam")}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              返回考试列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Exam in progress
  const answeredCount = exam.questions.filter((q) => q.answered || (answers[q.id] && answers[q.id].trim())).length;
  const timeWarning = timeLeft < 300; // 5 minutes warning

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold text-gray-900">{exam.title}</h1>
            <span className="text-sm text-gray-500">{answeredCount}/{exam.total_questions} 已答</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`text-xl font-mono font-bold ${timeWarning ? "text-red-600 animate-pulse" : "text-gray-800"}`}>
              {formatTime(timeLeft)}
            </div>
            <button
              onClick={() => setShowSubmitConfirm(true)}
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {isSubmitting ? "提交中..." : "交卷"}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">
        {/* Sidebar - Question Navigation */}
        <div className="w-64 flex-shrink-0">
          <div className="bg-white rounded-xl shadow p-4 sticky top-20">
            <h3 className="text-sm font-medium text-gray-600 mb-3">题目导航</h3>
            <div className="grid grid-cols-5 gap-2">
              {exam.questions.map((q, idx) => {
                const isAnswered = q.answered || (answers[q.id] && answers[q.id].trim());
                const isCurrent = idx === currentQuestionIndex;
                return (
                  <button
                    key={q.id}
                    onClick={() => {
                      // Save current answer before switching
                      handleSaveAnswer();
                      setCurrentQuestionIndex(idx);
                    }}
                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${
                      isCurrent
                        ? "bg-blue-600 text-white ring-2 ring-blue-300"
                        : isAnswered
                        ? "bg-green-100 text-green-700 hover:bg-green-200"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>
            <div className="mt-4 text-xs text-gray-400 space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-green-100 border border-green-300"></div>
                <span>已作答</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-gray-100 border border-gray-300"></div>
                <span>未作答</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-blue-600"></div>
                <span>当前题目</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1">
          {currentQuestion && (
            <div className="bg-white rounded-xl shadow p-8">
              {/* Question Header */}
              <div className="flex items-center gap-3 mb-4">
                <span className="text-sm font-medium text-gray-400">第 {currentQuestionIndex + 1} 题</span>
                {currentQuestion.difficulty_level && (
                  <span className={`px-2 py-1 rounded text-xs font-medium ${difficultyColors[currentQuestion.difficulty_level] || "bg-gray-100 text-gray-600"}`}>
                    {difficultyLabels[currentQuestion.difficulty_level] || "未知"}
                  </span>
                )}
                {currentQuestion.domain_type && (
                  <span className="px-2 py-1 rounded text-xs bg-purple-100 text-purple-700">
                    {currentQuestion.domain_type}
                  </span>
                )}
              </div>

              {/* Question Title */}
              <h2 className="text-xl font-semibold text-gray-900 mb-4">{currentQuestion.title}</h2>

              {/* Question Content */}
              {currentQuestion.content && (
                <div className="bg-gray-50 rounded-lg p-4 mb-6 text-gray-700 whitespace-pre-wrap">
                  {currentQuestion.content}
                </div>
              )}

              {/* Answer Area */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  你的回答 <span className="text-gray-400 font-normal">(支持 Markdown)</span>
                </label>
                <textarea
                  ref={textareaRef}
                  value={answers[currentQuestion.id] || ""}
                  onChange={(e) => handleAnswerChange(e.target.value)}
                  className="w-full h-64 p-4 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                  placeholder="请输入你的答案..."
                />
                <div className="mt-3 flex justify-between items-center">
                  <span className="text-xs text-gray-400">
                    {(answers[currentQuestion.id] || "").length} 字符
                  </span>
                  <button
                    onClick={handleSaveAnswer}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm font-medium"
                  >
                    保存答案
                  </button>
                </div>
              </div>

              {/* Navigation Buttons */}
              <div className="mt-6 flex justify-between">
                <button
                  onClick={() => {
                    handleSaveAnswer();
                    if (currentQuestionIndex > 0) setCurrentQuestionIndex(currentQuestionIndex - 1);
                  }}
                  disabled={currentQuestionIndex === 0}
                  className="px-6 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ← 上一题
                </button>
                <button
                  onClick={() => {
                    handleSaveAnswer();
                    if (currentQuestionIndex < exam.questions.length - 1) setCurrentQuestionIndex(currentQuestionIndex + 1);
                  }}
                  disabled={currentQuestionIndex === exam.questions.length - 1}
                  className="px-6 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  下一题 →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Submit Confirmation Modal */}
      {showSubmitConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-8 max-w-md w-full mx-4">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">确认交卷？</h3>
            <div className="space-y-3 text-gray-600 mb-6">
              <p>已作答: <span className="font-medium text-gray-900">{answeredCount}</span> / {exam.total_questions}</p>
              <p>未作答: <span className="font-medium text-red-600">{exam.total_questions - answeredCount}</span></p>
              <p className="text-sm text-gray-500">交卷后将自动批改所有已作答的题目。</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowSubmitConfirm(false)}
                className="flex-1 px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50"
              >
                继续答题
              </button>
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {isSubmitting ? "提交中..." : "确认交卷"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Grading Progress Modal */}
      {grading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-8 max-w-lg w-full mx-4 text-center">
            <div className="text-4xl mb-4">📊</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">正在批改...</h3>
            <p className="text-gray-500 mb-4">AI 正在逐一批改你的答案</p>
            <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                style={{ width: `${gradingProgress.total > 0 ? (gradingProgress.graded / gradingProgress.total) * 100 : 0}%` }}
              />
            </div>
            <p className="text-sm text-gray-500 mb-4">
              {gradingProgress.graded} / {gradingProgress.total} 题已批改
            </p>
            {/* Streaming summary output */}
            {gradingSummary && (
              <div className="mt-4 p-3 rounded-lg bg-gray-50 border border-gray-200 text-left">
                <p className="text-xs font-medium text-gray-600 mb-2">批改总结</p>
                <div className="whitespace-pre-wrap text-sm text-gray-700 max-h-48 overflow-y-auto">
                  {gradingSummary}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
