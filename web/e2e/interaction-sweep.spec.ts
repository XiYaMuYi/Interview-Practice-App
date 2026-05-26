import { expect, test, type Page, type TestInfo } from "playwright/test";

type Finding = {
  page: string;
  kind: "console" | "pageerror" | "requestfailed" | "response" | "stuck-loading" | "action";
  detail: string;
};

const pagesToSweep = [
  { path: "/", name: "home" },
  { path: "/questions", name: "questions" },
  { path: "/import", name: "import" },
  { path: "/study", name: "study" },
  { path: "/interview", name: "interview" },
  { path: "/exam", name: "exam" },
  { path: "/stats", name: "stats" },
] as const;

const dangerousActionPattern =
  /删除|移除|清空|退出|登出|注销|提交|完成|结束|重置|确认|开始考试|创建考试|开始面试|上传|导入|生成|评分|讲解|登录|注册/i;

const safeButtonPattern =
  /搜索|应用筛选|清除筛选|随机抽题|再随机一题|首页|上一页|下一页|末页|跳转|练习模式|待复习|学习统计|公开模式|题目|导入|学习|面试|考试|统计|首页/i;

function isAppUrl(url: string) {
  return url.includes("/api/") || url.includes("127.0.0.1") || url.includes("localhost");
}

function isIgnoredResponse(url: string, status: number) {
  if (url.includes("/_next/")) return true;
  if (url.includes("/favicon")) return true;
  if (status < 400) return true;
  return false;
}

async function attachFindings(testInfo: TestInfo, findings: Finding[]) {
  await testInfo.attach("interaction-sweep-findings.json", {
    body: JSON.stringify(findings, null, 2),
    contentType: "application/json",
  });
}

async function waitForUiToSettle(page: Page) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(300);
}

async function assertNotBlank(page: Page) {
  await expect(page.locator("body")).toBeVisible();
  const bodyText = (await page.locator("body").innerText()).trim();
  expect(bodyText.length).toBeGreaterThan(0);
}

async function assertNoPermanentLoading(page: Page, findings: Finding[], pageName: string) {
  await page.waitForTimeout(800);
  const loading = page.getByText(/加载中|处理中|生成中|评分中|抽题中|Loading/i).first();
  if (await loading.isVisible().catch(() => false)) {
    await page.waitForTimeout(4_000);
    if (await loading.isVisible().catch(() => false)) {
      findings.push({
        page: pageName,
        kind: "stuck-loading",
        detail: `Possible stuck loading text: ${(await loading.innerText().catch(() => "")).trim()}`,
      });
    }
  }
}

async function instrumentPage(page: Page, findings: Finding[], pageName: string) {
  page.on("console", (message) => {
    if (message.type() === "error") {
      findings.push({ page: pageName, kind: "console", detail: message.text() });
    }
  });

  page.on("pageerror", (error) => {
    findings.push({ page: pageName, kind: "pageerror", detail: error.message });
  });

  page.on("requestfailed", (request) => {
    const failure = request.failure();
    const url = request.url();
    if (isAppUrl(url)) {
      findings.push({
        page: pageName,
        kind: "requestfailed",
        detail: `${request.method()} ${url} ${failure?.errorText ?? ""}`.trim(),
      });
    }
  });

  page.on("response", (response) => {
    const url = response.url();
    const status = response.status();
    if (!isIgnoredResponse(url, status) && isAppUrl(url)) {
      findings.push({
        page: pageName,
        kind: "response",
        detail: `${status} ${response.request().method()} ${url}`,
      });
    }
  });
}

test.describe("frontend interaction sweep", () => {
  for (const target of pagesToSweep) {
    test(`${target.name} page safe controls do not break the app`, async ({ page }, testInfo) => {
      const findings: Finding[] = [];
      await instrumentPage(page, findings, target.name);

      await page.goto(target.path);
      await waitForUiToSettle(page);
      await assertNotBlank(page);
      await assertNoPermanentLoading(page, findings, target.name);

      const selects = page.locator("select:visible");
      const selectCount = Math.min(await selects.count(), 6);
      for (let i = 0; i < selectCount; i += 1) {
        const select = selects.nth(i);
        const options = await select.locator("option").evaluateAll((nodes) =>
          nodes.map((node) => (node as HTMLOptionElement).value).filter(Boolean),
        );
        if (options[0]) {
          await select.selectOption(options[0]).catch((error) => {
            findings.push({ page: target.name, kind: "action", detail: `select ${i}: ${error}` });
          });
          await waitForUiToSettle(page);
        }
      }

      const checkboxes = page.locator("input[type='checkbox']:visible");
      const checkboxCount = Math.min(await checkboxes.count(), 4);
      for (let i = 0; i < checkboxCount; i += 1) {
        await checkboxes.nth(i).check().catch((error) => {
          findings.push({ page: target.name, kind: "action", detail: `checkbox ${i}: ${error}` });
        });
        await waitForUiToSettle(page);
      }

      const buttons = page.getByRole("button");
      const buttonCount = Math.min(await buttons.count(), 12);
      for (let i = 0; i < buttonCount; i += 1) {
        const button = buttons.nth(i);
        if (!(await button.isVisible().catch(() => false))) continue;
        if (!(await button.isEnabled().catch(() => false))) continue;

        const label = (await button.innerText().catch(() => "")).trim();
        const aria = (await button.getAttribute("aria-label").catch(() => "")) ?? "";
        const name = label || aria || `button ${i}`;

        if (dangerousActionPattern.test(name) && !safeButtonPattern.test(name)) continue;
        if (!safeButtonPattern.test(name)) continue;

        await button.click({ timeout: 5_000 }).catch((error) => {
          findings.push({ page: target.name, kind: "action", detail: `click "${name}": ${error}` });
        });
        await waitForUiToSettle(page);
        await assertNotBlank(page);
        await assertNoPermanentLoading(page, findings, target.name);
      }

      await attachFindings(testInfo, findings);
      expect(findings).toEqual([]);
    });
  }
});
