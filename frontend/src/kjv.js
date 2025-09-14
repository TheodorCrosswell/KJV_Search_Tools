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

    // Add a timeout to prevent waiting forever
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
  function initializeWorker() {
    worker = new Worker(new URL("./data.worker.js", import.meta.url), {
      type: "module",
    });

    worker.onmessage = (event) => {
      const { status, message, result } = event.data;
      if (status === "queryResult") {
        // --- If a promise is waiting, resolve it ---
        if (versePromiseResolver) {
          versePromiseResolver(result);
          versePromiseResolver = null; // Clear it for the next request
        }
      }
    };
    worker.postMessage({ command: "init" });
  }

  if (window.Worker) {
    initializeWorker();
  } else {
    console.error("<p>Your browser does not support Web Workers.</p>");
  }
});
