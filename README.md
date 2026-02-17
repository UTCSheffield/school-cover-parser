# School Cover Parser

Takes cover info from SIMS and makes better outputs

Hopefully this goes onto old kindles

https://www.galacticstudios.org/kindle-weather-display/

## Command-line usage

This project now uses a [Typer](https://typer.tiangolo.com/) CLI.

- Run with the default input (Downloads or `test_data/Notice Board Summary.html`):
	- `python main.py`
- Run on a specific HTML file:
	- `python main.py --file path/to/Notice\ Board\ Summary.html`
- Disable sending the Outlook email:
	- `python main.py --no-email`
- Test mode: run against all `.html` files in `test_data` (no email, no renames, no browser popups) and write separate outputs per file:
	- `python main.py --test`

Outputs are written into an `outputs` folder under the directory you run the command from (for example `P:\Documents\outputs`) as `cover_sheet*.html` and `supply_sheet*.html`.

## Installation as a package

You can install this project as a local package and use the CLI directly:

- Install in editable (development) mode from the repo root:
	- `pip install -e .`
- Run via the installed console script:
	- `school-cover-parser --test`
	- `school-cover-parser --file path/to/Notice\ Board\ Summary.html`
- Or run as a module:
	- `python -m school_cover_parser --test`
	- `python -m school_cover_parser --no-email`

The old entry point still works:

- `python main.py ...` (this forwards to the same Typer app under the hood).
