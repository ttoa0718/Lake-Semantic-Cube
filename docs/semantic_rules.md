# Semantic Rules

Rules are JSON files in `rules/` and are parsed by `src/lake_semantic_cube/semantics/parser.py`.

Implemented fields include:

- `rule_id`
- `rule_version`
- `semantic_type`
- `variables`
- `logic`
- `vertical_constraints`
- `depth_reference`
- `output_attributes`
- `metadata`

Variable conditions support operators implemented by the parser/evaluator: `<`, `<=`, `>`, `>=`, `==`, `between`, and `gradient_abs_gt`. Threshold types include `absolute` and dataset/global `percentile`.

Example from `rules/hypoxia.json`:

```json
{
  "semantic_type": "hypoxia_layer",
  "variables": [{"name": "DOX", "operator": "<", "threshold_type": "absolute", "threshold": 2.0}],
  "vertical_constraints": {"min_continuous_layers": 2, "min_thickness": 1.0}
}
```

Derived outputs include `occurrence`, `z_top`, `z_bottom`, `thickness`, `core_depth`, `segment_count`, `layer_start`, `layer_end`, and `semantic_mask`.
