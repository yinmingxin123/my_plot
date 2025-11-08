@echo off
chcp 65001 >nul
echo ========================================
echo     交互式绘图工具 - 一键打包
echo ========================================
echo.

echo [1/3] 检查并安装依赖...
python -m pip install -q -r requirements_build.txt
if errorlevel 1 (
    echo 错误: 依赖安装失败！
    pause
    exit /b 1
)
echo ✓ 依赖安装完成
echo.

echo [2/3] 开始打包...
python build_exe.py
if errorlevel 1 (
    echo 错误: 打包失败！
    pause
    exit /b 1
)
echo.

echo [3/3] 打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\交互式绘图工具\
echo.
echo 按任意键打开文件夹...
pause >nul
explorer dist\交互式绘图工具\

