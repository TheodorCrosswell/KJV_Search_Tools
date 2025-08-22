"""This module contains the code for creating the tiles.

How I made the tiles:
- Insert (Encode) KJV Bible verses into ChromaDB
- Compute similarity for every (verse_1, verse_2) pair
- Create tiles from similarity scores
- Upscale / Downscale tiles to fit map component

Please excuse the messy code. I had to reiterate
on my design, and I did not refactor the preceding code."""

from tqdm import tqdm
import polars as pl

# import chromadb
# import duckdb
import numpy as np
import sys
import os
import psutil
import gc
import time
from pathlib import Path
from PIL import Image
import numpy as np
import glob
import re
import shutil


# client = chromadb.PersistentClient(r"C:\repos\KJV_Search_Tools\.chroma")
# collection = client.get_or_create_collection("kjv_verses")
# connection = duckdb.connect(r"C:\repos\KJV_Search_Tools\data\kjv.duckdb")


class DataReader:
    """
    A dedicated reader for accessing slices from a large Feather file.

    This class provides a clean interface to read chunks of data without
    loading the entire file into memory, encapsulating the underlying
    storage and query mechanism.
    """

    def __init__(self, file_path: str | Path):
        """
        Initializes the DataReader with the path to the data file.

        Args:
            file_path: The path to the uncompressed Feather file.

        Raises:
            FileNotFoundError: If the file does not exist at the given path.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Data file not found at: {self.file_path}")

    def get_slice(self, start_row: int, num_rows: int) -> np.ndarray:
        """
        Reads a specific slice of rows from the Feather file.

        This method uses a lazy scan to ensure only the requested part of
        the file is loaded into memory.

        Args:
            start_row: The starting row index for the slice.
            num_rows: The number of rows to include in the slice.

        Returns:
            A NumPy array containing the requested data slice.
            The shape of the array will be (num_rows, num_columns).
        """
        try:
            # The core logic: lazy scan, slice, collect, and convert
            data_chunk_df = (
                pl.scan_ipc(self.file_path).slice(start_row, num_rows).collect()
            )

            # Return as a NumPy array for broad compatibility
            return data_chunk_df.to_numpy()

        except Exception as e:
            # Catch potential Polars/Arrow errors for better diagnostics
            print(f"An error occurred while reading the slice from {self.file_path}:")
            # Re-raise the exception to let the caller handle it
            raise e


def create_results_table():
    """Creates the table that will store the results from comparing all verses to each other"""
    connection.execute(  # [-128, 128] for color. don't need high precision
        """CREATE OR REPLACE TABLE raw (
        verse_1_int SMALLINT,
        verse_2_int SMALLINT,
        distance TINYINT,
        PRIMARY KEY(verse_1_int, verse_2_int)
    );"""  # TODO: Add order by for better compression
    )


def read_kjv_df(csv_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.csv"):
    """Reads kjv.csv as a Polars dataframe."""
    kjv = pl.read_csv(csv_path)
    return kjv


def write_kjv_df(
    kjv: pl.DataFrame, csv_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.csv"
):
    """Saves df_kjv as kjv.csv"""
    kjv.write_csv(csv_path)


def create_kjv_df(
    csv_path: str = r"C:\repos\KJV_Search_Tools\data\bible_data_set.csv",
):
    """
    This generates an enriched and reformatted dataframe from the data source (bible_data_set.csv)

    Assumptions:
    - The csv file has all the verses ordered from Genesis -> Revelation, chapter asc, verse asc.
    """
    kjv = pl.read_csv(csv_path)  # TODO: better path
    kjv = kjv.with_columns(
        [
            pl.col("text").str.len_chars().alias("length_chars"),
            pl.col("text").str.strip_chars(),
        ]
    ).rename(
        {
            "book": "book_name",
            "chapter": "chapter_number",
            "verse": "verse_number",
        }
    )

    book_num_df = (
        kjv.select(pl.col("book_name"))
        .group_by("book_name", maintain_order=True)
        .agg()
        .with_row_index("book_number")
        .with_columns(pl.col("book_number") + pl.lit(1))
    )

    kjv = (
        kjv.join(book_num_df, pl.col("book_name"))
        .with_row_index("verse_id")
        .with_columns([pl.col("verse_id") + pl.lit(1)])
        .select(
            [
                pl.col("verse_id"),
                pl.col("citation"),
                pl.col("book_name"),
                pl.col("book_number"),
                pl.col("chapter_number"),
                pl.col("verse_number"),
                pl.col("length_chars"),
                pl.col("text"),
            ]
        )
    )

    return kjv


def upload_kjv_to_chromadb(kjv: pl.DataFrame):
    """This insert and encodes each verse in ChromaDB. It uses the default encoder, All-MiniLM-l6-v2."""
    batch_size = 100
    for batch in (slices := tqdm(kjv.iter_slices(batch_size), total=len(kjv) // 100)):
        slices.set_description(f"{batch.item(0,0)}")
        ids = batch.select(pl.col("citation")).to_series().to_list()
        documents = batch.select(pl.col("text")).to_series().to_list()
        metadatas = batch.select(
            [
                pl.col("verse_id"),
                pl.col("book_name"),
                pl.col("book_number"),
                pl.col("chapter_number"),
                pl.col("verse_number"),
                pl.col("length_chars"),
            ]
        ).to_dicts()
        collection.upsert(
            ids, None, metadatas, documents
        )  # temporarily disabled in order to remove risk of overwriting or duplicates
    # 18m 16.5s for all 31102 verses in one go
    # 17m 35.2s for all verses in batches of 100
    print(collection.count())


def scale_distances_to_int8(distances_f64: np.ndarray) -> np.ndarray:
    """
    Scales a NumPy array of f64 distances to the int8 range [-128, 127],
    assuming the input distances are in the theoretical range of [0.0, 4.0].

    This is a lossy conversion designed to save memory and disk space.

    Args:
        distances_f64: A NumPy array of float64 distances (from an L2 space).

    Returns:
        A NumPy array of the same shape with dtype int8.
    """
    # 1. Define the global min/max for the source (f64) and target (int8) ranges.
    SOURCE_MIN = 0.0
    SOURCE_MAX = 4.0

    # Programmatically get the min/max for the int8 data type.
    TARGET_MIN = np.iinfo(np.int8).min  # This is -128
    TARGET_MAX = np.iinfo(np.int8).max  # This is 127

    # 2. Clip the input values to the assumed [0.0, 4.0] range.
    # This is a safety step to handle any values slightly outside the theoretical
    # bounds due to floating-point inaccuracies.
    clipped_distances = np.clip(distances_f64, SOURCE_MIN, SOURCE_MAX)

    # 3. Apply the min-max scaling formula.
    # This formula proportionally maps a value from the source range to the target range.
    # Formula: new = (old - old_min) / (old_range) * (new_range) + new_min
    scaled_distances = (clipped_distances - SOURCE_MIN) / (SOURCE_MAX - SOURCE_MIN) * (
        TARGET_MAX - TARGET_MIN
    ) + TARGET_MIN

    # 4. Round to the nearest whole number and cast to the int8 data type.
    distances_int8 = np.round(scaled_distances).astype(np.int8)

    return distances_int8


# Assume max distance = 4
def get_distances():
    """Computes the distances between every verse and saves them."""
    kjv = (
        pl.read_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")
        #
        .select(
            #
            pl.col("citation"),
            pl.col("verse_id"),
        )
    )

    # Get the current process
    process = psutil.Process(os.getpid())

    verses_count = collection.count()
    batch_size = 100
    for i in (pbar := tqdm(range(0, verses_count, batch_size), total=verses_count)):

        # Get memory information (including RSS)
        memory_info = process.memory_info()
        pbar.set_description(
            f"Memory in use: {memory_info.rss / (1024 * 1024):.2f} MB, Filesize: {sys.getsizeof(r"C:\repos\KJV_Search_Tools\data\kjv.csv")/1073741824:.2f}GB"
        )
        queries = collection.get(
            include=["embeddings"],
            limit=batch_size,
            where={
                "$and": [
                    {"verse_id": {"$gt": i}},
                    {"verse_id": {"$lte": i + batch_size}},
                ]
            },
        )
        results = collection.query(
            include=["distances"],
            query_embeddings=queries["embeddings"],
            n_results=32000,
        )  # TODO: change n_results to 32000
        # need to avoid getting metadatas. instead, do a join to get the verse_id from citation.

        # rows = []
        # for j, verse_1_id in enumerate(queries["ids"]):
        #     verse_2_ids = results["ids"][j]
        #     distances = np.array(results["distances"][j])
        #     distances = scale_distances_to_int8(distances)
        #     for i in range(len(verse_2_ids)):
        #         rows.append(
        #             {
        #                 "verse_1_citation": verse_1_id,
        #                 "verse_2_citation": verse_2_ids[i],
        #                 "distance": distances[i],
        #             }
        #         )
        # df = (
        #     pl.DataFrame(rows)
        #     .with_columns(pl.col("distance").cast(pl.Int8))
        #     .join(
        #         kjv,
        #         how="left",
        #         left_on=pl.col("verse_1_citation"),
        #         right_on=pl.col("citation"),
        #     )
        #     .rename({"verse_id": "verse_1_int"})
        #     .join(
        #         kjv,
        #         how="left",
        #         left_on=pl.col("verse_2_citation"),
        #         right_on=pl.col("citation"),
        #     )
        #     .rename({"verse_id": "verse_2_int"})
        #     .select(
        #         pl.col("verse_1_int").cast(pl.Int16),
        #         pl.col("verse_2_int").cast(pl.Int16),
        #         pl.col("distance"),
        #     )
        # )
        # connection.execute(
        #     """
        #     INSERT INTO raw
        #     SELECT *
        #     FROM df
        #     ON CONFLICT (verse_1_int, verse_2_int) DO NOTHING;
        #     """
        # )

        for j, verse_1_citation in enumerate(queries["ids"]):

            # These are the results for a single source verse (~31k items)
            verse_2_citations = results["ids"][j]
            distances_f64 = np.array(results["distances"][j])
            distances_i8 = scale_distances_to_int8(distances_f64)

            # Efficiently create a DataFrame for this single verse's results.
            # This avoids creating a huge list of dictionaries.
            df = pl.DataFrame(
                {
                    "verse_1_citation": verse_1_citation,
                    "verse_2_citation": verse_2_citations,
                    "distance": distances_i8,
                }
            ).with_columns(pl.col("distance").cast(pl.Int8))

            # Now perform the joins on this much smaller (~31k row) DataFrame
            df = (
                df.join(
                    kjv,
                    how="left",
                    left_on=pl.col("verse_1_citation"),
                    right_on=pl.col("citation"),
                )
                .rename({"verse_id": "verse_1_int"})
                .join(
                    kjv,
                    how="left",
                    left_on=pl.col("verse_2_citation"),
                    right_on=pl.col("citation"),
                )
                .rename({"verse_id": "verse_2_int"})
                .select(
                    pl.col("verse_1_int").cast(pl.Int16),
                    pl.col("verse_2_int").cast(pl.Int16),
                    pl.col("distance"),
                )
            )

            # Insert the results for this single verse into DuckDB
            connection.execute(
                """
                INSERT INTO raw
                SELECT *
                FROM df
                ON CONFLICT (verse_1_int, verse_2_int) DO NOTHING;
                """
            )

            # Explicitly clean up to keep memory usage low and stable
            del df
            del verse_2_citations
            del distances_f64
            del distances_i8
            gc.collect()

        pbar.update(batch_size)


