# Contributing to E-POS

## Running the tests
All the load-bearing math has unit tests. Run them with:

```
python -m pytest -q
```

Keep them green before committing.

## Where things live
- `logic/` — pure math (ESL, Classic POS, the Bayesian DFI engine, volumetrics).
  No Streamlit imports; fully unit-tested.
- `components/` and `components/tabs/` — the Streamlit UI.
- `methods/` — reference tables and Classic POS rendering.
- `data/` — a synthetic example model and **placeholder** calibration only. No
  proprietary data ships in this repository.

## Two gotchas worth knowing
1. **Streamlit widget state.** Do not combine `value=` and `key=` on the same
   widget; on a rerun the input can snap back to the default and lose the user's
   entry. Seed the default once with `st.session_state.setdefault(key, default)`
   and pass only `key=` to the widget.
2. **Stale dev server.** Streamlit caches imported modules. After editing code,
   fully stop and restart the dev server before judging behaviour; a stale
   server has more than once produced a confusing "the fix didn't work" report.

## Defaults
DFI input defaults live once in `logic/dfi_inputs.py`. Import those constants
rather than re-typing the numbers in widgets, so a default only ever changes in
one place.
