from tqdm import tqdm
import polars as pl
import chromadb
import duckdb
import numpy as np
import sys
import os
import psutil
import gc

client = chromadb.PersistentClient(r"C:\repos\KJV_Search_Tools\.chroma")
collection = client.get_or_create_collection("kjv_verses")
connection = duckdb.connect(r"C:\repos\KJV_Search_Tools\data\kjv.duckdb")


def create_results_table():
    connection.execute(  # [-128, 128] for color. don't need high precision
        """CREATE OR REPLACE TABLE raw (
        verse_1_int SMALLINT,
        verse_2_int SMALLINT,
        distance TINYINT,
        PRIMARY KEY(verse_1_int, verse_2_int)
    );"""  # TODO: Add order by for better compression
    )


def read_kjv_df(csv_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.csv"):
    kjv = pl.read_csv(csv_path)
    return kjv


def write_kjv_df(
    kjv: pl.DataFrame, csv_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.csv"
):
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


# # kjv.write_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")

# # kjv = pl.read_csv(r"C:\repos\KJV_Search_Tools\data\kjv.csv")


def upload_kjv_to_chromadb(kjv: pl.DataFrame):
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

    This is a lossy conversion designed to save memory.

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


def export_raw_to_parquet(
    output_path: str = r"C:\repos\KJV_Search_Tools\data\kjv.parquet",
):
    """
    Exports the 'raw' table to a ZSTD compressed Parquet file.
    """
    print(f"Exporting 'raw' table to {output_path}...")
    connection.execute(
        f"COPY raw TO '{output_path}' (FORMAT 'parquet', COMPRESSION 'zstd');"
    )
    print("Export complete.")
