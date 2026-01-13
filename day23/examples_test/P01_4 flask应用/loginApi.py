from flask import Flask, request, jsonify, session
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 设置一个密钥，用于加密 session 数据

# 模拟用户信息，实际项目中需要替换为真实的用户信息
users = {
    'hami': 'admin',
    'admin': 'admin'
}

# 条件: 必须登录,才能获取信息

# 登录接口
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username in users and users[username] == password:
        session['logged_in'] = True
        return 'Login successful', 200
    else:
        return 'Login failed', 401

# 查询信息接口，需要登录才能访问
@app.route('/get_info')
def get_info():
    if 'logged_in' in session and session['logged_in']:
        # 用户已登录，返回用户信息
        return 'User Info: OK'  # 返回用户信息
    else:
        # 用户未登录，返回未授权的状态码
        return 'Unauthorized', 401

if __name__ == '__main__':
    app.run(debug=True)