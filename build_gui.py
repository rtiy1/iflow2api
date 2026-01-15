import subprocess
import sys

# 使用 flet pack 打包
subprocess.run([sys.executable, "-m", "flet", "pack", "gui.py", "--name", "iFlow2API", "--add-data", "main.py;.", "--add-data", "config.py;.", "--add-data", "converters.py;."])
