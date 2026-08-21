import "@testing-library/jest-dom/vitest";

/** In-memory Storage shim so storage-safety assertions work in jsdom. */
class MemoryStorage implements Storage {
  private readonly store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

function installStorage(name: "localStorage" | "sessionStorage"): void {
  if (window[name] === undefined) {
    Object.defineProperty(window, name, {
      value: new MemoryStorage(),
      configurable: true,
    });
  }
}

installStorage("localStorage");
installStorage("sessionStorage");

