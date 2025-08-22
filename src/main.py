from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.helpers import pixel_info

app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/static/tiles", StaticFiles(directory="static/tiles"), name="tiles")


@app.get("/api/pixel_info/{x}/{y}")
def get_pixel_info(x: int, y: int):
    return pixel_info(x, y)


@app.get("/")
async def read_index():
    return FileResponse("index.html")