def benchmark_file(file_path: str):
    """Records the completion time to read certain chunks from the file."""
    tests = [
        (50, 2000555),
        (2267, 516),
        (45674, 45784),
        (367733, 26775554),
        (3467368, 247748),
        (25733456, 235632),
        (132456366, 7893),
        (546756843, 25645786),
        (754742225, 45363157),
        (886866432, 4577),
    ]
    total_time = 0
    for i in range(len(tests)):
        try:
            total_time -= time.perf_counter()
            df = pl.scan_ipc(file_path).slice(tests[i][0], tests[i][1]).collect()
            total_time += time.perf_counter()
        except Exception as e:
            print("Error while initializing dataframe:")
            raise (e)

    print(
        f"""
            {file_path}: {total_time:.2f} S
        """
    )


def run_benchmark_file():
    """Used to check if compression makes any difference in reading speed. It does. Just go uncompressed."""
    test_files = [
        r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted.feather",
        r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_lz4.feather",
        r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_zstd.feather",
    ]

    for file in test_files:
        benchmark_file(file)


def export_raw_to_parquet(
    output_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.parquet",
):
    """Saves the distances as a .parquet file."""
    """
    Exports the 'raw' table to a ZSTD compressed Parquet file.
    """
    print(f"Exporting 'raw' table to {output_path}...")
    connection.execute(
        f"COPY raw TO '{output_path}' (FORMAT 'parquet', COMPRESSION 'zstd');"
    )
    print("Export complete.")


