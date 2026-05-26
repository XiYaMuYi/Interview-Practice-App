import { expect, test, type APIRequestContext, type Page } from "playwright/test";

const BACKEND = "http://localhost:8000";
const ADMIN = { username: "e2e_admin", password: "Admin123!" };
const PASSWORD = "User123!";
const suffix = "perm_boundaries";

const USER_A = { username: `e2e_perm_a_${suffix}`, password: PASSWORD, email: `perm_a_${suffix}@example.test` };
const USER_B = { username: `e2e_perm_b_${suffix}`, password: PASSWORD, email: `perm_b_${suffix}@example.test` };
const PENDING = { username: `e2e_perm_pending_${suffix}`, password: PASSWORD, email: `perm_pending_${suffix}@example.test` };
const REJECTED = { username: `e2e_perm_rejected_${suffix}`, password: PASSWORD, email: `perm_rejected_${suffix}@example.test` };
const DISABLED = { username: `e2e_perm_disabled_${suffix}`, password: PASSWORD, email: `perm_disabled_${suffix}@example.test` };

async function registerUser(request: APIRequestContext, user: { username: string; password: string; email: string }) {
  const response = await request.post(`${BACKEND}/api/v1/auth/register`, { data: user });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as { user_id: string; username: string; review_status: string };
}

