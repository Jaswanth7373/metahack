import { useEffect, useRef, useState } from "react";
import { api, errorMessage, urls } from "../api";
import type { DocumentInfo, Lang, Sample } from "../types";
import { ErrorBanner } from "../components/ErrorBanner";
import { MicButton } from "../components/MicButton";
import { Badge } from "../components/Badge";
import { IconArrowRight, IconCamera, IconDoc, IconShield, IconSparkle, IconUpload } from "../components/Icons";
import { Spinner } from "../components/Spinner";

export const LANGUAGES: { code: string; label: string }[] = [
  { code: "auto", label: "Auto-detect" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "te", label: "తెలుగు" },
  { code: "fr", label: "Français" },
  { code: "ar", label: "العربية" },
  { code: "zh", label: "中文" },
  { code: "pt", label: "Português" },
];

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = /\.(pdf|png|jpe?g)$/i;

export function Home({
  doc,
  setDoc,
  onStart,
  starting,
  startError,
  clearStartError,
  onSpend,
}: {
  doc: DocumentInfo | null;
  setDoc: (d: DocumentInfo | null) => void;
  onStart: (requestText: string, language: string) => void;
  starting: boolean;
  startError: string | null;
  clearStartError: () => void;
  onSpend: () => void;
}) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [samplesError, setSamplesError] = useState<string | null>(null);
  const [loadingDoc, setLoadingDoc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("auto");
  const [detected, setDetected] = useState<Lang | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceMeta, setVoiceMeta] = useState<{ model: string; replayed: boolean } | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadSamples = () => {
    setSamplesError(null);
    api
      .samples()
      .then(setSamples)
      .catch((e) => setSamplesError(errorMessage(e)));
  };
  useEffect(loadSamples, []);

  async function pickSample(s: Sample) {
    setError(null);
    setLoadingDoc(s.id);
    try {
      const d = await api.fromSample(s.id);
      setDoc(d);
      setText(s.suggested_request);
      setDetected(null);
      setVoiceMeta(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingDoc(null);
    }
  }

  async function onFile(f: File | undefined) {
    if (!f) return;
    setError(null);
    if (!ALLOWED.test(f.name) && !/^image\/(png|jpeg)$|^application\/pdf$/.test(f.type)) {
      setError("Please choose a PDF, PNG or JPG file.");
      return;
    }
    if (f.size > MAX_BYTES) {
      setError("That file is larger than 10 MB. Please choose a smaller file or a lower-resolution photo.");
      return;
    }
    setLoadingDoc("upload");
    try {
      const d = await api.upload(f);
      setDoc(d);
      setText("");
      setDetected(null);
      setVoiceMeta(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingDoc(null);
      if (cameraRef.current) cameraRef.current.value = "";
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onAudio(wav: Blob) {
    setError(null);
    setTranscribing(true);
    try {
      const t = await api.transcribe(wav, language);
      setText(t.text);
      setDetected(t.language);
      setVoiceMeta({ model: t.model, replayed: t.replayed });
      if (t.language?.code && language === "auto") {
        const match = LANGUAGES.find((l) => l.code === t.language!.code.split("-")[0]);
        if (match) setLanguage(match.code);
      }
      onSpend();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setTranscribing(false);
    }
  }

  const hiddenInputs = (
    <>
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
    </>
  );

  if (!doc) {
    return (
      <div className="animate-fade-in">
        {hiddenInputs}
        <section className="pt-6 sm:pt-10">
          <p className="eyebrow">What paperwork are you trying to handle?</p>
          <h1 className="mt-2 text-[2.1rem] font-bold leading-[1.1] text-ink-950 sm:text-5xl">
            Understand paperwork.
            <br />
            <span className="text-accent-600">Take action with confidence.</span>
          </h1>
          <p className="mt-4 max-w-xl text-[1.05rem] leading-relaxed text-ink-600">
            Photograph a notice or form, say what you need in your own language, and PaperPilot explains it, plans the steps, fills the
            form, drafts a reply and tracks the deadline.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200">
            <IconShield className="h-4 w-4" />
            Your personal information is protected on this device before any cloud AI sees it.
          </div>
        </section>

        {error && (
          <div className="mt-5">
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <section className="mt-6 grid gap-3 sm:grid-cols-2">
          <button
            className="card flex min-h-[88px] items-center gap-4 p-4 text-left transition hover:border-accent-300 hover:shadow-lift"
            onClick={() => cameraRef.current?.click()}
            disabled={!!loadingDoc}
          >
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-accent-600 text-white">
              <IconCamera className="h-6 w-6" />
            </span>
            <span>
              <span className="block text-[1.05rem] font-semibold">Take photo</span>
              <span className="block text-sm text-ink-500">Use your phone camera</span>
            </span>
          </button>
          <button
            className="card flex min-h-[88px] items-center gap-4 p-4 text-left transition hover:border-accent-300 hover:shadow-lift"
            onClick={() => fileRef.current?.click()}
            disabled={!!loadingDoc}
          >
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-ink-900 text-white">
              {loadingDoc === "upload" ? <Spinner className="h-6 w-6" /> : <IconUpload className="h-6 w-6" />}
            </span>
            <span>
              <span className="block text-[1.05rem] font-semibold">Upload PDF or image</span>
              <span className="block text-sm text-ink-500">PDF, PNG or JPG · up to 10 MB</span>
            </span>
          </button>
        </section>

        <section className="mt-8">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Try a sample</h2>
            <span className="text-sm text-ink-500">Fictional documents</span>
          </div>
          {samplesError && (
            <div className="mt-3">
              <ErrorBanner message={samplesError} onRetry={loadSamples} />
            </div>
          )}
          <div className="mt-3 grid gap-3">
            {samples.map((s) => (
              <button
                key={s.id}
                onClick={() => pickSample(s)}
                disabled={!!loadingDoc}
                className="card group flex items-center gap-4 p-4 text-left transition hover:border-accent-300 hover:shadow-lift"
              >
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-ink-100 text-ink-700">
                  {loadingDoc === s.id ? <Spinner className="h-5 w-5" /> : <IconDoc className="h-6 w-6" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{s.title}</span>
                  <span className="block text-sm text-ink-500">{s.description}</span>
                </span>
                <IconArrowRight className="h-5 w-5 text-ink-400 transition group-hover:translate-x-0.5 group-hover:text-accent-600" />
              </button>
            ))}
            {!samples.length && !samplesError && (
              <div className="card flex items-center gap-3 p-4 text-ink-500">
                <Spinner className="h-5 w-5" /> Loading samples…
              </div>
            )}
          </div>
        </section>

        <section className="mt-10 grid gap-3 sm:grid-cols-3">
          {[
            ["Explains", "Plain language, in your language."],
            ["Acts", "Plans steps, fills the form, drafts the reply."],
            ["Protects", "Personal data is redacted locally first."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-2xl bg-white/60 p-4 ring-1 ring-inset ring-ink-200/70">
              <p className="font-semibold">{t}</p>
              <p className="mt-1 text-sm text-ink-600">{d}</p>
            </div>
          ))}
        </section>
      </div>
    );
  }

  return (
    <div className="animate-fade-in pt-4">
      {hiddenInputs}
      <div className="card flex items-center gap-4 p-3">
        <img
          src={urls.originalPage(doc.document_id, 0)}
          alt="First page of your document"
          className="h-24 w-[74px] shrink-0 rounded-lg border border-ink-200 bg-ink-50 object-cover object-top"
        />
        <div className="min-w-0 flex-1">
          <p className="eyebrow">Your document</p>
          <p className="truncate font-semibold">{doc.filename}</p>
          <p className="text-sm text-ink-500">
            {doc.page_count} page{doc.page_count === 1 ? "" : "s"} · stays on this device until redacted
          </p>
        </div>
        <button className="btn-ghost text-sm" onClick={() => setDoc(null)}>
          Change
        </button>
      </div>

      <section className="card mt-4 p-5 sm:p-6">
        <MicButton onAudio={onAudio} busy={transcribing} disabled={starting} />

        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="request" className="label mb-0">
              What do you need?
            </label>
            <div className="flex items-center gap-1.5">
              {detected && <Badge tone="accent">Detected: {detected.name}</Badge>}
              {voiceMeta && (
                <Badge tone={voiceMeta.replayed ? "replay" : "cloud"} title="Speech-to-text model">
                  {voiceMeta.model}
                  {voiceMeta.replayed ? " · replayed" : ""}
                </Badge>
              )}
            </div>
          </div>
          <textarea
            id="request"
            className="input mt-1.5 min-h-[110px] resize-y leading-relaxed"
            placeholder="e.g. “I don't understand this notice. Please help me respond before the deadline.” — or tap the mic and speak in your language."
            value={text}
            onChange={(e) => setText(e.target.value)}
            dir="auto"
          />
        </div>

        <div className="mt-4">
          <label htmlFor="lang" className="label">
            Explain in
          </label>
          <select id="lang" className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        {(error || startError) && (
          <div className="mt-4">
            <ErrorBanner
              message={(error || startError)!}
              onDismiss={() => {
                setError(null);
                clearStartError();
              }}
            />
          </div>
        )}

        <button
          className="btn-primary mt-5 w-full py-3.5 text-[1.05rem]"
          disabled={!text.trim() || starting || transcribing}
          onClick={() => onStart(text.trim(), language)}
        >
          {starting ? <Spinner className="h-5 w-5" /> : <IconSparkle className="h-5 w-5" />}
          Start
        </button>
        <p className="mt-3 text-center text-sm text-ink-500">PaperPilot will ask you to review and confirm before anything is finalized.</p>
      </section>
    </div>
  );
}
