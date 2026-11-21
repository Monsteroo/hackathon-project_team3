// Тестовий стенд бекенду «Голос + Геолокація». НЕ продуктовий UI — без стилів і дизайну.
// Потрібен лише для того, що не перевірити через curl: мікрофон (MediaRecorder) і GPS браузера.
import { useState } from "react";
import { api } from "./api.js";
import { useGeolocation } from "./hooks/useGeolocation.js";
import { useVoiceRecorder } from "./hooks/useVoiceRecorder.js";
import { useWebSpeech } from "./hooks/useWebSpeech.js";

const show = (v) => <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(v, null, 2)}</pre>;

export default function App() {
  const [voice, setVoice] = useState(null);
  const [origin, setOrigin] = useState(null);
  const [address, setAddress] = useState("Хрещатик 22");
  const [mode, setMode] = useState("walk");
  const [nearby, setNearby] = useState(null);
  const [route, setRoute] = useState(null);
  const [error, setError] = useState(null);

  const run = (p) => p.catch((e) => setError(`${e.code}: ${e.message}`));

  const recorder = useVoiceRecorder({
    onStop: (blob) => run(api.transcribe(blob).then(setVoice)),
  });
  const webSpeech = useWebSpeech({ onResult: (t) => run(api.parseText(t, "web_speech").then(setVoice)) });
  const geo = useGeolocation();

  const findStores = (o, m = mode) =>
    run(
      api.nearby({ ...o, mode: m, radiusKm: voice?.radius_km }).then((r) => {
        setNearby(r);
        setRoute(null);
      }),
    );

  const pickOrigin = (o) => {
    setError(null);
    setOrigin(o);
    findStores(o);
  };

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Geo-Voice testbench</h1>
      {error && <p role="alert">⚠️ {error}</p>}

      <h2>1. Голос → текст</h2>
      <button onClick={recorder.status === "recording" ? recorder.stop : recorder.start}>
        {recorder.status === "recording" ? `Стоп (${Math.ceil(60 - recorder.elapsed)} с)` : "Записати"}
      </button>{" "}
      <button onClick={webSpeech.start} disabled={!webSpeech.supported || webSpeech.listening}>
        Web Speech (fallback)
      </button>
      {(recorder.error || webSpeech.error) && <p>{recorder.error || webSpeech.error}</p>}
      {voice && show(voice)}

      <h2>2. Звідки йдемо</h2>
      <button onClick={() => run(geo.locate().then(async (p) => pickOrigin({ ...p, label: (await api.reverse(p)).label })))}>
        GPS {geo.status === "locating" && "…"}
      </button>{" "}
      <input value={address} onChange={(e) => setAddress(e.target.value)} />{" "}
      <button onClick={() => run(api.geocode(address).then(({ results }) => pickOrigin(results[0])))}>Знайти адресу</button>{" "}
      <select
        value={mode}
        onChange={(e) => {
          setMode(e.target.value);
          if (origin) findStores(origin, e.target.value);
        }}
      >
        <option value="walk">пішки</option>
        <option value="car">авто</option>
      </select>
      {origin && <p>📍 {origin.label} ({origin.lat.toFixed(5)}, {origin.lng.toFixed(5)})</p>}

      {nearby && (
        <>
          <h2>3. Магазини ({nearby.count}, радіус {nearby.radius_km} км, routing: {nearby.routing})</h2>
          <p>Рекомендовано: {nearby.recommended_id ?? "—"} ({nearby.recommended_reason ?? "—"})</p>
          <table>
            <tbody>
              {nearby.stores.map((s) => (
                <tr key={s.id} style={{ fontWeight: s.id === nearby.recommended_id ? 700 : 400 }}>
                  <td>{s.chain_name}</td>
                  <td>{s.address}</td>
                  <td>{s.duration_min} хв</td>
                  <td>{s.distance_km} км{s.estimated && " ≈"}</td>
                  <td>{s.has_online_prices ? "ціни ✓" : ""}{!s.in_radius && " (поза радіусом)"}</td>
                  <td>
                    <button onClick={() => run(api.route({ ...origin, storeId: s.id, mode }).then(setRoute))}>/api/route</button>{" "}
                    <a href={s.maps_urls[mode === "car" ? "driving" : "walking"]} target="_blank" rel="noreferrer">Google</a>{" "}
                    <a href={s.maps_urls.transit} target="_blank" rel="noreferrer">транспорт</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {route && show({ ...route, coordinates: `${route.coordinates.length} точок` })}
    </main>
  );
}
