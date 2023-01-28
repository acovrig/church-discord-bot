FROM python
WORKDIR /src
ENV TIKA_SERVER_JAR="file:///src/tika-server-1.24.jar"
CMD ["python", "main.py"]

# Add jar separately since it's unlikely to change
# and it's rather large
ADD tika-server-1.24.jar /src

RUN apt update \
  && apt install -y \
    libxslt1.1 \
    openjdk-11-jre \
    poppler-utils \
  && apt clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD requirements.txt /src
RUN pip install -r requirements.txt

ADD . /src