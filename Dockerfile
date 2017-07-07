FROM neurodebian:wheezy

# Add dcm2niix and lbgdcm (taken from scitran dcm2niix dockerfile)
RUN apt-get update -qq \
    && apt-get install -y \
    dcm2niix \
    libgdcm-tools \
    curl \
    unzip \
    pigz \
    bzip2 \
    gzip \
    wget

# Install and setup miniconda (taken from mriqc Dockerfile)
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.3.11-Linux-x86_64.sh && \
    bash Miniconda3-4.3.11-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.3.11-Linux-x86_64.sh

ENV PATH=/usr/local/miniconda/bin:$PATH \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

COPY . /root/src/fmrif_tools
RUN cd /root/src/fmrif_tools && \
    pip install -r requirements.txt && \
    pip install . && \
    rm -rf ~/.cache/pip

ENTRYPOINT["/usr/local/miniconda/bin/oxy2bids"]
