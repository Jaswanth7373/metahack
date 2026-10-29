import { useEffect, useRef, useState } from "react";
import { blobToWav, pickRecorderMime } from "../wav";
import { IconMic, IconStop } from "./Icons";
import { Spinner } from "./Spinner";

type State = "idle" | "recording" | "processing";

export function MicButton({
  onAudio,
  disabled,
  busy,
}: {
  onAudio: (wav: Blob) => void | Promise<void>;
  disabled?: boolean;
  busy?: boolean;
}) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (timer.current) window.clearInterval(timer.current);
    },
    [],
  );

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickRecorderMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timer.current) window.clearInterval(timer.current);
        setState("processing");
        try {
          const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
          const wav = await blobToWav(blob);
          await onAudio(wav);
        } catch {
          setError("We couldn't process that recording. Please try again or type your request.");
        } finally {
          setState("idle");
        }
      };
      recRef.current = rec;
      rec.start();
      setSeconds(0);
      timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      setState("recording");
    } catch {
      setError("Microphone access was blocked. You can type your request instead.");
      setState("idle");
    }
  }

  function stop() {
    recRef.current?.stop();
  }

  const working = state === "processing" || busy;
  return (
    <div className="flex flex-col items-center">
      <button
        type="button"
        onClick={state === "recording" ? stop : start}
        disabled={disabled || working || !supported}
        aria-pressed={state === "recording"}
        aria-label={state === "recording" ? "Stop recording" : "Tell PaperPilot what you need"}
        className={`relative inline-flex h-20 w-20 items-center justify-center rounded-full text-white shadow-lift transition-colors disabled:opacity-60 ${
          state === "recording" ? "bg-rose-600 animate-pulsering" : "bg-accent-600 hover:bg-accent-700"
        }`}
      >
        {working ? <Spinner className="h-7 w-7" /> : state === "recording" ? <IconStop className="h-8 w-8" /> : <IconMic className="h-9 w-9" />}
      </button>
      <p className="mt-3 text-center text-[0.95rem] font-semibold text-ink-800" aria-live="polite">
        {!supported
          ? "Voice input isn't supported in this browser"
          : state === "recording"
            ? `Listening… ${seconds}s — tap to finish`
            : working
              ? "Transcribing with Meta Voice Transcribe…"
              : "Tell PaperPilot what you need"}
      </p>
      <p className="mt-0.5 text-center text-sm text-ink-500">Speak in any language</p>
      {error && <p className="mt-2 text-center text-sm text-rose-700">{error}</p>}
    </div>
  );
}
