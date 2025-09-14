import { tileLayer } from "./map";

document.addEventListener("DOMContentLoaded", () => {
  // Color Filter Controls
  const tilePane = tileLayer.getContainer();
  const colorPresets = document.getElementById("color-presets");

  /**
   * Applies a CSS filter to the tile pane.
   * @param {string} filter - The CSS filter string to apply.
   */
  function applyFilter(filter) {
    tilePane.style.filter = filter;
  }

  // Event listener for the color presets dropdown
  colorPresets.addEventListener("change", (e) => {
    const selectedFilter = e.target.value;
    applyFilter(selectedFilter);
  });
});
