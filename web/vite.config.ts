import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

const workspaceRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, workspaceRoot, "VITE_");
  const logLevel =
    (["info", "warn", "error", "silent"] as const).find((level) => level === env.VITE_LOG_LEVEL) ??
    "info";

  return {
    base: command === "build" ? "/static/" : "/",
    envDir: workspaceRoot,
    logLevel,
    plugins: [tailwindcss(), vue()],
    server: {
      host: "localhost",
      port: 9081,
      strictPort: true,
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:9080",
          ws: true,
        },
      },
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
  };
});
