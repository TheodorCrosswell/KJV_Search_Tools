import { openDB } from 'idb';

let db;

// A function to populate the database from the JSON file
async function populateDB() {
  self.postMessage({ status: 'info', message: 'Checking for existing data...' });

  const tx = db.transaction('verses', 'readonly');
  const store = tx.objectStore('verses');
  const count = await store.count();
  await tx.done;

  if (count > 0) {
    self.postMessage({ status: 'info', message: 'Data already exists. Skipping population.' });
    return; // Data is already there, no need to import
  }

  self.postMessage({ status: 'info', message: 'Fetching data to populate the store...' });

  try {
    const response = await fetch('/dist/kjv.json'); // Make sure kjv.json is in the correct path
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const verses = await response.json();

    self.postMessage({ status: 'info', message: 'Data fetched. Populating data store...' });

    const writeTx = db.transaction('verses', 'readwrite');
    const writeStore = writeTx.objectStore('verses');

    for (const verse of verses) {
      writeStore.add(verse); // Use add() to insert each verse object
    }

    await writeTx.done;
    self.postMessage({ status: 'info', message: 'Data store populated successfully.' });

  } catch (error) {
    self.postMessage({ status: 'error', message: `Failed to populate data: ${error.message}` });
  }
}

// A function to initialize the database
async function initDB() {
  db = await openDB('my-database', 1, {
    upgrade(db, oldVersion, newVersion, transaction) {
      if (!db.objectStoreNames.contains('verses')) {
        const store = db.createObjectStore('verses', {
          keyPath: 'verse_id',
        });
        store.createIndex('citation', 'citation', { unique: true });
      }
    },
  });
}

// Listen for messages from the main thread
self.onmessage = async (event) => {
  const { command, payload } = event.data;

  if (command === 'init') {
    try {
      self.postMessage({ status: 'info', message: 'Initializing data store...' });
      
      await initDB();

      // Populate the DB with data if it's empty
      await populateDB();

      self.postMessage({ status: 'ready', message: 'Data store is ready.' });

    } catch (error) {
      self.postMessage({ status: 'error', message: `Database setup failed: ${error.message}` });
    }
  }

  if (command === 'query') {
    if (!db) {
      self.postMessage({ status: 'error', message: 'Database is not initialized.' });
      return;
    }

    try {
      const { verse_id } = payload;
      const result = await db.get('verses', verse_id);
      
      self.postMessage({ status: 'queryResult', result });

    } catch (error) {
      self.postMessage({ status: 'error', message: `Query failed: ${error.message}` });
    }
  }
};