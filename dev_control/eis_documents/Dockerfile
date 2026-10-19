# Same verified browser runtime; no model or application credentials are added.
FROM sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng antiword unrtf \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir openpyxl==3.1.5 defusedxml==0.7.1
USER 10001:10001
ENTRYPOINT ["python3"]
