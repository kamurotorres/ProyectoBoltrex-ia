// craco.config.js — Boltrex
// P2.27: se quitaron los plugins de la plataforma donde nació el proyecto (visual-edits,
// health-check). Queda solo lo que la app usa: alias '@' → src y las reglas de hooks.
const path = require("path");
require("dotenv").config();

module.exports = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    configure: (webpackConfig) => {
      // Menos carpetas vigiladas en desarrollo (recarga más rápida).
      webpackConfig.watchOptions = {
        ...webpackConfig.watchOptions,
        ignored: ["**/node_modules/**", "**/.git/**", "**/build/**", "**/dist/**", "**/coverage/**", "**/public/**"],
      };
      return webpackConfig;
    },
  },
};
