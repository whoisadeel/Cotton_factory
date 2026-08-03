module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/forms.py",
    "./apps/**/templatetags/*.py",
  ],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'] },
      keyframes: {
        slideDown: { '0%': { opacity: '0', transform: 'translateY(-4px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
      },
      animation: { slideDown: 'slideDown 0.2s ease-out', fadeIn: 'fadeIn 0.3s ease-out' },
    },
  },
}
