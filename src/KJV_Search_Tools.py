import chromadb
import polars as pl
import streamlit as st
from src import *


def get_session_state():
    if "verses_count" not in st.session_state:
        st.session_state.verses_count = verses_collection.count()
    if "kjv" not in st.session_state:
        st.session_state.kjv = pl.read_csv(
            r"C:\repos\KJV_Search_Tools\data\bible_data_set.csv"
        )


def main():
    get_session_state()
    st.dataframe(st.session_state.kjv)
    st.markdown(f"""Total verses in database: {st.session_state.verses_count}""")


if __name__ == "__main__":
    main()
