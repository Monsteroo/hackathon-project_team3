import { useCallback, useEffect, useRef, useState } from "react";

export const MAX_RECORDING_S = 60; // рішення команди 21.11

// Chrome/Firefox пишуть webm/opus, Safari — mp4/aac. Whisper приймає обидва.
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

function pickMime() {
  if (typeof MediaRecorder === "undefined") return null;
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported?.(m)) ?? "";
}

const MIC_ERRORS = {
  NotAllowedError: "Доступ до мікрофона заборонено. Дозвольте його в налаштуваннях браузера або введіть текст.",
  NotFoundError: "Мікрофон не знайдено. Введіть запит текстом.",
  NotReadableError: "Мікрофон зайнятий іншою програмою.",
  SecurityError: "Мікрофон працює лише через HTTPS або localhost.",
};

/**
 * Запис голосу: status = idle | recording | stopped | error.
 * onStop(blob) викликається з готовим записом (автостоп на MAX_RECORDING_S).
 */
export function useVoiceRecorder({ onStop, maxSeconds = MAX_RECORDING_S } = {}) {
  const [status, setStatus] = useState("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const onStopRef = useRef(onStop);
  onStopRef.current = onStop;

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && pickMime() !== null;

  const cleanup = useCallback(() => {
    clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!supported) {
      setError("Цей браузер не підтримує запис звуку. Введіть запит текстом.");
      setStatus("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      streamRef.current = stream;
      const mime = pickMime();
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 32000 } : undefined);
      const chunks = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = () => {
        cleanup();
        setStatus("stopped");
        onStopRef.current?.(new Blob(chunks, { type: recorder.mimeType || mime || "audio/webm" }));
      };
      recorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
      setElapsed(0);
      const started = Date.now();
      timerRef.current = setInterval(() => {
        const s = (Date.now() - started) / 1000;
        setElapsed(s);
        if (s >= maxSeconds) stop();
      }, 200);
    } catch (e) {
      cleanup();
      setError(MIC_ERRORS[e?.name] ?? "Не вдалося увімкнути мікрофон.");
      setStatus("error");
    }
  }, [supported, maxSeconds, stop, cleanup]);

  useEffect(() => () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    cleanup();
  }, [cleanup]);

  return { supported, status, elapsed, error, start, stop, maxSeconds };
}
