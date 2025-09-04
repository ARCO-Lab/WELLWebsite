// PostCSS configuration file for processing CSS with plugins like Tailwind CSS and Autoprefixer

const config = {
  plugins: {
    '@tailwindcss/postcss': {}, // Tailwind CSS plugin for PostCSS
    'autoprefixer': {},         // Adds vendor prefixes to CSS rules
  },
}

export default config