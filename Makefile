PY ?= python
export PYTHONPATH := src

VIZ_PORT ?= 8000

.PHONY: all build validate test fetch clean mcp embed viz viz-serve

all: build validate          ## build the dataset, then validate it

build:                       ## raw inputs -> dist/sinew.sqlite + dist/parquet/
	$(PY) -m sinew.build

validate:                    ## run the P0 validation suite against dist/sinew.sqlite
	$(PY) -m sinew.validate

test:                        ## run the pytest suite
	$(PY) -m pytest -q

fetch:                       ## verify (or --download) raw inputs against sources.lock.json
	$(PY) -m sinew.fetch

mcp:                         ## run the read-only MCP server over dist/sinew.sqlite (needs `.[mcp]`)
	$(PY) -m sinew.mcp.server

embed:                       ## build the Tier-3 meaning layer -> meaning.json + derived_* (needs `.[embed]`; run after build)
	$(PY) -m sinew.embed

viz:                         ## export the telescope views -> dist/viz/ (open index.html for the hero terrain)
	$(PY) -m sinew.export_viz

viz-serve: viz               ## serve dist/viz/ so drill-down (fetch) works: http://localhost:$(VIZ_PORT)
	cd dist/viz && $(PY) -m http.server $(VIZ_PORT)

clean:                       ## remove build outputs
	rm -rf dist
