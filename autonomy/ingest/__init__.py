"""External data-intake adapters for the autonomy loop.

Each submodule is a keyless, read-only, fail-closed fetcher that turns a public
feed into typed, point-in-time evidence. Intake never trades; it only produces
observations and (optionally) challenger signals that a settlement-backed
promotion review can later admit to the execution ensemble.
"""
