"""在电脑上试说中文命令（不刷板子）。

加载训练好的中文检查点，把一句话解析成符号帧，并给出"这台板子会不会
执行"的判断（引脚合法性 / 周期上下限——与 gpio_control.c 同一套规则）。
名字能否解析属于设备上的别名表，这里不做判断，只显示抄下来的名字。

用法：
    uv run python src/zh_demo.py                     # 交互输入
    uv run python src/zh_demo.py "打开4号脚" "闪5号脚三次"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data"))

import frames  # noqa: E402
from evaluate import Decoder  # noqa: E402

RUN = ROOT / "runs" / "cmd-zh-s0.pt"

ACTION_ZH = {"set": "设置电平", "read": "读状态", "blink": "闪烁",
             "seq": "流水灯", "stop": "停止", "alias": "命名",
             "unknown": "看不懂"}


def describe(f: frames.Frame) -> str:
    bits = [ACTION_ZH.get(f.action.value, f.action.value)]
    for t in f.targets:
        if isinstance(t, frames.Pin):
            bits.append(f"引脚{t.n}")
        elif isinstance(t, frames.Name):
            bits.append(f"名字「{t.s}」")
        else:
            bits.append("全部")
    if f.level is not None:
        bits.append({"high": "高", "low": "低", "toggle": "翻转"}[f.level.value])
    if f.interval_ms is not None:
        bits.append(f"周期{f.interval_ms}ms")
    if f.count is not None:
        bits.append("无限次" if f.count == 0 else f"{f.count}次")
    return " / ".join(bits)


def main() -> None:
    # 老 Windows 控制台按 GBK 输出，遇到生僻字会 UnicodeEncodeError 直接崩。
    # 保留控制台自己的编码（强行改 UTF-8 只会变乱码），只把无法编码的字符替换掉。
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    dec = Decoder(RUN)
    lines = sys.argv[1:]
    if not lines:
        print("=" * 60)
        print("  中文试说：说一句话，看模型把它解析成什么符号")
        print("=" * 60)
        print()
        print("  试试这些：")
        print("    打开4号脚")
        print("    让客厅的灯闪三下")
        print("    把12号脚叫做客厅的灯    然后就能说：打开客厅的灯")
        print("    关掉全部")
        print("    今天就先这样吧        （应当拒绝：不是引脚命令）")
        print("    关掉100号脚           （应当拒绝：板上没这个脚）")
        print()
        print("  直接回车退出。")
        print("-" * 60)
        print()
        while True:
            try:
                s = input("> ").strip()
            except EOFError:
                break
            if not s:
                break
            one(dec, s)
        return
    for s in lines:
        one(dec, s)


def one(dec: Decoder, text: str) -> None:
    f, syms, _ = dec.parse(text)
    print(f"\n你: {text}")
    print(f"符号: {' '.join(syms) if syms else '(空)'}")
    if f is None:
        print("结果: 输出不成形（模型生成的符号不符合语法）")
        return
    print(f"理解: {describe(f)}")
    if f.action is frames.Action.UNKNOWN:
        print("结果: 拒绝——这个设备只做引脚命令")
        return
    verdict, msg = frames.range_check(f)
    if verdict is frames.Verdict.EXECUTE:
        print("结果: 可以执行（名字是否存在由设备上的别名表决定）")
    else:
        print(f"结果: 拒绝——{msg}")


if __name__ == "__main__":
    main()