def generate_256px_image_direct(start_px_x: int, start_px_y: int):
    """Generates a 256x256px image from the raw data. These images will then be used to create all the other layers of tiles."""
    df = pl.read_ipc(
        r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_uint8_jank.feather"
    )

    df_img = pl.DataFrame()
    for i in range(0, 256):
        df_slice = df.slice(start_px_x + (start_px_y * 31102) + (i * 31102), 256)
        try:
            count = df_slice.count()[0, 0]
            assert df_slice.count()[0, 0] == 256
        except AssertionError as e:
            df_padding = (
                pl.DataFrame([255 for n in range(256 - count)])
                .rename({"column_0": "distance"})
                .cast(pl.UInt8)
            )
            df_slice = pl.concat([df_slice, df_padding])
        df_img = pl.concat([df_img, df_slice])
    df_img = df_img.rechunk()

    pixels = df_img.to_numpy().tobytes()
    img = Image.new("L", (256, 256))
    img.frombytes(pixels)

    if start_px_x + 256 > 31102:
        difference = (start_px_x + 256) - 31102
        img_cover = Image.new("L", (difference, 256), 255)
        img.paste(img_cover, (256 - difference, 0))

    return img


def generate_images_from_mmap():
    """Orchestrates generating all the initial zoom level 7 native resolution tiles."""
    image_shape = (31102, 31102)
    tile_shape = (256, 256)

    # TODO: This should be computed for a dynamic image size.
    # In this case, I hardcoded it because the image is always 31102 x 31102.
    # 31102 / 256 ~= 121. So a 122 x 122 grid of 256 x 256 images will cover it.
    # 128 = 2^7, so we need 7 zoom levels

    # Image file storage:
    #   File naming convention: f"{start_px_y}.png"
    #   File path convention: f"{zoom_level}/{start_px_x}"
    # create zoom level 0 from the raw data,
    # then create higher zoom level based on previous zoom level to save compute power.

    generate_images_list = []
    zoom_level = 7
    start_px_x = [x for x in range(0, 31102, 256)]
    start_px_y = [x for x in range(0, 31102, 256)]

    for x in (pbar := tqdm(start_px_x, total=122 * 122)):
        for y in start_px_y:
            images_path = r"C:\repos\KJV_Search_Tools\static/tiles"
            image_name_pattern = "{start_px_y}.png"
            image_path_pattern = "{zoom_level}/{start_px_x}"

            full_image_path = os.path.join(
                images_path,
                image_path_pattern.format_map(
                    {
                        "zoom_level": zoom_level,
                        "start_px_x": x,
                    }
                ),
                image_name_pattern.format_map(
                    {
                        "start_px_y": y,
                    }
                ),
            )

            directory = os.path.dirname(full_image_path)

            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            img = generate_256px_image_direct(x, y)
            img.save(full_image_path)
            pbar.update(1)


def test_resampling_methods():
    """Showcases which resampling method is best.
    I settled on Lanczos."""
    methods_to_try = [
        Image.Resampling.BICUBIC,
        Image.Resampling.BILINEAR,
        Image.Resampling.BOX,
        Image.Resampling.HAMMING,
        Image.Resampling.LANCZOS,
        Image.Resampling.NEAREST,
    ]

    source_images = [
        Image.open(r"C:\repos\KJV_Search_Tools\img\0_256\0\0\0_256_0_0.png"),
        Image.open(r"C:\repos\KJV_Search_Tools\img\0_256\256\0\0_256_256_0.png"),
        Image.open(r"C:\repos\KJV_Search_Tools\img\0_256\0\256\0_256_0_256.png"),
        Image.open(r"C:\repos\KJV_Search_Tools\img\0_256\256\256\0_256_256_256.png"),
    ]

    for i, method in enumerate(methods_to_try):
        downsampled_img = Image.new("L", (256, 256))
        downsampled_img.paste(source_images[0].resize((128, 128), method), (0, 0))
        downsampled_img.paste(source_images[1].resize((128, 128), method), (128, 0))
        downsampled_img.paste(source_images[2].resize((128, 128), method), (0, 128))
        downsampled_img.paste(source_images[3].resize((128, 128), method), (128, 128))
        downsampled_img.save(r"C:/repos/KJV_Search_Tools/img/test/" + f"{i}" + ".png")

    # I choose BOX method.