async function loginApi(request: APIRequestContext, username: string, password = PASSWORD) {
  const response = await request.post(`${BACKEND}/api/v1/auth/login`, { data: { username, password } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as { access_token: string; refresh_token: string; expires_in: number };
}

async function authHeaders(request: APIRequestContext, username: string, password = PASSWORD) {
  const token = await loginApi(request, username, password);
  return { Authorization: `Bearer ${token.access_token}` };
}

async function reviewUser(request: APIRequestContext, userId: string, action: "approved" | "rejected") {
  const headers = await authHeaders(request, ADMIN.username, ADMIN.password);
  const response = await request.post(`${BACKEND}/api/v1/admin/users/${userId}/review`, {
    headers,
    data: { action, remark: "E2E permission boundary" },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

async function loginPage(page: Page, username: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel(/鐢ㄦ埛鍚峾閻€劍鍩涢崥?/).fill(username);
  await page.getByLabel(/瀵嗙爜|鐎靛棛鐖?).fill(password);
  await Promise.all([
    page.waitForURL("**/", { timeout: 15000 }),
    page.locator("form").getByRole("button", { name: /鐧诲綍|閻ц缍? }).click(),
  ]);
}

async function callStatus(request: APIRequestContext, method: "get" | "post" | "put" | "delete", url: string, options: any = {}) {
  const response = await request[method](url, options);
  return response.status();
}

async function expectGuestGate(page: Page) {
  await page.waitForFunction(() => {
    const text = document.body?.innerText || "";
    return (
      text.includes("需要登录") ||
      text.includes("登录以使用完整功能") ||
      text.includes("登录后可浏览公共题库") ||
      text.includes("请先登录以访问此功能")
    );
  }, null, { timeout: 15000 });

  await expect(page.locator("body")).toContainText(
    /需要登录|登录以使用完整功能|登录后可浏览公共题库|请先登录以访问此功能/
  );
}

test.describe.serial("permission boundaries", () => {
  test.beforeAll(async () => {});

  test("admin-only APIs and pages reject non-admins", async ({ request, page }) => {
    const userHeaders = await authHeaders(request, USER_A.username);

    expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users/pending`)).toBe(401);
    expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users/pending`, { headers: userHeaders })).toBe(403);
    expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users`, { headers: userHeaders })).toBe(403);
    expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/audit-logs`, { headers: userHeaders })).toBe(403);

    await page.goto("/admin/review");
    await expect(page).toHaveURL(/\/$/);

    await loginPage(page, USER_A.username);
    await page.goto("/admin/review");
    await expect(page).toHaveURL(/\/$/);
      await expectGuestGate(page);
  });

  test("guest pages and module APIs are gated", async ({ request, page }) => {
    const guestStatuses = [
      await callStatus(request, "get", `${BACKEND}/api/v1/questions?page=1&page_size=1`),
      await callStatus(request, "get", `${BACKEND}/api/v1/study/stats`),
      await callStatus(request, "post", `${BACKEND}/api/v1/import/text`, { form: { text: "What is RAG?" } }),
      await callStatus(request, "post", `${BACKEND}/api/v1/exams/sessions`, {
        data: { title: "guest exam", duration_minutes: 10, question_count: 1 },
      }),
      await callStatus(request, "post", `${BACKEND}/api/v1/chat/session`),
      await callStatus(request, "post", `${BACKEND}/api/v1/ai/interview/start`, {
        data: { domain: "RAG", max_turns: 1 },
      }),
    ];
    expect(guestStatuses).toEqual([401, 401, 401, 401, 401, 401]);

    const gatedPages = ["/questions", "/import", "/study", "/stats", "/exam", "/interview"];
    for (const path of gatedPages) {
      await page.goto(path);
      await expectGuestGate(page);
    }
  });

  test("write APIs require login and enforce ownership", async ({ request }) => {
    const userAHeaders = await authHeaders(request, USER_A.username);
    const userBHeaders = await authHeaders(request, USER_B.username);

    const guestCreate = await request.post(`${BACKEND}/api/v1/questions/`, {
      data: { title: `E2E guest write ${suffix}`, content: "guest write", source_type: "E2E_PERM" },
    });
    expect(guestCreate.status()).toBe(401);

    const createA = await request.post(`${BACKEND}/api/v1/questions/`, {
      headers: userAHeaders,
      data: { title: `E2E user A write ${suffix}`, content: `E2E user A write ${suffix}`, source_type: "E2E_PERM" },
    });
    expect(createA.ok(), await createA.text()).toBeTruthy();
    const questionA = await createA.json() as { id: string };

    expect(await callStatus(request, "put", `${BACKEND}/api/v1/questions/${questionA.id}`, {
      headers: userBHeaders,
      data: { title: "cross update should fail" },
    })).toBe(403);
    expect(await callStatus(request, "delete", `${BACKEND}/api/v1/questions/${questionA.id}`, { headers: userBHeaders })).toBe(403);

    const ownUpdate = await request.put(`${BACKEND}/api/v1/questions/${questionA.id}`, {
      headers: userAHeaders,
      data: { title: `E2E user A updated ${suffix}` },
    });
    expect(ownUpdate.ok(), await ownUpdate.text()).toBeTruthy();
  });

  test("pending, rejected, and disabled accounts are blocked from login and guided to the right page", async ({ request, page }) => {
    const pendingLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: PENDING });
    expect(pendingLogin.status()).toBe(403);

    const rejectedLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: REJECTED });
    expect(rejectedLogin.status()).toBe(403);

    const disabledLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: DISABLED });
    expect(disabledLogin.status()).toBe(401);

    await page.goto("/login");
    await page.getByRole("button", { name: /娉ㄥ唽|濞夈劌鍞? }).click();
    await page.getByLabel(/鐢ㄦ埛鍚峾閻€劍鍩涢崥?/).fill(`e2e_perm_ui_pending_${suffix}`);
    await page.getByLabel(/瀵嗙爜|鐎靛棛鐖?).fill(PASSWORD);
    await page.getByLabel(/閭|闁喚顔?).fill(`perm_ui_pending_${suffix}@example.test`);
    await page.locator("form").getByRole("button", { name: /娉ㄥ唽|濞夈劌鍞? }).click();
    await expect(page).toHaveURL(/\/pending/);
  });

  test("token refresh and logout behave correctly", async ({ request, page }) => {
    const tokens = await loginApi(request, USER_A.username);

    const refresh = await request.post(`${BACKEND}/api/v1/auth/refresh`, {
      data: { refresh_token: tokens.refresh_token },
    });
    expect(refresh.ok(), await refresh.text()).toBeTruthy();

    const accessAsRefresh = await request.post(`${BACKEND}/api/v1/auth/refresh`, {
      data: { refresh_token: tokens.access_token },
    });
    expect(accessAsRefresh.status()).toBe(401);

    const invalidMe = await request.get(`${BACKEND}/api/v1/auth/me`, {
      headers: { Authorization: "Bearer invalid.token.value" },
    });
    expect(invalidMe.status()).toBe(401);

    await loginPage(page, USER_A.username);
      await expectGuestGate(page);
    await page.evaluate((badToken) => {
      const raw = localStorage.getItem("ipa_auth_tokens");
      if (!raw) throw new Error("missing auth tokens");
      const tokens = JSON.parse(raw);
      tokens.accessToken = badToken;
      tokens.expiresAt = Date.now() + 60 * 60 * 1000;
      localStorage.setItem("ipa_auth_tokens", JSON.stringify(tokens));
    }, `bad.${suffix}.token`);
    const refreshTriggered = page.waitForResponse((response) =>
      response.url().includes("/api/v1/auth/refresh") && response.request().method() === "POST",
    );
    await page.reload();
    await refreshTriggered;
      await expectGuestGate(page);
    await page.locator("header button").filter({ hasText: USER_A.username }).click();
    await page.getByRole("button", { name: /閫�鍑虹櫥褰晐闁偓閸戣櫣娅ヨぐ?/ }).click();
      await expectGuestGate(page);
    expect(await page.evaluate(() => localStorage.getItem("ipa_auth_tokens"))).toBeNull();
  });

  test("study records are isolated per user even for shared public questions", async ({ request }) => {
    const adminHeaders = await authHeaders(request, ADMIN.username, ADMIN.password);
    const userAHeaders = await authHeaders(request, USER_A.username);
    const userBHeaders = await authHeaders(request, USER_B.username);

    const createPublic = await request.post(`${BACKEND}/api/v1/questions/`, {
      headers: adminHeaders,
      data: { title: `E2E public shared study ${suffix}`, content: `E2E public shared study ${suffix}`, source_type: "E2E_PERM_PUBLIC" },
    });
    expect(createPublic.ok(), await createPublic.text()).toBeTruthy();
    const publicQuestion = await createPublic.json() as { id: string };

    const recordA = await request.post(`${BACKEND}/api/v1/study/records`, {
      headers: userAHeaders,
      data: { question_id: publicQuestion.id, study_type: "practice", user_answer: "A private answer", ai_score: 91 },
    });
    expect(recordA.ok(), await recordA.text()).toBeTruthy();

    const listA = await request.get(`${BACKEND}/api/v1/study/records?page=1&page_size=100`, { headers: userAHeaders });
    const listB = await request.get(`${BACKEND}/api/v1/study/records?page=1&page_size=100`, { headers: userBHeaders });
    const recordsByQuestionA = await request.get(`${BACKEND}/api/v1/study/records/${publicQuestion.id}`, { headers: userAHeaders });
    const recordsByQuestionB = await request.get(`${BACKEND}/api/v1/study/records/${publicQuestion.id}`, { headers: userBHeaders });

    expect((await listA.json()).items.some((item: any) => item.user_answer === "A private answer")).toBeTruthy();
    expect((await listB.json()).items.some((item: any) => item.user_answer === "A private answer")).toBeFalsy();
    expect((await recordsByQuestionA.json()).items.some((item: any) => item.user_answer === "A private answer")).toBeTruthy();
    expect((await recordsByQuestionB.json()).items.some((item: any) => item.user_answer === "A private answer")).toBeFalsy();
  });
});
