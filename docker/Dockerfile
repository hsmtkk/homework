FROM python:3.8.5-buster as builder

WORKDIR /usr/local/src

RUN curl -L -O http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
 && tar fxz ta-lib-0.4.0-src.tar.gz

WORKDIR /usr/local/src/ta-lib

RUN ./configure --prefix=/usr/local \
 && make \
 && make install

FROM python:3.8.5-buster

COPY --from=builder /usr/local /usr/local
COPY docker/wait-for-it.sh /opt/wait-for-it.sh

RUN python -m pip install --upgrade pip

COPY AIfx /opt/AIfx

WORKDIR /opt/AIfx

RUN pip install django==3.1 omitempty==0.1.1 mysqlclient==2.0.1 numpy==1.19.1 python-dateutil==2.8.1 oandapyV20==0.6.3 requests==2.24.0

# numpy is required to build TA-Lib
RUN pip install TA-Lib==0.4.18

ENV LD_LIBRARY_PATH=/usr/local/lib

EXPOSE 80

ENTRYPOINT ["/opt/wait-for-it.sh", "mysql:3306", "--", "python", "manage.py", "runserver", "0.0.0.0:80"]

