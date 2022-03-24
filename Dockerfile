FROM python
WORKDIR /src
ENV TIKA_SERVER_JAR="file:///src/tika-server-1.24.jar"
CMD ["python", "main.py"]

RUN apt update \
  && apt install -y \
    libxslt1.1 \
    openjdk-11-jre \
  && apt clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD requirements.txt /src
RUN pip install -r requirements.txt

ADD . /src