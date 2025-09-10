import { map, nativeZoom } from "./map";

document.addEventListener('DOMContentLoaded', () => {
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
});