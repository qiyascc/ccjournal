/**
 * CC Journal — self-hosted Tailwind build.
 * CDN'i (cdn.tailwindcss.com) değiştirir. Tüm tema + şablonlardaki sınıfları tarar,
 * yalnız kullanılanları üretir (purge). darkMode CDN'deki `class` ayarıyla aynı.
 *
 * Derle:  cd frontend && npm install && npm run build
 * Çıktı:  static/css/tailwind.build.css  → {% static 'css/tailwind.build.css' %}
 */
module.exports = {
  darkMode: "class",
  content: [
    "../themes/**/*.html",
    "../templates/**/*.html",
    "../apps/**/*.py",
    "../plugins/**/*.html",
  ],
  theme: {
    extend: {
      // Şablonlarda kullanılan base-* tonları (dark: varyantları için) —
      // Tailwind'in nötr paletine eşlenir.
      colors: {
        base: {
          50: "#f8fafc", 100: "#f1f5f9", 200: "#e2e8f0", 300: "#cbd5e1",
          400: "#94a3b8", 500: "#64748b", 600: "#475569", 700: "#334155",
          800: "#1e293b", 900: "#0f172a", 950: "#020617",
        },
      },
    },
  },
  plugins: [],
};
