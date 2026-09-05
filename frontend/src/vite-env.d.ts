/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Basis-URL des FastAPI-Backends, siehe .env.example. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
