import { expect, test } from "playwright/test";
import type { APIRequestContext, APIResponse } from "playwright/test";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

const questionFixture =
  process.env.E2E_QUESTION_FILE ||
  "D:\\AI_Project\\Al_learn\\vault\\AI应用落地分层演绎\\异步与并发调度层（redis 分层）.md";

const resumeFixture =
  process.env.E2E_RESUME_FILE ||
  "C:\\Users\\admin\\Desktop\\简历word版.pdf";

async function expectOkJson(response: APIResponse) {
  expect(response.ok(), `${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function cleanupE2eSmokeQuestions(request: APIRequestContext) {
  const response = await request.get("/api/v1/questions/search", {
    params: { q: "E2E smoke", page_size: 100 },
  });
  if (!response.ok()) return;

  const data = await response.json() as { items?: Array<{ id?: string }> };
  await Promise.all(
    (data.items ?? [])
      .filter((item) => item.id)
      .map((item) => request.delete(`/api/v1/questions/${item.id}`)),
  );
}

test.describe("Interview Practice smoke", () => {
  test.afterEach(async ({ request }) => {
    await cleanupE2eSmokeQuestions(request);
  });

  test("home and questions page load", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "面试练习平台" })).toBeVisible();

    await page.getByRole("link", { name: "题目", exact: true }).click();
    await expect(page.getByRole("heading", { name: "题目列表" })).toBeVisible();
    await expect(page.getByPlaceholder("搜索题目标题或内容关键词...")).toBeVisible();
  });

  test("question filters apply through the frontend", async ({ page }) => {
    await page.goto("/questions");
    await expect(page.getByRole("heading", { name: "题目列表" })).toBeVisible();

    await page.locator("#source-filter").selectOption("upload");

    const filteredResponse = page.waitForResponse((response) => {
      const url = response.url();
      return (
        response.request().method() === "GET" &&
        url.includes("/api/v1/questions") &&
        url.includes("source_type=upload")
      );
    });

    await page.getByRole("button", { name: "应用筛选" }).click();
    const response = await filteredResponse;
    expect(response.ok()).toBeTruthy();

    await expect(page.getByText("调整筛选条件后点击“应用筛选”")).toBeVisible();
    await expect(page.getByText("upload").first()).toBeVisible();
  });

  test("study random draw uses the random question endpoint", async ({ page }) => {
    await page.goto("/study");
    await expect(page.getByRole("heading", { name: "学习练习" })).toBeVisible();

    const randomResponsePromise = page.waitForResponse((response) => {
      const url = response.url();
      return response.request().method() === "GET" && url.includes("/api/v1/questions/random");
    });

    await page.getByRole("button", { name: "随机抽题" }).click();
    const randomResponse = await randomResponsePromise;
    expect(randomResponse.ok()).toBeTruthy();

    const randomQuestion = await randomResponse.json() as { id?: string; title?: string };
    expect(randomQuestion.id).toBeTruthy();

    await page.waitForResponse((response) => {
      const url = response.url();
      return response.request().method() === "GET" && url.includes(`/api/v1/questions/${randomQuestion.id}/detail`);
    });
    await expect(page.locator("h2").filter({ hasText: randomQuestion.title || "" })).toBeVisible();
  });

  test("question file import creates questions", async ({ request }) => {
    test.skip(
      process.env.E2E_RUN_SLOW_IMPORT !== "1",
      "Full file import calls the LLM extraction pipeline and is intentionally opt-in. Set E2E_RUN_SLOW_IMPORT=1 to run it.",
    );
    test.skip(!fs.existsSync(questionFixture), `Missing question fixture: ${questionFixture}`);

    const fixtureText = fs.readFileSync(questionFixture, "utf-8");
    const compactMarkdown = [
      "# E2E 题目录入冒烟样本",
      "",
      fixtureText.slice(0, 600),
      "",
      "## 1. Redis 在 AI 异步任务队列中有什么作用？",
      "",
      "答案：Redis 可以缓存任务状态、记录进度、承接高频读取，并配合消息队列削峰填谷。",
    ].join("\n");

    const response = await request.post("/api/v1/import/file", {
      multipart: {
        file: {
          name: `e2e-${path.basename(questionFixture)}`,
          mimeType: "text/markdown",
          buffer: Buffer.from(compactMarkdown, "utf-8"),
        },
      },
      timeout: 180_000,
    });
    const data = await expectOkJson(response) as {
      status?: string;
      questions_extracted?: number;
      question_ids?: string[];
    };

    expect(data.status).toBe("success");
    expect(data.questions_extracted ?? 0).toBeGreaterThan(0);
    expect(data.question_ids?.length ?? 0).toBeGreaterThan(0);
  });

  test("question batch import creates a known smoke question", async ({ request }) => {
    const content = `E2E smoke ${Date.now()}：Redis 在 AI 异步任务队列中有什么作用？`;
    let questionId: string | undefined;
    const response = await request.post("/api/v1/questions/import", {
      data: {
        questions: [
          {
            content,
            category: "Agent",
            difficulty: 3,
            reference_answer: "Redis 可以缓存任务状态、记录进度，并配合队列削峰填谷。",
          },
        ],
      },
    });
    const data = await expectOkJson(response) as {
      status?: string;
      success?: number;
      results?: Array<{ id?: string; title?: string }>;
    };

    expect(data.status).toBe("completed");
    expect(data.success).toBe(1);
    questionId = data.results?.[0]?.id;
    expect(questionId).toBeTruthy();

    if (questionId) {
      const deleteResponse = await request.delete(`/api/v1/questions/${questionId}`);
      expect(deleteResponse.ok()).toBeTruthy();
    }
  });

  test("resume upload creates a pending resume", async ({ request }) => {
    test.skip(!fs.existsSync(resumeFixture), `Missing resume fixture: ${resumeFixture}`);

    const response = await request.post("/api/v1/resumes/upload", {
      multipart: {
        file: {
          name: path.basename(resumeFixture),
          mimeType: "application/pdf",
          buffer: fs.readFileSync(resumeFixture),
        },
      },
      timeout: 120_000,
    });
    const data = await expectOkJson(response) as {
      id?: string;
      parse_status?: string;
      raw_text?: string;
    };

    expect(data.id).toBeTruthy();
    expect(data.parse_status).toBeTruthy();
    expect(data.raw_text?.length ?? 0).toBeGreaterThan(50);

    if (data.id) {
      const deleteResponse = await request.delete(`/api/v1/resumes/${data.id}`);
      expect(deleteResponse.ok()).toBeTruthy();
    }
  });

  test("exam can be created, listed, and opened", async ({ request }) => {
    const createResponse = await request.post("/api/v1/exams/sessions", {
      data: {
        title: `Smoke Exam ${Date.now()}`,
        duration_minutes: 10,
        question_count: 2,
      },
    });
    const created = await expectOkJson(createResponse) as { id?: string; total_questions?: number };

    expect(created.id).toBeTruthy();
    expect(created.total_questions).toBeGreaterThan(0);

    const detailResponse = await request.get(`/api/v1/exams/sessions/${created.id}`);
    const detail = await expectOkJson(detailResponse) as { id?: string; questions?: unknown[] };
    expect(detail.id).toBe(created.id);
    expect(detail.questions?.length ?? 0).toBeGreaterThan(0);

    const listResponse = await request.get("/api/v1/exams/sessions?page=1&page_size=5");
    const list = await expectOkJson(listResponse) as { items?: Array<{ id?: string }> };
    expect(list.items?.some((item) => item.id === created.id)).toBeTruthy();
  });

  test("AI explanation task exposes an SSE status event", async ({ page, baseURL }) => {
    const origin = baseURL || "http://127.0.0.1:3000";
    await page.goto("/");

    const taskId = await page.evaluate(async (base) => {
      const response = await fetch(`${base}/api/v1/ai/explain-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_text: "What is RAG?", depth: "brief" }),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      return data.task_id as string;
    }, origin);

    expect(taskId).toBeTruthy();

    const firstEvent = await readFirstSseEvent(`${origin}/api/v1/tasks/${taskId}/events`, 20_000);

    expect(firstEvent).toContain("event:");
    expect(firstEvent).toContain(taskId);
  });
});

async function readFirstSseEvent(url: string, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => {
      request.destroy();
      reject(new Error(`Timed out waiting for SSE event from ${url}`));
    }, timeoutMs);

    const request = http.get(url, (response) => {
      if (response.statusCode && response.statusCode >= 400) {
        clearTimeout(timer);
        request.destroy();
        reject(new Error(`SSE request failed: ${response.statusCode}`));
        return;
      }

      response.on("data", (chunk: Buffer) => {
        buffer += chunk.toString("utf-8");
        if (buffer.includes("\n\n")) {
          clearTimeout(timer);
          request.destroy();
          resolve(buffer);
        }
      });

      response.on("error", (error) => {
        clearTimeout(timer);
        reject(error);
      });
    });

    request.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}
