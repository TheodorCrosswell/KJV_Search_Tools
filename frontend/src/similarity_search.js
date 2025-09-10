import { map, nativeZoom } from "./map";
import { getVerseNumber } from "./verse_selector";
import 'leaflet';


document.addEventListener('DOMContentLoaded', () => {
    // Similarity Search
    const verseMatchButton = document.getElementById('match-button');
    const clearMarkersButton = document.getElementById('clear-markers-button');

    // const nativeZoom = 7

    function getVerseMatches() {         
        // We want the pixel coordinates at the zoom level that represents the original image size.
        const targetZoom = nativeZoom;

        // Construct the URL for our FastAPI endpoint
        const verseSimilaritySearchApiUrl = `/api/verse_similarity_search/${getVerseNumber()}/50`;

        // Use fetch to make the API call
        fetch(verseSimilaritySearchApiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const popupContents = JSON.parse(data)
                popupContents.forEach(item => {
                    const xCoord = item.xCoord;
                    const yCoord = item.yCoord;
                    delete item.xCoord;
                    delete item.yCoord;


                    const latlng = map.unproject([yCoord, xCoord], targetZoom);

                    const contentLines = [];
                    for (const [key, value] of Object.entries(item)) {
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
        markerGroup.clearLayers();
    }

    var markerGroup = L.featureGroup().addTo(map);

    verseMatchButton.addEventListener('click', getVerseMatches);

    clearMarkersButton.addEventListener('click', clearMarkers);
});