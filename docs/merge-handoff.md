# External merge handoff

The autonomous loop deliberately does not merge its own pull requests. A verified PR is handed to an external operator such as Manus using a `READY_TO_MERGE` PR comment containing the exact head SHA and CI run URL. After merge, CI completion wakes the next autonomous cycle.
