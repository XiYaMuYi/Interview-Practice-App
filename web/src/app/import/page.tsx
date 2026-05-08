"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import axios from "axios";

interface ImportResult {
  status: string;
  questions_extracted: number;
  knowledge_nodes: number;
  question_ids: string[];
}

interface FileUploadResult {
  status: string;
  file_id: string;
  file_name: string;
  parse_status: string;
  questions_extracted: number;
  knowledge_nodes: number;
  question_ids: string[];
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

export default function ImportPage() {
  // Text import state
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<FileUploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  const processFile = useCallback(async (file: File) => {
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
      const res = await axios.post("/api/v1/files/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadResult(res.data);
    } catch {
      setUploadError("文件上传失败，请检查网络连接或后端服务状态");
    } finally {
      setUploading(false);
    }
  }, []);

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
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [processFile]
  );

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">导入题目</h1>
      <p className="text-gray-600 mb-8">
        粘贴面试题目文本或上传文件，系统将自动解析并导入
      </p>

      {/* Text import */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
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

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-700 font-medium">文本导入成功！</p>
          <p className="text-green-600 text-sm mt-1">
            提取 {result.questions_extracted} 道题目，{result.knowledge_nodes} 个知识节点。
          </p>
          <Link
            href="/questions"
            className="inline-block mt-3 text-sm text-blue-600 hover:underline"
          >
            查看题目列表 &rarr;
          </Link>
        </div>
      )}

      {/* File upload */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">文件上传</h2>
        <p className="text-sm text-gray-500 mb-4">
          支持 PDF、DOCX、TXT、MD 格式
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
              <span className="text-gray-600 font-medium">上传并解析中...</span>
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
              <span className="text-sm text-gray-400">
                PDF, DOCX, TXT, MD
              </span>
            </div>
          )}
        </div>
      </div>

      {uploadError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {uploadError}
        </div>
      )}

      {uploadResult && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-700 font-medium">文件上传成功！</p>
          <dl className="mt-2 space-y-1 text-sm text-green-600">
            <div className="flex gap-2">
              <span className="text-gray-500">文件名：</span>
              <span className="font-medium">{uploadResult.file_name}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-500">解析状态：</span>
              <span
                className={`font-medium ${
                  uploadResult.parse_status === "success"
                    ? "text-green-700"
                    : "text-yellow-700"
                }`}
              >
                {uploadResult.parse_status === "success" ? "解析成功" : uploadResult.parse_status}
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-500">提取题目：</span>
              <span className="font-medium">{uploadResult.questions_extracted} 道</span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-500">知识节点：</span>
              <span className="font-medium">{uploadResult.knowledge_nodes} 个</span>
            </div>
          </dl>
          <Link
            href="/questions"
            className="inline-block mt-3 text-sm text-blue-600 hover:underline"
          >
            查看题目列表 &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
