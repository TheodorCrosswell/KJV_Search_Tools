import { marker } from "leaflet";
import { map, nativeZoom } from "./map";
import "leaflet";
import { getVerseInfoById } from "./kjv";

document.addEventListener("DOMContentLoaded", () => {
  // Verse Selector
  const bookSelect = document.getElementById("book-select");
  const chapterSelect = document.getElementById("chapter-select");
  const verseSelect = document.getElementById("verse-select");

  let bibleData = {};

  // Fetch the Bible data from the FastAPI backend
  fetch("dist/verse_selector_data.json")
    .then((response) => response.json())
    .then((data) => {
      bibleData = data;
      populateBooks();
      // Set the initial book to Genesis and populate chapters
      bookSelect.value = "Genesis";
      populateChapters();
      // Set the initial chapter to 1 and populate verses
      chapterSelect.value = "1";
      populateVerses();
      // Set the initial verse to 1
      verseSelect.value = "1";
    });

  function populateBooks() {
    bookSelect.innerHTML = "";
    for (const book in bibleData) {
      const option = document.createElement("option");
      option.value = book;
      option.textContent = book;
      bookSelect.appendChild(option);
    }
  }

  function populateChapters() {
    const selectedBook = bookSelect.value;
    if (selectedBook) {
      chapterSelect.innerHTML = "";
      const bookInfo = bibleData[selectedBook];
      for (let i = 1; i <= bookInfo.chapters; i++) {
        const option = document.createElement("option");
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
      verseSelect.innerHTML = "";
      const versesInChapter = bibleData[selectedBook].verses[selectedChapter];
      for (let i = 1; i <= versesInChapter; i++) {
        const option = document.createElement("option");
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
        if (
          !bookData.verses[chapter] ||
          verse > bookData.verses[chapter] ||
          verse < 1
        ) {
          verseCoordLabel.innerHTML = `Invalid address.
                     Book: ${bookName} Chapter: ${chapter} Verse: ${verse}`;
          return -1;
        }

        // Add verses from preceding chapters in the target book
        for (let ch = 1; ch < chapter; ch++) {
          verseCount += bookData.verses[ch];
        }

        // Add the verse number from the target chapter
        verseCount += verse;

        // Return the final count as we've found our verse
        return verseCount;
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

  bookSelect.addEventListener("change", () => {
    populateChapters();
    // Also populate the verses for the first chapter of the new book
    populateVerses();
  });

  chapterSelect.addEventListener("change", () => {
    populateVerses();
  });

  // Similarity Search
  const verseMatchButton = document.getElementById("match-button");
  const clearMarkersButton = document.getElementById("clear-markers-button");
  const previousMarkerButton = document.getElementById(
    "previous-marker-button"
  );
  const nextMarkerButton = document.getElementById("next-marker-button");
  const currentVerseSelect = document.getElementById("current-verse-select");
  let currentMarkerIndex = 0;
  let currentVerseNumber = 1;
  let markersList = {};
  // const nativeZoom = 7

  // --- Make the function async to use await ---
  async function getVerseMatches() {
    // Construct the URL for our FastAPI endpoint
    currentVerseNumber = getVerseNumber();
    const verseSimilaritySearchApiUrl = `/api/verse_similarity_search/${currentVerseNumber}/50`;

    // Use fetch to make the API call
    fetch(verseSimilaritySearchApiUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        return response.json();
      })
      .then(async (data) => {
        markersList[currentVerseNumber] = [];
        currentMarkerIndex = 0;
        const xVerseInfo = await getVerseInfoById(currentVerseNumber);
        for (const markerData of JSON.parse(data)) {
          const latlng = map.unproject(
            [markerData.xCoord - 0.5, markerData.yCoord - 0.5],
            nativeZoom
          );
          const yVerseInfo = await getVerseInfoById(markerData.yCoord);

          const popupContent = `<b>Distance:</b> ${markerData.distance}<br>
            <b>Coordinates:</b> ${xVerseInfo.verse_id}, ${yVerseInfo.verse_id}<br>
            <b>X Citation:</b> ${xVerseInfo.citation}<br>
            <b>X Text:</b> ${xVerseInfo.text}<br>
            <b>Y Citation:</b> ${yVerseInfo.citation}<br>
            <b>Y Text:</b> ${yVerseInfo.text}`;

          const newMarker = L.marker(latlng)
            .bindPopup(popupContent)
            .addTo(markerGroup);
          markersList[currentVerseNumber].push(newMarker);
        }

        const newOption = document.createElement("option");
        newOption.value = currentVerseNumber;
        newOption.textContent = xVerseInfo.citation;

        currentVerseSelect.appendChild(newOption);
        currentVerseSelect.value = currentVerseNumber;
      })
      .catch((error) => {
        console.error("There was a problem with the fetch operation:", error);
      });
  }

  function clearMarkers() {
    markersList = {};
    markerGroup.clearLayers();
    currentVerseSelect.options.length = 0;
  }

  function panToMarker() {
    // --- Defensive Check ---
    // Ensure that marker data exists for the current verse number
    if (
      !markersList[currentVerseNumber] ||
      markersList[currentVerseNumber].length === 0
    ) {
      console.error("No marker data available for verse:", currentVerseNumber);
      console.error(markersList);
      return; // Exit the function if no data
    }

    // --- Boundary Checks ---
    // Make sure the index is within the bounds of the array
    if (currentMarkerIndex < 0) {
      console.log(
        `index ${currentMarkerIndex} < 0, is not within the marker array`
      );
      currentMarkerIndex = 0;
    }
    if (currentMarkerIndex >= markersList[currentVerseNumber].length) {
      console.log(
        `index ${currentMarkerIndex} > ${
          markersList[currentVerseNumber].length - 1
        }, is not within the marker array`
      );
      currentMarkerIndex = markersList[currentVerseNumber].length - 1;
    }

    const markerLatLng =
      markersList[currentVerseNumber][currentMarkerIndex].getLatLng();
    map.panTo(markerLatLng);
  }

  nextMarkerButton.addEventListener("click", () => {
    currentMarkerIndex += 1;
    panToMarker();
    markersList[currentVerseNumber][currentMarkerIndex].openPopup();
  });

  previousMarkerButton.addEventListener("click", () => {
    currentMarkerIndex -= 1;
    panToMarker();
    markersList[currentVerseNumber][currentMarkerIndex].openPopup();
  });

  var markerGroup = L.featureGroup().addTo(map);

  verseMatchButton.addEventListener("click", getVerseMatches);

  clearMarkersButton.addEventListener("click", clearMarkers);

  currentVerseSelect.addEventListener("change", () => {
    currentVerseNumber = currentVerseSelect.value;
    currentMarkerIndex = -1;
  });
});
