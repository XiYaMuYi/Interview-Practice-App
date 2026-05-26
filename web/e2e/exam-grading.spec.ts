import { expect, test, type APIRequestContext, type Page, type TestInfo } from "playwright/test";

type PageProblem = {
  kind: "console" | "pageerror" | "requestfailed" | "response";
  detail: string;
};

function requireAiOptIn() {
  test.skip(process.env.E2E_RUN_AI !== "1", "Real LLM grading E2E is opt-in. Set E2E_RUN_AI=1 to run.");
}

function watchPageProblems(page: Page) {
  const problems: PageProblem[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push({ kind: "console", detail: message.text() });
  });
  page.on("pageerror", (error) => problems.push({ kind: "pageerror", detail: error.message }));
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
  await testInfo.attach("exam-grading-problems.json", {
    body: JSON.stringify(problems, null, 2),
    contentType: "application/json",
  });
}

async function pollExamUntilGraded(request: APIRequestContext, examId: string) {
  let latest: any = null;
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/exams/sessions/${examId}`);
    if (!response.ok()) return "request_failed";
    latest = await response.json();
    return latest.status;
  }, { timeout: 240_000, intervals: [2_000, 3_000, 5_000] }).toBe("graded");
  return latest;
}

test.describe("real exam grading flow", () => {
  test.beforeEach(() => {
    requireAiOptIn();
  });

  test("exam can be submitted, graded by real LLM, and rendered with feedback", async ({ page, request }, testInfo) => {
    test.setTimeout(300_000);
    const problems = watchPageProblems(page);
    const title = `E2E Real Grading ${Date.now()}`;

    const createResponse = await request.post("/api/v1/exams/sessions", {
      data: {
        title,
        duration_minutes: 10,
        question_count: 1,
      },
    });
    expect(createResponse.ok(), await createResponse.text()).toBeTruthy();
    const created = await createResponse.json() as { id?: string };
    expect(created.id).toBeTruthy();
    const examId = created.id!;

    await page.goto(`/exam/session/${examId}`);
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible();
    await textarea.fill([
      "E2E real grading answer:",
      "I would identify the core concept, explain the implementation tradeoffs,",
      "and mention observability, failure handling, and a concrete production example.",
    ].join(" "));

    const saveResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1/exams/sessions/${examId}/answers`),
    );
    await textarea.locator("xpath=following::button[1]").click();
    expect((await saveResponse).ok()).toBeTruthy();

    await page.getByRole("button", { name: /交卷/ }).click();
    await expect(page.locator(".fixed")).toBeVisible();

    const submitResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/v1/exams/sessions/${examId}/submit`),
    );
    await page.getByRole("button", { name: /确认交卷/ }).click();
    expect((await submitResponse).ok()).toBeTruthy();

    await expect(page.locator("body")).toContainText(/正在批改|批改/);
    const graded = await pollExamUntilGraded(request, examId);
    const firstQuestion = graded.questions?.[0];
    expect(graded.total_score).toEqual(expect.any(Number));
    expect(firstQuestion?.score).toEqual(expect.any(Number));
    expect(firstQuestion?.feedback ?? "").not.toHaveLength(0);

    await expect(page.locator("textarea")).toHaveCount(0, { timeout: 240_000 });
    await expect(page.locator("body")).toContainText(title);
    await expect(page.locator("body")).toContainText(String(firstQuestion.score));
    await expect(page.locator("body")).toContainText((firstQuestion.feedback as string).slice(0, 12));
    await expect(page.getByRole("button", { name: /返回考试列表/ })).toBeVisible();

    await attachProblems(testInfo, problems);
    expect(problems).toEqual([]);
  });
});
