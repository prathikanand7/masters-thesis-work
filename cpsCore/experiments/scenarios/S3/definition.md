# S3 — Multi-component runner orchestration

See `../scenarios.md` for full definition.

## Trace slice

Source file: `../../runtime_traces.txt`  
Filter: `ClientComponent = Synchronization` AND `ServerComponent in [Aggregation, Utilities, Logging]`
AND `ClientFunction in [SimpleRunner.runStage, SimpleRunner.runStages, SynchronizedRunnerMaster.runAllStages]`

Run `../extract_slices.py --scenario S3` to regenerate this file.
