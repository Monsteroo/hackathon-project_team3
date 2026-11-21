import { useCallback, useState } from "react";

const GEO_ERRORS = {
  1: "Доступ до геолокації заборонено. Введіть адресу вручну.",
  2: "Не вдалося визначити місцезнаходження. Введіть адресу вручну.",
  3: "Визначення місцезнаходження зайняло задовго. Спробуйте ще раз або введіть адресу.",
};

/** Кнопка «Моє місцезнаходження»: locate() → Promise<{lat, lng, accuracy}>. */
export function useGeolocation() {
  const [status, setStatus] = useState("idle"); // idle | locating | done | error
  const [error, setError] = useState(null);

  const locate = useCallback(
    () =>
      new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
          const msg = "Браузер не підтримує геолокацію. Введіть адресу вручну.";
          setError(msg);
          setStatus("error");
          reject(new Error(msg));
          return;
        }
        setStatus("locating");
        setError(null);
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            setStatus("done");
            resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy });
          },
          (err) => {
            const msg = GEO_ERRORS[err.code] ?? GEO_ERRORS[2];
            setError(msg);
            setStatus("error");
            reject(new Error(msg));
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
        );
      }),
    [],
  );

  return { status, error, locate };
}
