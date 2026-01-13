from flask import Flask, send_file, abort
import os

app = Flask(__name__)


# download_file.py
@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join("img", filename)

    if not os.path.exists(file_path):
        abort(404, description="File not found")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename  # 保持原始文件名
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)  # 修改端口避免冲突