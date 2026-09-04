import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  // 저장소의 단일 원본 데이터를 그대로 정적 배포 산출물에 포함합니다.
  // 빌드 후 /manifest.json, /departments/*.json 으로 접근할 수 있습니다.
  publicDir: fileURLToPath(new URL('../data', import.meta.url)),
  // 환경변수는 저장소 루트 .env 하나로 관리합니다. VITE_ 접두사만 노출됩니다.
  envDir: fileURLToPath(new URL('..', import.meta.url)),
})