def downsize_images(four_images: list[Image.Image]) -> Image.Image:
    """Downsamples and combines 4 256x256px tiles into a lower detail 256x256 tile.
    Image order:
    - Left, Top,
    - Right, Top,
    - Left, Bottom,
    - Right, Bottom.
    """
    assert len(four_images) == 4

    downsampled_img = Image.new("L", (256, 256))
    downsampled_img.paste(
        four_images[0].resize((128, 128), Image.Resampling.LANCZOS), (0, 0)
    )
    downsampled_img.paste(
        four_images[1].resize((128, 128), Image.Resampling.LANCZOS), (128, 0)
    )
    downsampled_img.paste(
        four_images[2].resize((128, 128), Image.Resampling.LANCZOS), (0, 128)
    )
    downsampled_img.paste(
        four_images[3].resize((128, 128), Image.Resampling.LANCZOS), (128, 128)
    )
    return downsampled_img


def get_source_images_for_this_tile(
    zoom_level: int, start_px_x: int, start_px_y: int
) -> list[Image.Image]:
    """Gets the PIL.Image.Images to downsample for the given tile parameters."""
    sizes_map = {
        0: 32768,
        1: 16384,
        2: 8192,
        3: 4096,
        4: 2048,
        5: 1024,
        6: 512,
        7: 256,
    }

    source_zoom_level = zoom_level + 1
    source_size = sizes_map[source_zoom_level]
    coords = [
        [start_px_x, start_px_y],
        [start_px_x + source_size, start_px_y],
        [start_px_x, start_px_y + source_size],
        [start_px_x + source_size, start_px_y + source_size],
    ]

    image_paths = [
        image_name_and_folder_handler(
            source_zoom_level,
            coords[0][0],
            coords[0][1],
        ),
        image_name_and_folder_handler(
            source_zoom_level,
            coords[1][0],
            coords[1][1],
        ),
        image_name_and_folder_handler(
            source_zoom_level,
            coords[2][0],
            coords[2][1],
        ),
        image_name_and_folder_handler(
            source_zoom_level,
            coords[3][0],
            coords[3][1],
        ),
    ]

    images = []
    for image_path in image_paths:
        if not os.path.exists(
            image_path
        ):  # and source_zoom_level != 7: # I don't understand this caveat. It was important but I can't remember why. Oh, I think maybe it was when i was generating the full resolution image.
            img = Image.new("L", (256, 256), 255)
        else:
            img = Image.open(image_path)
        images.append(img)

    assert len(images) == 4
    return images


# TODO: file structure was changed, need to update other functions.
# def image_name_and_folder_handler(
#     zoom_level: int, start_px_x: int, start_px_y: int
# ) -> str:
#     # TODO: update with new leaflet-style naming convention
#     """"""
#     images_path = r"C:\repos\KJV_Search_Tools\static/tiles"
#     image_path_pattern = "{zoom_level}/{start_px_x}"
#     image_name_pattern = "{start_px_y}.png"

#     full_image_path = os.path.join(
#         images_path,
#         image_path_pattern.format_map(
#             {
#                 "zoom_level": zoom_level,
#                 "start_px_x": start_px_x,
#             }
#         ),
#         image_name_pattern.format_map(
#             {
#                 "start_px_y": start_px_y,
#             }
#         ),
#     )

#     directory = os.path.dirname(full_image_path)

#     if not os.path.exists(directory):
#         os.makedirs(directory, exist_ok=True)
#     return full_image_path


def generate_images_zoom():
    """Orchestrates taking all the images and downsizing them until
    it reaches a 256x256px tile that encompasses
    the entire 31102x31102 original image."""
    image_shape = (31102, 31102)
    tile_shape = (256, 256)
    zoom_levels = list(range(0, 7))[::-1]  # [6, 5, 4, 3, 2, 1, 0]

    sizes_map = {
        0: 32768,
        1: 16384,
        2: 8192,
        3: 4096,
        4: 2048,
        5: 1024,
        6: 512,
        7: 256,
    }

    for zoom_level in zoom_levels:
        tile_repr = sizes_map[zoom_level]
        start_px_x = [x for x in range(0, 31102, tile_repr)]
        start_px_y = [x for x in range(0, 31102, tile_repr)]

        for x in (pbar := tqdm(start_px_x, total=len(start_px_x) * len(start_px_y))):
            for y in start_px_y:
                image_path = image_name_and_folder_handler(zoom_level, x, y)
                source_images = get_source_images_for_this_tile(zoom_level, x, y)
                output_image = downsize_images(source_images)
                output_image.save(image_path)
                pbar.update(1)


def pixel_info(x: int, y: int):
    """Can be used to get metadata for 2 verse_id s"""
    distance = (
        pl.scan_ipc(
            r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_uint8_jank.feather"
        )
        .slice(x + y * 31102, 1)
        .collect()
        .to_dicts()
    )[0]["distance"]
    verse_x_info = (
        pl.scan_ipc(r"C:\repos\KJV_Search_Tools\data\kjv.feather")
        .filter(pl.col("verse_id").eq(x))
        .collect()
        .to_dicts()
    )[0]
    verse_y_info = (
        pl.scan_ipc(r"C:\repos\KJV_Search_Tools\data\kjv.feather")
        .filter(pl.col("verse_id").eq(y))
        .collect()
        .to_dicts()
    )[0]
    return {
        "verse_x_info": verse_x_info,
        "verse_y_info": verse_y_info,
        "distance": distance,
    }


