/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        graphite: {
          950: "#0B0D12",
          900: "#12151C",
          800: "#171B24",
          700: "#20242F",
          600: "#2B3040",
          500: "#3C4257",
        },
        signal: {
          DEFAULT: "#5B6CFF",
          soft: "#8891FF",
          dim: "#333B66",
        },
        wire: {
          amber: "#E8A33D",
          green: "#3DDC97",
          red: "#FF5C72",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
