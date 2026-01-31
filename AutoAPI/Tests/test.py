import requests
import yaml
from jsonpath_ng import parse


def dtestd():
    res = requests.post(
        url="https://ug.baidu.com/mcp/pc/pcsearch",
        json={"invoke_info":{"pos_1":[{}],"pos_2":[{}],"pos_3":[{}]}}
    )
    expr = parse("$.errmsg")
    ma = expr.find(res.json())
    value = [m.value for m in ma]
    print(value)

    print(res.json())

if __name__ == "__main__":
    # yaml.safe_load_all()
    dtestd()