def get_full_resolution_image():
    """Creates a full 31102x31102px image, representing everything."""
    full_img = Image.new("L", (31102, 31102))
    df_images_list = pl.DataFrame(
        glob.glob(r"C:/repos/KJV_Search_Tools/img/lanczos/0_256/*/*/*.png")
    )
    assert df_images_list.count().to_dicts()[0]["column_0"] == 14884
    df_images_list = (
        df_images_list.rename({"column_0": "raw_path"})
        .with_columns(
            pl.col("raw_path")
            .str.extract_groups(
                r"C:/repos/KJV_Search_Tools/img/lanczos/0_256\\(\d+)\\(\d+)\\.*.png"
            )
            .alias("captures")
        )
        .unnest("captures")
        .rename({"1": "x", "2": "y"})
        .with_columns([pl.col("x").cast(int), pl.col("y").cast(int)])
    )
    for raw_path, x, y in tqdm(df_images_list.iter_rows(), total=14884):
        small_img = Image.open(raw_path)
        full_img.paste(small_img, (x, y))
    full_img.save(r"C:\repos\KJV_Search_Tools\img\test\full_resolution.png")


def run_retrieval_benchmark():
    """Used to check what retrieval method is quickest.

    Conclusion: scan_ipc is ridiculously slow when collecting in a loop.
    It's amost certainly better to just load the whole dataset into memory."""
    df_benchmark = pl.DataFrame(
        {"benchmark": "blank", "effective time": 0.0, "count": 0}
    )

    def df_memory_cold_retrieval():
        print(
            "Retrieval from Dataframe using read_ipc(), including read time (31102 slices x 31102 rows):"
        )
        # Preparation, such as loading the file into memory for warm runs.
        start_time = time.perf_counter()
        # Measured portion
        df_distance = pl.read_ipc(
            r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted.feather"
        )
        df_metadata = pl.read_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")
        count = 0
        for slice in tqdm(df_distance.iter_slices(31102)):
            slice = slice.with_row_index("verse_id", 1).join(df_metadata, "verse_id")
            count += slice.count().to_dicts()[0]["citation"]
        end_time = time.perf_counter()
        # Cleanup and logging results
        time_elapsed = end_time - start_time
        print(f"Time elapsed: {time_elapsed:.2f}s")
        df_time = pl.DataFrame(
            {
                "benchmark": df_memory_cold_retrieval.__name__,
                "effective time": time_elapsed,
                "count": count,
            }
        )
        df_benchmark.vstack(df_time, in_place=True)

    def df_memory_warm_retrieval():
        print(
            "Retrieval from Dataframe using read_ipc(), excluding read time (31102 slices x 31102 rows):"
        )
        # Preparation, such as loading the file into memory for warm runs.
        df_distance = pl.read_ipc(
            r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted.feather"
        )
        df_metadata = pl.read_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")
        start_time = time.perf_counter()
        # Measured portion
        count = 0
        for slice in tqdm(df_distance.iter_slices(31102)):
            slice = slice.with_row_index("verse_id", 1).join(df_metadata, "verse_id")
            count += slice.count().to_dicts()[0]["citation"]
        end_time = time.perf_counter()
        # Cleanup and logging results
        time_elapsed = end_time - start_time
        print(f"Time elapsed: {time_elapsed:.2f}s")
        df_time = pl.DataFrame(
            {
                "benchmark": df_memory_cold_retrieval.__name__,
                "effective time": time_elapsed,
                "count": count,
            }
        )
        df_benchmark.vstack(df_time, in_place=True)

    def df_disk_retrieval():
        print("Retrieval from Dataframe using scan_ipc() (31102 slices x 31102 rows):")
        # Preparation, such as loading the file into memory for warm runs.
        start_time = time.perf_counter()
        df_distance = pl.scan_ipc(
            r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted.feather"
        )
        df_metadata = pl.scan_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")
        # Measured portion
        count = 0
        # for slice in tqdm(df_distance.slice(count, 31102)):
        pbar = tqdm(total=31102)
        while count < 31102 * 31102:
            slice = df_distance.slice(count, 31102)
            slice = slice.with_row_index("verse_id", 1).join(df_metadata, "verse_id")
            count += slice.count().collect().to_dicts()[0]["citation"]
            pbar.update(1)
        end_time = time.perf_counter()
        # Cleanup and logging results
        time_elapsed = end_time - start_time
        print(f"Time elapsed: {time_elapsed:.2f}s")
        df_time = pl.DataFrame(
            {
                "benchmark": df_memory_cold_retrieval.__name__,
                "effective time": time_elapsed,
                "count": count,
            }
        )
        df_benchmark.vstack(df_time, in_place=True)

    def duckdb_disk_cold_retrieval():
        print(
            "Retrieval from DuckDB on disk, including read time  (31102 slices x 31102 rows):"
        )
        pass

    def duckdb_disk_warm_retrieval():
        print(
            "Retrieval from DuckDB on disk, excluding read time (31102 slices x 31102 rows):"
        )
        pass

    def chromadb_disk_cold_retrieval():
        print(
            "Retrieval from ChromaDB on disk, excluding read time (x slices x 31102 rows):"
        )
        pass

    def chromadb_memory_cold_retrieval():
        print(
            "Retrieval from ChromaDB on disk, excluding read time (x slices x 31102 rows):"
        )
        pass

    def chromadb_memory_warm_retrieval():
        print(
            "Retrieval from ChromaDB on disk, excluding read time (x slices x 31102 rows):"
        )
        pass

    df_memory_cold_retrieval()
    df_memory_warm_retrieval()
    df_disk_retrieval()
    print("Speed comparison:")
    print(df_benchmark)


