"""Document naming: heuristics, LLM prompts and analysis, and filename assembly.

Decides what to ask a model and how to combine its answers with deterministic
heuristics into a filename; :mod:`folionym.llm` owns how the model is reached.
Public callers use :mod:`folionym.filename`.
"""
