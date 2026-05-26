import { expect, test, type Page, type TestInfo } from "playwright/test";

type PageProblem = {
  kind: "console" | "pageerror" | "requestfailed" | "response";
  detail: string;
};

function watchPageProblems(page: Page) {
  const problems: PageProblem[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      problems.push({ kind: "console", detail: message.text() });
    }
  });

  page.on("pageerror", (error) => {
    problems.push({ kind: "pageerror", detail: error.message });
  });

  page.on("requestfailed", (request) => {
    const url = request.url();
    if (url.includes("/api/") || url.includes("127.0.0.1") || url.includes("localhost")) {
      problems.push({
        kind: "requestfailed",
        detail: `${request.method()} ${url} ${request.failure()?.errorText ?? ""}`.trim(),
      });
    }
  });

  page.on("response", (response) => {
    const url = response.url();
    const status = response.status();
    if (status >= 400 && !url.includes("/_next/") && !url.includes("/favicon")) {
      problems.push({ kind: "response", detail: `${status} ${response.request().method()} ${url}` });
    }
  });

  return problems;
}

async function attachProblems(testInfo: TestInfo, problems: PageProblem[]) {
  await testInfo.attach("business-flow-problems.json", {
    body: JSON.stringify(problems, null, 2),
    contentType: "application/json",
  });
}

async function expectPageHealthy(page: Page) {
  await expect(page.locator("body")).toBeVisible();
  await expect.poll(async () => (await page.locator("body").innerText()).trim().length).toBeGreaterThan(0);
}

async function mockInterviewStart(page: Page, firstQuestion = "E2E interview first question about RAG.") {
  await page.route("**/api/v1/ai/interview/start", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "e2e-interview-session",
        first_question: firstQuestion,
        max_turns: 5,
      }),
    });
  });
}

