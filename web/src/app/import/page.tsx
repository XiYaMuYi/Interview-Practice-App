"use client";

import { useState } from "react";
import axios from "axios";

export default function ImportPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ imported: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleImport = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await axios.post("/api/v1/import/text", { text });
      setResult(res.data);
      setText("");
    } catch {
      setError("导入失败，请检查文本格式或后端服务状态");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">导入题目</h1>
      <p className="text-gray-600 mb-8">
        粘贴面试题目文本，系统将自动解析并导入
      </p>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <label
          htmlFor="import-text"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          题目文本
        </label>
        <textarea
          id="import-text"
          rows={12}
          className="w-full border border-gray-300 rounded-lg p-3 font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
          placeholder={`在此粘贴题目文本...\n\n示例格式：\n题目：什么是闭包？\n难度：medium\n分类：JavaScript\n\n题目：请解释 React 的虚拟 DOM\n难度：medium\n分类：前端框架`}
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

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
          导入成功！新增 {result.imported} 道题目，跳过 {result.skipped} 道。
        </div>
      )}
    </div>
  );
}
