from datetime import datetime
import json
import hashlib, base64
from cryptography.fernet import Fernet

import requests


def send_post_request(username:str,password:str,key:str='fds') -> dict:
    url = 'http://192.168.20.14:8000/api/user'

    today = datetime.now().strftime("%Y-%m-%d")
    accesskey = hashlib.md5(today.encode('utf-8'))
    accesskey.update(key.encode('utf-8'))
    accesskey = accesskey.hexdigest()

    key_32 = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
    cipher_suite = Fernet(key_32)
    encrypted_password = cipher_suite.encrypt(password.encode()).decode()

    header = {
        "x-gw-accesskey": accesskey,
        "Content-Type": "application/json"
    }
    body = {
        "type": 'verify',
        "username": username,
        'password':encrypted_password,
    }
    try:
        res = requests.post(url,headers=header,json=body)
        res = json.loads(res.text)
    except Exception as e:
        res = {'错误':str(e)}
    return res


if __name__=='__main__':
    res = send_post_request('qidongkai','123')
    print(res)
