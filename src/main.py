from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import polars as pl

# To start in server in development mode:
#  ./.venv/Scripts/python.exe -m fastapi dev ./src/main.py
# To start server in production mode:
# ./.venv/Scripts/python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000

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
    df = pl.read_csv("static/kjv/kjv.csv")

    # Load the verse details lookup table
    app_data["verse_info"] = df.select(["citation", "text"]).rename(
        {"citation": "Verse"}
    )

    app_data["verse_selector_data"] = {}

    # Get a series of unique book names
    unique_books = df.get_column("book_name").unique(maintain_order=True)

    for book_name in unique_books:
        # Filter the DataFrame for the current book
        book_df = df.filter(pl.col("book_name") == book_name)

        # Find the maximum chapter number for the book
        max_chapter = book_df.get_column("chapter_number").max()

        # Group by chapter to find the max verse in each chapter
        verses_per_chapter_df = book_df.group_by(
            "chapter_number", maintain_order=True
        ).agg(pl.max("verse_number").alias("max_verse"))

        # Convert the result to a dictionary {chapter: max_verse}
        # Polars makes this easy by zipping the two columns.
        # We cast chapter to string to match the desired JSON output format.
        verses_dict = dict(
            zip(
                verses_per_chapter_df.get_column("chapter_number").cast(str),
                verses_per_chapter_df.get_column("max_verse"),
            )
        )

        # Assemble the final structure for this book
        app_data["verse_selector_data"][book_name] = {
            "chapters": max_chapter,
            "verses": verses_dict,
        }

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
app.mount("/static", StaticFiles(directory="static"), name="static")


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


@app.get("/")
async def read_index():
    """This is the main page."""
    return FileResponse("static/pages/index.html")


@app.get("/favicon.ico")
async def read_index():
    """This is the favicon."""
    return FileResponse("static/favicon/kjv.png")
