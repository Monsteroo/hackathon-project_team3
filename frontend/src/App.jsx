import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import LocationPicker from "./components/LocationPicker.jsx";
import StoreList from "./components/StoreList.jsx";
import StoresMap from "./components/StoresMap.jsx";
import VoiceInput from "./components/VoiceInput.jsx";

const MODES = [
  { id: "walk", label: "🚶 Пішки" },
  { id: "car", label: "🚗 Авто" },
];

export default function App() {
  const [query, setQuery] = useState(null); // {text, raw_text, mode, radius_km, ...} — віддаємо агенту (Учасник 5)
  const [location, setLocation] = useState(null); // {lat, lng, label, source}
  const [mode, setMode] = useState("walk"); // за замовчуванням пішки (рішення команди)
  const [radiusKm, setRadiusKm] = useState(null); // null → дефолт бекенду: пішки 2 км / авто 10 км
  // ID магазинів з підтвердженою ціною й наявністю кошика — прийдуть від агента / БД Учасника 2
  const [confirmedStoreIds] = useState(null);
  const [nearby, setNearby] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [route, setRoute] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const reqId = useRef(0);

  const onQuery = useCallback((q) => {
    setQuery(q);
    if (q.mode) setMode(q.mode);
    setRadiusKm(q.radius_km ?? null);
  }, []);

  // Магазини поруч: при зміні точки, режиму, радіуса або підтверджених магазинів
  useEffect(() => {
    if (!location) return;
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    api
      .nearby({ lat: location.lat, lng: location.lng, mode, radiusKm, storeIds: confirmedStoreIds })
      .then((res) => {
        if (id !== reqId.current) return; // відповідь на застарілий запит
        setNearby(res);
        setSelectedId(res.recommended_id ?? res.stores[0]?.id ?? null);
      })
      .catch((e) => id === reqId.current && setError(e.message))
      .finally(() => id === reqId.current && setLoading(false));
  }, [location, mode, radiusKm, confirmedStoreIds]);

  // Лінія маршруту до обраного магазину
  useEffect(() => {
    if (!location || !selectedId) {
      setRoute(null);
      return;
    }
    let alive = true;
    api
      .route({ lat: location.lat, lng: location.lng, storeId: selectedId, mode })
      .then((r) => alive && setRoute(r))
      .catch(() => alive && setRoute(null));
    return () => {
      alive = false;
    };
  }, [location, selectedId, mode]);

  const selected = nearby?.stores.find((s) => s.id === selectedId);

  return (
    <div className="app">
      <header className="top">
        <h1>VoiceCart AI</h1>
      </header>

      <main className="layout">
        <div className="side">
          <VoiceInput onQuery={onQuery} />
          {query && (
            <section className="panel query" aria-live="polite">
              <p className="query__text">«{query.text}»</p>
              {query.cleanup?.guard === "rejected" && (
                <p className="msg">Показуємо текст без обробки, щоб нічого не додати від себе.</p>
              )}
            </section>
          )}

          <LocationPicker value={location} onChange={setLocation} />

          <section className="panel modes" role="group" aria-label="Як добиратися">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                aria-pressed={mode === m.id}
                className={mode === m.id ? "on" : ""}
                onClick={() => {
                  setMode(m.id);
                  setRadiusKm(null); // ручне перемикання — дефолтний радіус для режиму
                }}
              >
                {m.label}
              </button>
            ))}
            {selected && (
              <a className="button" href={selected.maps_urls.transit} target="_blank" rel="noreferrer">
                🚌 Громадським транспортом
              </a>
            )}
          </section>

          {selected && (
            <section className="panel selected">
              <h2>{selected.chain_name}</h2>
              <p>{selected.address}</p>
              <p>
                {route ? `${Math.round(route.duration_min)} хв · ${route.distance_km} км` : "Будую маршрут…"}
                {route?.estimated && " (приблизно)"}
              </p>
              <a
                className="button primary"
                href={mode === "car" ? selected.maps_urls.driving : selected.maps_urls.walking}
                target="_blank"
                rel="noreferrer"
              >
                Відкрити маршрут у Google Maps
              </a>
            </section>
          )}

          {error && <p className="msg msg--warn" role="alert">{error}</p>}
          {nearby && (
            <section className="panel">
              <h2>
                Магазини поруч ({nearby.count}) · до {nearby.radius_km} км
                {nearby.radius_expanded && " — поруч не знайшли, розширили пошук"}
              </h2>
              <StoreList
                stores={nearby.stores}
                selectedId={selectedId}
                recommendedId={nearby.recommended_id}
                onSelect={setSelectedId}
              />
            </section>
          )}
        </div>

        <div className="mapwrap" aria-busy={loading}>
          <StoresMap
            origin={location}
            stores={nearby?.stores}
            selectedId={selectedId}
            recommendedId={nearby?.recommended_id}
            route={route}
            onSelect={setSelectedId}
          />
        </div>
      </main>
    </div>
  );
}
