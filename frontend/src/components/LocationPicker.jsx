import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useGeolocation } from "../hooks/useGeolocation.js";

/** Звідки йдемо: кнопка GPS або адреса з підказками. onChange({lat, lng, label, source}). */
export default function LocationPicker({ value, onChange }) {
  const geo = useGeolocation();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [message, setMessage] = useState(null);
  const skipSuggest = useRef(false);

  useEffect(() => {
    if (value?.label) {
      skipSuggest.current = true;
      setQuery(value.label);
    }
  }, [value?.label]);

  // Підказки під час набору (Photon), з паузою 350 мс
  useEffect(() => {
    if (skipSuggest.current) {
      skipSuggest.current = false;
      return;
    }
    if (query.trim().length < 3) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const { results } = await api.geocode(query, { suggest: true, near: value });
        setSuggestions(results);
      } catch {
        setSuggestions([]);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (r, source) => {
    setSuggestions([]);
    setMessage(null);
    onChange({ lat: r.lat, lng: r.lng, label: r.label, source });
  };

  const useGps = async () => {
    setMessage(null);
    try {
      const pos = await geo.locate();
      let label = "Моє місцезнаходження";
      try {
        label = (await api.reverse(pos)).label || label;
      } catch {
        /* адреса не обов'язкова — координати вже є */
      }
      pick({ ...pos, label }, "gps");
    } catch (e) {
      setMessage(e.message);
    }
  };

  const searchAddress = async (e) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    try {
      const { results } = await api.geocode(query);
      if (results.length) pick(results[0], "address");
      else setMessage("Адресу не знайдено. Уточніть місто, вулицю й номер будинку.");
    } catch (err) {
      setMessage(err.message);
    }
  };

  return (
    <section className="panel location">
      <button type="button" onClick={useGps} disabled={geo.status === "locating"}>
        {geo.status === "locating" ? "Визначаю…" : "📍 Моє місцезнаходження"}
      </button>
      <form className="row combo" onSubmit={searchAddress}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="або адреса: Хрещатик 22, Київ"
          aria-label="Адреса"
          autoComplete="off"
        />
        <button type="submit">Знайти</button>
        {suggestions.length > 0 && (
          <ul className="suggestions" role="listbox">
            {suggestions.map((s) => (
              <li key={`${s.lat},${s.lng}`}>
                <button type="button" onClick={() => pick(s, "address")}>{s.label}</button>
              </li>
            ))}
          </ul>
        )}
      </form>
      {message && <p className="msg msg--warn" role="alert">{message}</p>}
    </section>
  );
}
