import { expect, test, type APIRequestContext, type Page } from "playwright/test";

const BACKEND = "http://localhost:8000";
const ADMIN = { username: "e2e_admin", password: "Admin123!" };
const suffix = Date.now();
const USER_A = { username: `e2e_user_a_${suffix}`, password: "User123!", email: `a_${suffix}@example.test` };
const USER_B = { username: `e2e_user_b_${suffix}`, password: "User123!", email: `b_${suffix}@example.test` };
const PUBLIC_TITLE = `E2E public question ${suffix}`;
const PRIVATE_A_TITLE = `E2E private question A ${suffix}`;
const PRIVATE_B_TITLE = `E2E private question B ${suffix}`;

async function apiJson(request: APIRequestContext, path: string, options: Parameters<APIRequestContext["post"]>[1] = {}) {
  const response = await request.fetch(path, options as any);
  const text = await response.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  return { response, body, text };
}

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/用户名|鐢ㄦ埛/).fill(username);
  await page.getByLabel(/密码|瀵嗙爜/).fill(password);
  await Promise.all([
    page.waitForURL("**/", { timeout: 15000 }),
    page.locator("form").getByRole("button", { name: /登录|鐧诲綍/ }).click(),
  ]);
}

test.describe.serial("auth and permissions", () => {
  test("auth config and guest protection", async ({ request }) => {
    const cfg = await request.get(`${BACKEND}/api/v1/auth/config`);
    expect(cfg.ok()).toBeTruthy();
    await expect(cfg.json()).resolves.toMatchObject({ auth_enabled: true, public_mode: true });

    const guestStats = await request.get(`${BACKEND}/api/v1/study/stats`);
    expect(guestStats.status()).toBe(401);

    const guestQuestions = await request.get(`${BACKEND}/api/v1/questions?page=1&page_size=1`);
    expect(guestQuestions.status()).toBe(401);

    const guestSearch = await request.get(`${BACKEND}/api/v1/questions/search?q=E2E&page=1&page_size=1`);
    expect(guestSearch.status()).toBe(401);

    const guestRandom = await request.get(`${BACKEND}/api/v1/questions/random`);
    expect(guestRandom.status()).toBe(401);
  });

  test("guest question pages do not load question data", async ({ page }) => {
    const questionApiResponses: number[] = [];
    page.on("response", (response) => {
      if (response.url().includes("/api/v1/questions")) {
        questionApiResponses.push(response.status());
      }
    });

    await page.goto("/questions");
    await expect(page.locator("body")).toContainText(/登录|鐧诲綍|閻ц缍?/);
    await page.waitForTimeout(500);
    expect(questionApiResponses).toEqual([]);
  });

  test("register, approve, and login flows", async ({ request, page }) => {
    const adminLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: ADMIN });
    expect(adminLogin.ok()).toBeTruthy();
    const adminBody = await adminLogin.json();
    const adminToken = adminBody.access_token as string;

    for (const user of [USER_A, USER_B]) {
      const reg = await request.post(`${BACKEND}/api/v1/auth/register`, { data: user });
      expect(reg.ok()).toBeTruthy();
      const regBody = await reg.json();
      expect(regBody.review_status).toBe("pending");
    }

    const pendingLogin = await request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USER_A.username, password: USER_A.password },
    });
    expect(pendingLogin.ok()).toBeFalsy();

    const pendingList = await request.get(`${BACKEND}/api/v1/admin/users/pending`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(pendingList.ok()).toBeTruthy();
    const pendingUsers = await pendingList.json();
    expect(pendingUsers.map((u: any) => u.username)).toEqual(expect.arrayContaining([USER_A.username, USER_B.username]));

    for (const user of pendingUsers.filter((u: any) => [USER_A.username, USER_B.username].includes(u.username))) {
      const review = await request.post(`${BACKEND}/api/v1/admin/users/${user.user_id}/review`, {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: { action: "approved", remark: "E2E approval" },
      });
      expect(review.ok()).toBeTruthy();
    }

    const loginA = await request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USER_A.username, password: USER_A.password },
    });
    const loginB = await request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USER_B.username, password: USER_B.password },
    });
    expect(loginA.ok()).toBeTruthy();
    expect(loginB.ok()).toBeTruthy();

    await login(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin/review");
    await expect(page.locator("body")).toContainText(/用户审核|鐢ㄦ埛瀹℃牳|暂无|鏆傛棤/);
    await expect(page.locator("header")).toContainText(/审核|瀹℃牳/);
  });

  test("data isolation and page control", async ({ request, page }) => {
    const adminLogin = await request.post(`${BACKEND}/api/v1/auth/login`, { data: ADMIN });
    const adminBody = await adminLogin.json();
    const adminToken = adminBody.access_token as string;

    const loginA = await request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USER_A.username, password: USER_A.password },
    });
    const loginB = await request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { username: USER_B.username, password: USER_B.password },
    });
    const loginAJson = await loginA.json();
    const loginBJson = await loginB.json();
    const tokenA = loginAJson.access_token as string;
    const tokenB = loginBJson.access_token as string;

    const createA = await request.post(`${BACKEND}/api/v1/questions/`, {
      headers: { Authorization: `Bearer ${tokenA}` },
      data: { title: PRIVATE_A_TITLE, content: PRIVATE_A_TITLE, source_type: "E2E_AUTH" },
    });
    const createB = await request.post(`${BACKEND}/api/v1/questions/`, {
      headers: { Authorization: `Bearer ${tokenB}` },
      data: { title: PRIVATE_B_TITLE, content: PRIVATE_B_TITLE, source_type: "E2E_AUTH" },
    });
    const createPublic = await request.post(`${BACKEND}/api/v1/questions/`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { title: PUBLIC_TITLE, content: PUBLIC_TITLE, source_type: "E2E_AUTH_PUBLIC" },
    });

    expect(createA.ok()).toBeTruthy();
    expect(createB.ok()).toBeTruthy();
    expect(createPublic.ok()).toBeTruthy();
    const createPublicJson = await createPublic.json();

    const listA = await request.get(`${BACKEND}/api/v1/questions?page=1&page_size=100&source_type=E2E_AUTH`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const listB = await request.get(`${BACKEND}/api/v1/questions?page=1&page_size=100&source_type=E2E_AUTH`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    const titlesA = (await listA.json()).items.map((item: any) => item.title);
    const titlesB = (await listB.json()).items.map((item: any) => item.title);
    expect(titlesA).toContain(PRIVATE_A_TITLE);
    expect(titlesA).not.toContain(PRIVATE_B_TITLE);
    expect(titlesB).toContain(PRIVATE_B_TITLE);
    expect(titlesB).not.toContain(PRIVATE_A_TITLE);

    const publicUser = await request.get(`${BACKEND}/api/v1/questions?page=1&page_size=100&source_type=E2E_AUTH_PUBLIC`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    const publicGuest = await request.get(`${BACKEND}/api/v1/questions?page=1&page_size=100&source_type=E2E_AUTH_PUBLIC`);
    expect((await publicUser.json()).items.map((item: any) => item.title)).toContain(PUBLIC_TITLE);
    expect(publicGuest.status()).toBe(401);

    const publicGuestDetail = await request.get(`${BACKEND}/api/v1/questions/${createPublicJson.id}/detail`);
    expect(publicGuestDetail.status()).toBe(401);

    const createBJson = await createB.json();
    const crossRead = await request.get(`${BACKEND}/api/v1/questions/${createBJson.id}/detail`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    expect(crossRead.status()).toBe(403);

    const adminAttempt = await request.get(`${BACKEND}/api/v1/admin/users/pending`, {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    expect(adminAttempt.status()).toBe(403);

    const guestPage = await page.context().newPage();
    await guestPage.goto("/study");
    await expect(guestPage.locator("body")).toContainText(/登录|鐧诲綍/);
    await guestPage.close();

    await login(page, ADMIN.username, ADMIN.password);
    await page.goto("/study");
    await expect(page.locator("body")).toContainText(/学习|练习|统计/);
  });
});
