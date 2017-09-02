FROM neurodebian:trusty

# Add dcm2niix and lbgdcm (taken from scitran dcm2niix dockerfile)
RUN apt-get update -qq \
    && apt-get install -y \
    git \
    curl \
    build-essential \
    cmake \
    pkg-config \
    libgdcm-tools=2.2.4-1.1ubuntu4 \
    bsdtar \
    unzip \
    pigz \
    gzip \
    wget \
    jq \
    libgl1-mesa-glx

# Compile DCM2NIIX from source (latest commit as of Sept. 1, 2017)
ENV DCMCOMMIT=988d16b7327028d46ed7f45f00cc704254a91446
RUN curl -#L  https://github.com/rordenlab/dcm2niix/archive/$DCMCOMMIT.zip | bsdtar -xf- -C /usr/local
WORKDIR /usr/local/dcm2niix-${DCMCOMMIT}/build
RUN cmake -DUSE_OPENJPEG=ON ../ && \
    make && \
    make install


# Install and setup miniconda (taken from mriqc Dockerfile)
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.3.21-Linux-x86_64.sh && \
    bash Miniconda3-4.3.21-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.3.21-Linux-x86_64.sh

ENV PATH=/usr/local/miniconda/bin:$PATH \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN conda install -y \
          numpy==1.13.1 \
          matplotlib==2.0.2 \
          pandas==0.20.3; \
    sync &&  \
    chmod +x /usr/local/miniconda/bin/* && \
    conda clean --all -y; sync && \
    python -c "from matplotlib import font_manager" && \
    sed -i 's/\(backend *: \).*$/\1Agg/g' $( python -c "import matplotlib; print(matplotlib.matplotlib_fname())" )

WORKDIR /usr/local/src/fmrif_tools
COPY . /usr/local/src/fmrif_tools
RUN cd /usr/local/src/fmrif_tools && \
    pip install -r docker_requirements.txt && \
    pip install . && \
    rm -rf ~/.cache/pip

RUN ldconfig

ENTRYPOINT ["/usr/local/miniconda/bin/oxy2bids"]
