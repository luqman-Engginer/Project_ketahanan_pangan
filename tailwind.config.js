/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.{html,j2}",
    "./app/static/js/**/*.js",
    "./app/services/**/*.py",
    "./app/blueprints/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          400: "var(--color-primary-400)",
          600: "var(--color-primary-600)",
          700: "var(--color-primary-700)",
          soft: "var(--color-primary-soft)",
        },
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        line: "var(--color-border)",
        ink: {
          DEFAULT: "var(--color-ink)",
          muted: "var(--color-ink-muted)",
        },
        success: {
          DEFAULT: "var(--color-success)",
          soft: "var(--color-success-soft)",
          ink: "var(--color-success-ink)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          soft: "var(--color-warning-soft)",
          ink: "var(--color-warning-ink)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          soft: "var(--color-danger-soft)",
          ink: "var(--color-danger-ink)",
        },
      },
      fontFamily: {
        sans: ['"Poppins"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "var(--radius-card)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
      },
    },
  },
  plugins: [],
};