def janky_tile_rearranging():
    """Literally trash code. I just needed to quickly rearrange
    the file structure, so I made quick modifications and ran it."""

    def downsize_images(four_images: list[Image.Image]) -> Image.Image:
        """Downsamples and combines the images into a lower detail tile.
        Image order:
        - Left, Top,
        - Right, Top,
        - Left, Bottom,
        - Right, Bottom.
        """
        assert len(four_images) == 4

        downsampled_img = Image.new("L", (256, 256))
        downsampled_img.paste(
            four_images[0].resize((128, 128), Image.Resampling.LANCZOS), (0, 0)
        )
        downsampled_img.paste(
            four_images[1].resize((128, 128), Image.Resampling.LANCZOS), (128, 0)
        )
        downsampled_img.paste(
            four_images[2].resize((128, 128), Image.Resampling.LANCZOS), (0, 128)
        )
        downsampled_img.paste(
            four_images[3].resize((128, 128), Image.Resampling.LANCZOS), (128, 128)
        )
        return downsampled_img

    def get_source_images(
        output_zoom_level: int, tile_repr: int, start_px_x: int, start_px_y: int
    ) -> list[Image.Image]:
        sizes_map = {
            0: 256,
            1: 512,
            2: 1024,
            3: 2048,
            4: 4096,
            5: 8192,
            6: 16384,
            7: 32768,
        }

        source_size = sizes_map[output_zoom_level - 1]

        coords = [
            [start_px_x, start_px_y],
            [start_px_x + source_size, start_px_y],
            [start_px_x, start_px_y + source_size],
            [start_px_x + source_size, start_px_y + source_size],
        ]

        image_paths = [
            source_image_name_and_folder_handler(
                output_zoom_level - 1,
                source_size,
                coords[0][0],
                coords[0][1],
            ),
            source_image_name_and_folder_handler(
                output_zoom_level - 1,
                source_size,
                coords[1][0],
                coords[1][1],
            ),
            source_image_name_and_folder_handler(
                output_zoom_level - 1,
                source_size,
                coords[2][0],
                coords[2][1],
            ),
            source_image_name_and_folder_handler(
                output_zoom_level - 1,
                source_size,
                coords[3][0],
                coords[3][1],
            ),
        ]

        images = []
        for image_path in image_paths:
            if not os.path.exists(image_path) and output_zoom_level - 1 != 0:
                img = Image.new("L", (256, 256), 255)
            else:
                img = Image.open(image_path)
            images.append(img)

        assert len(images) == 4
        return images

    def new_image_name_and_folder_handler(
        zoom_level: int, tile_repr: int, start_px_x: int, start_px_y: int
    ) -> str:
        images_path = r"C:\repos\KJV_Search_Tools\static\tiles"
        image_name_pattern = "{start_px_y}.png"
        image_path_pattern = "{zoom_level}/{start_px_x}/"

        full_image_path = os.path.join(
            images_path,
            image_path_pattern.format_map(
                {
                    "zoom_level": 7 - zoom_level,
                    "start_px_x": start_px_x,
                }
            ),
            image_name_pattern.format_map(
                {
                    "start_px_y": start_px_y,
                }
            ),
        )

        directory = os.path.dirname(full_image_path)

        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return full_image_path

    def source_image_name_and_folder_handler(
        zoom_level: int, tile_repr: int, start_px_x: int, start_px_y: int
    ) -> str:
        images_path = r"C:\repos\KJV_Search_Tools\img\lanczos"
        image_name_pattern = "{zoom_level}_{tile_repr}_{start_px_x}_{start_px_y}.png"
        image_path_pattern = "{zoom_level}_{tile_repr}/{start_px_x}/{start_px_y}"

        full_image_path = os.path.join(
            images_path,
            # image_path_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
            # image_name_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
            image_path_pattern.format_map(
                {
                    "zoom_level": zoom_level,
                    "tile_repr": tile_repr,
                    "start_px_x": start_px_x,
                    "start_px_y": start_px_y,
                }
            ),
            image_name_pattern.format_map(
                {
                    "zoom_level": zoom_level,
                    "tile_repr": tile_repr,
                    "start_px_x": start_px_x,
                    "start_px_y": start_px_y,
                }
            ),
        )

        directory = os.path.dirname(full_image_path)

        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return full_image_path

    def generate_images_zoom():

        image_shape = (31102, 31102)
        tile_shape = (256, 256)
        zoom_levels = list(range(1, 8))  # [1, 2, 3, 4, 5, 6, 7]

        generate_images_list = []
        for zoom_level in zoom_levels:
            tile_repr = pow(2, zoom_level) * tile_shape[0]
            start_px_x = [x for x in range(0, image_shape[0], tile_repr)]
            start_px_y = [x for x in range(0, image_shape[0], tile_repr)]
            # end_px_x = [x + tile_repr for x in start_px_x]
            # end_px_y = [x + tile_repr for x in start_px_y]
            generate_images_list.append(
                {
                    "zoom_level": zoom_level,
                    "tile_repr": tile_repr,
                    "start_px_x": start_px_x,
                    "start_px_y": start_px_y,
                }
            )

        for level in zoom_levels:
            # print(generate_images_list[level - 1])
            zoom_level = generate_images_list[level - 2]["zoom_level"]
            tile_repr = generate_images_list[level - 1]["tile_repr"]
            start_px_x = generate_images_list[level - 1]["start_px_x"]
            start_px_y = generate_images_list[level - 1]["start_px_y"]

            for x in (
                pbar := tqdm(start_px_x, total=len(start_px_x) * len(start_px_y))
            ):
                for y in start_px_y:
                    # for x in (pbar := tqdm([0], total=122*122)):
                    #     for y in [0]:
                    pbar.update(1)
                    image_path = new_image_name_and_folder_handler(
                        zoom_level, tile_repr, x, y
                    )
                    source_images = get_source_images(zoom_level, tile_repr, x, y)
                    output_image = downsize_images(source_images)
                    output_image.save(image_path)

    def generate_zoom_0_image(
        zoom_level: int, tile_repr: int, start_px_x: int, start_px_y: int
    ):

        # images_path = r"C:\repos\KJV_Search_Tools\img"
        # image_name_pattern = "{zoom_level}_{tile_repr}_{start_px_x}_{start_px_y}.png"
        # image_path_pattern = "{zoom_level}_{tile_repr}/{start_px_x}/{start_px_y}"

        # full_image_path = os.path.join(
        #     images_path,
        #     # image_path_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
        #     # image_name_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
        #     image_path_pattern.format_map(
        #         {
        #             "zoom_level": zoom_level,
        #             "tile_repr": tile_repr,
        #             "start_px_x": start_px_x,
        #             "start_px_y": start_px_y,
        #         }
        #     ),
        #     image_name_pattern.format_map(
        #         {
        #             "zoom_level": zoom_level,
        #             "tile_repr": tile_repr,
        #             "start_px_x": start_px_x,
        #             "start_px_y": start_px_y,
        #         }
        #     ),
        # )

        # # TODO: handle edge of df. I will set the missing values to 127 (max in df is 30, technical max is 127)
        # # y > 31102 is handled.
        # # x > 31102 is unhandled. TODO
        # directory = os.path.dirname(full_image_path)

        # if not os.path.exists(directory):
        #     os.makedirs(directory, exist_ok=True)

        df = pl.read_ipc(
            r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_uint8_jank.feather"
        )

        df_img = pl.DataFrame()
        for i in range(0, 256):
            # if x_out_of_bound_flag:
            #     number_out_of_bounds = 967_334_404 - (start_px_x + (start_px_y * 31102) + (i * 31102) + 256)
            #     df_slice = pl.concat(
            #         [
            #             df.slice(
            #                 start_px_x + (start_px_y * 31102) + (i * 31102),
            #                 256 - number_out_of_bounds,
            #             ),
            #             pl.DataFrame([255 for n in range(number_out_of_bounds)]),
            #         ]
            #         , rechunk=True
            #     )
            # else:
            #     df_slice = (
            #         df.slice(start_px_x + (start_px_y * 31102) + (i * 31102), 256)
            #     )
            df_slice = df.slice(start_px_x + (start_px_y * 31102) + (i * 31102), 256)
            try:
                count = df_slice.count()[0, 0]
                assert df_slice.count()[0, 0] == 256
            except AssertionError as e:
                df_padding = (
                    pl.DataFrame([255 for n in range(256 - count)])
                    .rename({"column_0": "distance"})
                    .cast(pl.UInt8)
                )
                df_slice = pl.concat([df_slice, df_padding])
            df_img = pl.concat([df_img, df_slice])
        df_img = df_img.rechunk()
        # print(df_img)

        pixels = df_img.to_numpy().tobytes()
        img = Image.new("L", (256, 256))
        img.frombytes(pixels)

        if start_px_x + 256 > 31102:
            difference = (start_px_x + 256) - 31102
            img_cover = Image.new("L", (difference, 256), 255)
            img.paste(img_cover, (256 - difference, 0))

        return img

    # img = Image.new("L", (256, 256))
    # img.frombytes(pixels)
    # img.save(full_image_path)

    def generate_images_from_mmap(ipc_feather_file: str):
        image_shape = (31102, 31102)
        tile_shape = (256, 256)

        # TODO: This should be computed for a dynamic image size.
        # In this case, I hardcoded it because the image is always 31102 x 31102.
        # 31102 / 256 ~= 121. So a 128 x 128 grid of 256 x 256 images will cover it.
        # 128 = 2^7, so we need 7 zoom levels (or 8 = 128 x 128, 9 = 64 x 64, 10 = 32 x 32, (...), 14 = 2 x 2, 15 = 1 x 1)
        final_grid_size = (128, 128)
        zoom_levels = list(range(0, 7))  # [0, 1, 2, 3, 4, 5, 6]

        # Image file storage:
        #   File naming convention: f"{start_px_x}_{start_px_y}_{image_size}"
        #   File path convention: f"{zoom_level}"
        images_path = r"C:\repos\KJV_Search_Tools\static\tiles"
        image_name_pattern = "{start_px_y}.png"
        image_path_pattern = "{zoom_level}/{start_px_x}"

        # create zoom level 0 from the raw data,
        # then create higher zoom level based on previous zoom level to save compute power.

        generate_images_list = []
        for zoom_level in zoom_levels:
            tile_repr = pow(2, zoom_level) * tile_shape[0]
            start_px_x = [x for x in range(0, image_shape[0], tile_repr)]
            start_px_y = [x for x in range(0, image_shape[0], tile_repr)]
            # end_px_x = [x + tile_repr for x in start_px_x]
            # end_px_y = [x + tile_repr for x in start_px_y]
            generate_images_list.append(
                {
                    "zoom_level": zoom_level,
                    "tile_repr": tile_repr,
                    "start_px_x": start_px_x,
                    "start_px_y": start_px_y,
                }
            )

        print(generate_images_list[0])
        zoom_level = 7
        # zoom_level = generate_images_list[0]["zoom_level"]
        tile_repr = generate_images_list[0]["tile_repr"]
        start_px_x = generate_images_list[0]["start_px_x"]
        start_px_y = generate_images_list[0]["start_px_y"]
        for x in (pbar := tqdm(start_px_x, total=122 * 122)):
            for y in start_px_y:
                pbar.update(1)
                # zoom_level = 99
                # for x in [0, 30976]:
                #     for y in [0, 30976]:
                images_path = r"C:\repos\KJV_Search_Tools\static\tiles"
                image_name_pattern = "{start_px_y}.png"
                image_path_pattern = "{zoom_level}/{start_px_x}/"

                full_image_path = os.path.join(
                    images_path,
                    # image_path_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
                    # image_name_pattern.format(zoom_level, tile_repr, start_px_x, start_px_y),
                    image_path_pattern.format_map(
                        {
                            "zoom_level": zoom_level,
                            "tile_repr": tile_repr,
                            "start_px_x": x,
                            "start_px_y": y,
                        }
                    ),
                    image_name_pattern.format_map(
                        {
                            "zoom_level": zoom_level,
                            "tile_repr": tile_repr,
                            "start_px_x": x,
                            "start_px_y": y,
                        }
                    ),
                )

                # TODO: handle edge of df. I will set the missing values to 127 (max in df is 30, technical max is 127)
                # y > 31102 is handled.
                # x > 31102 is unhandled. TODO
                directory = os.path.dirname(full_image_path)

                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)

                img = generate_zoom_0_image(zoom_level, tile_repr, x, y)
                img.save(full_image_path)

        # for zoom_level in zoom_levels:
        #     generate_images_zoom(zoom_level)
        # print("Generated all images.")

        # generate_images_from_mmap("G")

        # # about 30 - 40 images per second, ~6:49 minutes for all images.

    generate_images_zoom()
    generate_images_from_mmap(
        r"C:\repos\KJV_Search_Tools\data\kjv_distance_sorted_uint8_jank.feather"
    )


