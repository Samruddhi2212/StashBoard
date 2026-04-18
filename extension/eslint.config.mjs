import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      globals: {
        chrome:               "readonly",
        document:             "readonly",
        window:               "readonly",
        navigator:            "readonly",
        crypto:               "readonly",
        setTimeout:           "readonly",
        clearTimeout:         "readonly",
        console:              "readonly",
        Promise:              "readonly",
        Event:                "readonly",
        URL:                  "readonly",
        IntersectionObserver: "readonly",
        confirm:              "readonly",
        HTMLInputElement:     "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["warn", { "argsIgnorePattern": "^_" }],
      "no-console":     "off",
    },
  },
];
