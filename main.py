"""入口。打包与直接运行都走这里。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import main  # noqa: E402

if __name__ == "__main__":
    main()
