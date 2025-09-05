document.addEventListener('DOMContentLoaded', () => {
    const bookSelect = document.getElementById('book-select');
    const chapterSelect = document.getElementById('chapter-select');
    const verseSelect = document.getElementById('verse-select');

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

    bookSelect.addEventListener('change', () => {
        const selectedBook = bookSelect.value;
        chapterSelect.innerHTML = '<option value="">Select a Chapter</option>';
        verseSelect.innerHTML = '<option value="">Select a Verse</option>';
        chapterSelect.disabled = true;
        verseSelect.disabled = true;

        if (selectedBook) {
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
        verseSelect.innerHTML = '<option value="">Select a Verse</option>';
        verseSelect.disabled = true;

        if (selectedBook && selectedChapter) {
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
});