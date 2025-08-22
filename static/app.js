// Step 1: Map Initialization

// Create a new Leaflet map instance and attach it to the 'map' div
// L.CRS.Simple is used for non-geographical maps with a simple Cartesian coordinate system. [10]
const map = L.map('map', {
    crs: L.CRS.Simple,
    // Set the minimum zoom level for the map
    minZoom: 0,
    // maxZoom: 12,
});

// Set the initial view of the map.
// The coordinates are [y, x] and the number is the zoom level.
// For a simple CRS, [0, 0] is a common starting center.
map.setView([0, 0], 2);


// Step 2: Tile Layer

// Define the URL template for the tiles from the FastAPI back-end
const tileUrl = '/static/tiles/{z}/{x}/{y}.png';

// Create a tile layer with the specified URL and configurations
const tileLayer = L.tileLayer(tileUrl, {
    minZoom: 0,
    maxZoom: 12,
    maxNativeZoom: 9,
    // NEW: The absolute highest zoom level the layer will display.
    // This should match the map's maxZoom to allow zooming that far.
    tileSize: 256,
    noWrap: true, // Prevents the map from repeating horizontally
    attribution: 'Your Image Viewer' // Optional: Add an attribution control
});

// Add the configured tile layer to the map
tileLayer.addTo(map);