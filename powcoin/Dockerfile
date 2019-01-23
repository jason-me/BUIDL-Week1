FROM python:3.7.0
ADD requirements.txt ./
RUN pip install -r requirements.txt
ADD mypowcoin.py ./
ADD utils.py ./
ADD identities.py ./


CMD ["python", "-u", "mypowcoin.py", "serve"]
