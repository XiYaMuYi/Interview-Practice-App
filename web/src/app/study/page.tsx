"use client";

import { useEffect, useState, useCallback } from "react";
import axios from "axios";

// ─── Types ───────────────────────────────────────────────────────────

interface QuestionListItem {
  id: string;
  title: string;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  mastery_level: number | null;
}

interface QuestionDetail {
  id: string;
  title: string;
  content: string | null;
  source_type: string | null;
  source_ref: string | null;
  source_excerpt: string | null;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  difficulty_score: number | null;
  answer_summary: string | null;
  answer_detail: string | null;
  explanation: string | null;
  common_pitfalls: string | null;
  review_status: string | null;
  created_at: string;
  tags: { tag_name: string | null; tag_type: string | null; source_type: string | null; confidence: number | null }[];
  knowledge_nodes: { node_name: string | null; node_type: string | null; relation_type: string | null; confidence: number | null }[];
}

interface EvaluationResult {
  score: number;
  feedback: string;
  missing_points: string[];
  is_pass: boolean;
  mastery_level: number;
}

interface ExplainResult {
  answer_short: string;
  answer_detail: string;
  explanation: string;
  knowledge_points: string[];
  common_pitfalls: string | null;
  related_questions: string[];
}

interface ReviewListItem {
  question_id: string;
  question_title: string;
  difficulty_level: number | null;
  mastery_level: number | null;
  next_review_at: string | null;
  review_status: string | null;
}

interface StudyStats {
  total_sessions: number;
  total_reviews: number;
  total_practice: number;
  average_score: number | null;
  questions_mastered: number;
  questions_pending: number;
}

type TabKey = "practice" | "review" | "stats";
type Depth = "brief" | "standard" | "deep";

// ─── Helpers ─────────────────────────────────────────────────────────

const domainLabel = (d: string | null) => {
  if (!d) return "未分类";
  const map: Record<string, string> = {
    RAG: "RAG", Backend: "后端", Frontend: "前端",
    Database: "数据库", DevOps: "DevOps", Algorithm: "算法", ML: "机器学习",
  };
  return map[d] || d;
};

const difficultyText = (level: number | null) => {
  if (level == null) return "未定级";
  const map: Record<number, string> = { 1: "入门", 2: "简单", 3: "中等", 4: "困难", 5: "专家" };
  return map[level] || `${level}`;
};

const difficultyColor = (level: number | null) => {
  if (level == null) return "bg-gray-100 text-gray-600";
  const map: Record<number, string> = {
    1: "bg-green-100 text-green-700", 2: "bg-lime-100 text-lime-700",
    3: "bg-yellow-100 text-yellow-700", 4: "bg-orange-100 text-orange-700",
    5: "bg-red-100 text-red-700",
  };
  return map[level] || "bg-gray-100 text-gray-600";
};

const qualityLabels = ["完全不会", "严重不足", "部分正确", "基本正确", "良好", "完美"];

function formatReviewTime(raw: string | null) {
  if (!raw) return "未安排";
  const d = new Date(raw);
  return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

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

// ─── MarkdownContent (reused from QuestionCard) ──────────────────────

function MarkdownContent({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith("### ")) return <h3 key={i} className="text-base font-semibold mt-3 mb-1">{line.slice(4)}</h3>;
        if (line.startsWith("## ")) return <h2 key={i} className="text-lg font-semibold mt-4 mb-1">{line.slice(3)}</h2>;
        if (line.startsWith("# ")) return <h1 key={i} className="text-xl font-bold mt-4 mb-1">{line.slice(2)}</h1>;
        if (line.startsWith("**") && line.endsWith("**")) return <p key={i} className="font-semibold mt-2">{line.slice(2, -2)}</p>;
        if (line.startsWith("- ") || line.startsWith("* ")) return <li key={i} className="ml-4 list-disc text-gray-700">{line.slice(2)}</li>;
        const numMatch = line.match(/^(\d+)\.\s/);
        if (numMatch) return <li key={i} className="ml-4 list-decimal text-gray-700">{line.slice(numMatch[0].length)}</li>;
        if (line.trim() === "```") return null;
        if (line.trim() === "") return <br key={i} />;
        return <p key={i} className="text-gray-700 leading-relaxed">{line}</p>;
      })}
    </div>
  );
}

