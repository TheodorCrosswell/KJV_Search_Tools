from fastapi import FastAPI, Request, Depends, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import polars as pl
import json
from chromadb import PersistentClient, Collection
import zipfile
import io

# To start in server in development mode:
#  ./.venv/Scripts/python.exe -m fastapi dev ./backend/src/main.py
# To start server in production mode:
# ./.venv/Scripts/python.exe -m uvicorn backend.src.main:app --host 0.0.0.0 --port 8000

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
    """This loads the kjv.csv file into memory, allowing for fast retrieval of pixel_info"""
    # --- Code to run on startup ---
    df = pl.read_csv("frontend/dist/kjv.csv")

    # Load the verse details lookup table
    app_data["verse_info"] = df.select(["citation", "text"]).rename(
        {"citation": "Verse"}
    )

    # Load verse_selector_data from JSON file
    with open("frontend/dist/verse_selector_data.json") as file:
        app_data["verse_selector_data"] = json.load(file)

    app_data["chroma_collection"] = PersistentClient(".chroma").get_collection(
        "kjv_verses"
    )

    zip_path = "/tiles/tiles.zip"
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


# Serve index.html, app.js, scripts, and tiles.
app.mount("/dist", StaticFiles(directory="frontend/dist"), name="dist")
# Now using an uncompressed .zip archive in order to speed up file transfer
# app.mount("/tiles", StaticFiles(directory="frontend/tiles"), name="tiles")


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


# TODO: consider moving this to client-side processing to avoid loading the server much.
@app.get("/api/pixel_info/{x}/{y}")
@limiter.limit("1/second")
def get_pixel_info(x: int, y: int, request: Request):
    """This is used to get the verse addresses for the clicked pixel.
    - x: the index of verse x
    - y: the index of verse y"""
    verse_df = pl.DataFrame(app_data["verse_info"])

    # Make sure verse_id is a valid index
    if 0 <= x <= len(verse_df) and 0 <= y <= len(verse_df):
        # .row() returns a tuple of the values in that row
        x_row_data = verse_df.row(x - 1)
        y_row_data = verse_df.row(y - 1)
        # Convert the tuple of data into a dictionary
        verse_x_dict = {
            "X " + col: val for col, val in zip(verse_df.columns, x_row_data)
        }
        verse_y_dict = {
            "Y " + col: val for col, val in zip(verse_df.columns, y_row_data)
        }
        result = {"Coordinates": f"{x}, {y}", **verse_x_dict, **verse_y_dict}
    else:
        result = {
            "error": "Verse ID out of bounds",
            "verse_x_id": x,
            "verse_y_id": y,
        }
    return result


@app.get("/api/verse_selector_data")
async def get_verse_selector_data():
    return app_data["verse_selector_data"]


@app.get("/api/verse_similarity_search/{verse_id}/{n_results}")
@limiter.limit("10/minute")
async def get_verse_similarity_results(
    request: Request, verse_id: int, n_results: int = 10
):
    collection = app_data["chroma_collection"]
    # collection = Collection()
    verse_results = collection.get(
        where={"verse_id": {"$eq": verse_id}},
        include=["embeddings", "documents"],
        limit=1,
    )
    verse_embeddings = verse_results["embeddings"]
    verse_citation = verse_results["ids"][0]
    verse_text = verse_results["documents"][0]

    raw_results = collection.query(
        query_embeddings=verse_embeddings,
        n_results=n_results + 1,
        include=["distances", "metadatas", "documents"],
    )
    results = {
        "citations": raw_results["ids"][0],
        "verse_ids": [x["verse_id"] for x in raw_results["metadatas"][0]],
        "distances": raw_results["distances"][0],
        "texts": raw_results["documents"][0],
    }

    popup_contents = []
    for i in range(1, len(results["citations"])):
        popup_contents.append(
            {
                "Distance": f"{results['distances'][i]:.2f}",
                "Coordinates": f"{str(verse_id)}, {results['verse_ids'][i]}",
                "yCoord": int(verse_id),
                "xCoord": int(results["verse_ids"][i]),
                "X Verse": f"{verse_citation}",
                "X Text": f"{verse_text}",
                "Y Verse": f"{results['citations'][i]}",
                "Y Text": f"{results['texts'][i]}",
            }
        )
    return json.dumps(popup_contents)


@app.get("/")
async def get_index():
    """This is the main page."""
    return FileResponse("frontend/dist/index.html")


@app.get("/favicon.ico")
async def get_favicon():
    """This is the favicon."""
    return FileResponse("frontend/dist/kjv.png")


@app.get("/og.png")
async def get_favicon():
    """This is the opengraph preview image."""
    return FileResponse("frontend/dist/og.png")


@app.get("/changelog")
async def get_changelog():
    """This returns the changelog file."""
    return FileResponse("frontend/dist/changelog.json")
