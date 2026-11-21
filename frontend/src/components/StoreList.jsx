import { storeState } from "./StoresMap.jsx";

const fmtKm = (km) => (km < 1 ? `${Math.round(km * 1000)} м` : `${km.toFixed(1)} км`);
const fmtMin = (m) => (m < 60 ? `${Math.round(m)} хв` : `${Math.floor(m / 60)} год ${Math.round(m % 60)} хв`);

const BADGE = {
  selected: "маршрут",
  recommended: "рекомендовано",
  priced: "є ціни",
  unpriced: "без онлайн-цін",
};

/** Список магазинів у радіусі, від найближчого за часом. Клік — перебудувати маршрут. */
export default function StoreList({ stores, selectedId, recommendedId, onSelect }) {
  if (!stores.length) return <p className="msg">Поруч магазинів не знайдено.</p>;
  return (
    <ol className="stores">
      {stores.map((s) => {
        const state = storeState(s, { selectedId, recommendedId });
        return (
          <li key={s.id}>
            <button type="button" className={`store store--${state}`} onClick={() => onSelect(s.id)}>
              <span className="store__name">{s.chain_name}</span>
              <span className="store__addr">{s.address}</span>
              <span className="store__eta">
                {fmtMin(s.duration_min)} · {fmtKm(s.distance_km)}
                {s.estimated && <abbr title="Сервіс маршрутів недоступний — оцінка за прямою"> ≈</abbr>}
              </span>
              <span className={`badge badge--${state}`}>{BADGE[state]}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
