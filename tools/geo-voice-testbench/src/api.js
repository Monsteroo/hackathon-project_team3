// Клієнт API модулів geo і voice спільного бекенду. Усі помилки → ApiError з code від бекенду.
// Ключ: VITE_API_KEY у tools/geo-voice-testbench/.env.local (не комітиться), значення з API_KEYS у backend/.env.

const API_KEY = import.meta.env.VITE_API_KEY ?? "";

export class ApiError extends Error {
  constructor(code, message, { status = 0, fallback = false } = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.fallback = fallback; // true → запропонувати Web Speech / ручний ввід
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(path, { ...options, headers: { "X-API-Key": API_KEY, ...options.headers } });
  } catch {
    throw new ApiError("network", "Немає з'єднання з сервером", { fallback: true });
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    // detail: {code, message[, fallback]} від модулів; масив — помилка валідації FastAPI; рядок — auth/інше
    const d = body.detail;
    const err = Array.isArray(d) ? { code: "validation_error" } : typeof d === "object" && d ? d : { code: res.status === 401 ? "unauthorized" : undefined, message: d };
    throw new ApiError(err.code || `http_${res.status}`, err.message || "Помилка сервера", {
      status: res.status,
      fallback: err.fallback ?? res.status >= 500,
    });
  }
  return body;
}

const qs = (params) =>
  new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();

export const api = {
  transcribe(blob) {
    const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
    const form = new FormData();
    form.append("audio", blob, `voice.${ext}`);
    return request("/voice/transcribe", { method: "POST", body: form });
  },
  parseText(text, source = "manual") {
    return request("/voice/parse-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source }),
    });
  },
  geocode(q, { suggest = false, near } = {}) {
    return request(`/geo/geocode?${qs({ q, suggest, lat: near?.lat, lng: near?.lng, limit: 5 })}`);
  },
  reverse({ lat, lng }) {
    return request(`/geo/reverse?${qs({ lat, lng })}`);
  },
  nearby({ lat, lng, mode = "walk", radiusKm, storeIds }) {
    return request(
      `/geo/stores/nearby?${qs({ lat, lng, mode, radius_km: radiusKm, store_ids: storeIds?.join(",") })}`,
    );
  },
  route({ lat, lng, storeId, mode = "walk" }) {
    return request(`/geo/route?${qs({ lat, lng, store_id: storeId, mode })}`);
  },
};
