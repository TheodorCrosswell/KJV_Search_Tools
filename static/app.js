//app.js


// Step 1: Define Image Dimensions
// IMPORTANT: Replace with the full width and height of your original image at max zoom (level 7)
const imageWidth = 32768; // Example: 32 tiles * 256px/tile
const imageHeight = 32768; // Example: 32 tiles * 256px/tile

// Step 2: Map Initialization

// Create a new Leaflet map instance and attach it to the 'map' div
// L.CRS.Simple is used for non-geographical maps with a simple Cartesian coordinate system.
const map = L.map('map', {
    crs: L.CRS.Simple,
    // Set the minimum zoom level for the map
    minZoom: 0,
    maxZoom: 7, // Make sure maxZoom is set here as well
});

// Step 3: Define Map Bounds
// We define the coordinate system with the top-left corner at [0, 0]
// and the bottom-right corner at [imageHeight, imageWidth].
// Note: Leaflet uses [y, x] for coordinates.
const southWest = map.unproject([0, imageHeight], map.getMaxZoom());
const northEast = map.unproject([imageWidth, 0], map.getMaxZoom());
const bounds = new L.LatLngBounds(southWest, northEast);


// Set the view to fit these bounds
map.fitBounds(bounds);

// Step 4: Custom Tile Layer

// Extend the L.TileLayer class to use custom coordinates in the URL
L.TileLayer.CustomCoords = L.TileLayer.extend({
    getTileUrl: function(coords) {
        const zoom = this._map.getZoom();
        const multiplier = 256 * Math.pow(2, this.options.maxZoom - zoom);
        const x = coords.x * multiplier;
        const y = coords.y * multiplier;
        return `/static/tiles/${zoom}/${x}/${y}.png`;
    }
});

// Create a new instance of our custom tile layer
const tileLayer = new L.TileLayer.CustomCoords('', {
    minZoom: 0,
    maxZoom: 7,
    tileSize: 256,
    noWrap: true, // Prevents the map from repeating
    bounds: bounds, // IMPORTANT: Associate the tile layer with the bounds
    attribution: 'Your Image Viewer'
});


// Add the configured tile layer to the map
tileLayer.addTo(map);