# Fix Exam Grading SSE Issue - Stuck at "0/10"

## Problem
After submitting an exam, the frontend gets stuck on the grading modal showing "正在批改... 0/10 题已批改" and never progresses, even though the backend completes grading successfully (confirmed via backend logs showing status='graded', total_score calculated).

## Root Cause Analysis
The SSE (Server-Sent Events) connection between frontend and backend for the grading endpoint (`/api/v1/exams/sessions/{exam_id}/grade`) is not properly delivering progress events to the frontend UI.

Key findings:
1. Backend successfully grades exams and sends SSE events (`grading_progress`, `grading_complete`)
2. Frontend uses `EventSource` to connect to `/api/v1/exams/sessions/{exam_id}/grade`
3. The frontend's `eventSource.onmessage` handler is not receiving the events properly
4. Backend sends events in format: `data: {json}\n\n` (unnamed events)
5. The `onerror` handler fires too aggressively, closing the connection before events arrive

## Files to Examine
- `web/src/app/exam/session/[id]/page.tsx` - Frontend exam page with grading modal
- `backend/app/api/v1/routes/exam_routes.py` - Backend `/grade` endpoint
- `backend/app/services/exam_service.py` - `grade_exam` service method

## Required Fixes

### 1. Fix SSE Event Handling
The frontend needs to properly handle both named and unnamed SSE events. Update the EventSource setup to:
- Use `addEventListener('message', ...)` as primary handler
- Add fallback handlers for specific event types
- Parse the JSON data correctly from `event.data`
- Handle the `grading_progress`, `grading_complete`, `token`, and `error` events

### 2. Fix Error Handler
The current `onerror` handler is too aggressive:
- It fires on initial connection and during reconnection attempts
- It closes the EventSource immediately, preventing event delivery
- Update to only handle actual errors (readyState === CLOSED after events received)

### 3. Add Timeout Protection
Add a timeout mechanism so if no events are received within a reasonable time (e.g., 10 minutes), the modal closes and shows an appropriate message instead of being stuck forever.

### 4. Verify Backend SSE Format
Ensure the backend is sending properly formatted SSE events:
```
data: {"event":"grading_progress","graded":1,"total":10}

data: {"event":"grading_complete","total_score":85.5}

```
Each event should end with double newline (`\n\n`).

## Testing Requirements
After making changes:
1. Verify the frontend properly receives and displays grading progress
2. Confirm the modal closes when grading completes
3. Ensure error cases are handled gracefully
4. Test that the exam results page loads after grading

## Important Notes
- Do NOT change the backend SSE event format or structure
- Preserve existing API contracts
- Keep the auto-save fix that prevents 400 errors after submission
- The fix should work with the existing Next.js dev server proxy configuration