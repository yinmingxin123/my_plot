"""
自动打包脚本
使用PyInstaller将应用打包成exe
"""
import os
import sys
import shutil
import subprocess
import io

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    print("=" * 60)
    print("交互式绘图工具 - 打包脚本")
    print("=" * 60)
    
    # 检查PyInstaller是否安装
    try:
        import PyInstaller
        print(f"[OK] PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[INFO] 未安装 PyInstaller")
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller 安装完成")
    
    # 清理旧的构建文件
    print("\n清理旧的构建文件...")
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  已删除: {folder}")
    
    spec_file = "交互式绘图工具.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"  已删除: {spec_file}")
    
    print("\n开始打包...")
    
    # PyInstaller命令
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=交互式绘图工具",
        "--onedir",  # 打包成文件夹模式
        "--console",  # 显示控制台窗口，便于查看状态
        "--icon=NONE",
        "--add-data=app.py;.",
        "--add-data=sample_data.csv;.",
        "--add-data=使用说明_exe版本.txt;.",
        "--hidden-import=streamlit",
        "--hidden-import=pandas",
        "--hidden-import=plotly",
        "--hidden-import=openpyxl",
        "--hidden-import=streamlit.web.cli",
        "--hidden-import=streamlit.runtime.scriptrunner.magic_funcs",
        "--collect-all=streamlit",
        "--collect-all=plotly",
        "--noconfirm",  # 不确认覆盖
        "launcher.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 60)
        print("[SUCCESS] 打包成功！")
        print("=" * 60)
        print(f"\n可执行文件位置: dist/交互式绘图工具/交互式绘图工具.exe")
        print("\n使用说明:")
        print("1. 进入 dist/交互式绘图工具/ 文件夹")
        print("2. 双击 交互式绘图工具.exe 启动")
        print("3. 可以将整个文件夹分发给其他用户")
        print("=" * 60)
        
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] 打包失败！")
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

