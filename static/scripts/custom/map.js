// Map Initialization

// Create a new Leaflet map instance and attach it to the 'map' div
const map = L.map('map', {
    crs: L.CRS.Simple,
    minZoom: 0,
    fullscreenControl: true,
});

// Define the pixel boundaries of the image at its native zoom level
const imagePixelBounds = [
    [0, 0], // Top-left corner
    [31102, 31102] // Bottom-right corner
];

// The native zoom level of your image, where 1 map unit = 1 pixel
const nativeZoom = 7;

// Convert these pixel points into the map's LatLng coordinate system
const imageLatLngBounds = L.latLngBounds(
    map.unproject(imagePixelBounds[0], 7), // Use native zoom level 7
    map.unproject(imagePixelBounds[1], 7) // Use native zoom level 7
);

// Related to main.py
const tileUrl = '/static/tiles/{z}/{x}/{y}.png';

const tileLayer = L.tileLayer(tileUrl, {
    minZoom: 0,
    maxZoom: 12, // Max zoom is higher, to allow the user to zoom more and easily distinguish and click individual pixels.
    maxNativeZoom: 9, // 7 is native resolution, 9 is a 64x64px image upscaled to 256, to enable more zooming.
    tileSize: 256,
    noWrap: true,
    attribution: '<a href="https://huggingface.co/datasets/Theodor-Crosswell/KJV_Similarity" target="_blank">KJV Dataset</a> by <a href="https://github.com/TheodorCrosswell" target="_blank">Theodor Crosswell</a>', // I made the tiles and distances dataset.
    bounds: imageLatLngBounds, // To prevent the page from requesting nonexistent tiles from the server.
});
tileLayer.addTo(map);

// Map initial view
map.fitBounds(imageLatLngBounds);

// Click handling
map.on('click', function(e) {
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

// Color Filter Controls
const tilePane = tileLayer.getContainer();
const colorPresets = document.getElementById('color-presets');
const hueSlider = document.getElementById('hue-slider');
const sepiaSlider = document.getElementById('sepia-slider');
const saturateSlider = document.getElementById('saturate-slider');
const brightnessSlider = document.getElementById('brightness-slider');
const resetButton = document.getElementById('reset-filters');

const hueValue = document.getElementById('hue-value');
const sepiaValue = document.getElementById('sepia-value');
const saturateValue = document.getElementById('saturate-value');
const brightnessValue = document.getElementById('brightness-value');

function updateFilter() {
    const hue = hueSlider.value;
    const sepia = sepiaSlider.value;
    const saturate = saturateSlider.value;
    const brightness = brightnessSlider.value;

    hueValue.textContent = `${hue}deg`;
    sepiaValue.textContent = `${sepia}%`;
    saturateValue.textContent = `${saturate}%`;
    brightnessValue.textContent = `${brightness}%`;

    // The order of CSS filters is important.
    // 1. sepia() introduces color. This is necessary for hue-rotate and saturate to work on grayscale images.
    // 2. saturate() adjusts the intensity of the new color.
    // 3. hue-rotate() shifts the color.
    // 4. brightness() adjusts the overall lightness/darkness.
    tilePane.style.filter = `sepia(${sepia}%) saturate(${saturate}%) hue-rotate(${hue}deg) brightness(${brightness}%)`;
}


function resetFilters() {
    hueSlider.value = 0;
    sepiaSlider.value = 0;
    saturateSlider.value = 100;
    brightnessSlider.value = 100;
    colorPresets.value = 'none';
    updateFilter();
}

colorPresets.addEventListener('change', (e) => {
    const selectedFilter = e.target.value;
    if (selectedFilter === 'none') {
        resetFilters();
        return;
    }

    // Default values
    const filterValues = {
        'hue-rotate': 0,
        'sepia': 0,
        'saturate': 100,
        'brightness': 100
    };

    selectedFilter.split(' ').forEach(filter => {
        const property = filter.substring(0, filter.indexOf('('));
        const value = filter.substring(filter.indexOf('(') + 1, filter.indexOf(')'));

        switch (property) {
            case 'hue-rotate':
                filterValues[property] = parseInt(value); // e.g., "90deg" -> 90
                break;
            case 'sepia':
                filterValues[property] = parseFloat(value); // e.g., "100%" -> 100
                break;
            case 'saturate':
            case 'brightness':
                const numericValue = parseFloat(value);
                if (value.includes('%')) {
                    filterValues[property] = numericValue;
                } else {
                    filterValues[property] = numericValue * 100;
                }
                break;
        }
    });

    hueSlider.value = filterValues['hue-rotate'];
    sepiaSlider.value = filterValues['sepia'];
    saturateSlider.value = filterValues['saturate'];
    brightnessSlider.value = filterValues['brightness'];

    updateFilter();
});


hueSlider.addEventListener('input', updateFilter);
sepiaSlider.addEventListener('input', updateFilter);
saturateSlider.addEventListener('input', updateFilter);
brightnessSlider.addEventListener('input', updateFilter);
resetButton.addEventListener('click', resetFilters);

// Initial filter update
updateFilter();


// *** NEW FEATURE: PAN TO COORDINATE ***

// Get the HTML elements for the pan controls
const xCoordInput = document.getElementById('x-coord');
const yCoordInput = document.getElementById('y-coord');
const panButton = document.getElementById('pan-button');

/**
 * Pans the map to a specific pixel coordinate.
 * @param {number} x The x-coordinate (horizontal).
 * @param {number} y The y-coordinate (vertical).
 */
function panToPixel(x, y) {
    // Check if the inputs are valid numbers
    if (isNaN(x) || isNaN(y)) {
        alert('Please enter valid numeric coordinates.');
        return;
    }

    // Clamp the coordinates to the valid image range (1 to 31102)
    const min = 1;
    const max = 31102;
    const clampedX = Math.min(Math.max(x, min), max);
    const clampedY = Math.min(Math.max(y, min), max);

    // Create a Leaflet Point object from the pixel coordinates
    const pixelPoint = L.point(clampedX, clampedY);

    // Convert the pixel point to a LatLng object at the native zoom level
    // This is the crucial step to translate pixel space to map space
    const latLng = map.unproject(pixelPoint, nativeZoom);

    // Pan the map to the calculated LatLng coordinate
    map.panTo(latLng);
}

// Add a click event listener to the button
panButton.addEventListener('click', () => {
    // Get the values from the input fields and convert them to integers
    const x = parseInt(xCoordInput.value, 10);
    const y = parseInt(yCoordInput.value, 10);

    // Call the pan function with the parsed coordinates
    panToPixel(x, y);
});