"""必须映射到 <unknown> 的中文域外话语（zh_negatives.py）。

角色与 data/negatives.py 完全相同：这台设备没有云端兜底，"今天天气怎么
样"被解析成 <set> <p2> <high> 就真的会开灯。所以 <unknown> 是**训练出来
的输出类别**，不是事后加的置信度阈值——这个文件就是它的训练信号。

有价值的负样本是近似样本。泛泛的闲聊很容易拒、学到的东西很少；"打开"
（话说一半）和"有哪些引脚可以用"（关于本机的问题）才决定误接受率。

英文版的两条结构性教训在这里原样沿用：

  * 越界的数值（引脚 100、周期 5ms）**不是负样本**——模型照抄数字，由
    硬件层拒绝。把它们放在负样本里，等于训练"见大数就拒"的条件反射。
  * 负样本必须经过**与正样本相同的装饰机制**（zh_realize._decorate）。
    哪一种语气装饰（"请"、"好吗"、句号、问号）只出现在一侧，哪一侧的
    模型就会把它当作类别证据，而不去看内容。

中文特有的一处改动：英文 truncate() 按空格切词，中文没有空格，改成按
**字**切——只在切点前一个字是虚词/动词（把、让、请、的、每……）时保留
切口，否则切出来的"打开4号脚"是完整命令，和正样本自相矛盾。
"""

from __future__ import annotations

import random

import zh_realize as realize
import zh_names as names
from frames import EXAMPLE_NAMES, PINS_S3, ROUND_INTERVALS

# 设备名词，给"不支持的能力"造近似样本用。中文名词。
EXAMPLE_NAMES_ZH = ["台灯", "风扇", "蜂鸣器", "加热器", "阀门", "继电器",
                    "警笛", "红色LED", "厨房的灯", "书房台灯", "指示灯"]

# --- 远域：完全不同的任务 -----------------------------------------------------

OTHER_DOMAIN = [
    "今天天气怎么样", "今天天气怎么样啊", "定一个早上七点的闹钟", "放首歌",
    "播放下一首", "给我妈发条消息", "打电话给爸爸", "现在几点了",
    "今天几号", "帮我记一下要买牛奶", "去车站怎么走", "讲个笑话",
    "17乘4等于多少", "把这段话翻译成英语", "昨晚比赛谁赢了",
    "读一下新闻", "帮我点个外卖", "订一张两人的桌子",
    "珠峰有多高", "法国的首都是哪里", "把音量调大", "把屏幕调亮一点",
    "打开车库门", "把前门锁上", "我的心率是多少", "一个苹果多少卡路里",
    "写一首诗", "总结一下这篇文章", "现在股票行情如何",
    "把恒温器调到21度", "用吸尘器打扫客厅", "明天要下雨吗",
    "给我推荐一部电影", "帮我算一下房贷", "查一下快递到哪了",
]
# 刻意不收："打开电视"、"关掉取暖器"这类。它们是结构上完全合法的命令，
# 只是目标不在别名表里——那必须在"解析别名"这一层失败，而不是在解析命令
# 这一层。见 frames.py。

CHITCHAT = [
    "你好", "嗨", "喂", "早上好", "晚安", "你好呀", "你是谁",
    "你能干什么", "谢谢", "谢谢你", "多谢", "没事了", "算了吧",
    "对不起", "哎呀", "不错", "挺好", "好", "嗯", "哦", "是的", "不是",
    "可能吧", "什么", "啊？", "帮帮我", "你在吗", "说句话", "测试",
    "测试一下", "ping", "在吗？", "有人吗", "哈喽", "hi", "hello",
]

# --- 近似样本：长得像命令，但不是可执行的命令 ---------------------------------

META_QUESTIONS = [
    "有哪些引脚可以用", "哪些引脚是安全的", "你能控制什么",
    "列出所有引脚", "给我看看引脚图", "什么是GPIO", "引脚是怎么回事",
    "闪烁是什么意思", "4号脚用起来安全吗", "还有哪些引脚空着",
    "一共有几个LED", "4号脚上接了什么", "我起过哪些名字",
    "我的别名有哪些", "我把4号脚叫什么来着", "你最快能闪多快",
    "最长的时间间隔是多少", "你能同时控制几个引脚", "支持PWM吗",
    "4号脚的电压是多少", "4号脚能过多大电流", "怎么给引脚接线",
    "你们家设备多少钱", "这个板子是什么型号",
]

