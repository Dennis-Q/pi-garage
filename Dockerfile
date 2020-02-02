# For raspberry pi zero we need to specify architecture, otherwise you can use the general alpine
FROM arm32v6/alpine
#FROM alpine
ENV LANG C.UTF-8


# Install requirements for add-on
RUN apk add --no-cache python3 \
    && pip3 install --upgrade pip

RUN set -xe \
    && apk add --no-cache -Uu --virtual .build-dependencies python3-dev libffi-dev openssl-dev build-base musl \
    && pip3 install --no-cache --upgrade pyserial RPi.GPIO \
    && apk del --purge .build-dependencies \
    && apk add --no-cache --purge curl ca-certificates musl wiringpi \
    && rm -rf /var/cache/apk/* /tmp/*



RUN apk add --no-cache --virtual .build-deps \
        gcc \
        g++ \
        python3-dev \
    && pip3 install requests ephem configparser paho-mqtt \
    && apk del .build-deps

# required for pigpio module in Python..
RUN apk add --no-cache --virtual .build-deps \
        gcc \
        make \
        musl-dev \
        tar \
  && wget -O /tmp/pigpio.tar abyz.me.uk/rpi/pigpio/pigpio.tar \
  && tar -xf /tmp/pigpio.tar -C /tmp \
  && sed -i "/ldconfig/d" /tmp/PIGPIO/Makefile \
  && make -C /tmp/PIGPIO \
  && make -C /tmp/PIGPIO install \
  && rm -rf /tmp/PIGPIO /tmp/pigpio.tar \
  && apk del .build-deps

ADD app /app/app
WORKDIR /app/data
## change default location of log file to location inside docker
RUN sed -i -e 's:/home/pi/pi-garage/data/:/app/data/:g' /app/app/defaultConfig.conf 
RUN sed -i -e 's/pi\ =\ pigpio\.pi()/pi\ =\ pigpio\.pi("172.18.0.1")/g' /app/app/operateGarage.py \
    && sed -i -e 's/if\ sys\.version_info\[0\]\ <\ 3\:/return\ True\ # no need to start pigpiod inside docker, connecting to host instead!\n\ \ \ \ \ \ \ if\ sys\.version_info\[0\]\ <\ 3\:/g' /app/app/operateGarage.py

# set timezone
RUN apk add --no-cache tzdata
ENV TZ=Europe/Amsterdam
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
