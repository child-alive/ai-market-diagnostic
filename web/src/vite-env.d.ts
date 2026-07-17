/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_LIVE: string
  readonly VITE_API_BASE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
