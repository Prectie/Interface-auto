from flask import Flask, request, jsonify
import os

# 创建一个接口  后面会有课讲flask
# 创建了一个名为 app 的 Flask 应用程序对象。
app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload():
    #  只用到 image 参数,我们必须传这个参数
    # 当没有image属性提示用户
    if 'image' not in request.files:
        data = {
            'msg': '当前未填写image参数',
            'code': 400,
        }
        return jsonify(data)

    # 获取到当前图片请求中的文件
    file = request.files['image']

    print(file.filename)

    # # 当image没有传递图片的时候提示用户
    # if file.filename == '':
    #     data = {
    #         'msg': '您未选择对应的图片',
    #         'code': 400,
    #     }
    #     return jsonify(data)

    #  把对应的图片进行保存到当前的目录下的img目录
    save_path = os.path.join('img', file.filename)
    file.save(save_path)

    data = {
        'msg': 'ok',
        'code': 200
    }
    return jsonify(data)#将字典转换为 JSON 响应并返回给客户端


if __name__ == '__main__':
    # app.run()
    app.run(debug=True)#启动 Flask 应用程序，并启用调试模式
