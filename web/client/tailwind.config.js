/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"] ,
  theme: {
    extend: {
      colors: {
        "stage-grid": "rgba(148, 163, 184, 0.18)"
      },
      boxShadow: {
        "panel": "0 24px 50px -40px rgba(15, 23, 42, 0.8)",
        "node": "0 14px 30px -20px rgba(15, 23, 42, 0.7)"
      }
    }
  },
  plugins: []
};
