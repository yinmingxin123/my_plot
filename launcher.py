"""
交互式绘图工具启动器
自动启动Streamlit应用并打开浏览器
"""
import subprocess
import webbrowser
import time
import socket
import sys
import os
import io
from pathlib import Path

# 设置输出编码为UTF-8（Windows）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def find_free_port():
    """查找可用的端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def wait_for_server(port, timeout=10):
    """等待服务器启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(('localhost', port))
                return True
        except (socket.timeout, ConnectionRefusedError):
            time.sleep(0.5)
    return False

def main():
    # 获取当前脚本所在目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是python脚本
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    app_file = os.path.join(application_path, 'app.py')
    
    # 检查app.py是否存在
    if not os.path.exists(app_file):
        print(f"错误: 找不到 app.py 文件")
        print(f"期望路径: {app_file}")
        input("按回车键退出...")
        sys.exit(1)
    
    # 查找可用端口
    port = find_free_port()
    url = f"http://localhost:{port}"
    
    print("=" * 60)
    print("交互式绘图工具")
    print("=" * 60)
    print(f"正在启动服务器...")
    print(f"服务器地址: {url}")
    print("=" * 60)
    
    # 启动streamlit服务器
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_file,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none"
    ]
    
    try:
        # 启动streamlit进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=application_path
        )
        
        # 等待服务器启动
        print("等待服务器启动...")
        if wait_for_server(port):
            print(f"服务器启动成功！")
            print(f"正在打开浏览器: {url}")
            time.sleep(1)
            webbrowser.open(url)
            print("\n提示:")
            print("- 浏览器已打开，可以开始使用")
            print("- 关闭此窗口将停止服务器")
            print("- 如需重新打开页面，请访问:", url)
            print("=" * 60)
            
            # 保持进程运行
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n正在关闭服务器...")
                process.terminate()
                process.wait()
        else:
            print("错误: 服务器启动超时")
            process.terminate()
            input("按回车键退出...")
            
    except Exception as e:
        print(f"错误: {str(e)}")
        input("按回车键退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()