// ─── Practice Mode ───────────────────────────────────────────────────

function PracticeMode() {
  const [questions, setQuestions] = useState<QuestionListItem[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // Filters
  const [domainFilter, setDomainFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");

  // Current question
  const [currentQ, setCurrentQ] = useState<QuestionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(-1);

  // Answer
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);

  // Explanation
  const [explaining, setExplaining] = useState(false);
  const [explainResult, setExplainResult] = useState<ExplainResult | null>(null);
  const [explainDepth, setExplainDepth] = useState<Depth>("standard");
  const [evalError, setEvalError] = useState<string | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);

  const loadQuestions = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const params: Record<string, string | number> = { offset: 0, limit: 200 };
      if (domainFilter) params.domain_type = domainFilter;
      if (difficultyFilter) params.difficulty_level = parseInt(difficultyFilter, 10);
      const res = await axios.get("/api/v1/questions", { params });
      setQuestions(res.data.items);
    } catch {
      setListError("加载题目失败，请确保后端服务正在运行");
    } finally {
      setLoadingList(false);
    }
  }, [domainFilter, difficultyFilter]);

  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  const pickQuestion = useCallback(async (index: number) => {
    if (index < 0 || index >= questions.length) return;
    setLoadingDetail(true);
    setSubmitted(false);
    setEvalResult(null);
    setExplainResult(null);
    setAnswer("");
    setEvalError(null);
    setExplainError(null);
    setQuestionIndex(index);
    try {
      const q = questions[index];
      const res = await axios.get(`/api/v1/questions/${q.id}/detail`);
      setCurrentQ(res.data);
    } catch {
      setCurrentQ(null);
    } finally {
      setLoadingDetail(false);
    }
  }, [questions]);

  const handleSubmit = async () => {
    if (!currentQ || !answer.trim()) return;
    setEvaluating(true);
    try {
      // 1. Evaluate
      const evalRes = await axios.post("/api/v1/ai/evaluate", {
        question_id: currentQ.id,
        user_answer: answer,
      });
      const evalData: EvaluationResult = evalRes.data;
      setEvalResult(evalData);

      // 2. Save study record
      await axios.post("/api/v1/study/records", {
        question_id: currentQ.id,
        study_type: "practice",
        user_answer: answer,
        ai_score: evalData.score,
        ai_feedback: evalData.feedback,
        mastery_level: evalData.mastery_level,
      });

      setSubmitted(true);
    } catch {
      setEvalError("评分失败，请检查网络连接或后端服务状态");
    } finally {
      setEvaluating(false);
    }
  };

  const handleExplain = async (depth: Depth) => {
    if (!currentQ) return;
    setExplaining(true);
    setExplainError(null);
    setExplainDepth(depth);
    try {
      const res = await axios.post("/api/v1/ai/explain", {
        question_id: currentQ.id,
        depth,
      });
      setExplainResult(res.data);
    } catch {
      setExplainError("生成讲解失败");
    } finally {
      setExplaining(false);
    }
  };

  const handleNext = () => {
    if (questions.length === 0) return;
    const next = questionIndex < 0 ? 0 : (questionIndex + 1) % questions.length;
    pickQuestion(next);
  };

  const domains = ["RAG", "Backend", "Frontend", "Database", "DevOps", "Algorithm", "ML"];

  if (loadingList) return <div className="text-center text-gray-500 py-12">加载题目中...</div>;
  if (listError) return <div className="text-center text-red-500 py-12">{listError}</div>;
  if (questions.length === 0) return <div className="text-center text-gray-500 py-12">暂无题目，请先导入题目。</div>;

  return (
    <div className="space-y-6">
      {/* Filters + pick */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">领域:</label>
            <select value={domainFilter} onChange={(e) => { setDomainFilter(e.target.value); setQuestionIndex(-1); setCurrentQ(null); }}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
              <option value="">全部</option>
              {domains.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">难度:</label>
            <select value={difficultyFilter} onChange={(e) => { setDifficultyFilter(e.target.value); setQuestionIndex(-1); setCurrentQ(null); }}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
              <option value="">全部</option>
              {[1,2,3,4,5].map((d) => <option key={d} value={d}>{d} - {difficultyText(d)}</option>)}
            </select>
          </div>
          <button onClick={handleNext}
            className="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
            {questionIndex < 0 ? "随机抽题" : "下一题"}
          </button>
        </div>
        <p className="text-sm text-gray-500">共 {questions.length} 道题目可供练习</p>
      </div>

      {/* Question detail */}
      {loadingDetail && <div className="text-center text-gray-500 py-8">加载题目详情...</div>}

      {!loadingDetail && currentQ && (
        <>
          {/* Header */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-700">
                {currentQ.question_type || "未分类"}
              </span>
              <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
                {domainLabel(currentQ.domain_type)}
              </span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${difficultyColor(currentQ.difficulty_level)}`}>
                {difficultyText(currentQ.difficulty_level)}
              </span>
              {questionIndex >= 0 && (
                <span className="text-sm text-gray-400 ml-auto">{questionIndex + 1} / {questions.length}</span>
              )}
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-4">{currentQ.title}</h2>
            {currentQ.content && (
              <div className="bg-gray-50 rounded-lg p-4">
                <MarkdownContent text={currentQ.content} />
              </div>
            )}
          </div>

          {/* Answer input */}
          {!submitted && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">你的回答</label>
              <textarea
                rows={6}
                className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
                placeholder="在此输入你的回答..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <button
                onClick={handleSubmit}
                disabled={evaluating || !answer.trim()}
                className="mt-3 px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {evaluating ? "评分中..." : "提交回答"}
              </button>
              {evalError && <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{evalError}</div>}
            </div>
          )}

          {/* Evaluation result */}
          {submitted && evalResult && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">评分结果</h3>
              <div className="flex items-center gap-4 mb-4">
                <div className={`text-4xl font-bold ${scoreColor(evalResult.score)}`}>{evalResult.score}</div>
                <div className="flex-1">
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div className={`h-2.5 rounded-full ${scoreBarColor(evalResult.score)}`} style={{ width: `${evalResult.score}%` }} />
                  </div>
                </div>
                <span className={`px-3 py-1 rounded text-sm font-medium ${evalResult.is_pass ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {evalResult.is_pass ? "通过" : "未通过"}
                </span>
              </div>

              {/* Feedback */}
              {evalResult.feedback && (
                <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <h4 className="text-sm font-semibold text-blue-900 mb-1">反馈</h4>
                  <MarkdownContent text={evalResult.feedback} />
                </div>
              )}

              {/* Missing points */}
              {evalResult.missing_points.length > 0 && (
                <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <h4 className="text-sm font-semibold text-amber-900 mb-2">遗漏要点</h4>
                  <ul className="list-disc ml-5 space-y-1">
                    {evalResult.missing_points.map((p, i) => <li key={i} className="text-gray-700">{p}</li>)}
                  </ul>
                </div>
              )}

              {/* Answer textarea (show after submission for reference) */}
              <details className="mb-4">
                <summary className="text-sm text-gray-500 cursor-pointer">查看我的回答</summary>
                <div className="mt-2 p-3 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap">{answer}</div>
              </details>

              {/* Explain buttons */}
              <div className="flex flex-wrap gap-3">
                {(["brief", "standard", "deep"] as Depth[]).map((d) => (
                  <button key={d} onClick={() => handleExplain(d)} disabled={explaining}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      explainDepth === d && explaining ? "bg-indigo-600 text-white opacity-50"
                        : explainDepth === d && explainResult ? "bg-indigo-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    } disabled:cursor-not-allowed`}>
                    {explainDepth === d && explaining ? "生成中..." : d === "brief" ? "简要讲解" : d === "standard" ? "标准讲解" : "深入讲解"}
                  </button>
                ))}
              </div>
              {explainError && <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{explainError}</div>}
            </div>
          )}

          {/* Explanation result */}
          {explainResult && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-indigo-900 mb-3">
                AI 讲解（{explainDepth === "brief" ? "简要" : explainDepth === "standard" ? "标准" : "深入"}）
              </h3>
              {explainResult.answer_short && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-indigo-800 mb-1">简要回答</h4>
                  <MarkdownContent text={explainResult.answer_short} />
                </div>
              )}
              {explainResult.answer_detail && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-indigo-800 mb-1">详细讲解</h4>
                  <MarkdownContent text={explainResult.answer_detail} />
                </div>
              )}
              {explainResult.explanation && (
                <div>
                  <h4 className="text-sm font-semibold text-indigo-800 mb-1">补充说明</h4>
                  <MarkdownContent text={explainResult.explanation} />
                </div>
              )}
              {explainResult.knowledge_points.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-indigo-800 mb-2">知识点</h4>
                  <div className="flex flex-wrap gap-2">
                    {explainResult.knowledge_points.map((kp, i) => (
                      <span key={i} className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded text-sm">{kp}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Next button */}
          <div className="flex justify-end">
            <button onClick={handleNext}
              className="px-6 py-2.5 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-900 transition-colors">
              下一题 &rarr;
            </button>
          </div>
        </>
      )}

      {/* No question selected state */}
      {!loadingDetail && !currentQ && questionIndex < 0 && (
        <div className="text-center text-gray-400 py-16">
          <svg className="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
          </svg>
          <p className="text-lg font-medium">点击「随机抽题」开始练习</p>
        </div>
      )}
    </div>
  );
}

// ─── Review Mode ─────────────────────────────────────────────────────

function ReviewMode() {
  const [reviewItems, setReviewItems] = useState<ReviewListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active review
  const [activeQ, setActiveQ] = useState<QuestionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [answer, setAnswer] = useState("");
  const [qualityRating, setQualityRating] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const loadReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get("/api/v1/study/review-list");
      setReviewItems(res.data.items);
    } catch {
      setError("加载待复习列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadReviews(); }, [loadReviews]);

  const startReview = useCallback(async (questionId: string) => {
    setLoadingDetail(true);
    setAnswer("");
    setQualityRating(null);
    setSubmitError(null);
    setSubmitSuccess(false);
    try {
      const res = await axios.get(`/api/v1/questions/${questionId}/detail`);
      setActiveQ(res.data);
    } catch {
      setActiveQ(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const handleSubmitReview = async () => {
    if (!activeQ || qualityRating == null) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await axios.post("/api/v1/study/review", {
        question_id: activeQ.id,
        quality: qualityRating,
        user_answer: answer || null,
      });
      setSubmitSuccess(true);
      // Remove from list
      setReviewItems((prev) => prev.filter((r) => r.question_id !== activeQ.id));
    } catch {
      setSubmitError("记录复习失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackToList = () => {
    setActiveQ(null);
    loadReviews();
  };

  if (loading) return <div className="text-center text-gray-500 py-12">加载中...</div>;
  if (error) return <div className="text-center text-red-500 py-12">{error}</div>;

  // Active review flow
  if (activeQ) {
    if (loadingDetail) return <div className="text-center text-gray-500 py-12">加载题目详情...</div>;

    if (submitSuccess) {
      return (
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <div className="text-green-500 text-5xl mb-4">&#10003;</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">复习完成！</h3>
          <p className="text-gray-500 mb-6">已记录本次复习，下次复习时间已更新。</p>
          <button onClick={handleBackToList}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors">
            返回待复习列表
          </button>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <button onClick={handleBackToList} className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
          &larr; 返回列表
        </button>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex flex-wrap gap-2 mb-3">
            <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
              {domainLabel(activeQ.domain_type)}
            </span>
            <span className={`px-2 py-1 rounded text-xs font-medium ${difficultyColor(activeQ.difficulty_level)}`}>
              {difficultyText(activeQ.difficulty_level)}
            </span>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">{activeQ.title}</h2>
          {activeQ.content && (
            <div className="bg-gray-50 rounded-lg p-4 mb-4">
              <MarkdownContent text={activeQ.content} />
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">回忆回答（可选）</label>
          <textarea rows={5}
            className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-y"
            placeholder="尝试回忆这道题的要点..."
            value={answer} onChange={(e) => setAnswer(e.target.value)} />
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">自我评估（质量评分）</h3>
          <div className="flex flex-wrap gap-2">
            {[0, 1, 2, 3, 4, 5].map((q) => (
              <button key={q} onClick={() => setQualityRating(q)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  qualityRating === q
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}>
                {q} — {qualityLabels[q]}
              </button>
            ))}
          </div>
          {submitError && <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{submitError}</div>}
          <button onClick={handleSubmitReview} disabled={submitting || qualityRating == null}
            className="mt-4 px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {submitting ? "提交中..." : "完成复习"}
          </button>
        </div>
      </div>
    );
  }

  // Review list
  if (reviewItems.length === 0) {
    return (
      <div className="text-center text-gray-400 py-16">
        <svg className="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
        <p className="text-lg font-medium">暂无待复习题目</p>
        <p className="text-sm mt-1">完成练习后，题目会进入复习计划</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500 mb-4">共 {reviewItems.length} 道题目待复习</p>
      {reviewItems.map((item) => (
        <div key={item.question_id}
          className="bg-white rounded-lg shadow-sm border p-4 flex flex-col sm:flex-row sm:items-center gap-3 hover:border-blue-300 transition-colors">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{item.question_title}</h3>
            <div className="flex gap-2 mt-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${difficultyColor(item.difficulty_level)}`}>
                {difficultyText(item.difficulty_level)}
              </span>
              {item.review_status && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700">
                  {item.review_status}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-xs text-gray-400">复习: {formatReviewTime(item.next_review_at)}</span>
            <button onClick={() => startReview(item.question_id)}
              className="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
              开始复习
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Stats Mode ──────────────────────────────────────────────────────

function StatsMode() {
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await axios.get("/api/v1/study/stats");
        setStats(res.data);
      } catch {
        setError("获取学习统计失败");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="text-center text-gray-500 py-12">加载中...</div>;
  if (error) return <div className="text-center text-red-500 py-12">{error}</div>;
  if (!stats) return <div className="text-center text-gray-500 py-12">暂无统计数据</div>;

  const cards = [
    { label: "总练习次数", value: stats.total_practice, icon: "📝", color: "bg-blue-50 border-blue-200" },
    { label: "总复习次数", value: stats.total_reviews, icon: "🔄", color: "bg-green-50 border-green-200" },
    { label: "平均分数", value: stats.average_score != null ? stats.average_score.toFixed(1) : "—", icon: "📊", color: "bg-purple-50 border-purple-200" },
    { label: "已掌握题目", value: stats.questions_mastered, icon: "✅", color: "bg-emerald-50 border-emerald-200" },
    { label: "待复习题目", value: stats.questions_pending, icon: "⏳", color: "bg-amber-50 border-amber-200" },
    { label: "总学习次数", value: stats.total_sessions, icon: "📚", color: "bg-indigo-50 border-indigo-200" },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map(({ label, value, icon, color }) => (
          <div key={label} className={`${color} border rounded-lg p-5`}>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">{icon}</span>
              <span className="text-sm font-medium text-gray-600">{label}</span>
            </div>
            <div className="text-3xl font-bold text-gray-900">{value}</div>
          </div>
        ))}
      </div>

      {/* Summary bar */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">学习概览</h3>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-600">练习 / 复习比例</span>
            <span className="font-medium">
              {stats.total_practice + stats.total_reviews > 0
                ? `${Math.round((stats.total_practice / (stats.total_practice + stats.total_reviews)) * 100)}% 练习`
                : "暂无数据"}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-500 h-3 rounded-full"
              style={{
                width: stats.total_practice + stats.total_reviews > 0
                  ? `${(stats.total_practice / (stats.total_practice + stats.total_reviews)) * 100}%`
                  : "0%",
              }}
            />
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-600">掌握率</span>
            <span className="font-medium">
              {stats.questions_mastered + stats.questions_pending > 0
                ? `${Math.round((stats.questions_mastered / (stats.questions_mastered + stats.questions_pending)) * 100)}%`
                : "暂无数据"}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-green-500 h-3 rounded-full"
              style={{
                width: stats.questions_mastered + stats.questions_pending > 0
                  ? `${(stats.questions_mastered / (stats.questions_mastered + stats.questions_pending)) * 100}%`
                  : "0%",
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────

export default function StudyPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("practice");

  const tabs: { key: TabKey; label: string }[] = [
    { key: "practice", label: "练习模式" },
    { key: "review", label: "待复习" },
    { key: "stats", label: "学习统计" },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">学习练习</h1>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
        {tabs.map(({ key, label }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "practice" && <PracticeMode />}
      {activeTab === "review" && <ReviewMode />}
      {activeTab === "stats" && <StatsMode />}
    </div>
  );
}
