import "@testing-library/jest-dom/vitest";
import { vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// jsdom × Node 20+ interop shim.
//
// In recent Node versions (≥ 20, definitely ≥ 24), the global `TextEncoder`
// installed by jsdom returns a `Uint8Array` whose constructor lives in
// jsdom's own realm — but `instanceof globalThis.Uint8Array` is then false
// because `globalThis.Uint8Array` is Node's. `lib/crypto.ts` has an
// `instanceof Uint8Array` guard and (correctly) rejects.  Re-bind the
// global `TextEncoder` so its output is always a *Node* Uint8Array.
// ---------------------------------------------------------------------------
const NativeTextEncoder = globalThis.TextEncoder;
class PatchedTextEncoder extends NativeTextEncoder {
  encode(input?: string): Uint8Array<ArrayBuffer> {
    const out = super.encode(input);
    const copy = out instanceof Uint8Array ? out : new Uint8Array(out);
    return copy as Uint8Array<ArrayBuffer>;
  }
}
(globalThis as unknown as { TextEncoder: typeof TextEncoder }).TextEncoder =
  PatchedTextEncoder as unknown as typeof TextEncoder;

// `fake-indexeddb`'s structured clone path can produce a `Uint8Array` whose
// constructor lives in a different realm than `globalThis.Uint8Array`, which
// breaks defensive `iv instanceof Uint8Array` checks in `lib/crypto.ts`.
// Patch `Symbol.hasInstance` to recognise any object whose constructor is
// also named "Uint8Array" (cross-realm safe).
const NativeHasInstance = Object.getOwnPropertyDescriptor(
  Function.prototype,
  Symbol.hasInstance,
);
Object.defineProperty(Uint8Array, Symbol.hasInstance, {
  value(value: unknown): boolean {
    if (
      ArrayBuffer.isView(value) &&
      typeof value === "object" &&
      value !== null &&
      (value as { constructor?: { name?: string } }).constructor?.name ===
        "Uint8Array"
    ) {
      return true;
    }
    return NativeHasInstance?.value?.call(this, value) ?? false;
  },
  configurable: true,
});

type StorageRecord = Record<string, unknown>;

interface MockStorageArea {
  _data: StorageRecord;
  get: (
    keys?: string | string[] | StorageRecord | null,
  ) => Promise<StorageRecord>;
  set: (items: StorageRecord) => Promise<void>;
  remove: (keys: string | string[]) => Promise<void>;
  clear: () => Promise<void>;
}

function createStorageArea(): MockStorageArea {
  const area: MockStorageArea = {
    _data: {},
    get: vi.fn(async (keys) => {
      if (keys === null || keys === undefined) {
        return { ...area._data };
      }
      if (typeof keys === "string") {
        return keys in area._data ? { [keys]: area._data[keys] } : {};
      }
      if (Array.isArray(keys)) {
        const out: StorageRecord = {};
        for (const k of keys) {
          if (k in area._data) out[k] = area._data[k];
        }
        return out;
      }
      const out: StorageRecord = {};
      for (const [k, def] of Object.entries(keys)) {
        out[k] = k in area._data ? area._data[k] : def;
      }
      return out;
    }),
    set: vi.fn(async (items) => {
      Object.assign(area._data, items);
    }),
    remove: vi.fn(async (keys) => {
      const arr = Array.isArray(keys) ? keys : [keys];
      for (const k of arr) delete area._data[k];
    }),
    clear: vi.fn(async () => {
      area._data = {};
    }),
  };
  return area;
}

interface ChromeMock {
  storage: {
    local: MockStorageArea;
    session: MockStorageArea;
    sync: MockStorageArea;
  };
  runtime: {
    id: string;
    getManifest: () => { version: string };
    sendMessage: ReturnType<typeof vi.fn>;
    onMessage: {
      addListener: ReturnType<typeof vi.fn>;
      removeListener: ReturnType<typeof vi.fn>;
      hasListener: ReturnType<typeof vi.fn>;
    };
    onInstalled: {
      addListener: ReturnType<typeof vi.fn>;
      removeListener: ReturnType<typeof vi.fn>;
    };
    lastError: chrome.runtime.LastError | undefined;
  };
  tabs: {
    query: ReturnType<typeof vi.fn>;
    sendMessage: ReturnType<typeof vi.fn>;
    create: ReturnType<typeof vi.fn>;
  };
  alarms: {
    create: ReturnType<typeof vi.fn>;
    clear: ReturnType<typeof vi.fn>;
    onAlarm: {
      addListener: ReturnType<typeof vi.fn>;
      removeListener: ReturnType<typeof vi.fn>;
    };
  };
  scripting: {
    executeScript: ReturnType<typeof vi.fn>;
  };
  idle: {
    setDetectionInterval: ReturnType<typeof vi.fn>;
    queryState: ReturnType<typeof vi.fn>;
    onStateChanged: {
      addListener: ReturnType<typeof vi.fn>;
      removeListener: ReturnType<typeof vi.fn>;
    };
  };
  action: {
    setBadgeText: ReturnType<typeof vi.fn>;
    setBadgeBackgroundColor: ReturnType<typeof vi.fn>;
    setTitle: ReturnType<typeof vi.fn>;
    openPopup: ReturnType<typeof vi.fn>;
  };
}

function createChromeMock(): ChromeMock {
  return {
    storage: {
      local: createStorageArea(),
      session: createStorageArea(),
      sync: createStorageArea(),
    },
    runtime: {
      id: "once-extension-test",
      getManifest: () => ({ version: "0.1.0-test" }),
      sendMessage: vi.fn(async () => undefined),
      onMessage: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
        hasListener: vi.fn(),
      },
      onInstalled: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
      lastError: undefined,
      openOptionsPage: vi.fn(async () => undefined),
    } as unknown as ChromeMock["runtime"],
    tabs: {
      query: vi.fn(async () => []),
      sendMessage: vi.fn(async () => undefined),
      create: vi.fn(async () => undefined),
      onUpdated: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
      onRemoved: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
    } as unknown as ChromeMock["tabs"],
    alarms: {
      create: vi.fn(),
      clear: vi.fn(async () => true),
      onAlarm: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
    },
    scripting: {
      executeScript: vi.fn(async () => []),
    },
    idle: {
      setDetectionInterval: vi.fn(),
      queryState: vi.fn(async () => "active"),
      onStateChanged: {
        addListener: vi.fn(),
        removeListener: vi.fn(),
      },
    },
    action: {
      setBadgeText: vi.fn(async () => undefined),
      setBadgeBackgroundColor: vi.fn(async () => undefined),
      setTitle: vi.fn(async () => undefined),
      openPopup: vi.fn(async () => undefined),
    },
  };
}

declare global {
  // eslint-disable-next-line no-var
  var __APP_VERSION__: string;
}

(globalThis as unknown as { chrome: ChromeMock }).chrome = createChromeMock();
(globalThis as unknown as { __APP_VERSION__: string }).__APP_VERSION__ = "0.1.0-test";

beforeEach(() => {
  (globalThis as unknown as { chrome: ChromeMock }).chrome = createChromeMock();
});

if (!("fetch" in globalThis)) {
  (globalThis as unknown as { fetch: typeof fetch }).fetch = vi.fn();
}
