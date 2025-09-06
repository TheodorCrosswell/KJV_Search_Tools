document.addEventListener('DOMContentLoaded', () => {

// Verse Selector
    const bookSelect = document.getElementById('book-select');
    const chapterSelect = document.getElementById('chapter-select');
    const verseSelect = document.getElementById('verse-select');
    const verseMatchButton = document.getElementById('match-button');
    const clearMarkersButton = document.getElementById('clear-markers-button');
    const verseCoordLabel = document.getElementById('verse_coord');

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


    // Similarity Search
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
                popupContents = JSON.parse(data)
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

    // Changelog
    const changelogPopup = document.getElementById('changelog-popup');
    const changelogList = document.getElementById('changelog-list');
    const closePopupButton = document.getElementById('close-popup');

    const showChangelogPopup = (content) => {
        changelogList.innerHTML = DOMPurify.sanitize(marked.parse(content));
        changelogPopup.classList.remove('hidden');
    };

    const hideChangelogPopup = () => {
        changelogPopup.classList.add('hidden');
    };

    const checkChangelog = async () => {
        try {
            const response = await fetch('/changelog');
            const data = await response.json();
            const latestData = data[0];
            const currentVersion = latestData.version;
            const lastSeenVersion = localStorage.getItem('lastSeenChangelogVersion');

            if (currentVersion !== lastSeenVersion) {
                let changelogContent = '';
                const recentChangelogs = data.slice(0, 5);

                recentChangelogs.forEach(release => {
                    changelogContent += `## ${release.version}\n\n${release.notes}\n\n---\n\n`;
                });

                changelogContent += 'For a full list of changes, please visit the [GitHub releases page](https://github.com/TheodorCrosswell/KJV_Search_Tools/releases).\n';
                
                showChangelogPopup(changelogContent);
                localStorage.setItem('lastSeenChangelogVersion', currentVersion);
            }
        } catch (error) {
            console.error('Failed to fetch changelog:', error);
        }
    };

    closePopupButton.addEventListener('click', hideChangelogPopup);
    checkChangelog();
});