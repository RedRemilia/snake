# 贪吃蛇 · Neon Snake

一个使用 Python + pygame 编写的霓虹风贪吃蛇游戏，包含平滑移动、动态音效、粒子特效、最高分记录和完整的菜单 / 暂停 / 结束界面。

## 快速开始

```powershell
conda activate py313
python main.py
```

也可以在 Windows 下直接双击 `run.bat`，它会自动激活 `py313` 环境。

首次运行时如果环境中缺少 pygame，游戏会自动调用当前 Python 的 pip 安装 `requirements.txt` 中的依赖。也可以手动安装：

```powershell
conda activate py313
python -m pip install -r requirements.txt
```

## 操作

| 按键 | 功能 |
| --- | --- |
| `方向键` / `WASD` | 移动（支持缓存两次转向） |
| `SPACE` / `P` | 暂停 / 继续 |
| `SPACE` / `ENTER` | 在菜单或结算页开始游戏 |
| `R` | 暂停或结算时重新开始 |
| `M` | 开启 / 关闭音效 |
| `ESC` | 游戏中暂停；暂停 / 结算页返回菜单；菜单中退出游戏 |

## 玩法与特性

- 每吃到一个果实获得 10 分，蛇身增长，移动速度逐渐加快。
- 撞到墙壁或自己的身体会结束游戏；蛇尾本步会移开，因此可以安全进入尾格。
- 最高分会自动保存到 `highscore.json`，下次启动继续保留。
- 蛇的转向经过平滑插值，吃着果实时有粒子爆发与分数飘字。
- 所有音效由 Python 标准库实时合成，不需要额外素材文件。
- 窗口失去焦点时会自动暂停。
- 支持鼠标点击菜单按钮，所有按钮都有悬停反馈。

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `main.py` | 游戏完整源码 |
| `requirements.txt` | Python 依赖 |
| `run.bat` | Windows 一键启动脚本 |
| `highscore.json` | 首次产生最高分后自动生成 |
