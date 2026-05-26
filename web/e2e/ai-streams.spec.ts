import { expect, test, type APIRequestContext } from "playwright/test";
import http from "node:http";
import https from "node:https";

type SseEvent = {
  event: string;
  data: Record<string, any>;
  raw: string;
};

function requireAiOptIn() {
  test.skip(process.env.E2E_RUN_AI !== "1", "Real LLM E2E is opt-in. Set E2E_RUN_AI=1 to run.");
}

function parseSseBlock(block: string): SseEvent | null {
  const lines = block.split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return null;

  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;

  const rawData = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(rawData), raw: block };
  } catch {
    return { event, data: { raw: rawData }, raw: block };
  }
}

async function readSse(
  url: string,
  options: {
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
    timeoutMs?: number;
    stopWhen?: (event: SseEvent, events: SseEvent[]) => boolean;
  } = {},
): Promise<SseEvent[]> {
  const parsed = new URL(url);
  const client = parsed.protocol === "https:" ? https : http;
  const method = options.method ?? "GET";
  const payload = options.body ? JSON.stringify(options.body) : undefined;
  const events: SseEvent[] = [];

  return new Promise((resolve, reject) => {
    let settled = false;
    let buffer = "";
    const req = client.request(
      parsed,
      {
        method,
        headers: {
          Accept: "text/event-stream",
          ...(payload ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) } : {}),
        },
      },
      (res) => {
        if ((res.statusCode ?? 500) >= 400) {
          let errorBody = "";
          res.on("data", (chunk) => { errorBody += chunk.toString("utf-8"); });
          res.on("end", () => {
            if (!settled) {
              settled = true;
              reject(new Error(`SSE request failed ${res.statusCode}: ${errorBody}`));
            }
          });
          return;
        }

        res.on("data", (chunk: Buffer) => {
          buffer += chunk.toString("utf-8");
          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() ?? "";

          for (const block of blocks) {
            const event = parseSseBlock(block);
            if (!event) continue;
            events.push(event);
            if (options.stopWhen?.(event, events) && !settled) {
              settled = true;
              req.destroy();
              resolve(events);
              return;
            }
          }
        });

        res.on("end", () => {
          if (!settled) {
            const event = parseSseBlock(buffer);
            if (event) events.push(event);
            settled = true;
            resolve(events);
          }
        });
      },
    );

    req.on("error", (error) => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    });

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        req.destroy();
        reject(new Error(`Timed out waiting for SSE from ${url}`));
      }
    }, options.timeoutMs ?? 180_000);

    req.on("close", () => clearTimeout(timer));
    if (payload) req.write(payload);
    req.end();
  });
}

async function getRandomQuestionId(request: APIRequestContext) {
  const response = await request.get("/api/v1/questions/random");
  expect(response.ok(), await response.text()).toBeTruthy();
  const question = await response.json() as { id?: string; title?: string };
  expect(question.id).toBeTruthy();
  return question.id!;
}

test.describe("real AI streaming flows", () => {
  test.beforeEach(() => {
    requireAiOptIn();
  });

  test("real explain task emits progress and reaches done over task SSE", async ({ request, baseURL }) => {
    const origin = baseURL || "http://127.0.0.1:3000";
    const response = await request.post("/api/v1/ai/explain-stream", {
      data: {
        question_text: "In one short paragraph, explain what RAG does in an AI application.",
        depth: "brief",
      },
      timeout: 180_000,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const { task_id: taskId } = await response.json() as { task_id?: string };
    expect(taskId).toBeTruthy();

    const events = await readSse(`${origin}/api/v1/tasks/${taskId}/events`, {
      timeoutMs: 180_000,
      stopWhen: (event) => event.event === "done" || event.event === "error" || !!event.data.error,
    });

    expect(events.some((event) => event.event === "progress")).toBeTruthy();
    expect(events.some((event) => event.event === "token")).toBeTruthy();
    expect(events.some((event) => event.event === "content")).toBeTruthy();
    expect(events.some((event) => event.event === "done" && event.data.status === "done")).toBeTruthy();
  });

  test("real answer evaluation stream returns a scored result", async ({ request, baseURL }) => {
    const origin = baseURL || "http://127.0.0.1:3000";
    const questionId = await getRandomQuestionId(request);

    const events = await readSse(`${origin}/api/v1/ai/evaluate-stream`, {
      method: "POST",
      body: {
        question_id: questionId,
        user_answer: "I would explain the main concept, name the tradeoffs, and give a practical example.",
      },
      timeoutMs: 180_000,
      stopWhen: (event) => event.event === "done" || event.event === "error",
    });

    const result = events.find((event) => event.event === "result");
    expect(result?.data.score).toEqual(expect.any(Number));
    expect(result?.data.feedback ?? "").not.toHaveLength(0);
    expect(events.some((event) => event.event === "done")).toBeTruthy();
  });

  test("real interview start and turn stream produce a final response", async ({ request, baseURL }) => {
    const origin = baseURL || "http://127.0.0.1:3000";
    const startResponse = await request.post("/api/v1/ai/interview/start", {
      data: { domain: "RAG", max_turns: 1 },
      timeout: 180_000,
    });
    expect(startResponse.ok(), await startResponse.text()).toBeTruthy();
    const started = await startResponse.json() as { session_id?: string; first_question?: string };
    expect(started.session_id).toBeTruthy();
    expect(started.first_question).toBeTruthy();

    const events = await readSse(`${origin}/api/v1/ai/interview/turn-stream`, {
      method: "POST",
      body: {
        session_id: started.session_id,
        current_turn: 1,
        max_turns: 1,
        question_text: started.first_question,
        user_answer: "RAG retrieves relevant context first, then grounds generation on that context to reduce hallucination.",
      },
      timeoutMs: 240_000,
      stopWhen: (event) => event.event === "done" || event.event === "error",
    });

    const evaluation = events.find((event) => event.event === "evaluation");
    const done = events.find((event) => event.event === "done");
    expect(evaluation?.data.score).toEqual(expect.any(Number));
    expect(done?.data.status).toBe("done");
    expect(done?.data.is_done).toBeTruthy();
  });
});
