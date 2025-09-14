import L from "leaflet";
import "leaflet.fullscreen";
import "leaflet/dist/leaflet.css";
import { getVerseInfoById } from "./kjv";

// Import the images directly from the leaflet package
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerIconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";

// Override the default icon options
delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIconRetinaUrl,
  shadowUrl: markerShadowUrl,
});
// Map Initialization

// Create a new Leaflet map instance and attach it to the 'map' div
export var map = L.map("map", {
  crs: L.CRS.Simple,
  minZoom: 0,
  fullscreenControl: true,
});

// Define the pixel boundaries of the image at its native zoom level
const imagePixelBounds = [
  [0, 0], // Top-left corner
  [31102, 31102], // Bottom-right corner
];

// The native zoom level of your image, where 1 map unit = 1 pixel
export const nativeZoom = 7;

// Convert these pixel points into the map's LatLng coordinate system
const imageLatLngBounds = L.latLngBounds(
  map.unproject(imagePixelBounds[0], 7), // Use native zoom level 7
  map.unproject(imagePixelBounds[1], 7) // Use native zoom level 7
);

// Related to main.py
const tileUrl = "/tiles/{z}/{x}/{y}.png";

export const tileLayer = L.tileLayer(tileUrl, {
  minZoom: 0,
  maxZoom: 12, // Max zoom is higher, to allow the user to zoom more and easily distinguish and click individual pixels.
  maxNativeZoom: 9, // 7 is native resolution, 9 is a 64x64px image upscaled to 256, to enable more zooming.
  tileSize: 256,
  noWrap: true,
  attribution:
    '<a href="https://huggingface.co/datasets/Theodor-Crosswell/KJV_Similarity" target="_blank">KJV Dataset</a> by <a href="https://github.com/TheodorCrosswell" target="_blank">Theodor Crosswell</a>', // I made the tiles and distances dataset.
  bounds: imageLatLngBounds, // To prevent the page from requesting nonexistent tiles from the server.
}).addTo(map);

// Map initial view
map.fitBounds(imageLatLngBounds);

document.addEventListener("DOMContentLoaded", () => {
  // Create a custom control
  var customControl = L.Control.extend({
    options: {
      position: "topright",
    },

    onAdd: function (map) {
      var container = L.DomUtil.create(
        "div",
        "leaflet-bar leaflet-control leaflet-control-custom"
      );

      // Search Button
      var searchButton = L.DomUtil.create(
        "a",
        "leaflet-control-custom-button",
        container
      );
      searchButton.id = "match-button";
      searchButton.innerHTML = "&#128269;";
      searchButton.href = "#";
      searchButton.role = "button";
      searchButton.title = "Search";

      // Previous Marker Button
      var prevButton = L.DomUtil.create(
        "a",
        "leaflet-control-custom-button",
        container
      );
      prevButton.id = "previous-marker-button";
      prevButton.innerHTML = "&#8592;";
      prevButton.href = "#";
      prevButton.role = "button";
      prevButton.title = "Previous Marker";

      // Next Marker Button
      var nextButton = L.DomUtil.create(
        "a",
        "leaflet-control-custom-button",
        container
      );
      nextButton.id = "next-marker-button";
      nextButton.innerHTML = "&#8594;";
      nextButton.href = "#";
      nextButton.role = "button";
      nextButton.title = "Next Marker";

      // Clear Markers Button
      var clearMarkersButton = L.DomUtil.create(
        "a",
        "leaflet-control-custom-button",
        container
      );
      clearMarkersButton.id = "clear-markers-button";
      clearMarkersButton.innerHTML = "&#128465;";
      clearMarkersButton.href = "#";
      clearMarkersButton.role = "button";
      clearMarkersButton.title = "Clear Markers";

      // Series Select Dropdown
      var seriesSelectContainer = L.DomUtil.create(
        "div",
        "custom-control-select",
        container
      );
      var seriesSelect = L.DomUtil.create("select", "", seriesSelectContainer);
      seriesSelect.id = "current-verse-select";

      // Book Select Dropdown
      var bookSelectContainer = L.DomUtil.create(
        "div",
        "custom-control-select",
        container
      );
      var bookSelect = L.DomUtil.create("select", "", bookSelectContainer);
      bookSelect.id = "book-select";

      // Container for Chapter and Verse selects to be on one row
      var chapterVerseRow = L.DomUtil.create(
        "div",
        "chapter-verse-row",
        container
      );

      // Chapter Select Dropdown
      var chapterSelectContainer = L.DomUtil.create(
        "div",
        "custom-control-select",
        chapterVerseRow
      );
      var chapterSelect = L.DomUtil.create(
        "select",
        "",
        chapterSelectContainer
      );
      chapterSelect.id = "chapter-select";

      // Verse Select Dropdown
      var verseSelectContainer = L.DomUtil.create(
        "div",
        "custom-control-select",
        chapterVerseRow
      );
      var verseSelect = L.DomUtil.create("select", "", verseSelectContainer);
      verseSelect.id = "verse-select";

      // Color Select Dropdown
      var colorSelectContainer = L.DomUtil.create(
        "div",
        "custom-control-select",
        container
      );
      var colorSelect = L.DomUtil.create("select", "", colorSelectContainer);
      colorSelect.id = "color-presets";
      colorSelect.innerHTML = `<option value="none">Default</option>
                <option value="sepia(100%) hue-rotate(0deg) saturate(200%) brightness(90%)">Sepia</option>
                <option value="sepia(100%) hue-rotate(90deg) saturate(200%) brightness(90%)">Jungle</option>
                <option value="sepia(100%) hue-rotate(180deg) saturate(120%) brightness(90%)">Ocean</option>
                <option value="sepia(100%) hue-rotate(270deg) saturate(180%) brightness(90%)">Pink</option>
            `;

      // Prevent map clicks from propagating to the controls
      L.DomEvent.disableClickPropagation(container);

      return container;
    },
  });

  // Add the custom control to the map
  map.addControl(new customControl());
});

// Pixel info - Retrieves verse info for clicked pixel
map.on("click", async function (e) {
  // We want the pixel coordinates at the zoom level that represents the original image size.
  const targetZoom = nativeZoom;

  // Project the map's lat/lng coordinates to pixel coordinates at our target zoom level.
  const pixelCoords = map.project(e.latlng, targetZoom);

  // The result from project() is an object with x and y properties.
  // We need to round them to get integer coordinates for the API call.
  const min = 1;
  const max = 31102;

  let x = Math.floor(pixelCoords.x) + 1;
  let y = Math.floor(pixelCoords.y) + 1;

  x = Math.min(Math.max(x, min), max);
  y = Math.min(Math.max(y, min), max);

  const xVerseInfo = await getVerseInfoById(x);
  const yVerseInfo = await getVerseInfoById(y);
  const popupContent = `<b>Coordinates:</b> ${xVerseInfo.verse_id}, ${yVerseInfo.verse_id}<br>
    <b>X Citation:</b> ${xVerseInfo.citation}<br>
    <b>X Text:</b> ${xVerseInfo.text}<br>
    <b>Y Citation:</b> ${yVerseInfo.citation}<br>
    <b>Y Text:</b> ${yVerseInfo.text}`;

  L.popup().setLatLng(e.latlng).setContent(popupContent).openOn(map);
});
