# Legacy experiment scripts

These files are preserved from the AutoDL experiment snapshot for traceability. They are not the recommended public evaluation pipeline.

Important limitations:

- `preprocess.py` creates overlapping windows before a random sample split.
- normalization statistics are calculated before the split;
- the same source recording can appear in train and test;
- the test split is inspected every epoch;
- the old 100% CNN accuracy must not be presented as cross-condition generalization.

P1 should replace this folder with group-based cross-condition evaluation before new bearing metrics are placed in the main README or resume.

