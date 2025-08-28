from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import polars as pl

# --- Rate Limiting Imports ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# This acts as a simple in-memory database
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

# --- Add Rate Limiting State and Exception Handler ---
# 2. Set the app's state to include the limiter instance.
app.state.limiter = limiter
# 3. Add the exception handler for when a request goes over the limit.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# keep this mounted so it can serve index.html and tiles and app.js
app.mount("/static", StaticFiles(directory="static"), name="static")
# This one is redundant since /static already covers it.
# app.mount("/static/tiles", StaticFiles(directory="static/tiles"), name="tiles")


@app.get("/api/pixel_info/{x}/{y}")
# 4. Apply the rate limit to this endpoint.
#    We use Depends() to inject the rate limit check.
#    The string "20/minute" means 20 requests are allowed per minute per IP.
@limiter.limit("1/second")
def get_pixel_info(x: int, y: int, request: Request):  # We must add request: Request
    """This is used to get the verse address for the clicked pixel."""
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


@app.get("/")
async def read_index():
    """This is the map."""
    return FileResponse("static/index.html")


@app.get("/favicon.ico")
async def read_index():
    """This is the map."""
    return FileResponse("static/kjv.png")
