# Rewrite regression tests

`rewrite-corpus/` holds fixed AI-style drafts. Use them to check that a change to `SKILL.md` did not make rewrites worse.

A file named `<name>.context.md` is the conversation around `<name>.md`. Give it to the rewriter as background; it is not a draft.

1. Rewrite every draft twice with the current skill and twice with the changed skill. Use the same agent and model each time. Save each run in its own folder, such as `out/old-run1/`.
2. Score the runs:

   ```bash
   python3 scripts/run_corpus.py tests/rewrite-corpus out/old-run1 out/old-run2 out/new-run1 out/new-run2
   ```

3. The change passes when the new runs' total is no higher than the old runs', every new rewrite passes, and a read of a few old/new pairs shows the new ones are at least as good. Read `pr-reply` and `slack-reply` by hand for §26: the reply must lead with the decision.

Scores vary between runs, so compare run totals, not single files.
