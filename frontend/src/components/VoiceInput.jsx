import { useCallback, useState } from "react";
import { api, ApiError } from "../api.js";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder.js";
import { useWebSpeech } from "../hooks/useWebSpeech.js";

/**
 * Голосовий запит → {text, raw_text, mode, radius_km, ...} через onQuery.
 * Ланцюжок запасних варіантів: Groq Whisper → Web Speech у браузері → ручний ввід.
 */
export default function VoiceInput({ onQuery }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [offerWebSpeech, setOfferWebSpeech] = useState(false);
  const [typed, setTyped] = useState("");

  const submitText = useCallback(
    async (text, source) => {
      if (!text.trim()) return;
      setBusy(true);
      setMessage(null);
      try {
        onQuery(await api.parseText(text, source));
      } catch {
        // Навіть без бекенду не губимо запит: текст як є, режим/радіус — з перемикачів
        onQuery({ text, raw_text: text, mode: null, radius_km: null, source, cleanup: { guard: "offline" } });
      } finally {
        setBusy(false);
      }
    },
    [onQuery],
  );

  const webSpeech = useWebSpeech({ onResult: (t) => submitText(t, "web_speech") });

  const recorder = useVoiceRecorder({
    onStop: async (blob) => {
      setBusy(true);
      setMessage(null);
      setOfferWebSpeech(false);
      try {
        const res = await api.transcribe(blob);
        setTyped(res.text);
        onQuery(res);
      } catch (e) {
        const err = e instanceof ApiError ? e : new ApiError("unknown", "Не вдалося розпізнати запис");
        setMessage(err.message);
        setOfferWebSpeech(err.fallback && webSpeech.supported);
      } finally {
        setBusy(false);
      }
    },
  });

  const recording = recorder.status === "recording";
  const left = Math.max(0, Math.ceil(recorder.maxSeconds - recorder.elapsed));

  return (
    <section className="panel voice">
      <button
        type="button"
        className={`mic ${recording ? "mic--on" : ""}`}
        onClick={recording ? recorder.stop : recorder.start}
        disabled={busy || webSpeech.listening}
        aria-pressed={recording}
      >
        {recording ? `■ Стоп (${left} с)` : busy ? "Розпізнаю…" : "🎤 Сказати, що купити"}
      </button>

      {(recorder.error || message || webSpeech.error) && (
        <p className="msg msg--warn" role="alert">{recorder.error || message || webSpeech.error}</p>
      )}
      {offerWebSpeech && (
        <button type="button" className="link" onClick={webSpeech.start} disabled={webSpeech.listening}>
          {webSpeech.listening ? "Слухаю…" : "Спробувати розпізнавання в браузері"}
        </button>
      )}

      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          submitText(typed, "manual");
        }}
      >
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="або напишіть: молоко, яйця, кава до 300 грн…"
          aria-label="Запит текстом"
        />
        <button type="submit" disabled={busy || !typed.trim()}>Готово</button>
      </form>
    </section>
  );
}
