# Scientific Decisions Required

The software interfaces support the manuscript method, but the following scientific parameters need author confirmation before final publication use.

1. EFDC vertical layer definition

The formal code supports explicit depth edges, sigma edges, and uniform relative layers. The current example configuration uses sigma-style edges. The true Changtan EFDC vertical layer definition should be confirmed from the model setup files before producing publication semantic products.

2. Layer order

The formal code allows `surface_to_bottom` and `bottom_to_surface`. The manuscript and generated metadata should state the confirmed EFDC order.

3. Water depth or bathymetry source

Dynamic bathymetry is supported through a `water_depth(y,x)` grid. The authoritative Changtan bathymetry source should be selected and recorded.

4. Percentile reference scope

The first implementation supports dataset/global percentile thresholds. If the manuscript requires time-window or region-specific percentile thresholds, those scopes should be specified.

5. ODC semantic product registration policy

The package generates deterministic semantic metadata. The final PostgreSQL-backed product names and indexing workflow should be confirmed before inserting semantic products into the shared ODC database.