OPINIONS = [
    "我喜欢4号脚", "4号脚是我最喜欢的", "这个LED太亮了", "风扇太吵了",
    "这个真酷", "刚才成功了", "刚才没成功", "灯本来就是开着的",
    "我觉得2号脚坏了", "蜂鸣器真烦人", "太好了，台灯亮了",
    "厨房的灯一直闪", "18号脚好像没反应", "这个反应有点慢啊",
    "你们这个好玩",
]

# --- 近似样本：残缺或缺槽位的命令 ---------------------------------------------

TRUNCATED = [
    "打开", "关闭", "打开那个", "关闭我的", "闪", "闪烁", "设置",
    "读取", "查看", "切换", "流水", "跑马", "命名", "叫",
    "请打开", "帮我把", "能不能闪一下", "把4号", "把4号脚设置成",
    "读取那个", "叫4号", "命名4号", "闪4号", "让", "把那个",
    "请把那个", "我想让你", "麻烦你", "每300毫秒", "5次", "一直",
    "高电平", "低电平", "开", "关", "那个台灯", "引脚", "GPIO",
    # 介词尾巴。英文版靠词表排除危险切口，中文按字切（见 truncate），
    # 这一族直接列出而不是推导。
    "停止闪烁在", "取消闪烁在", "查看的状态", "把4号脚的状态",
    "4号脚的状态是什么", "切换的状态", "在4号脚上跑马灯",
]

_ALL_PINS_HEAD = ["所有引脚", "全部", "每个引脚", "所有的灯", "全部GPIO",
                  "所有的"]


def pin_range(rng: random.Random) -> str:
    """"打开4到8号脚"。一段连续引脚，语法表达不了。

    英文版实测的教训："pins 4-8"被读成 **48号脚**——两个数字被当成一个
    数，而48恰好是这块板子上的真引脚。"4到8号"也没好到哪去：开了4和8，
    跳过中间所有。展开区间是个合理的功能，但那是改语法（加一个 <range>
    槽位让运行时枚举）的事，不是让模型猜的事。
    """
    lo = rng.choice(PINS_S3[:-4])
    hi = lo + rng.randint(2, 8)
    verb = rng.choice(["打开", "关闭", "闪", "切换", "流水", "依次点亮",
                       "查看", "读取"])
    ref = rng.choice([f"{lo}到{hi}号脚", f"{lo}-{hi}号脚",
                      f"{lo}到{hi}号引脚", f"引脚{lo}到{hi}",
                      f"GPIO{lo}-{hi}", f"{lo}至{hi}号脚",
                      f"从{lo}到{hi}号脚"])
    return f"{verb}{ref}"


def exception_set(rng: random.Random) -> str:
    """"打开除4和5以外的所有引脚"。全集减子集。

    语法里只有 <all> 或显式列表，没有中间态。英文版实测：这个形状没训练
    过时直接拒收；多引脚命令一加上，<all> 反而成了最近的匹配——"所有引
    脚除了4和5"变成了**打开4和5**。要的相反，来自一句十四万行语料里只有
    一行的形状。碰巧正确不是正确，分布一移它就往模型偏的方向错。
    """
    ps = rng.sample(PINS_S3, rng.randint(1, 3))
    lst = (str(ps[0]) if len(ps) == 1
           else "、".join(map(str, ps[:-1])) + f"和{ps[-1]}")
    head = rng.choice(_ALL_PINS_HEAD)
    verb = rng.choice(["打开", "关闭", "闪", "切换", "停止"])
    return rng.choice([
        f"{verb}{head}，除了{'引脚' if rng.random() < 0.5 else ''}{lst}",
        f"{verb}{head}但不要{lst}",
        f"{verb}{head}，除了{lst}号",
        f"{verb}除了{lst}以外的{head}",
        f"{verb}{head}，{lst}除外",
        f"{verb}剩下的引脚", f"{verb}其他的引脚",
        f"{verb}前{rng.randint(2, 5)}个引脚", f"{verb}后{rng.randint(2, 5)}个引脚",
        f"{verb}奇数号脚", f"{verb}偶数号脚", f"{verb}隔一个引脚",
    ])


