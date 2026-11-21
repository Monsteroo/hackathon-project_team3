import { useSyncExternalStore } from 'react'
import { CITIES, DEFAULT_CITY, type City } from './cities'

/** Місто зберігається на пристрої (DESIGN.md §4.7). Сховище може бути недоступне — тоді лише в пам'яті. */
const STORAGE_KEY = 'sayvy.city'
const listeners = new Set<() => void>()

function readStored(): City {
  try {
    const id = localStorage.getItem(STORAGE_KEY)
    return CITIES.find((c) => c.id === id) ?? DEFAULT_CITY
  } catch {
    return DEFAULT_CITY
  }
}

let current: City | null = null

function getSnapshot(): City {
  current ??= readStored()
  return current
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setCity(city: City) {
  current = city
  try {
    localStorage.setItem(STORAGE_KEY, city.id)
  } catch {
    // приватний режим або заблоковане сховище: місто живе до перезавантаження
  }
  listeners.forEach((l) => l())
}

export function useCity(): City {
  return useSyncExternalStore(subscribe, getSnapshot, () => DEFAULT_CITY)
}
