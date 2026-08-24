import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn().mockImplementation(query => ({ matches: false, media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() })) })
Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() })
Object.defineProperty(globalThis, 'confirm', { configurable: true, value: vi.fn(() => true) })
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
Object.defineProperty(globalThis, 'ResizeObserver', { configurable: true, value: ResizeObserverMock })
function memoryStorage(): Storage { const values = new Map<string, string>(); return { get length() { return values.size }, clear: () => values.clear(), getItem: key => values.get(key) ?? null, key: index => [...values.keys()][index] ?? null, removeItem: key => { values.delete(key) }, setItem: (key, value) => { values.set(key, String(value)) } } }
Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: memoryStorage() })
Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: memoryStorage() })
afterEach(() => { cleanup(); localStorage.clear(); sessionStorage.clear(); vi.restoreAllMocks() })