def duration(rng: random.Random) -> str:
    """"让4号脚闪10秒"。用时长当结束条件。

    语法里从来没表达过这个——工具数的是次数不是时间——但没人训练过拒绝，
    模型把"10秒"读成1000ms的频率，一直闪下去。错的频率加错的结束条件，
    来自一句两样都没提的话。
    """
    p = rng.choice(PINS_S3)
    # 秒数刻意偏小。"闪10秒"和"每10秒闪一次"迎面相撞——区分它们的只有
    # "闪"后面的介词结构，重叠区训练不足时模型就倒向频率。
    n = rng.randint(2, 12) if rng.random() < 0.6 else rng.randint(2, 90)
    unit = rng.choice(["秒", "秒钟", "分钟", "分钟", "小时", "秒", "秒钟"])
    verb = rng.choice(["闪", "闪烁", "亮", "运行"])
    return rng.choice([
        f"让{p}号脚{verb}{n}{unit}",
        f"让{p}号脚{verb}接下来的{n}{unit}",
        f"打开{p}号脚{n}{unit}",
        f"{p}号脚保持高电平{n}{unit}",
        f"让{p}号脚{verb}半分钟",
        f"打开{p}号脚过一会儿再关",
        f"让{p}号脚持续{n}{unit}后停止",
    ])


def relative_reference(rng: random.Random) -> str:
    """"把刚才那个关掉"。每句话在设计上互相独立，没有上一轮可指——
    刻意不支持，见 frames.py。"""
    return rng.choice([
        "把刚才那个关掉", "把它再打开", "再来一次", "撤销刚才的",
        "另一个", "下一个也一样", "现在轮到另一个LED", "把它放回去",
        "恢复原样", "再做一遍同样的事", "还有旁边那个",
        "重复你刚才做的", "撤销上一条命令", "刚才改的是哪个脚",
        "回到刚才的样子", "把上次的流水再跑一遍", "反着来一遍",
    ])


