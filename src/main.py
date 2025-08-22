from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.helpers import pixel_info

# New imports
from contextlib import asynccontextmanager
import polars as pl

# 1. A dictionary to hold our loaded dataframes
# This acts as a simple in-memory "database"
app_data = {}


# 2. The lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Code to run on startup ---
    print("Server starting up...")
    # Load the large coordinate-to-verse_id mapping
    # Replace 'your_large_data.feather' with your actual file name
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


# 3. Create the FastAPI app and attach the lifespan event handler
app = FastAPI(lifespan=lifespan)

# app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/static/tiles", StaticFiles(directory="static/tiles"), name="tiles")


@app.get("/api/pixel_info/{x}/{y}")
def get_pixel_info(x: int, y: int):
    verse_df = pl.DataFrame(app_data["verse_info"])

    # Make sure verse_id is a valid index
    if 0 <= x <= len(verse_df) and 0 <= y <= len(verse_df):
        # We use verse_id - 1 because row indexes are 0-based
        # .row() returns a tuple of the values in that row
        x_row_data = verse_df.row(x)
        y_row_data = verse_df.row(y)
        # Convert the tuple of data into a dictionary
        # We get the column names from the dataframe
        verse_x_dict = {
            "X " + col: val for col, val in zip(verse_df.columns, x_row_data)
        }
        verse_y_dict = {
            "Y " + col: val for col, val in zip(verse_df.columns, y_row_data)
        }
    else:
        tooltip = {
            "error": "Verse ID out of bounds",
            "verse_x_id": x,
            "verse_y_id": y,
        }
    result = {"Coordinates": f"{x+1}, {y+1}", **verse_x_dict, **verse_y_dict}
    return result


@app.get("/")
async def read_index():
    return FileResponse("index.html")
