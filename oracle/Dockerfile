# The differential-test oracle: the NeMo r1.2.0 pynini grammars behind the Python wrapper the port reproduces.
# pynini only ships x86_64 manylinux wheels, so the image is linux/amd64 (Rosetta/QEMU on Apple silicon).
#
#   docker build --platform linux/amd64 -f oracle/Dockerfile -t zyphra-textnorm-oracle .
#   docker run --rm -v "$PWD":/repo -w /repo zyphra-textnorm-oracle python oracle/dump_golden.py --all
FROM --platform=linux/amd64 python:3.12-slim

RUN pip install --no-cache-dir pynini==2.1.6 sacremoses==0.1.1 regex==2025.11.3 joblib tqdm

COPY oracle/nemo_text_processing /oracle/nemo_text_processing
COPY oracle/*.py /oracle/
ENV PYTHONPATH=/oracle
WORKDIR /oracle