def unsupported_capability(rng: random.Random) -> str:
    """模拟量、颜色、定时和条件——这些能力没有。

    英文版实测：这类输入在保留集上漏过 20%，所以给它们单独的生成器而不
    是几条字面量。类别取自保留集里出现过的，但每句话都是生成的——把评
    测句抄进训练会毁掉测量。
    """
    p, nm = rng.choice(PINS_S3), rng.choice(EXAMPLE_NAMES_ZH)
    pct = rng.choice([10, 20, 25, 30, 50, 60, 75, 80, 90])
    secs = rng.randint(2, 90)
    colour = rng.choice(["红色", "绿色", "蓝色", "黄色", "紫色", "青色",
                         "品红", "暖白", "橙色", "粉色"])
    return rng.choice([
        # 模拟量 / PWM
        f"把{p}号脚调到{pct}%", f"把{p}号脚亮度设为{pct}%",
        f"把{nm}调暗到一半", f"调暗{p}号脚", f"调暗{nm}",
        f"让{p}号脚{pct}%亮", f"让{nm}在{secs}秒内渐亮",
        f"让{p}号脚渐暗", f"把{p}号脚亮度慢慢拉高",
        f"把{p}号脚占空比设为{pct}%", f"让{nm}平滑调光",
        f"把{nm}的强度调到中等", f"在{p}号脚上输出模拟值128",
        f"在{p}号脚输出模拟信号", f"把{nm}的亮度调低",
        f"调亮{nm}", f"让{nm}暗一点", f"把{p}号脚设为2.5伏",
        f"在{p}号脚输出3.3伏", f"把{p}号脚强度降到一半",
        f"把{nm}强度拉满", f"把{p}号脚强度调到{pct}%",
        # 模拟量*读取*。开头就是我们自己的读取动词，所以要学的是宾语：
        # 电压和ADC计数不支持，数字电平支持。没有它们，"READ ANALOG
        # VOLTAGE ON PIN 10"会被执行。
        f"读一下{p}号脚的模拟电压", f"读取{p}号脚的模拟值",
        f"{p}号脚的电压是多少", f"测一下{p}号脚的电压",
        f"ADC读取{p}号脚", f"读{p}号脚的ADC", f"测{p}号脚的电流",
        f"采样{p}号脚的模拟输入",
        # 颜色
        f"把{p}号脚改成{colour}", f"把{nm}变成{colour}",
        f"让{p}号脚发{colour}光", f"在{p}号脚上循环变色",
        f"把{p}号脚色调设为{colour}", f"把{nm}色温设为3000K",
        f"把{p}号脚的RGB灯换成{colour}",
        f"把{p}号脚RGB设为{rng.randint(0, 255)} {rng.randint(0, 255)} "
        f"{rng.randint(0, 255)}",
        # 定时
        f"{secs}分钟后打开{p}号脚", f"一小时后关闭{nm}",
        f"定时下午5点关闭{p}号脚", f"日落时打开{nm}",
        f"等{secs}秒再切换{p}号脚", f"每天早上8点打开{p}号脚",
        f"让{nm}午夜前一直关着", f"{secs}分钟后自动关闭{p}号脚",
        # 条件 / 传感器
        f"如果{p}号脚是高的就打开{rng.choice(PINS_S3)}号脚",
        f"当{p}号脚上的按钮按下时闪{nm}",
        f"每当{p}号脚变高就切换{nm}",
        f"监控{p}号脚，变化时打开{nm}",
        f"温度传感器触发时关闭{nm}",
        f"如果{rng.choice(PINS_S3)}号脚变低就在{p}号脚上响警报",
        f"读{p}号脚并把状态复制到{rng.choice(PINS_S3)}号脚",
        f"把{p}号脚和{rng.choice(PINS_S3)}号脚联动，一起开关",
        f"等{p}号脚变低后把{rng.choice(PINS_S3)}号脚拉高",
        f"{p}号脚为高期间一直闪{nm}",
        # 摩斯码 / 我们没有的花样
        f"让{nm}按摩斯码闪", f"让{nm}平滑呼吸", f"在{p}号脚上放心跳模式",
        f"让{nm}渐变彩虹色",
    ])


_Q_OBJECT = [
    "法国的首都", "人生的意义", "144的平方根", "日本的人口",
    "水的沸点", "东京现在的时间", "最高的山峰", "光速",
    "比特币的价格", "一切的答案", "最好的编程语言",
    "到月球的距离", "明天的天气", "越位规则", "哈姆雷特的剧情",
    "一只燕子飞行的速度",
]


def offdomain_question(rng: random.Random) -> str:
    """通用问句。开头和读取命令一模一样（"……是什么"），光靠结构拒不掉
    ——早期模型把"法国的首都是什么"答成了 <read> <name>。这里要教的判别
    特征是宾语的形状：长长的"的"字短语或算式，永远不会是短设备名词。
    仍然是结构，不是对"名词是不是已知别名"的判断。"""
    a, b = rng.randint(2, 99), rng.randint(2, 99)
    return rng.choice([
        f"{rng.choice(_Q_OBJECT)}是什么",
        f"告诉我{rng.choice(_Q_OBJECT)}",
        f"{a}乘{b}等于多少", f"{a}加{b}是多少",
        f"算一下{a}除以{b}", f"{b}的{a}%是多少",
        f"{a}减{b}等于几", f"算{a * a}的平方根",
        f"一年有多少{rng.choice(['天', '周'])}",
        f"谁{rng.choice(['写了红楼梦', '发明了晶体管', '得了诺贝尔奖'])}",
        f"{rng.choice(['最近的车站在哪', '我的手机在哪', '珠峰在哪'])}",
        f"明天{rng.choice(['会不会下雨', '气温多少度'])}",
    ])


