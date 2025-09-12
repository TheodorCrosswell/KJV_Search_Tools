import { marker } from "leaflet";
import { map, nativeZoom } from "./map";
import 'leaflet';

document.addEventListener('DOMContentLoaded', () => {
    // Verse Selector
    const bookSelect = document.getElementById('book-select');
    const chapterSelect = document.getElementById('chapter-select');
    const verseSelect = document.getElementById('verse-select');
    // Not properly implemented yet
    // const verseCitationLabel = document.getElementById('verse-citation');
    // const verseTextLabel = document.getElementById('verse-text');


    let bibleData = {};

    // Fetch the Bible data from the FastAPI backend
    fetch('/api/verse_selector_data')
        .then(response => response.json())
        .then(data => {
            bibleData = data;
            populateBooks();
            // Set the initial book to Genesis and populate chapters
            bookSelect.value = 'Genesis';
            populateChapters();
            // Set the initial chapter to 1 and populate verses
            chapterSelect.value = '1';
            populateVerses();
            // Set the initial verse to 1
            verseSelect.value = '1';
        });

    function populateBooks() {
        bookSelect.innerHTML = ''
        for (const book in bibleData) {
            const option = document.createElement('option');
            option.value = book;
            option.textContent = book;
            bookSelect.appendChild(option);
        }
    }

    function populateChapters() {
        const selectedBook = bookSelect.value;
        if (selectedBook) {
            chapterSelect.innerHTML = '';
            const bookInfo = bibleData[selectedBook];
            for (let i = 1; i <= bookInfo.chapters; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i;
                chapterSelect.appendChild(option);
            }
        }
    }

    function populateVerses() {
        const selectedBook = bookSelect.value;
        const selectedChapter = chapterSelect.value;

        if (selectedBook && selectedChapter) {
            verseSelect.innerHTML = '';
            const versesInChapter = bibleData[selectedBook].verses[selectedChapter];
            for (let i = 1; i <= versesInChapter; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i;
                verseSelect.appendChild(option);
            }
        }
    }

    function getVerseNumber() {
        const bookName = bookSelect.value;
        const chapter = +chapterSelect.value;
        const verse = +verseSelect.value; // Unary plus operator - converts string and other types to number.

        let verseCount = 0;
        const bookList = Object.keys(bibleData);

        for (const currentBookName of bookList) {
            const bookData = bibleData[currentBookName];

            // If we found the target book
            if (currentBookName === bookName) {
                // Validate that the chapter and verse exist
                if (!bookData.verses[chapter] || verse > bookData.verses[chapter] || verse < 1) {
                    verseCoordLabel.innerHTML = `Invalid address.
                     Book: ${bookName} Chapter: ${chapter} Verse: ${verse}`
                    return -1
                }

                // Add verses from preceding chapters in the target book
                for (let ch = 1; ch < chapter; ch++) {
                    verseCount += bookData.verses[ch];
                }

                // Add the verse number from the target chapter
                verseCount += verse;

                // Return the final count as we've found our verse
                return verseCount
            }
            // If it's a book before the target book
            else {
                // Add all verses from all chapters of the current book
                for (let ch = 1; ch <= bookData.chapters; ch++) {
                    verseCount += bookData.verses[ch];
                }
            }
        }
    }

    bookSelect.addEventListener('change', () => {
        populateChapters();
        // Also populate the verses for the first chapter of the new book
        populateVerses();
    });

    chapterSelect.addEventListener('change', () => {
        populateVerses();
    });
    
    // Not properly implemented yet
    // verseSelect.addEventListener('change', () => {
    //     populateVerseLabel();
    // });

    // Similarity Search
    const verseMatchButton = document.getElementById('match-button');
    const clearMarkersButton = document.getElementById('clear-markers-button');
    const previousMarkerButton = document.getElementById('previous-marker-button');
    const nextMarkerButton = document.getElementById('next-marker-button');
    const currentVerseSelect = document.getElementById("current-verse-select");
    let markerDatas = {};
    let currentMarkerIndex = -1;
    let currentVerseNumber = -1;
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
                const newOption = document.createElement('option');
                newOption.value = currentVerseNumber;
                newOption.textContent = +currentVerseNumber + " Need to look coord up in kjv";
                currentVerseSelect.appendChild(newOption);
                currentVerseSelect.value = currentVerseNumber
            })
            .catch(error => {
                console.error('There was a problem with the fetch operation:', error);
            });
    }

    function clearMarkers() {
        markerDatas = {};
        markerGroup.clearLayers();
        currentVerseSelect.options.length = 0;
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

    currentVerseSelect.addEventListener('change', () =>{
        currentVerseNumber = currentVerseSelect.value
        currentMarkerIndex = -1
    });
});