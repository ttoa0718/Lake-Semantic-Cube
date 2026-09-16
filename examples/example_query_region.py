from lake_semantic_cube.cli import run_demo


if __name__ == "__main__":
    summary = run_demo("demo_output")
    print(summary["region_query_csv"])
