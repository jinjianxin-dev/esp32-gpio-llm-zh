"""手写中文保留评测集（build_zh_eval.py）。

纪律与英文版相同：这些句子**手工写**，不经过训练语料的模板生成器——
用生成器造保留集等于考试用原题。句子按"一个人第一次拿到这块板子会敲
什么"来写，标签逐条配，不跑任何采样。

四类都收：

  * 正样本：六种动作、引脚/名字/混合目标、对话与 terse 两种语域；
  * 替换探针：点名板上不存在的引脚——黄金帧**结构合法**但 range_check
    拒绝，模型若答了一个能执行的命令就是替换失败（本项目最致命的错）；
  * 负样本：<unknown>——闲聊、关于本机的问题、域外任务、残句、
    不支持的能力（亮度/颜色/定时/条件）；
  * 边界：区间引脚（"4到8号"）、时长结束条件（"闪10秒"）——语法表达
    不了，必须拒绝。

输出 data/eval/zh_dev.jsonl。用法：
    uv run python data/build_zh_eval.py
"""

from __future__ import annotations

import json
from pathlib import Path

import frames
from frames import Action, Frame, Level, Name, Pin

OUT = Path(__file__).parent / "eval" / "zh_dev.jsonl"


# (话语, 黄金帧)。None 表示黄金是 <unknown>。
ROWS: list[tuple[str, Frame | None]] = [
    # --- set ---------------------------------------------------------------
    ("打开5号脚", Frame(Action.SET, [Pin(5)], level=Level.HIGH)),
    ("帮我把12号引脚关掉", Frame(Action.SET, [Pin(12)], level=Level.LOW)),
    ("2号灯亮起来", Frame(Action.SET, [Pin(2)], level=Level.HIGH)),
    ("GPIO17断电", Frame(Action.SET, [Pin(17)], level=Level.LOW)),
    ("把48号脚和21号脚都打开",
     Frame(Action.SET, [Pin(48), Pin(21)], level=Level.HIGH)),
    ("关闭第3、7、9脚",
     Frame(Action.SET, [Pin(3), Pin(7), Pin(9)], level=Level.LOW)),
    ("把客厅的灯开一下", Frame(Action.SET, [Name("客厅的灯")], level=Level.HIGH)),
    ("鱼缸灯关了", Frame(Action.SET, [Name("鱼缸灯")], level=Level.LOW)),
    ("把书房台灯和车库卷帘门电机反转一下",
     Frame(Action.SET, [Name("书房台灯"), Name("车库卷帘门电机")],
           level=Level.TOGGLE)),
    ("15号脚翻个面", Frame(Action.SET, [Pin(15)], level=Level.TOGGLE)),
    ("打开6号脚，再打开11号脚",
     Frame(Action.SET, [Pin(6), Pin(11)], level=Level.HIGH)),
    ("40 高", Frame(Action.SET, [Pin(40)], level=Level.HIGH)),
    ("10号 低", Frame(Action.SET, [Pin(10)], level=Level.LOW)),
    # --- blink ---------------------------------------------------------------
    ("让9号脚闪，每800毫秒一次",
     Frame(Action.BLINK, [Pin(9)], interval_ms=800, count=0)),
    ("3号脚闪烁5次", Frame(Action.BLINK, [Pin(3)], count=5)),
    ("指示灯闪两下", Frame(Action.BLINK, [Name("指示灯")], count=2)),
    ("让走廊的灯每半秒一次地闪",
     Frame(Action.BLINK, [Name("走廊的灯")], interval_ms=500, count=0)),
    ("38号脚快一点闪",
     Frame(Action.BLINK, [Pin(38)], interval_ms=200, count=0)),
    ("41号脚慢一点闪",
     Frame(Action.BLINK, [Pin(41)], interval_ms=2000, count=0)),
    ("闪4号脚 十次 每一秒一次",
     Frame(Action.BLINK, [Pin(4)], interval_ms=1000, count=10)),
    ("让楼顶的警示灯一直闪",
     Frame(Action.BLINK, [Name("楼顶的警示灯")], interval_ms=500, count=0)),
    ("1号脚每秒五次地闪",
     Frame(Action.BLINK, [Pin(1)], interval_ms=200, count=0)),
    # --- read ----------------------------------------------------------------
    ("7号脚现在什么情况", Frame(Action.READ, [Pin(7)])),
    ("看看13号脚", Frame(Action.READ, [Pin(13)])),
    ("厨房的灯是开着吗", Frame(Action.READ, [Name("厨房的灯")])),
    ("P21状态", Frame(Action.READ, [Pin(21)])),
    ("42号脚是高电平还是低电平", Frame(Action.READ, [Pin(42)])),
    ("读一下机房的散热风扇", Frame(Action.READ, [Name("机房的散热风扇")])),
    ("前门的灯跟后门的灯都什么状态",
     Frame(Action.READ, [Name("前门的灯"), Name("后门的灯")])),
    # --- seq -----------------------------------------------------------------
    ("让2、3、4号脚轮流点亮，每300毫秒一次",
     Frame(Action.SEQ, [Pin(2), Pin(3), Pin(4)], interval_ms=300, count=0)),
    ("流水 6 7 8 9", Frame(Action.SEQ, [Pin(6), Pin(7), Pin(8), Pin(9)])),
    ("在1到4号脚上跑马灯每150毫秒循环3轮",
     Frame(Action.SEQ, [Pin(1), Pin(2), Pin(3), Pin(4)],
           interval_ms=150, count=3)),
    ("让门廊的灯跑一遍流水，重复4次",
     Frame(Action.SEQ, [Name("门廊的灯")], count=4)),
    ("让10、11、12、13、14号脚逐个闪，速度1秒",
     Frame(Action.SEQ, [Pin(10), Pin(11), Pin(12), Pin(13), Pin(14)],
           interval_ms=1000, count=0)),
    # --- stop ----------------------------------------------------------------
    ("都停了", Frame(Action.STOP, [])),
    ("别闪了", Frame(Action.STOP, [])),
    ("停掉8号脚的闪烁", Frame(Action.STOP, [Pin(8)])),
    ("让客厅灯串停下来", Frame(Action.STOP, [Name("客厅灯串")])),
    # --- alias ---------------------------------------------------------------
    ("以后管4号脚叫台灯", Frame(Action.ALIAS, [Pin(4), Name("台灯")])),
    ("5、6、7这三个脚就都叫鱼缸灯组吧",
     Frame(Action.ALIAS, [Pin(5), Pin(6), Pin(7), Name("鱼缸灯组")])),
    ("把42号脚命名为大门警示灯",
     Frame(Action.ALIAS, [Pin(42), Name("大门警示灯")])),
    ("21号脚是我的夜灯", Frame(Action.ALIAS, [Pin(21), Name("我的夜灯")])),
    # --- 替换探针：引脚不存在，模型必须照抄并让硬件拒绝 -----------------------
    ("打开100号脚", Frame(Action.SET, [Pin(100)], level=Level.HIGH)),
    ("关闭19号引脚", Frame(Action.SET, [Pin(19)], level=Level.LOW)),
    ("闪50号脚三次", Frame(Action.BLINK, [Pin(50)], count=3)),
    ("让31号脚每秒闪一次",
     Frame(Action.BLINK, [Pin(31)], interval_ms=1000, count=0)),
    ("读一下0号脚", Frame(Action.READ, [Pin(0)])),
    # --- 替换探针：周期越界 ----------------------------------------------------
    ("每5毫秒闪一次2号脚",
     Frame(Action.BLINK, [Pin(2)], interval_ms=5, count=0)),
    ("让6号脚每60秒闪一次",
     Frame(Action.BLINK, [Pin(6)], interval_ms=60000, count=0)),
    # --- 边界：语法表达不了，必须 <unknown> ------------------------------------
    ("打开4到8号脚", None),
    ("关闭除了10号以外的所有引脚", None),
    ("让3号脚闪10秒钟", None),
    ("明天早上8点打开2号脚", None),
    # --- 负样本：<unknown> ------------------------------------------------------
    ("你好呀", None),
    "在吗", "谢谢你", "你是机器人吗", "现在几点了", "今天天气怎么样",
    "放一首歌听听", "帮我定个闹钟", "讲个笑话呗", "查一下我的快递",
    "有哪些引脚可以用", "什么是GPIO", "你能控制几个引脚",
    "4号脚安全吗", "支持PWM吗", "我把18号脚命名过吗",
    "我喜欢4号脚", "这个风扇太吵了", "刚才那条命令没成功",
    "把灯调到50%亮度", "把台灯调成暖白色", "让客厅灯渐亮",
    "读一下5号脚的电压", "在7号脚输出模拟信号",
    "等5秒再打开8号脚", "如果3号脚是高的就把9号脚打开",
    "每天下午6点自动关闭4号脚", "日落以后打开花园的灯",
    "打开", "关掉那个", "帮我把", "每500毫秒", "三次", "一直",
    "那个台灯", "引脚", "闪一下那个", "设置成",
    "把4号脚", "读取那个", "让客厅的灯",
    "打开前几个引脚", "闪一下除2号脚之外的灯", "把状态复制到6号脚",
    "17乘8等于多少", "水的沸点是多少", "怎么去最近的地铁站",
    "asdkjh qwe", "嗯嗯哦哦",
]


def main() -> None:
    rows = []
    for item in ROWS:
        if isinstance(item, str):
            text, frame = item, None
        else:
            text, frame = item
        if frame is None:
            gold = Frame(Action.UNKNOWN)
            action, source = "unknown", "zh_holdout_neg"
        else:
            frames.validate(frame)
            gold = frame
            action, source = gold.action.value, "zh_holdout_pos"
        rows.append({
            "text": text,
            "symbols": frames.to_symbols(gold),
            "action": action,
            "source": source,
            "stratum": "zh_holdout",
            "locked": False,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    print(f"wrote {OUT}  {len(rows)} rows")
    print(Counter(r["action"] for r in rows))


if __name__ == "__main__":
    main()
