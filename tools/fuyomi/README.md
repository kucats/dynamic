# Fuyomi tools

The score-reading engine and correction workflow live in `kucats/vEdit` under `src/vedit/fuyomi`. These small entry points keep the engine in one place while making it convenient to create and publish reading results from this catalog repository.

## Read a score

Install the vEdit Fuyomi extra and make the `vedit` command available on `PATH`. Then pass any Fuyomi subcommand and its arguments through the wrapper:

```sh
python3 tools/fuyomi/score_reading.py init --help
python3 tools/fuyomi/score_reading.py review path/to/reading-workspace
```

The wrapper forwards an argument vector directly to `vedit specialized fuyomi`; it does not invoke a shell or duplicate recognition/correction logic.

## Publish a result

Copy only the intended reading-result HTML and PDF outputs into `public/composers/<composer>/<work>/<part>/`. Do not add the original score PDF, source scans, OMR archive, audio, private workspace, or machine-specific path. Add a catalog item to `public/catalog.json` with its source hash, artifact SHA-256 values, review state, limitations, and project README. The catalog supports a generated HTML guide plus linked interactive HTML artifacts and one PDF per item.

Build and validate the static pages with:

```sh
python3 tools/fuyomi/publish.py build
python3 tools/fuyomi/publish.py validate
```

`publish.py` delegates to the shared standard-library builder and validator under `tools/`.
