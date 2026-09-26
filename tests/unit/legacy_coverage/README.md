# Legacy coverage tests

These files fill coverage gaps in the research lanes: the indicator generator, the MLX/Metal
engine, the paper OMS and the visualization helpers. Each test touches several modules, so the
files are grouped by history, not by topic.

The research lanes are frozen (bug fixes only), so these tests stay as a regression net and are
not extended. New tests go into a thematic file named after the module they cover, for example
`tests/unit/test_verify_signing.py`. When you fix a bug in a frozen lane, move the tests you touch
into the matching thematic file.
