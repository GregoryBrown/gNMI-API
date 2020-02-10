# gNMI-API
Simple API for connecting to an gNMI network device and upload to an Elasticsearch Database

## Requirements
* Python3.6+
* Elasticsearch TSDB running 7.x+ (If you want to upload to ES)
* Ability to do pip install

## Installing in a virutal environment

```python
lab@web-ott-execution-server-1:~/test$ python3.7 -m venv venv
lab@web-ott-execution-server-1:~/test$ source venv/bin/activate
(venv) lab@web-ott-execution-server-1:~/test$
```

Clone from Github

```python
(venv) lab@web-ott-execution-server-1:~/test$ git clone https://github.com/GregoryBrown/gNMI-API.git
Cloning into 'gNMI-API'...
remote: Enumerating objects: 113, done.
remote: Counting objects: 100% (113/113), done.
remote: Compressing objects: 100% (87/87), done.
remote: Total 113 (delta 62), reused 72 (delta 26), pack-reused 0
Receiving objects: 100% (113/113), 56.03 KiB | 6.23 MiB/s, done.
Resolving deltas: 100% (62/62), done.
(venv) lab@web-ott-execution-server-1:~/test$
```

Install the required packages

```python
(venv) lab@web-ott-execution-server-1:~/test/gNMI-API$ pip install -r requirements.txt 
Collecting alabaster==0.7.12 (from -r requirements.txt (line 1))
[SNIP]
````



