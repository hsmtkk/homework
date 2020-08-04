FROM python:3.8.5-buster

RUN python -m pip install --upgrade pip

COPY AIfx /opt/AIfx

WORKDIR /opt/AIfx

RUN pip install django==3.1 omitempty==0.1.1 mysqlclient==2.0.1 numpy==1.19.1 talib==0.1.1

EXPOSE

ENTRYPOINT

