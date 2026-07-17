/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_LIVE: string
  readonly VITE_API_BASE: string
  readonly VITE_DOMESTIC_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
