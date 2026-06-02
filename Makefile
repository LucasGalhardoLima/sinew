PY ?= python
export PYTHONPATH := src

.PHONY: all build validate test fetch clean

all: build validate          ## build the dataset, then validate it

build:                       ## raw inputs -> dist/sinew.sqlite + dist/parquet/
	$(PY) -m sinew.build

validate:                    ## run the P0 validation suite against dist/sinew.sqlite
	$(PY) -m sinew.validate

test:                        ## run the pytest suite
	$(PY) -m pytest -q

fetch:                       ## verify (or --download) raw inputs against sources.lock.json
	$(PY) -m sinew.fetch

clean:                       ## remove build outputs
	rm -rf dist