def conditional_wrapper(rng: random.Random) -> str:
    """合法命令包在条件或延时里，语法没有表达手段。两种语序都漏过。"""
    p, q = rng.sample(PINS_S3, 2)
    cmd = rng.choice([
        f"闪{p}号脚", f"打开{p}号脚", f"关闭{p}号脚", f"切换{p}号脚",
        f"停止{p}号脚的闪烁", f"在{p}和{q}上跑流水", f"把{p}号脚拉高",
        f"读{p}号脚",
    ])
    cond = rng.choice([
        f"如果{q}号脚是高的", f"如果{q}号脚关闭了", f"当{q}号脚变低时",
        f"每当{q}号脚变化", f"一旦{q}号脚开了",
        f"如果{q}号脚上的按钮被按下", f"除非{q}号脚已经开着",
        f"过{rng.randint(2, 90)}秒", f"过{rng.randint(2, 59)}分钟",
        "日落时", "下午5点", "明天早上", "每天早上8点",
        f"{rng.randint(2, 30)}分钟后", "我到家的时候",
        "温度传感器触发时", "门开着的时候",
        f"在{rng.randint(1, 12)}点", f"在{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}",
        "每天晚上", "每天早晨", "每天夜里", "明早第一件事",
        "工作日", "黎明时", "黄昏时",
    ])
    if rng.random() < 0.5:
        return f"{cond}{cmd}"
    return f"{cmd}，{cond}"


# 不能合法结尾的字。只有落点在这些字上的切口才保留——否则把"闪4号脚每
# 300毫秒5次"切成"闪4号脚"，那是完全合法的命令，负样本会和正样本矛盾。
_DANGLING = {
    "把", "让", "请", "帮", "帮帮", "麻烦", "的", "每", "和", "与", "跟",
    "在", "是", "到", "给", "向", "了", "就", "然后", "再", "还有",
    "以及", "叫", "叫做", "命名为", "设置", "设置为", "读取", "查看",
    "检查", "闪", "闪烁", "打开", "关闭", "切换", "流水", "跑马", "扫描",
    "停止", "取消", "结束", "停掉", "别", "我想", "能不能", "可不可以",
    "当", "如果", "每当", "一旦", "除非", "等", "过", "在……上", "从",
    "状态", "电平", "读数", "间隔", "速度", "频率", "次数", "引脚",
    "号脚", "那个", "这个", "我", "你", "告诉我", "给我", "报告",
}

PUNCT = "？。！，"


def truncate(text: str, rng: random.Random) -> str | None:
    """把一条真命令切短；切不出残句就返回 None。

    半截输入曾是最大的误接受类别——"闪12号"带着尾巴、"查看的状态"、
    "把15号设成"都被执行过。从正样本用的表面形式出发推导残句，能系统性
    地盖住这个形状，手写清单从来做不到。

    中文没有空格，按**字**切：候选切点是"前一个字符是虚词/动词"的位置，
    这样切出来的尾巴才是真的悬空。
    """
    text = text.rstrip(PUNCT)
    cuts = [i for i in range(1, len(text))
            if text[i - 1] in _DANGLING or text[i - 1:i + 1] in _DANGLING]
    if not cuts:
        return None
    return text[:rng.choice(cuts)]


_INV_POOL = ("abcdefghijklmnopqrstuvwxyz"
             "的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已亲其进此话常与活正感")


def gibberish(rng: random.Random) -> str:
    """乱码。中英混合：既有一串字母，也有一串常用字随机组合——对串口
    接口来说，两种垃圾都会有人敲进来。"""
    n = rng.randint(1, 4)
    out = []
    for _ in range(n):
        if rng.random() < 0.5:
            out.append("".join(rng.choice(_INV_POOL[:26])
                               for _ in range(rng.randint(2, 9))))
        else:
            out.append("".join(rng.choice(_INV_POOL[26:])
                               for _ in range(rng.randint(2, 6))))
    return " ".join(out)


# 权重偏向近似样本：误接受率测的就是它们。第三项是 realize._decorate
# 给这句话穿的语气。
_BANKS = [
    (OTHER_DOMAIN, 14, "imperative"),
    (CHITCHAT, 10, "neutral"),
    (META_QUESTIONS, 16, "question"),
    (OPINIONS, 10, "neutral"),
    (TRUNCATED, 22, "imperative"),
]
_GEN = [(unsupported_capability, 18, "imperative"),
        (conditional_wrapper, 12, "imperative"),
        (offdomain_question, 10, "question"),
        (relative_reference, 8, "imperative"),
        (pin_range, 10, "imperative"),
        (duration, 12, "imperative"),
        (exception_set, 10, "imperative"),
        (gibberish, 4, "terse")]


