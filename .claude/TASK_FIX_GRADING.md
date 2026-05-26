# Fix Exam Grading SSE - Stuck at "0/10" Progress

## Problem
After submitting an exam, the frontend grading modal gets stuck showing "0/10 题已批改" and never updates, even though the backend completes grading successfully (confirmed via logs: status='graded', total_score calculated).

## Root Cause
The SSE (Server-Sent Events) connection for `/api/v1/exams/sessions/{id}/grade` is not properly delivering progress events to the frontend. The backend sends events but the frontend's EventSource handler doesn't receive them.

## Files to Fix
- `web/src/app/exam/session/[id]/page.tsx` - SSE event handling in handleSubmit
- `web/next.config.mjs` - Check if rewrite rules are buffering SSE streams
- `web/src/app/api/v1/exams/[...path]/route.ts` - If exists, ensure SSE passthrough

## Requirements
1. Ensure SSE events (grading_progress, grading_complete, error) are properly received and parsed
2. Handle both named SSE events (with `event:` line) and unnamed events (data-only)
3. Add timeout protection so modal doesn't freeze forever (close after ~10 min with message)
4. Don't change backend SSE format or API contracts
5. Keep existing auto-save fix that prevents 400 errors post-submission
6. Next.js dev server may buffer SSE - if rewrite is intercepting, add SSE passthrough headers or bypass

## Testing
Verify: progress updates display, modal closes on completion, errors handled gracefully.

When done, restart the Next.js dev server if next.config.mjs was changed.