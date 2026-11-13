import pluginVue from "eslint-plugin-vue";
import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";

export default defineConfigWithVueTs(
  {
    ignores: ["dist/**", "coverage/**", "node_modules/**"],
  },
  ...pluginVue.configs["flat/recommended"],
  vueTsConfigs.recommended,
  {
    files: ["**/*.{ts,vue}"],
    rules: {
      "@typescript-eslint/consistent-type-imports": "error",
      "vue/block-order": ["error", { order: ["template", "script", "style"] }],
      "vue/html-closing-bracket-newline": "off",
      "vue/html-indent": "off",
      "vue/html-self-closing": "off",
      "vue/max-attributes-per-line": "off",
      "vue/multi-word-component-names": "off",
      "vue/multiline-html-element-content-newline": "off",
      "vue/singleline-html-element-content-newline": "off",
    },
  },
  {
    files: ["src/domains/room/MessageTimeline.vue"],
    rules: {
      "vue/no-v-html": "off",
    },
  },
);
