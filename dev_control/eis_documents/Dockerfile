# Same verified browser runtime; no model or application credentials are added.
ARG BASE_IMAGE=stroyka-eis-documents:reviewed-browser-base
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng antiword unrtf libwmf-bin fonts-urw-base35 \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir openpyxl==3.1.5 defusedxml==0.7.1 libarchive-c==5.3
USER 10001:10001
ENTRYPOINT ["python3"]
