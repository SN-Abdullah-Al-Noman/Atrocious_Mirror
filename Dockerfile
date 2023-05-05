FROM noman12/atrociousmirror:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apt -qq update --fix-missing && \
    apt -qq install -y mediainfo

RUN apt-get -y clean
RUN apt-get -y autoremove

COPY . .

# Add EXPOSE 80 if you want to deploy this repo on back4app

CMD ["bash", "start.sh"]

