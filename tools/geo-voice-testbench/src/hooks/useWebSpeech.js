import { useCallback, useRef, useState } from "react";

// Запасне розпізнавання в браузері (Chrome/Edge), коли Groq недоступний або вичерпано ліміт.
const Recognition = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

export function useWebSpeech({ onResult } = {}) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const recRef = useRef(null);

  const start = useCallback(() => {
    if (!Recognition) {
      setError("Запасне розпізнавання недоступне в цьому браузері. Введіть запит текстом.");
      return;
    }
    const rec = new Recognition();
    rec.lang = "uk-UA";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => onResult?.(e.results[0][0].transcript);
    rec.onerror = (e) => setError(e.error === "not-allowed" ? "Доступ до мікрофона заборонено." : "Не вдалося розпізнати мову.");
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setError(null);
    setListening(true);
    rec.start();
  }, [onResult]);

  const stop = useCallback(() => recRef.current?.stop(), []);

  return { supported: !!Recognition, listening, error, start, stop };
}
