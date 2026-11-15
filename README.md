# Five

适配 Cardputer Zero 的离线五子棋。支持离线人机和同机双人。人机模式可选执黑或执白，默认执黑。难度分为简单、普通和困难，默认普通。

## 安装

将 `dist/five_1.0.0-7_arm64.deb` 复制到 Cardputer Zero，在设备上运行：

```sh
sudo apt install ./five_1.0.0-7_arm64.deb
```

安装后从应用启动器打开 **Five**。

## 商店简介

离线五子棋，支持人机和同机双人。 Offline Gomoku vs CPU or a friend.

**简体中文**

在 Cardputer Zero 上离线下五子棋。和 Rapfi 对弈，可选简单、普通、困难三档，也可以和朋友用同一台设备轮流落子。棋盘可选 15×15 或 13×13，规则可选自由或连珠禁手。两种对局均支持悔棋和续局，界面和规则说明支持简体中文和英文。

**English**

Play Gomoku offline on Cardputer Zero. Face Rapfi at one of three difficulty levels or take turns with a friend on the same device. Choose a 15×15 or 13×13 board and play with freestyle or Renju fouls. Both modes support undo and resume. The interface and rules guide are available in Simplified Chinese and English.

## 最近改动 / What's new

**1.0.0-7**

- Rapfi 落子失败后会自动重试。连续失败时，重试间隔从 0.5 秒逐步增加到 4 秒。重试期间仍可悔棋或返回菜单。
- Five automatically retries when Rapfi fails to return a move. For repeated failures, the delay grows from 0.5 seconds to 4 seconds. You can still undo or return to the menu while Five retries.

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
- 简单、普通、困难使用 Rapfi 的棋力参数 25、65、100，并分别限制搜索时间和深度。
- 默认自由规则，黑白都无禁手，五连及以上获胜。
- 连珠禁手中，黑棋恰好五连获胜，白棋五连或更长即胜。黑棋三三、四四或长连判白胜，同一步恰好五连时优先判黑胜。开局黑白轮流落子。可在设置中打开「规则说明」。
- 旧版仅启用部分禁手的人机棋局可以按原规则以同机双人方式续下。
- 界面支持简体中文和英文，默认简体中文。
- 落子音效默认开启，可在设置中关闭。人机和双人对局共用这一设置。

## 桌面预览与打包

使用 Python 3.9+ 和 Pillow 9.2+。桌面预览还需要 Tk。Linux 可安装 `fonts-noto-cjk`。可用 `FIVE_FONT` 指定字体文件。

```sh
python -m pip install "Pillow>=9.2"
python five.py
pwsh -File build_rapfi.ps1
python build_package.py
```

## 代码来源与许可证

Windows 上的 ARM64 打包使用 `build_rapfi.ps1`。桌面预览的人机模式可通过 `FIVE_RAPFI` 指定适合本机的 Rapfi 可执行文件，模型和配置放在该文件旁。

Five 用标准 Gomocup 文本协议与独立的 Rapfi 进程通信。Rapfi 引擎按 GPL-3.0-or-later 分发，官方经典模型权重采用 CC0-1.0。安装包的 `/usr/share/doc/five/` 包含许可证文本、精确对应的 Rapfi 源码和构建脚本。引擎提交为 `1387d11312190ec66665d361ff07a7c70221b78a`，权重提交为 `7eeb19b55219a48138756293f92211a1539bab4d`。

Five 自有代码的发布许可证待确定。若采用 Proprietary，其条款应明确仅适用于 Five 自有部分，Rapfi 和模型权重继续按各自许可证分发。屏幕适配代码和 Debian 打包脚本沿用了 WebRadio 的部分实现。Pillow、python-evdev 和 Noto CJK 字体通过系统软件包安装。

- [Rapfi 引擎许可证](https://github.com/dotb1ue/rapfi/blob/master/Copying.txt)
- [Rapfi 官方权重](https://github.com/dotb1ue/rapfi-networks)
- [GPLv3 第 6 节](https://www.gnu.org/licenses/gpl-3.0.html#section6)
