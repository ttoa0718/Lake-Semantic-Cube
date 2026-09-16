# Installation

## Conda

```bash
git clone [GITHUB URL TO BE ADDED]
cd Lake-Semantic-Cube/softwarex
conda env create -f environment.yml
conda activate lake-semantic-cube
python -m pip install -e .
```

## Pip

```bash
cd softwarex
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Open Data Cube

ODC is optional for the synthetic demo and required for PostgreSQL-backed catalog discovery. Install and initialize ODC separately, ensure PostgreSQL is available, and place `datacube` on `PATH` or set `DATACUBE_EXE`.

No PostgreSQL password is stored in this repository. Use environment variables or the standard ODC configuration files on the target machine.
