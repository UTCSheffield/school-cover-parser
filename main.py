"""
Script to convert SIMS Notice Board Summary to a nicer output
"""
import os
from pathlib import Path
import webbrowser
import re
import getpass

import arrow
import typer
from bs4 import BeautifulSoup
import pandas as pd
from win32com import client
# from playwright.sync_api import sync_playwright
"""Compatibility wrapper so existing workflows can still run main.py.

The real implementation now lives in the school_cover_parser package.
"""

from school_cover_parser.cli import app


if __name__ == "__main__":  # pragma: no cover
    app()
DATA_FILENAME = "Notice Board Summary.html"