def copy_rename_tiles():
    """This was used to convert the pixel-based naming scheme to the leaflet-style naming scheme"""

    sizes_map = {
        0: 32768,
        1: 16384,
        2: 8192,
        3: 4096,
        4: 2048,
        5: 1024,
        6: 512,
        7: 256,
    }

    original_files = glob.glob(r"C:\repos\KJV_Search_Tools\static\tiles/*/*/*.png")
    assert len(original_files) == 19907
    pattern = r"static\\tiles\\(?P<zoom>\d+)\\(?P<x>\d+)\\(?P<y>\d+).png"
    new_files = []
    for old_path in original_files:
        new_map = re.search(pattern, old_path).groupdict()
        new_map["x"] = int(new_map["x"])
        new_map["y"] = int(new_map["y"])
        new_map["zoom"] = int(new_map["zoom"])
        new_map["x"] = new_map["x"] // sizes_map[new_map["zoom"]]
        new_map["y"] = new_map["y"] // sizes_map[new_map["zoom"]]
        new_path = f"C:\\repos\\KJV_Search_Tools\\static\\tiles_leaflet\\{new_map["zoom"]}\\{new_map["x"]}\\{new_map["y"]}.png"
        new_files.append(new_path)
    print(f"New paths are like : {new_files[5000]}")
    for i, new_path in enumerate(new_files):
        directory = os.path.dirname(new_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        shutil.copyfile(original_files[i], new_path)
        # break


def upsize_image(source_image: Image.Image) -> list[Image.Image]:
    """Divides an image into 4 with the same resolution,
    allowing for extreme zoom and rendering the individual pixels
    Image order:
    - Left, Top,
    - Right, Top,
    - Left, Bottom,
    - Right, Bottom.
    """

    upsized_images = [
        source_image.resize(
            (256, 256), resample=Image.Resampling.NEAREST, box=(0, 0, 128, 128)
        ),
        source_image.resize(
            (256, 256), resample=Image.Resampling.NEAREST, box=(128, 0, 256, 128)
        ),
        source_image.resize(
            (256, 256), resample=Image.Resampling.NEAREST, box=(0, 128, 128, 256)
        ),
        source_image.resize(
            (256, 256), resample=Image.Resampling.NEAREST, box=(128, 128, 256, 256)
        ),
    ]
    return upsized_images


def create_upsized_images_for_this_tile(zoom: int, x: int, y: int):
    """Divides the given 256x256px tile into 4x 64x64px tiles,
    which are then each upscaled back to 256x256px."""
    source_path = image_name_and_folder_handler(zoom, x, y)
    source_tile = Image.open(source_path)

    output_zoom_level = zoom + 1

    images = upsize_image(source_tile)
    assert len(images) == 4

    image_paths = [
        image_name_and_folder_handler(
            output_zoom_level,
            2 * x,
            2 * y,
        ),
        image_name_and_folder_handler(
            output_zoom_level,
            2 * x + 1,
            2 * y,
        ),
        image_name_and_folder_handler(
            output_zoom_level,
            2 * x,
            2 * y + 1,
        ),
        image_name_and_folder_handler(
            output_zoom_level,
            2 * x + 1,
            2 * y + 1,
        ),
    ]
    images[0].save(image_paths[0])
    images[1].save(image_paths[1])
    images[2].save(image_paths[2])
    images[3].save(image_paths[3])


def image_name_and_folder_handler(zoom: int, x: int, y: int) -> str:
    """Handles making the filepath string and creating needed directories."""
    images_path = r"C:\repos\KJV_Search_Tools\static/tiles"
    image_path_pattern = "{zoom}/{x}/{y}.png"

    full_image_path = os.path.join(
        images_path,
        image_path_pattern.format_map(
            {
                "zoom": zoom,
                "x": x,
                "y": y,
            }
        ),
    )

    directory = os.path.dirname(full_image_path)

    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return full_image_path


def get_zoom_x_y_from_tile_path(tile_path: str):
    """Gets the zoom, x, y values from the tile's storage path."""
    pattern = r"static\\tiles\\(?P<zoom>\d+)\\(?P<x>\d+)\\(?P<y>\d+).png"
    new_map = re.search(pattern, tile_path).groupdict()
    new_map["x"] = int(new_map["x"])
    new_map["y"] = int(new_map["y"])
    new_map["zoom"] = int(new_map["zoom"])
    return new_map


def generate_images_extra_zoom():
    """Generates images that are just upscaled versions
    of quadrants of the original 256x256px tiles"""
    zoom_levels = list(range(8, 10))  # [8, 9]
    for zoom_level in zoom_levels:
        source_zoom_level = zoom_level - 1
        source_tiles = [
            os.path.normpath(path)
            for path in glob.glob(
                f"C:/repos/KJV_Search_Tools/static/tiles/{source_zoom_level}/*/*.png"
            )
        ]
        for source_tile_path in (pbar := tqdm(source_tiles, total=len(source_tiles))):
            zoom_x_y = get_zoom_x_y_from_tile_path(source_tile_path)
            create_upsized_images_for_this_tile(
                zoom_x_y["zoom"],
                zoom_x_y["x"],
                zoom_x_y["y"],
            )
            pbar.update(1)
