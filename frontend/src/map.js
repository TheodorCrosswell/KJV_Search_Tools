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

// Click handling
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
