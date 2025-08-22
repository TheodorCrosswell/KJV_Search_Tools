from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import polars as pl

# C:\repos\KJV_Search_Tools\.venv\Scripts\python.exe -m fastapi dev C:\repos\KJV_Search_Tools\src\main.py
# This acts as a simple in-memory database
app_data = {}


# The lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """This loads the kjv.csv file into memory, allowing for fast retrieval of pixel_info"""
    # --- Code to run on startup ---
    # Load the verse details lookup table
    app_data["verse_info"] = (
        pl.read_csv("static/kjv.csv")
        .select(["citation", "text"])
        .rename({"citation": "Verse"})
    )
    print("Data loaded successfully.")

    yield  # The application runs while the lifespan function is yielded

    # --- Code to run on shutdown ---
    print("Server shutting down...")
    app_data.clear()  # Clear the data on shutdown


# Create the FastAPI app and attach the lifespan event handler
app = FastAPI(lifespan=lifespan)

# keep this mounted so it can serve index.html and tiles and app.js
app.mount("/static", StaticFiles(directory="static"), name="static")
# TODO: This is redundant, see above ^^^
app.mount("/static/tiles", StaticFiles(directory="static/tiles"), name="tiles")


@app.get("/api/pixel_info/{x}/{y}")
def get_pixel_info(x: int, y: int):
    """This is used to get the verse address for the clicked pixel."""
    verse_df = pl.DataFrame(app_data["verse_info"])

    # Make sure verse_id is a valid index
    if 0 <= x <= len(verse_df) and 0 <= y <= len(verse_df):
        # .row() returns a tuple of the values in that row
        x_row_data = verse_df.row(x)
        y_row_data = verse_df.row(y)
        # Convert the tuple of data into a dictionary
        verse_x_dict = {
            "X " + col: val for col, val in zip(verse_df.columns, x_row_data)
        }
        verse_y_dict = {
            "Y " + col: val for col, val in zip(verse_df.columns, y_row_data)
        }
        result = {"Coordinates": f"{x+1}, {y+1}", **verse_x_dict, **verse_y_dict}
    else:
        result = {
            "error": "Verse ID out of bounds",
            "verse_x_id": x,
            "verse_y_id": y,
        }
    return result


@app.get("/")
async def read_index():
    """This is the map."""
    return FileResponse("index.html")
