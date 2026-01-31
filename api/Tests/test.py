import requests
import yaml
from jsonpath_ng import parse


def dtestd():
    res = requests.post(
        url="http://192.168.1.141:8088/rbac/login/login",
        json={
            'code': '',
            'isNew': '1',
            'u': 'auto',
            'p': '123'
        }
    )
    expr = parse("$.success")
    ma = expr.find(res.json())
    value = [m.value for m in ma]
    print(value)

    print(res.json())

if __name__ == "__main__":
    # yaml.safe_load_all()
    dtestd()

