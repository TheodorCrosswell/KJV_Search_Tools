import { marker } from "leaflet";
import { map, nativeZoom } from "./map";
import { getVerseNumber } from "./verse_selector";
import 'leaflet';


document.addEventListener('DOMContentLoaded', () => {
    // Similarity Search
    const verseMatchButton = document.getElementById('match-button');
    const clearMarkersButton = document.getElementById('clear-markers-button');
    const previousMarkerButton = document.getElementById('previous-marker-button');
    const nextMarkerButton = document.getElementById('next-marker-button');
    let markerDatas = {};
    let currentMarkerIndex = 0;
    let currentVerseNumber = 0;
    // const nativeZoom = 7

    function getVerseMatches() {         

        // Construct the URL for our FastAPI endpoint
        currentVerseNumber = getVerseNumber();
        const verseSimilaritySearchApiUrl = `/api/verse_similarity_search/${currentVerseNumber}/50`;

        // Use fetch to make the API call
        fetch(verseSimilaritySearchApiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                markerDatas[currentVerseNumber] = JSON.parse(data)
                markerDatas[currentVerseNumber].forEach(item => {
                    const markerData = item
                    const xCoord = markerData.xCoord;
                    const yCoord = markerData.yCoord;

                    const latlng = map.unproject([xCoord, yCoord], nativeZoom);

                    // --- Create a shallow copy for the popup content ---
                    const popupData = { ...item };
                    // Delete from the copy, not the original
                    delete popupData.xCoord;
                    delete popupData.yCoord;

                    const contentLines = [];
                    // Iterate over the copied data to build the popup
                    for (const [key, value] of Object.entries(popupData)) {
                        const formattedKey = key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                        contentLines.push(`<b>${formattedKey}:</b> ${value}`);
                    }
                    const popupContent = contentLines.join('<br>');

                    L.marker(latlng).bindPopup(popupContent).addTo(markerGroup);
                });
            })
            .catch(error => {
                console.error('There was a problem with the fetch operation:', error);
            });
    }

    function clearMarkers() {
        markerDatas = {};
        markerGroup.clearLayers();
    }

    function panToMarker() {
        const markerData = markerDatas[currentVerseNumber][currentMarkerIndex];
        // Create a Leaflet Point object from the pixel coordinates
        // const pixelPoint = L.point(markerData.xCoord, markerData.yCoord);

        // Convert the pixel point to a LatLng object at the native zoom level
        // This is the crucial step to translate pixel space to map space
        const latLng = map.unproject([markerData.xCoord, markerData.yCoord], nativeZoom);

        // Pan the map to the calculated LatLng coordinate
        map.panTo(latLng);
    }

    var markerGroup = L.featureGroup().addTo(map);

    verseMatchButton.addEventListener('click', getVerseMatches);

    clearMarkersButton.addEventListener('click', clearMarkers);

    nextMarkerButton.addEventListener('click', () => {
        currentMarkerIndex += 1;
        panToMarker();
    });

    previousMarkerButton.addEventListener('click', () => {
        currentMarkerIndex -= 1;
        panToMarker();
    });
});