test.describe("controlled business flows", () => {
  test("exam session can be opened, started, answered, and navigated", async ({ page, request }, testInfo) => {
    const problems = watchPageProblems(page);

    const createResponse = await request.post("/api/v1/exams/sessions", {
      data: {
        title: `E2E Controlled Exam ${Date.now()}`,
        duration_minutes: 10,
        question_count: 2,
      },
    });
    expect(createResponse.ok(), await createResponse.text()).toBeTruthy();
    const created = await createResponse.json() as { id: string; total_questions: number };
    expect(created.id).toBeTruthy();
    expect(created.total_questions).toBeGreaterThan(0);

    const startResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1/exams/sessions/${created.id}/start`),
    );

    await page.goto(`/exam/session/${created.id}`);
    await startResponse;
    await expectPageHealthy(page);

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible();
    await textarea.fill("E2E answer: Redis can cache task state and coordinate async queues.");

    const saveResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1/exams/sessions/${created.id}/answers`),
    );
    await page.locator("textarea").locator("xpath=following::button[1]").click();
    expect((await saveResponse).ok()).toBeTruthy();

    await expect(page.locator("body")).toContainText("1/");

    const enabledNavigationButtons = page.locator("button:visible:not([disabled])");
    const beforeText = await textarea.inputValue();
    await enabledNavigationButtons.filter({ hasText: /下一题|涓嬩竴棰?/ }).first().click();
    await expect(textarea).toBeVisible();
    await enabledNavigationButtons.filter({ hasText: /上一题|涓婁竴棰?/ }).first().click();
    await expect(textarea).toHaveValue(beforeText);

    await attachProblems(testInfo, problems);
    expect(problems).toEqual([]);
  });

  test("interview setup starts a session and submits one mocked turn", async ({ page }, testInfo) => {
    const problems = watchPageProblems(page);

    await mockInterviewStart(page, "请解释 RAG 在 AI 应用中的作用。");

    await page.route("**/api/v1/ai/interview/turn-stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: [
          'event: evaluation\ndata: {"score":82,"feedback":"回答覆盖了检索和生成两个核心点。"}',
          'event: followup\ndata: {"followup_question":"如果检索结果质量不好，你会如何优化？"}',
          'event: done\ndata: {"score":82,"feedback":"回答覆盖了检索和生成两个核心点。","followup_question":"如果检索结果质量不好，你会如何优化？","is_done":false}',
          "",
        ].join("\n\n"),
      });
    });

    await page.goto("/interview");
    await expectPageHealthy(page);

    await page.locator("button").filter({ hasText: /RAG/ }).first().click();

    const startResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes("/api/v1/ai/interview/start"),
    );
    await page.locator("button").last().click();
    expect((await startResponse).ok()).toBeTruthy();

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible();
    await expect(page.locator("body")).toContainText("RAG");
    await textarea.fill("RAG 会先检索外部知识，再把上下文交给模型生成更可靠的回答。");

    const turnResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes("/api/v1/ai/interview/turn-stream"),
    );
    await page.locator("textarea").locator("xpath=following::button[1]").click();
    expect((await turnResponse).ok()).toBeTruthy();

    await expect(textarea).toHaveValue("");
    await expect(page.locator("body")).toContainText("如果检索结果质量不好");
    await expect(page.locator("body")).toContainText("历史对话");

    await attachProblems(testInfo, problems);
    expect(problems).toEqual([]);
  });

  test("interview setup buttons and exit flow stay responsive", async ({ page }, testInfo) => {
    const problems = watchPageProblems(page);

    await page.route("**/api/v1/resumes**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
      });
    });
    await mockInterviewStart(page);

    await page.goto("/interview");
    await expectPageHealthy(page);

    const buttons = page.locator("button");
    const startButton = buttons.last();
    await expect(startButton).toBeDisabled();

    await buttons.nth(1).click();
    await expect(startButton).toBeDisabled();
    await expect(page.locator("body")).toContainText(/简历|resume|暂无|Empty/i);

    await buttons.nth(0).click();
    await page.locator("button").filter({ hasText: /RAG/ }).first().click();
    await expect(startButton).toBeEnabled();

    await page.locator("button").filter({ hasText: /困难|hard/i }).first().click();
    const startResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes("/api/v1/ai/interview/start"),
    );
    await startButton.click();
    expect((await startResponse).ok()).toBeTruthy();

    await expect(page.locator("textarea")).toBeVisible();
    await expect(page.locator("body")).toContainText("E2E interview first question");

    await page.locator("button").filter({ hasText: /退出|Exit/i }).first().click();
    await expect(page.locator("textarea")).toHaveCount(0);
    await expect(page.locator("button").last()).toBeEnabled();

    await attachProblems(testInfo, problems);
    expect(problems).toEqual([]);
  });

  test("interview final output page renders score, summary, history, and reset action", async ({ page }, testInfo) => {
    const problems = watchPageProblems(page);

    await mockInterviewStart(page, "E2E final interview question.");
    await page.route("**/api/v1/ai/interview/turn-stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: [
          'event: evaluation\ndata: {"score":88,"feedback":"E2E final feedback: answer is structured and practical."}',
          'event: summary\ndata: {"summary":"E2E final summary: candidate understands retrieval, grounding, and generation."}',
          'event: done\ndata: {"score":88,"feedback":"E2E final feedback: answer is structured and practical.","summary":"E2E final summary: candidate understands retrieval, grounding, and generation.","followup_question":null,"is_done":true}',
          "",
        ].join("\n\n"),
      });
    });

    await page.goto("/interview");
    await page.locator("button").filter({ hasText: /RAG/ }).first().click();
    await page.locator("button").last().click();

    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible();
    await textarea.fill("E2E final answer: use retrieval to ground the model before generation.");

    const turnResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes("/api/v1/ai/interview/turn-stream"),
    );
    await textarea.locator("xpath=following::button[1]").click();
    expect((await turnResponse).ok()).toBeTruthy();

    await expect(page.locator("body")).toContainText("88");
    await expect(page.locator("body")).toContainText("E2E final summary");
    await expect(page.locator("body")).toContainText("E2E final feedback");
    await expect(page.locator("a[href='/stats']").filter({ hasText: /查看统计|Stats/i })).toBeVisible();

    await page.locator("button.btn-primary").last().click();
    await expect(page.locator("body")).not.toContainText("E2E final summary");
    await expect(page.locator("textarea")).toHaveCount(0);
    await expect(page.locator("button").last()).toBeEnabled();

    await attachProblems(testInfo, problems);
    expect(problems).toEqual([]);
  });
});
