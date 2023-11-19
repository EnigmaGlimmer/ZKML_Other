FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

WORKDIR /srv
COPY . ./

#install solc
# update bins
RUN apt-get update && apt-get -y install build-essential curl git \
libexpat1-dev libfreetype6-dev

#add rust
RUN curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# add svm
RUN rustup override set nightly && cargo install svm-rs
# install solc
RUN svm install 0.8.20


# Install production dependencies.
RUN pip install -r requirements.txt
RUN pip install numpy
RUN pip install ezkl

RUN pip install onnx onnxruntime

CMD python main.py
#CMD [ "bash" ]