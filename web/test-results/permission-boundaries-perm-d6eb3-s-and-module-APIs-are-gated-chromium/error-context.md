# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: permission-boundaries.spec.ts >> permission boundaries >> guest pages and module APIs are gated
- Location: e2e\permission-boundaries.spec.ts:75:7

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: locator('body')
Expected pattern: /登录|鐧诲綍|閫€鍑虹櫥褰?|\u767b\u5f55/
Received string:  "AIAI 面试知识库让学习、刷题与面试训练形成闭环首页题目题库加载中..."
Timeout: 15000ms

Call log:
  - Expect "toContainText" with timeout 15000ms
  - waiting for locator('body')
    18 × locator resolved to <body class="__variable_1e4310 __variable_c3aa02 antialiased min-h-screen bg-app-bg text-app-fg">…</body>
       - unexpected value "AIAI 面试知识库让学习、刷题与面试训练形成闭环首页题目题库加载中..."

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - banner [ref=e3]:
    - generic [ref=e4]:
      - link "AI AI 面试知识库 让学习、刷题与面试训练形成闭环" [ref=e5] [cursor=pointer]:
        - /url: /
        - generic [ref=e6]: AI
        - generic [ref=e7]:
          - generic [ref=e8]: AI 面试知识库
          - generic [ref=e9]: 让学习、刷题与面试训练形成闭环
      - navigation [ref=e10]:
        - link "首页" [ref=e11] [cursor=pointer]:
          - /url: /
        - link "题目" [ref=e12] [cursor=pointer]:
          - /url: /questions
  - main [ref=e14]:
    - paragraph [ref=e19]: 加载中...
