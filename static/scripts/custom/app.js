document.addEventListener('DOMContentLoaded', () => {
    const bookSelect = document.getElementById('book-select');
    const chapterSelect = document.getElementById('chapter-select');
    const verseSelect = document.getElementById('verse-select');
    const verseMatchButton = document.getElementById('match-button');
    const verseCoordLabel = document.getElementById('verse_coord');

    let bibleData = {};

    // Fetch the Bible data from the FastAPI backend
    fetch('/api/verse_selector_data')
        .then(response => response.json())
        .then(data => {
            bibleData = data;
            populateBooks();
        });

    function populateBooks() {
        for (const book in bibleData) {
            const option = document.createElement('option');
            option.value = book;
            option.textContent = book;
            bookSelect.appendChild(option);
        }
    }

    function getVerseNumber() {
        const bookName = bookSelect.value;
        const chapter = +chapterSelect.value;
        const verse = +verseSelect.value; // Unary Plus operator - converts string and other types to number.

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
        const selectedBook = bookSelect.value;
        // chapterSelect.innerHTML = '<option value="1">1</option>';
        // verseSelect.innerHTML = '<option value="1">1</option>';
        chapterSelect.disabled = false;
        verseSelect.disabled = false;

        if (selectedBook) {
            chapterSelect.innerHTML = '';
            const bookInfo = bibleData[selectedBook];
            for (let i = 1; i <= bookInfo.chapters; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i;
                chapterSelect.appendChild(option);
            }
            chapterSelect.disabled = false;
        }
    });

    chapterSelect.addEventListener('change', () => {
        const selectedBook = bookSelect.value;
        const selectedChapter = chapterSelect.value;
        // verseSelect.innerHTML = '<option value="">1</option>';
        verseSelect.disabled = false;

        if (selectedBook && selectedChapter) {
            verseSelect.innerHTML = '';
            const versesInChapter = bibleData[selectedBook].verses[selectedChapter];
            for (let i = 1; i <= versesInChapter; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = i;
                verseSelect.appendChild(option);
            }
            verseSelect.disabled = false;
        }
    });

    function getVerseMatches() {
        fetch(`/api/verse_similarity_search/${getVerseNumber()}/10`)
        .then(response => response.json())
        .then(data => {
            results = data;
            
        });
        verseCoordLabel.innerText = results
    }

    verseMatchButton.addEventListener('click', getVerseMatches)
});