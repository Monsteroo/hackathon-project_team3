import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";

const KYIV = [50.4501, 30.5234];

// Стани маркерів (кольори тимчасові — фінальні дасть дизайн Учасника 3)
export const MARKER = {
  selected: { color: "#0b5cff", fillColor: "#0b5cff", radius: 11 },
  recommended: { color: "#0a7a3d", fillColor: "#18a957", radius: 10 },
  priced: { color: "#0a7a3d", fillColor: "#ffffff", radius: 7 },
  unpriced: { color: "#8a8f98", fillColor: "#d9dce1", radius: 6 },
};

export function storeState(store, { selectedId, recommendedId }) {
  if (store.id === selectedId) return "selected";
  if (store.id === recommendedId) return "recommended";
  return store.confirmed || store.has_online_prices ? "priced" : "unpriced";
}

const RANK = { selected: 0, recommended: 1, priced: 2, unpriced: 3 };

function FitView({ origin, focus, route }) {
  const map = useMap();
  useEffect(() => {
    const fit = () => {
      const pts = route?.length ? route : [origin, focus].filter(Boolean).map((p) => [p.lat, p.lng]);
      if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40], maxZoom: 16 });
      else if (origin) map.setView([origin.lat, origin.lng], 15);
    };
    fit();
    // Контейнер карти змінює розмір (поворот телефона, перехід мобільна ↔ десктоп) — Leaflet сам цього не бачить
    let t;
    const ro = new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(() => {
        map.invalidateSize();
        fit();
      }, 150);
    });
    ro.observe(map.getContainer());
    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }, [map, origin, focus, route]);
  return null;
}

/** Карта: ви, усі магазини в радіусі (згруповані по будівлі), маршрут до обраного. */
export default function StoresMap({ origin, stores = [], selectedId, recommendedId, route, onSelect }) {
  const places = useMemo(() => {
    const byPlace = new Map();
    for (const s of stores) {
      const list = byPlace.get(s.place_id) ?? [];
      list.push(s);
      byPlace.set(s.place_id, list);
    }
    return [...byPlace.values()].map((list) => {
      const states = list.map((s) => storeState(s, { selectedId, recommendedId }));
      const best = states.reduce((a, b) => (RANK[a] <= RANK[b] ? a : b));
      return { list, state: best, lat: list[0].lat, lng: list[0].lng };
    });
  }, [stores, selectedId, recommendedId]);

  const selected = stores.find((s) => s.id === selectedId);

  return (
    <MapContainer center={origin ? [origin.lat, origin.lng] : KYIV} zoom={13} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitView origin={origin} focus={selected} route={route?.coordinates} />

      {route?.coordinates?.length > 1 && (
        <Polyline
          positions={route.coordinates}
          pathOptions={{ color: "#0b5cff", weight: 5, opacity: 0.8, dashArray: route.estimated ? "8 8" : null }}
        />
      )}

      {places
        .sort((a, b) => RANK[b.state] - RANK[a.state]) // важливіші маркери малюються зверху
        .map((p) => (
          <CircleMarker
            key={p.list[0].place_id}
            center={[p.lat, p.lng]}
            pathOptions={{ ...MARKER[p.state], weight: 2, fillOpacity: 1 }}
            radius={MARKER[p.state].radius}
            eventHandlers={{ click: () => p.list.length === 1 && onSelect(p.list[0].id) }}
          >
            <Tooltip direction="top">{p.list.map((s) => s.chain_name).join(" · ")}</Tooltip>
            {p.list.length > 1 && (
              <Popup>
                {p.list.map((s) => (
                  <button key={s.id} type="button" className="link" onClick={() => onSelect(s.id)}>
                    {s.chain_name} — {s.duration_min} хв
                  </button>
                ))}
              </Popup>
            )}
          </CircleMarker>
        ))}

      {origin && (
        <CircleMarker
          center={[origin.lat, origin.lng]}
          radius={8}
          pathOptions={{ color: "#ffffff", fillColor: "#e5483b", fillOpacity: 1, weight: 3 }}
        >
          <Tooltip permanent direction="bottom" offset={[0, 8]}>Ви тут</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
