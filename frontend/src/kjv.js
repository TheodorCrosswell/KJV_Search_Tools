// --- Make these accessible globally within the script ---
let worker;
let versePromiseResolver = null;

/**
 * A globally accessible function to get verse information by its ID.
 * Returns a Promise that resolves with the verse data { citation, text, ... }.
 * @param {number} verseId The verse ID to look up.
 * @returns {Promise<Object|null>}
 */
export function getVerseInfoById(verseId) {
  return new Promise((resolve, reject) => {
    if (!worker) {
      return reject(new Error("Web Worker is not initialized yet."));
    }
    // Store the resolver function to be called when the worker responds
    versePromiseResolver = resolve;
    // Send the query command to the worker
    worker.postMessage({ command: "query", payload: { verse_id: verseId } });

    // Optional: Add a timeout to prevent waiting forever
    setTimeout(() => {
      if (versePromiseResolver) {
        // If it hasn't been resolved yet
        reject(new Error(`Timeout waiting for verse data for ID: ${verseId}`));
        versePromiseResolver = null;
      }
    }, 5000); // 5-second timeout
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const verseMatchButton = document.getElementById("match-button");
  const verseSelect = document.getElementById("current-verse-select");
  const verseTextDiv = document.getElementById("verse-info");

  function initializeWorker() {
    verseTextDiv.innerHTML = "<p>Initializing data store...</p>";
    worker = new Worker(new URL("./data.worker.js", import.meta.url), {
      type: "module",
    });

    worker.onmessage = (event) => {
      const { status, message, result } = event.data;
      console.log("Message from worker:", event.data);

      if (status === "info") {
        verseTextDiv.innerHTML = `<p>${message}</p>`;
      } else if (status === "ready") {
        verseTextDiv.innerHTML = `<p>${message} You can now search.</p>`;
      } else if (status === "queryResult") {
        // --- If a promise is waiting, resolve it ---
        if (versePromiseResolver) {
          versePromiseResolver(result);
          versePromiseResolver = null; // Clear it for the next request
        }
        // Also display the results in the main view as before
        displayResults(result);
      } else if (status === "error") {
        verseTextDiv.innerHTML = `<p style="color: red;">Error: ${message}</p>`;
      }
    };
    worker.postMessage({ command: "init" });
  }

  function handleSearch() {
    const verseId = parseInt(verseSelect.value, 10);
    if (isNaN(verseId)) {
      verseTextDiv.innerHTML =
        '<p style="color: red;">Please enter a valid Verse ID.</p>';
      return;
    }
    verseTextDiv.innerHTML = `<p>Searching for Verse ID: ${verseId}...</p>`;

    // --- Use the new Promise-based function ---
    getVerseInfoById(verseId).catch((error) => {
      console.error("Search failed:", error);
      verseTextDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    });
  }

  function displayResults(result) {
    if (result) {
      verseTextDiv.innerHTML = `
        <h3>${result.citation}</h3>
        <p>${result.text}</p>
      `;
    } else {
      verseTextDiv.innerHTML = "<p>Verse not found.</p>";
    }
  }

  if (window.Worker) {
    initializeWorker();
    verseMatchButton.addEventListener("click", handleSearch);
    verseSelect.addEventListener("change", handleSearch);
  } else {
    verseTextDiv.innerHTML =
      "<p>Your browser does not support Web Workers.</p>";
  }
});
