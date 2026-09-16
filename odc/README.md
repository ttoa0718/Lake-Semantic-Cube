# Open Data Cube Materials

This directory contains public-release ODC examples. They are sanitized and use relative or placeholder locations.

Generate real metadata from the project root:

```bash
python -m lake_semantic_cube index-odc --output-dir odc_output
```

Register products and datasets in an initialized ODC database:

```bash
datacube product add odc/products/changtan_efdc_hourtif_real.product.yaml
datacube product add odc/products/changtan_base_zarr_real.product.yaml
datacube product add odc/products/changtan_vertical_semantic_real.product.yaml
datacube product add odc/products/changtan_s2_fai_sample.product.yaml
datacube dataset add odc/datasets/changtan_vertical_semantic_real_hypoxia_layer.example.odc-metadata.yaml
datacube dataset add odc/datasets/changtan_s2_fai_sample_20251103.odc-metadata.yaml
datacube product list
datacube dataset search product=changtan_vertical_semantic_real
datacube dataset search product=changtan_s2_fai_sample
```

Before indexing real data, regenerate dataset metadata on the target computer so `location` fields point to valid local or object-store URIs.
