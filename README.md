# Bible Verse Similarity Map

_An interactive map of verse similarity in the King James Bible._

_Try it out at http://kjv-search-tools.online/ or https://kjv-similarity-map-244276769903.us-south1.run.app/_

https://hub.docker.com/r/theodorcrosswell/kjv-similarity-map

This project presents an interactive map that visualizes the similarity between verses in the King James Version (KJV) of the Bible. Each pixel on this canvas represents a unique pairing of two verses, with the color intensity signifying the closeness of their semantic meaning.

## Gallery

<img width="1869" height="625" alt="image" src="https://github.com/user-attachments/assets/77bd5cfe-f58b-44ef-b70e-e2b36a46f0ab" />

## How It Works

The creation of this map is a multi-step process that transforms the biblical text into a visual representation of its own internal connections. The methodology is as follows:

1.  **Verse Encoding:** Every verse in the KJV Bible is encoded into a high-dimensional vector using a sentence-embedding model (All-MiniLM-l6-v2). This process converts the text of each verse into a numerical representation that captures its semantic meaning.

2.  **Similarity Computation:** A similarity score is calculated for every possible pair of verses. This results in a comprehensive matrix of verse-to-verse semantic relationships.

3.  **Tile Generation:** The similarity scores are then used to generate a vast grid of image tiles. Each pixel within these tiles corresponds to a specific verse pairing, and its color value is determined by the similarity score.

4.  **Interactive Map:** These tiles are served as an interactive map, allowing for seamless zooming and panning. This enables users to explore the relationships between verses at various levels of detail, from a high-level overview of the entire Bible to a close-up view of individual verse-to-verse connections.

## Features

- **Interactive Exploration:** Zoom and pan across the entire KJV Bible to find patterns.
- **Verse Information:** Click on any pixel to reveal the two verses it represents, allowing for a direct comparison of their text and context.
- **Discover Connections:** Uncover connections and patterns between different books and chapters of the Bible.
- **Intuitive Interface:** A clean and user-friendly interface makes it easy to navigate and explore the vast dataset.

## Technical Stack

This project is brought to life through a combination of powerful technologies:

- **Backend:**
  - **FastAPI:** A modern, fast web framework for building APIs with Python.
  - **Polars:** A data manipulation library for handling large datasets.
- **Frontend:**
  - **Leaflet.js:** An open-source JavaScript library for mobile-friendly interactive maps.
  - **HTML/CSS/JavaScript:** The foundational technologies for building the user interface.
- **Data Processing:**
  - **ChromaDB:** An open-source embedding database for storing and querying vector representations of the Bible verses.
  - **NumPy:** A fundamental package for scientific computing with Python.
  - **Pillow (PIL):** A powerful image processing library for Python.

## Getting Started

You can either run this project directly from the source code, or from a docker image.

To run it as a docker image:

1.  **Pull the image:**
    ```bash
    docker pull theodorcrosswell/kjv-similarity-map:latest
    ```
2.  **Run the image as a container:**
    ```bash
    docker run -p 8000:8000 --name kjv-similarity-map kjv-similarity-map:latest  
    ```
3.  **Open 127.0.0.1:8000 in your web browser.**


To run this project locally, you will need to have Python installed on your machine.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/TheodorCrosswell/KJV_Search_Tools.git
    ```
2.  **Install the required Python packages:**
    ```bash
    python -m pip install -r requirements.txt
    ```
3.  **Start the backend server:**
    ```bash
    python -m fastapi dev main.py
    ```
    or
    ```bash
    python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
    ```
4.  **Open 127.0.0.1:8000 in your web browser.**

You should now be able to interact with the Bible Verse Similarity Map on your local machine.
