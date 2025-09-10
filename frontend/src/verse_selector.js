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

    export function getVerseNumber() {
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

    // Not properly implemented yet
    // function populateVerseLabel () {
    //     verseCitationLabel.innerHTML = 
    //     verseTextLabel.innerHTML = 
    //     fetch('/dist/kjv.json')
    //     .then(response => response.json())
    //     .then(data => {
    //         citation = data // TODO
    //     });
    // }

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

   