```

# Test source

```ts
  1   | import { expect, test, type APIRequestContext, type Page } from "playwright/test";
  2   | 
  3   | const BACKEND = "http://localhost:8000";
  4   | const ADMIN = { username: "e2e_admin", password: "Admin123!" };
  5   | const PASSWORD = "User123!";
  6   | const suffix = "perm_boundaries";
  7   | 
  8   | const USER_A = { username: `e2e_perm_a_${suffix}`, password: PASSWORD, email: `perm_a_${suffix}@example.test` };
  9   | const USER_B = { username: `e2e_perm_b_${suffix}`, password: PASSWORD, email: `perm_b_${suffix}@example.test` };
  10  | const PENDING = { username: `e2e_perm_pending_${suffix}`, password: PASSWORD, email: `perm_pending_${suffix}@example.test` };
  11  | const REJECTED = { username: `e2e_perm_rejected_${suffix}`, password: PASSWORD, email: `perm_rejected_${suffix}@example.test` };
  12  | const DISABLED = { username: `e2e_perm_disabled_${suffix}`, password: PASSWORD, email: `perm_disabled_${suffix}@example.test` };
  13  | 
  14  | async function registerUser(request: APIRequestContext, user: { username: string; password: string; email: string }) {
  15  |   const response = await request.post(`${BACKEND}/api/v1/auth/register`, { data: user });
  16  |   expect(response.ok(), await response.text()).toBeTruthy();
  17  |   return (await response.json()) as { user_id: string; username: string; review_status: string };
  18  | }
  19  | 
  20  | async function loginApi(request: APIRequestContext, username: string, password = PASSWORD) {
  21  |   const response = await request.post(`${BACKEND}/api/v1/auth/login`, { data: { username, password } });
  22  |   expect(response.ok(), await response.text()).toBeTruthy();
  23  |   return (await response.json()) as { access_token: string; refresh_token: string; expires_in: number };
  24  | }
  25  | 
  26  | async function authHeaders(request: APIRequestContext, username: string, password = PASSWORD) {
  27  |   const token = await loginApi(request, username, password);
  28  |   return { Authorization: `Bearer ${token.access_token}` };
  29  | }
  30  | 
  31  | async function reviewUser(request: APIRequestContext, userId: string, action: "approved" | "rejected") {
  32  |   const headers = await authHeaders(request, ADMIN.username, ADMIN.password);
  33  |   const response = await request.post(`${BACKEND}/api/v1/admin/users/${userId}/review`, {
  34  |     headers,
  35  |     data: { action, remark: "E2E permission boundary" },
  36  |   });
  37  |   expect(response.ok(), await response.text()).toBeTruthy();
  38  | }
  39  | 
  40  | async function loginPage(page: Page, username: string, password = PASSWORD) {
  41  |   await page.goto("/login");
  42  |   await page.getByLabel(/用户名|鐢ㄦ埛鍚?/).fill(username);
  43  |   await page.getByLabel(/密码|瀵嗙爜/).fill(password);
  44  |   await Promise.all([
  45  |     page.waitForURL("**/", { timeout: 15000 }),
  46  |     page.locator("form").getByRole("button", { name: /登录|鐧诲綍/ }).click(),
  47  |   ]);
  48  | }
  49  | 
  50  | async function callStatus(request: APIRequestContext, method: "get" | "post" | "put" | "delete", url: string, options: any = {}) {
  51  |   const response = await request[method](url, options);
  52  |   return response.status();
  53  | }
  54  | 
  55  | test.describe.serial("permission boundaries", () => {
  56  |   test.beforeAll(async () => {});
  57  | 
  58  |   test("admin-only APIs and pages reject non-admins", async ({ request, page }) => {
  59  |     const userHeaders = await authHeaders(request, USER_A.username);
  60  | 
  61  |     expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users/pending`)).toBe(401);
  62  |     expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users/pending`, { headers: userHeaders })).toBe(403);
  63  |     expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/users`, { headers: userHeaders })).toBe(403);
  64  |     expect(await callStatus(request, "get", `${BACKEND}/api/v1/admin/audit-logs`, { headers: userHeaders })).toBe(403);
  65  | 
  66  |     await page.goto("/admin/review");
  67  |     await expect(page).toHaveURL(/\/$/);
  68  | 
  69  |     await loginPage(page, USER_A.username);
  70  |     await page.goto("/admin/review");
  71  |     await expect(page).toHaveURL(/\/$/);
  72  |     await expect(page.locator("body")).not.toContainText(/审核|瀹℃牳/);
  73  |   });
  74  | 
  75  |   test("guest pages and module APIs are gated", async ({ request, page }) => {
  76  |     const guestStatuses = [
  77  |       await callStatus(request, "get", `${BACKEND}/api/v1/questions?page=1&page_size=1`),
  78  |       await callStatus(request, "get", `${BACKEND}/api/v1/study/stats`),
  79  |       await callStatus(request, "post", `${BACKEND}/api/v1/import/text`, { form: { text: "What is RAG?" } }),
  80  |       await callStatus(request, "post", `${BACKEND}/api/v1/exams/sessions`, {
  81  |         data: { title: "guest exam", duration_minutes: 10, question_count: 1 },
  82  |       }),
  83  |       await callStatus(request, "post", `${BACKEND}/api/v1/chat/session`),
  84  |       await callStatus(request, "post", `${BACKEND}/api/v1/ai/interview/start`, {
  85  |         data: { domain: "RAG", max_turns: 1 },
  86  |       }),
  87  |     ];
  88  |     expect(guestStatuses).toEqual([401, 401, 401, 401, 401, 401]);
  89  | 
  90  |     const gatedPages = ["/questions", "/import", "/study", "/stats", "/exam", "/interview"];
  91  |     for (const path of gatedPages) {
  92  |       await page.goto(path);
> 93  |       await expect(page.locator("body")).toContainText(/登录|鐧诲綍|閫€鍑虹櫥褰?|\u767b\u5f55/);
      |                                          ^ Error: expect(locator).toContainText(expected) failed
  94  |     }
  95  |   });
  96  | 
  97  |   test("write APIs require login and enforce ownership", async ({ request }) => {
  98  |     const userAHeaders = await authHeaders(request, USER_A.username);
  99  |     const userBHeaders = await authHeaders(request, USER_B.username);
  100 | 
  101 |     const guestCreate = await request.post(`${BACKEND}/api/v1/questions/`, {
  102 |       data: { title: `E2E guest write ${suffix}`, content: "guest write", source_type: "E2E_PERM" },
  103 |     });
  104 |     expect(guestCreate.status()).toBe(401);
  105 | 
  106 |     const createA = await request.post(`${BACKEND}/api/v1/questions/`, {
  107 |       headers: userAHeaders,
  108 |       data: { title: `E2E user A write ${suffix}`, content: `E2E user A write ${suffix}`, source_type: "E2E_PERM" },
  109 |     });
  110 |     expect(createA.ok(), await createA.text()).toBeTruthy();
  111 |     const questionA = await createA.json() as { id: string };
  112 | 
  113 |     expect(await callStatus(request, "put", `${BACKEND}/api/v1/questions/${questionA.id}`, {
  114 |       headers: userBHeaders,
  115 |       data: { title: "cross update should fail" },
  116 |     })).toBe(403);
  117 |     expect(await callStatus(request, "delete", `${BACKEND}/api/v1/questions/${questionA.id}`, { headers: userBHeaders })).toBe(403);
  118 | 
  119 |     const ownUpdate = await request.put(`${BACKEND}/api/v1/questions/${questionA.id}`, {
  120 |       headers: userAHeaders,
  121 |       data: { title: `E2E user A updated ${suffix}` },
  122 |     });
  123 |     expect(ownUpdate.ok(), await ownUpdate.text()).toBeTruthy();
  124 |   });
  125 | 
  126 |   test("pending, rejected, and disabled accounts are blocked from login and guided to the right page", async ({ request, page }) => {
  127 |     const pendingLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: PENDING });
  128 |     expect(pendingLogin.status()).toBe(403);
  129 | 
  130 |     const rejectedLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: REJECTED });
  131 |     expect(rejectedLogin.status()).toBe(403);
  132 | 
  133 |     const disabledLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: DISABLED });
  134 |     expect(disabledLogin.status()).toBe(401);
  135 | 
  136 |     await page.goto("/login");
  137 |     await page.getByRole("button", { name: /注册|娉ㄥ唽/ }).click();
  138 |     await page.getByLabel(/用户名|鐢ㄦ埛鍚?/).fill(`e2e_perm_ui_pending_${suffix}`);
  139 |     await page.getByLabel(/密码|瀵嗙爜/).fill(PASSWORD);
  140 |     await page.getByLabel(/邮箱|閭/).fill(`perm_ui_pending_${suffix}@example.test`);
  141 |     await page.locator("form").getByRole("button", { name: /注册|娉ㄥ唽/ }).click();
  142 |     await expect(page).toHaveURL(/\/pending/);
  143 |   });
  144 | 
  145 |   test("token refresh and logout behave correctly", async ({ request, page }) => {
  146 |     const tokens = await loginApi(request, USER_A.username);
  147 | 
  148 |     const refresh = await request.post(`${BACKEND}/api/v1/auth/refresh`, {
  149 |       data: { refresh_token: tokens.refresh_token },
  150 |     });
  151 |     expect(refresh.ok(), await refresh.text()).toBeTruthy();
  152 | 
  153 |     const accessAsRefresh = await request.post(`${BACKEND}/api/v1/auth/refresh`, {
  154 |       data: { refresh_token: tokens.access_token },
  155 |     });
  156 |     expect(accessAsRefresh.status()).toBe(401);
  157 | 
  158 |     const invalidMe = await request.get(`${BACKEND}/api/v1/auth/me`, {
  159 |       headers: { Authorization: "Bearer invalid.token.value" },
  160 |     });
  161 |     expect(invalidMe.status()).toBe(401);
  162 | 
  163 |     await loginPage(page, USER_A.username);
  164 |     await expect(page.locator("header")).toContainText(USER_A.username);
  165 |     await page.evaluate((badToken) => {
  166 |       const raw = localStorage.getItem("ipa_auth_tokens");
  167 |       if (!raw) throw new Error("missing auth tokens");
  168 |       const tokens = JSON.parse(raw);
  169 |       tokens.accessToken = badToken;
  170 |       tokens.expiresAt = Date.now() + 60 * 60 * 1000;
  171 |       localStorage.setItem("ipa_auth_tokens", JSON.stringify(tokens));
  172 |     }, `bad.${suffix}.token`);
  173 |     const refreshTriggered = page.waitForResponse((response) =>
  174 |       response.url().includes("/api/v1/auth/refresh") && response.request().method() === "POST",
  175 |     );
  176 |     await page.reload();
  177 |     await refreshTriggered;
  178 |     await expect(page.locator("header")).toContainText(USER_A.username);
  179 |     await page.locator("header button").filter({ hasText: USER_A.username }).click();
  180 |     await page.getByRole("button", { name: /退出登录|閫€鍑虹櫥褰?/ }).click();
  181 |     await expect(page.locator("header")).not.toContainText(USER_A.username);
  182 |     expect(await page.evaluate(() => localStorage.getItem("ipa_auth_tokens"))).toBeNull();
  183 |   });
  184 | 
  185 |   test("study records are isolated per user even for shared public questions", async ({ request }) => {
  186 |     const adminHeaders = await authHeaders(request, ADMIN.username, ADMIN.password);
  187 |     const userAHeaders = await authHeaders(request, USER_A.username);
  188 |     const userBHeaders = await authHeaders(request, USER_B.username);
  189 | 
  190 |     const createPublic = await request.post(`${BACKEND}/api/v1/questions/`, {
  191 |       headers: adminHeaders,
  192 |       data: { title: `E2E public shared study ${suffix}`, content: `E2E public shared study ${suffix}`, source_type: "E2E_PERM_PUBLIC" },
  193 |     });
```