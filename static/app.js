// Map Initialization

// Create a new Leaflet map instance and attach it to the 'map' div
const map = L.map('map', {
    crs: L.CRS.Simple,
    minZoom: 0
});

// Define the pixel boundaries of the image at its native zoom level
const imagePixelBounds = [
    [0, 0],              // Top-left corner
    [31102, 31102]       // Bottom-right corner
];

// Convert these pixel points into the map's LatLng coordinate system
const imageLatLngBounds = L.latLngBounds(
    map.unproject(imagePixelBounds[0], 7), // Use native zoom level 7
    map.unproject(imagePixelBounds[1], 7)  // Use native zoom level 7
);

// Related to main.py
const tileUrl = '/static/tiles/{z}/{x}/{y}.png';

const tileLayer = L.tileLayer(tileUrl, {
    minZoom: 0,
    maxZoom: 12, // Max zoom is higher, to allow the user to zoom more and easily distinguish and click individual pixels.
    maxNativeZoom: 9, // 7 is native resolution, 9 is a 64x64px image upscaled to 256, to enable more zooming.
    tileSize: 256,
    noWrap: true,
    attribution: 'KJV Dataset by <a href="https://github.com/TheodorCrosswell">Theodor Crosswell', // I made the tiles and distances dataset.
    bounds: imageLatLngBounds , // To prevent the page from requesting nonexistent tiles from the server.
});
tileLayer.addTo(map);

// Map initial view
map.fitBounds(imageLatLngBounds);

// Click handling
map.on('click', function(e) {
    // We want the pixel coordinates at the zoom level that represents the original image size.
    const targetZoom = 7;

    // Project the map's lat/lng coordinates to pixel coordinates at our target zoom level.
    const pixelCoords = map.project(e.latlng, targetZoom);

    // The result from project() is an object with x and y properties.
    // We need to round them to get integer coordinates for the API call.
    const x = Math.floor(pixelCoords.x);
    const y = Math.floor(pixelCoords.y);

    // Construct the URL for our FastAPI endpoint
    const apiUrl = `/api/pixel_info/${x}/${y}`;

    // Use fetch to make the API call
    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const contentLines = [];
            for (const [key, value] of Object.entries(data)) {
                const formattedKey = key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                contentLines.push(`<b>${formattedKey}:</b> ${value}`);
            }
            const popupContent = contentLines.join('<br>');

            L.popup()
                .setLatLng(e.latlng)
                .setContent(popupContent)
                .openOn(map);
        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
        });
});