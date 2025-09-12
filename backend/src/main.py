from fastapi import FastAPI, Request, Depends, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
from chromadb import PersistentClient, Collection
import zipfile
import io
import os

# To start server in development mode:
#  ./.venv/Scripts/python.exe -m fastapi dev ./backend/src/main.py
# To start server in production mode:
# ./.venv/Scripts/python.exe -m uvicorn backend.src.main:app --host 0.0.0.0 --port 8000

# 1. Get the directory of the current file (main.py)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Go up one level to the project root ('backend/')
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)

# This acts as an in-memory database
app_data = {}

# --- Rate Limiting Setup ---
# 1. Create a Limiter instance.
#    get_remote_address is a function that identifies the client by their IP.
#    The default storage is an in-memory dictionary.
limiter = Limiter(key_func=get_remote_address)


# The lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Opens tiles.zip and ChromaDB Collection"""

    app_data["chroma_collection"] = PersistentClient(
        os.path.join(project_root, ".chroma")
    ).get_collection("kjv_verses")

    # zipfile
    zip_path = os.path.join(project_root, "tiles", "tiles.zip")
    app_data["tiles_zipfile"] = zipfile.ZipFile(zip_path, "r")

    print("Data loaded successfully.")

    yield  # The application runs while the lifespan function is yielded

    # --- Code to run on shutdown ---
    print("Server shutting down...")
    app_data.clear()  # Clear the data on shutdown


# Create the FastAPI app and attach the lifespan event handler
app = FastAPI(lifespan=lifespan)

# --- Add Rate Limiting State and Exception Handler ---
# 2. Set the app's state to include the limiter instance.
app.state.limiter = limiter
# 3. Add the exception handler for when a request goes over the limit.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Serve index.html, app.js, scripts
app.mount(
    "/dist",
    StaticFiles(directory=os.path.join(project_root, "frontend/dist")),
    name="dist",
)


@app.get("/tiles/{filename:path}")
async def serve_file_from_zip(filename: str):
    """
    Serves a file from a zip archive efficiently.

    Args:
        filename: The path to the file within the zip archive.

    Returns:
        A StreamingResponse with the file data if found, otherwise raises
        an HTTPException.
    """
    try:
        # Directly access the file info. This is much faster.
        # It will raise a KeyError if the file is not found.
        file_info = app_data["tiles_zipfile"].getinfo(filename)

        # Use a context manager to open and read the specific file
        with app_data["tiles_zipfile"].open(file_info) as file_data:
            # Wrap the file-like object in a BytesIO stream
            content = io.BytesIO(file_data.read())
            return StreamingResponse(content, media_type="image/png")

    except KeyError:
        # This is the expected exception when a file is not in the archive.
        raise HTTPException(status_code=404, detail="File not found in archive")
    except FileNotFoundError:
        # This would happen if 'file_archive.zip' itself is missing.
        raise HTTPException(status_code=500, detail="Archive not found")

@app.get("/api/verse_similarity_search/{verse_id}/{n_results}")
@limiter.limit("10/minute")
async def get_verse_similarity_results(
    request: Request, verse_id: int, n_results: int = 10
):
    if n_results > 100:
        n_results = 100
    elif n_results < 1:
        n_results = 1
    collection = app_data["chroma_collection"]
    # collection = Collection()
    verse_results = collection.get(
        where={"verse_id": {"$eq": verse_id}},
        include=["embeddings"],
        limit=1,
    )
    verse_embeddings = verse_results["embeddings"]

    raw_results = collection.query(
        query_embeddings=verse_embeddings,
        n_results=n_results + 1, # In order to avoid having a where filter, this is probably quicker
        include=["distances", "metadatas"],
    )
    results = {
        "verse_ids": [x["verse_id"] for x in raw_results["metadatas"][0]],
        "distances": raw_results["distances"][0],
    }

    marker_datas = []
    for i in range(1, len(results["verse_ids"])):
        marker_datas.append(
            {
                "distance": f"{results['distances'][i]:.2f}",
                "xCoord": int(verse_id),
                "yCoord": int(results["verse_ids"][i]),
            }
        )
    return json.dumps(marker_datas)


@app.get("/")
async def get_index():
    """This is the main page."""
    return FileResponse(os.path.join(project_root, "frontend/dist/index.html"))


@app.get("/favicon.ico")
async def get_favicon():
    """This is the favicon."""
    return FileResponse(os.path.join(project_root, "frontend/dist/kjv.png"))
