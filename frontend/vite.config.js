import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    // This is the important part
    // outDir: '../static', // Build assets to the ../static directory
    emptyOutDir: true,   // Clears the directory before building
  },
  base: '/dist/',
})