import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";
import type { DocumentInfo, Health, Task } from "./types";
import { TopBar } from "./components/TopBar";
import { Footer } from "./components/Footer";
import { TaskTabs, type TaskTab } from "./components/TaskTabs";
import { IconArrowLeft } from "./components/Icons";
import { Spinner } from "./components/Spinner";
import { Home } from "./screens/Home";
import { Timeline } from "./screens/Timeline";
import { Results } from "./screens/Results";
import { Privacy } from "./screens/Privacy";
import { Review } from "./screens/Review";
import { Done } from "./screens/Done";
import { Deadlines } from "./screens/Deadlines";

type Screen = "home" | "timeline" | "task" | "done" | "deadlines";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [screen, setScreen] = useState<Screen>("home");
  const [prevScreen, setPrevScreen] = useState<Screen>("home");
  const [tab, setTab] = useState<TaskTab>("results");
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [lastRun, setLastRun] = useState<{ text: string; language: string } | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshHealth();
    const id = window.setInterval(refreshHealth, 15000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [screen, tab]);

  async function start(text: string, language: string) {
    if (!doc) return;
    setStarting(true);
    setStartError(null);
    try {
      const { task_id } = await api.runAgent(doc.document_id, text, language);
      setLastRun({ text, language });
      setTask(null);
      setTaskId(task_id);
      setTab("results");
      setScreen("timeline");
    } catch (e) {
      setStartError(errorMessage(e));
    } finally {
      setStarting(false);
    }
  }

  function retry() {
    if (lastRun) void start(lastRun.text, lastRun.language);
    else setScreen("home");
  }

  function goDeadlines() {
    if (screen !== "deadlines") setPrevScreen(screen);
    setScreen("deadlines");
  }

  function newDocument() {
    setDoc(null);
    setTask(null);
    setTaskId(null);
    setScreen("home");
  }

  const needsReview = task?.fields.filter((f) => f.needs_review).length ?? 0;

  return (
    <div className="min-h-[100dvh]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <TopBar health={health} onHome={() => setScreen(task ? "task" : "home")} onDeadlines={goDeadlines} active={screen === "deadlines" ? "deadlines" : "other"} />
      <main id="main" className="mx-auto max-w-3xl px-4">
        {screen === "home" && (
          <Home
            doc={doc}
            setDoc={setDoc}
            onStart={start}
            starting={starting}
            startError={startError}
            clearStartError={() => setStartError(null)}
            onSpend={refreshHealth}
          />
        )}

        {screen === "timeline" && taskId && (
          <Timeline
            taskId={taskId}
            onDone={(t) => {
              // Re-subscribing replays the original `done` snapshot; keep any newer local state for the same task.
              setTask((cur) => (cur && cur.task_id === t.task_id ? cur : t));
              refreshHealth();
            }}
            onViewResults={() => {
              setTab("results");
              setScreen("task");
            }}
            onRetry={retry}
            onBack={() => setScreen("home")}
            onSpend={refreshHealth}
          />
        )}

        {screen === "task" && (
          <>
            <div className="flex items-center justify-between pt-4">
              <button className="btn-ghost -ml-3 text-sm" onClick={() => setScreen("timeline")} disabled={!taskId}>
                <IconArrowLeft className="h-4 w-4" /> Agent steps
              </button>
              <button className="btn-ghost -mr-3 text-sm" onClick={newDocument}>
                New document
              </button>
            </div>
            {task ? (
              <>
                <h1 className="text-[1.6rem] font-bold leading-tight sm:text-3xl">{task.document_title || "Your document"}</h1>
                <TaskTabs active={tab} onChange={setTab} needsReview={needsReview} />
                {tab === "results" && <Results task={task} onReview={() => setTab("review")} />}
                {tab === "privacy" && <Privacy taskId={task.task_id} />}
                {tab === "review" && (
                  <Review
                    task={task}
                    onTask={(t) => {
                      setTask(t);
                      refreshHealth();
                    }}
                    onConfirmed={(t) => {
                      setTask(t);
                      refreshHealth();
                      setScreen("done");
                    }}
                  />
                )}
              </>
            ) : (
              <div className="mt-10 flex items-center justify-center gap-2 text-ink-500">
                <Spinner className="h-5 w-5" /> Loading…
              </div>
            )}
          </>
        )}

        {screen === "done" && task && <Done task={task} onDeadlines={goDeadlines} onNew={newDocument} />}

        {screen === "deadlines" && (
          <>
            <div className="pt-4">
              <button className="btn-ghost -ml-3 text-sm" onClick={() => setScreen(prevScreen === "deadlines" ? "home" : prevScreen)}>
                <IconArrowLeft className="h-4 w-4" /> Back
              </button>
            </div>
            <Deadlines />
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}
