# Five

适配 Cardputer Zero 的离线五子棋。支持离线人机和同机双人。人机模式可选执黑或执白，默认执黑。难度分为简单、普通和困难，默认普通。

## 安装

将 `dist/five_1.0.0-5_arm64.deb` 复制到 Cardputer Zero，在设备上运行：

```sh
sudo apt install ./five_1.0.0-5_arm64.deb
```

安装后从应用启动器打开 **Five**。

## 商店简介

离线五子棋，支持人机和同机双人。 Offline Gomoku vs CPU or a friend.

**简体中文**

在 Cardputer Zero 上下五子棋。和电脑对弈，可选简单、普通、困难三档，也可以和朋友用同一台设备轮流落子。棋盘可选 15×15 或 13×13，规则可选自由、连珠禁手或自定义禁手。两种模式均支持悔棋，退出后可继续最近一盘未完成的对局。界面支持简体中文和英文。

**English**

Play Gomoku offline on Cardputer Zero. Face the computer at one of three difficulty levels or take turns with a friend on the same device. Choose a 15×15 or 13×13 board and play with freestyle, Renju fouls, or custom foul settings. Both modes support undo, and you can resume your most recent unfinished game. The interface is available in Simplified Chinese and English.

## 按键

| 按键 | 操作 |
| --- | --- |
| 方向键或 F / X / Z / C | 上 / 下 / 左 / 右移动光标 |
| Enter | 落子或确认菜单选项 |
| U | 悔棋。人机模式回到玩家上次落子前，双人模式退一步 |
| Esc 短按 | 松开时返回主菜单 |
| Esc 长按 3 秒 | 从任意页面退出应用 |

应用自动保存最近一局未完成的对局。新开一局前会确认是否替换存档。
电脑思考时可移动光标，电脑落子后光标留在原处。棋子上的标记指示最近一手。

## 设置

- 棋盘默认 15×15，可改为 13×13。棋盘和规则设置在新局生效。
- 人机执棋颜色在新局生效。选执白时由电脑执黑先手，悔棋最早可退到电脑的第一手之后。
- 默认自由规则，黑白都无禁手，五连及以上获胜。
- 连珠禁手预设启用黑棋的三三、四四、长连禁手。触犯禁手判白胜。自定义模式可以分别开关三项。连珠预设应用禁手判定，开局仍为黑白轮流落子。
- 界面支持简体中文和英文，默认简体中文。
- 落子音效默认开启，可在设置中关闭。人机和双人对局共用这一设置。

## 桌面预览与打包

使用 Python 3.9+ 和 Pillow 9.2+。桌面预览还需要 Tk。Linux 可安装 `fonts-noto-cjk`。可用 `FIVE_FONT` 指定字体文件。

```sh
python -m pip install "Pillow>=9.2"
python five.py
python build_package.py
```

## 代码来源与许可证

当前安装包使用内置 AI。屏幕适配代码和 Debian 打包脚本沿用了 WebRadio 的部分实现。Pillow、python-evdev 和 Noto CJK 字体通过系统软件包安装。Five 自有代码的发布许可证待确定。

Rapfi 是候选引擎。若随安装包分发，需保留引擎及随附组件的版权和许可证声明，并在二进制下载处明确提供该版本的完整对应源码、实际使用的补丁及构建和安装脚本。Rapfi 引擎采用 GPLv3，官方模型权重采用 CC0-1.0。发布时应记录引擎和权重的版本。Five 若计划与 Rapfi 一同开源，建议自有代码采用 GPL-3.0-or-later，并确认沿用代码的授权。

- [Rapfi 引擎许可证](https://github.com/dotb1ue/rapfi/blob/master/Copying.txt)
- [Rapfi 官方权重](https://github.com/dotb1ue/rapfi-networks)
- [GPLv3 第 6 节](https://www.gnu.org/licenses/gpl-3.0.html#section6)