def sample_negative(rng: random.Random) -> str:
    banks_w = sum(w for _, w, _ in _BANKS)
    gen_w = sum(w for _, w, _ in _GEN)
    if rng.random() < banks_w / (banks_w + gen_w):
        bank, mood = rng.choices([(b, m) for b, _, m in _BANKS],
                                 weights=[w for _, w, _ in _BANKS])[0]
        s = rng.choice(bank)
    else:
        fn, mood = rng.choices([(f, m) for f, _, m in _GEN],
                               weights=[w for _, w, _ in _GEN])[0]
        s = fn(rng)

    return realize._decorate(s, rng, mood)


_VARY_PREFIX = ["", "请", "帮我", "麻烦", "你好，", "好的，", "我想让你",
                "麻烦你", "先", "现在", "那么"]
_VARY_SUFFIX = ["", "，谢谢", "，现在", "，麻烦了", "，谢谢啦", "，好吗"]


def vary(text: str, rng: random.Random) -> str:
    """给一句话重新穿上一遍正样本同款的语气装饰。

    用于把一小池真实近似负样本拉宽到语料里更大的份额，同时不重复完全
    相同的字符串。
    """
    s = text.rstrip(PUNCT)
    s = rng.choice(_VARY_PREFIX) + s + rng.choice(_VARY_SUFFIX)
    return realize.punctuate(" ".join(s.split()), rng, q=0.10)


# --- 探测用生成器（不进训练语料）---------------------------------------------
#
# name_targeted / alias_request 在英文版里曾是"延迟能力"负样本，后来先后
# 转正。现在它们只用于**探测**训练好的模型——这是和训练它不同的另一件事。

def name_targeted(rng: random.Random) -> str:
    """一条以名字为目标、结构完全合法的命令。"""
    sp = realize.Speaker(rng)
    nm = sp.name(names.sample_group_name(rng) if rng.random() < 0.18
                 else names.sample_name(rng))
    kind = rng.random()

    if kind < 0.42:
        bank = rng.choices([realize.ON_T, realize.OFF_T, realize.TOGGLE_T,
                            realize.ON_BARE, realize.OFF_BARE],
                           weights=[38, 38, 12, 6, 6])[0]
        mood = "bare" if bank in (realize.ON_BARE, realize.OFF_BARE) else "imperative"
        s = bank[rng.randrange(len(bank))].format(r=nm) + sp.where()
        return realize._decorate(s, rng, mood)

    if kind < 0.62:
        s = rng.choice(realize.BLINK_T).format(r=nm)
        if rng.random() < 0.55:
            ms = rng.choice(ROUND_INTERVALS)
            s = f"{s}，{realize.interval_phrase(ms, rng)}"
            if rng.random() < 0.4:
                s = f"{s}，{realize.count_phrase(rng.randint(2, 20), rng, '下')}"
        return realize._decorate(s, rng)

    if kind < 0.80:
        r = rng.random()
        if r < 0.45:
            return realize._decorate(rng.choice(realize.READ_Q_T).format(r=nm)
                                     + sp.where(), rng, "question")
        if r < 0.85:
            return realize._decorate(rng.choice(realize.READ_CMD_T).format(r=nm)
                                     + sp.where(), rng, "imperative")
        return realize._decorate(rng.choice(realize.READ_FRAG_T).format(r=nm),
                                 rng, "bare")

    if kind < 0.92:
        return realize._decorate(rng.choice(realize.STOP_ONE_T).format(r=nm), rng)

    refs = [sp.name(names.sample_name(rng)) for _ in range(rng.randint(2, 4))]
    body = "、".join(refs[:-1]) + f"和{refs[-1]}"
    return realize._decorate(rng.choice(realize.SEQ_T).format(r=body), rng)


if __name__ == "__main__":
    rng = random.Random(3)
    print("--- 永久负样本 ---")
    for _ in range(20):
        print(" ", sample_negative(rng))
