import { useState, useEffect, useRef, useCallback } from 'react';

export interface TaskEvent {
  event_type: string;
  task_id?: string;
  phase?: string;
  progress?: number;
  current?: string;
  total_chunks?: number;
  chunk_index?: number;
  chunk_type?: string;
  total?: number;
  question_id?: string;
  content?: string;
  total_generated?: number;
  error?: string;
  recoverable?: boolean;
  status?: string;
  elapsed?: number;
  token?: string;
  [key: string]: unknown;
}

interface UseTaskEventsReturn {
  events: TaskEvent[];
  progress: number;
  status: string;
  currentPhase: string | null;
  currentMessage: string | null;
  error: string | null;
  isRecoverable: boolean;
  elapsed: number;
  totalGenerated: number;
  isConnected: boolean;
  accumulatedContent: string;
  reset: () => void;
}

export function useTaskEvents(
  taskId: string | null,
  options?: { onDone?: (finalState: { status: string; progress: number }) => void }
): UseTaskEventsReturn {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [currentMessage, setCurrentMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRecoverable, setIsRecoverable] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [totalGenerated, setTotalGenerated] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [accumulatedContent, setAccumulatedContent] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const reconnectRef = useRef(0);
  const maxReconnects = 3;
  // Refs for break condition inside the stream loop (avoids stale closure issues)
  const doneRef = useRef(false);
  const onDoneRef = useRef(options?.onDone);
  onDoneRef.current = options?.onDone;
  // Ref for token accumulation (avoids stale closure in SSE loop)
  const contentRef = useRef('');

  // Poll DB for task status as fallback/baseline
  const pollDbStatus = useCallback(async (tid: string) => {
    try {
      const res = await fetch(`/api/v1/resumes/tasks/${tid}`);
      if (!res.ok) return;
      const task = await res.json();
      if (task.status) setStatus(task.status);
      if (task.progress != null) setProgress(task.progress);
      if (task.current_phase) setCurrentPhase(task.current_phase);
      if (task.error_message) {
        setError(task.error_message);
      }
    } catch {
      // ignore — SSE will provide state
    }
  }, []);

  const connect = useCallback(() => {
    if (!taskId || abortRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;
    doneRef.current = false;
    reconnectRef.current = 0;

    // Poll DB first for baseline state
    pollDbStatus(taskId);

    const connectStream = async () => {
      try {
        setIsConnected(true);
        const res = await fetch(`/api/v1/tasks/${taskId}/events`, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!res.ok || !res.body) {
          throw new Error(`Stream request failed: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let eventType = '';

        while (true) {
          if (doneRef.current) break;

          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.slice(5).trim());
                const event: TaskEvent = { event_type: eventType || 'message', ...data };
                setEvents(prev => [...prev, event]);

                if (data.progress != null) setProgress(data.progress);
                if (data.phase) setCurrentPhase(data.phase);
                if (data.current) setCurrentMessage(data.current);
                if (data.elapsed != null) setElapsed(Math.round(data.elapsed));
                if (data.total_generated != null) setTotalGenerated(data.total_generated);
                if (data.status) setStatus(data.status);

                if (eventType === 'token' && data.token) {
                  contentRef.current += data.token;
                  setAccumulatedContent(contentRef.current);
                }

                if (eventType === 'done') {
                  doneRef.current = true;
                  setProgress(1);
                  // Poll DB to confirm final state
                  pollDbStatus(taskId);
                  onDoneRef.current?.({ status: data.status || 'done', progress: 1 });
                  break;
                } else if (eventType === 'error') {
                  setError(data.error || 'Unknown error');
                  setIsRecoverable(!!data.recoverable);
                  if (!data.recoverable) {
                    doneRef.current = true;
                    setStatus('failed');
                    // Poll DB to confirm error state
                    pollDbStatus(taskId);
                    break;
                  }
                }
              } catch {
                // ignore parse errors
              }
              eventType = '';
            }
          }
        }
      } catch (e: unknown) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          return;
        }
        setIsConnected(false);
        // Attempt reconnect
        if (reconnectRef.current < maxReconnects) {
          reconnectRef.current += 1;
          setTimeout(() => {
            if (!controller.signal.aborted && !doneRef.current) {
              connectStream();
            }
          }, 2000);
        } else {
          setError('Connection lost');
        }
      } finally {
        setIsConnected(false);
        abortRef.current = null;
      }
    };

    connectStream();
  }, [taskId, pollDbStatus]);

  useEffect(() => {
    connect();
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, [connect]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    reconnectRef.current = 0;
    doneRef.current = false;
    setEvents([]);
    setProgress(0);
    setStatus('pending');
    setCurrentPhase(null);
    setCurrentMessage(null);
    setError(null);
    setIsRecoverable(false);
    setElapsed(0);
    setTotalGenerated(0);
    setIsConnected(false);
    setAccumulatedContent('');
    contentRef.current = '';
  }, []);

  return {
    events, progress, status, currentPhase, currentMessage,
    error, isRecoverable, elapsed, totalGenerated, isConnected,
    accumulatedContent, reset,
  };
}
