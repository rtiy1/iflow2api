import daisyui from "daisyui";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        slate: {
          850: '#172033',
        }
      }
    },
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        dark: {
          "primary": "#3b82f6",
          "secondary": "#94a3b8",
          "accent": "#10b981",
          "neutral": "#1f2937",
          "base-100": "#0f172a",
          "base-200": "#1e293b",
          "base-300": "#334155",
          "info": "#0ea5e9",
          "success": "#10b981",
          "warning": "#f59e0b",
          "error": "#ef4444",
        },
      },
    ],
    darkTheme: "dark",
  },
}
