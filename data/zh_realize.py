"""表层实现：Frame -> 中文话语（zh_realize.py）。

角色与 data/realize.py 完全相同，只是表面语言换成中文。三条不可破坏的
不变量也原样保留：

  * 引脚号必须**逐字**出现在话语里，模板不许改写数字——标签就是从话语
    里抄的。
  * 一个模糊量词只许对应一个规范值。"快点"永远指 200ms，不许有时 100。
    同一句话两个标签，等于告诉模型这个槽位是噪音。
  * 模板只许配它语气接受的前缀。"请把"、"帮我"配祈使句；疑问句配疑问
    前缀，配错了就是语料 bug。

中文特有的两点：

  * 没有大小写，英文版那句"全大写变成命令的证据"的教训在这里天然不
    存在——但标点仍是两边共享的装饰，正负样本走同一个 _decorate。
  * 词间没有空格，所以模板与前后缀直接拼接，不加空格；terse 语域内部
    保留半角空格（"开 4"），用来给裸数字一个清晰边界。
"""

from __future__ import annotations

import random

import zh_names as names
from frames import Action, All, Frame, Level, Name, Pin, Target

NUM_WORDS = {
    1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六",
    7: "七", 8: "八", 9: "九", 10: "十", 11: "十一", 12: "十二",
    15: "十五", 20: "二十", 21: "二十一",
}

# 一个人怎么写引脚号。每句话选一次风格——同一句里混用"4号脚"和"GPIO 4"
# 是生成器的痕迹，不是人说话的样子。
PIN_STYLES = [
    lambda n: f"{n}号脚",
    lambda n: f"{n}号脚",
    lambda n: f"{n}号脚",
    lambda n: f"{n}号引脚",
    lambda n: f"引脚{n}",
    lambda n: f"第{n}脚",
    lambda n: f"第{n}号引脚",
    lambda n: f"GPIO{n}",
    lambda n: f"gpio {n}",
    lambda n: f"{n}号",
    lambda n: f"P{n}",
    # 唯一不是逐字抄数字的风格："四号脚"得翻译成 4。人们确实这么写，保留，
    # 但它是抄写语法里的一座 memorisation 孤岛（NUM_WORDS 只覆盖 1-15、20、21）。
    lambda n: f"{NUM_WORDS[n]}号脚" if n in NUM_WORDS else f"{n}号脚",
    # 裸数字。对着串口敲命令的人写"关 12"，不写"关闭12号引脚"。
    lambda n: f"{n}",
    lambda n: f"{n}",
]


class Speaker:
    """每句话一套风格，保证同一句内的指称一致。"""

    def __init__(self, rng: random.Random, terse: bool = False):
        self.rng = rng
        self.pin_style = rng.choice(PIN_STYLES)
        # 指示词加在名字前面。中文没有冠词，但"那个/我家的"是真实口语。
        # terse 输入多半不加，让名字出现在句首——句首的名字与句中的名字
        # 在 ByteLevel 下 token 不同，语料必须两种都教。
        self.det = rng.choices(["那个", "我的", "我家的", "", "这盏", "这边"],
                               weights=[15, 5, 5, 65, 5, 5] if terse
                               else [25, 8, 8, 50, 5, 4])[0]

    def pin(self, n: int) -> str:
        return self.pin_style(n)

    def name(self, text: str) -> str:
        return f"{self.det}{text}"

    def where(self) -> str:
        """句尾偶尔挂一个位置短语。

        "打开厨房的灯"是真实智能家居话语里的主流形状，第一批语料若一个
        都没有，模型会对整类句子回 <unknown>。这个位置信息是模型必须学会
        **忽略**的噪音：目标才是中心名词，这台设备没有房间的概念。
        """
        if self.rng.random() > 0.28:
            return ""
        place = self.rng.choice(names.PLACE)
        return self.rng.choice([
            f"，在{place}", f"，{place}那个", f"，{place}里的", "，楼上",
            "，楼下", f"，{place}那边", f"，我{place}",
        ])

    def target(self, t: Target) -> str:
        if isinstance(t, All):
            return self.rng.choice(
                ["全部", "所有引脚", "所有的", "每一个引脚", "所有灯",
                 "全部引脚", "全部GPIO", "所有LED", "整板", "所有的灯"])
        if isinstance(t, Name):
            # 逐字渲染，外面只加指示词。prepare.py 要在最终话语里找到这个
            # 片段并把标签的 token 切出来，任何对名字本身的改写都会让该行
            # 以 SpanError 作废。
            return self.name(t.s)
        return self.pin(t.n)

    # 连接列表最后两项的词。"和"不是唯一的；别的词缺席时，"打开4号脚然后
    # 5号脚"会只回来一个4。顺序词（"然后"）是刻意收进来的——对电平切换
    # 来说顺序无所谓，"4然后5"的正确读法是两个都要。
    _JOIN = ["和", "和", "和", "然后", "再", "还有", "以及", "跟"]

    def target_list(self, ts: list[Target]) -> str:
        rng = self.rng
        join = rng.choice(self._JOIN)
        if all(isinstance(t, Pin) for t in ts) and rng.random() < 0.55:
            ns = [t.n for t in ts]
            head = rng.choice(["引脚", "引脚", "GPIO", "脚位", "这几个脚"])
            style = rng.random()
            if style < 0.4:
                body = "、".join(str(n) for n in ns[:-1]) + f" {join} {ns[-1]}"
            elif style < 0.7:
                body = "、".join(str(n) for n in ns)
            else:
                body = " ".join(str(n) for n in ns)
            return f"{head} {body}"
        refs = [self.target(t) for t in ts]
        if rng.random() < 0.75:
            return "、".join(refs[:-1]) + f" {join} {refs[-1]}"
        return "、".join(refs)


# --------------------------------------------------------------------------
# 数量词
# --------------------------------------------------------------------------

# 模糊速度词，每个钉死在一个周期上，且只在采到该周期时才输出。
SPEED_WORDS: dict[int, list[str]] = {
    100: ["飞快", "非常快", "超快", "极速"],
    200: ["快点", "快速", "快一点", "快"],
    1000: ["慢点", "慢速", "慢一点", "慢"],
    2000: ["非常慢", "很慢", "慢慢来", "超慢"],
}

RATE_WORDS: dict[int, list[str]] = {
    100: ["一秒十次"],
    200: ["一秒五次"],
    250: ["一秒四次", "每四分之一秒一次"],
    500: ["一秒两次", "每半秒一次"],
    1000: ["一秒一次", "每秒一次"],
    1500: ["每1.5秒一次"],
    2000: ["每两秒一次", "每2秒一次"],
    3000: ["每三秒一次"],
}


def interval_phrase(ms: int, rng: random.Random) -> str:
    forms = [f"每{ms}毫秒", f"每{ms}ms", f"每 {ms} ms", f"间隔{ms}毫秒",
             f"隔{ms}毫秒", f"以{ms}毫秒为间隔", f"速度{ms}毫秒",
             f"周期{ms}毫秒", f"每{ms}毫秒一次"]
    if ms % 1000 == 0:
        s = ms // 1000
        # 缩写形式此前完全缺席：语料里没有"每30s"，保留集却随便用。语料
        # 里没有的形式不是罕见形式，是未知形式。
        forms += [f"每{s}秒", f"每{NUM_WORDS.get(s, s)}秒", f"间隔{s}秒",
                  f"以{s}秒为周期", f"{s}秒一次", f"每{s}s", f"速度{s}秒",
                  f"每{s}秒一次", f"隔{s}秒"]
    if ms % 1000 == 500:
        forms.append(f"每{ms / 1000:g}秒一次")
    # 分钟是人们对这个长度唯一会说出的单位，也是唯一换算成 x60000 的表面
    # 形式。没有它，六位数的采样值只可能以毫秒全写出现——没人那么说话。
    if ms % 60000 == 0:
        m = ms // 60000
        forms += [f"每{m}分钟", f"每{NUM_WORDS.get(m, m)}分钟",
                  f"间隔{m}分钟", f"以{m}分钟为周期"]
    # 赫兹。只在整数频率时输出，"以6.7赫兹"不是人会敲的句子，非整数只会
    # 教模型四舍五入。
    if ms and 1000 % ms == 0:
        hz = 1000 // ms
        forms += [f"以{hz}赫兹", f"{hz}赫兹", f"{hz}Hz", f"频率{hz}赫兹"]
    forms += RATE_WORDS.get(ms, [])
    forms += SPEED_WORDS.get(ms, [])
    return rng.choice(forms)


# "一直"类修饰语在中文里前置（"一直闪"），不能像英文 forever 那样挂在
# 句尾。0 次因此不归 count_phrase 管，由 _forever() 在合法位置插入。
FOREVER_PREFIX = ["一直", "不停地", "持续", "无限循环地", "没完没了地"]
FOREVER_SUFFIX = ["", "", "，别停", "，不要停", "，一直下去", "，直到我说停"]


def _forever(s: str, rng: random.Random) -> str:
    """把"无限次"放到中文合法的位置上：动词前的副词，或句尾的补充短语。"""
    if rng.random() < 0.5:
        return rng.choice(FOREVER_PREFIX) + s
    return s + rng.choice(FOREVER_SUFFIX)


def count_phrase(n: int, rng: random.Random, unit: str = "次") -> str:
    """`unit` 随动作走：流水灯跑"轮"，闪烁说"下"。

    0 次不在这里处理——见 _forever()，中文的"一直"必须前置。
    """
    if n == 0:
        return ""
    if n == 1:
        return rng.choice(["一次", "1次", f"一{unit}"])
    if n == 2:
        return rng.choice(["两次", "2次", f"两{unit}"])
    if n == 3:
        return rng.choice(["三次", "3次", f"三{unit}"])
    forms = [f"{n}次", f"重复{n}次", f"{n}{unit}", f"{n}回"]
    if n in NUM_WORDS:
        forms.append(f"{NUM_WORDS[n]}次")
    return rng.choice(forms)


# --------------------------------------------------------------------------
# 模板
# --------------------------------------------------------------------------
# `{r}` 是目标指称。模板一律自带配文，不加冠词——Speaker.name() 已经加过
# 指示词，"把那个那个台灯打开"就是这么来的。按语气分组，_decorate 才能挑
# 合法的前缀。

ON_T = [
    "打开{r}", "把{r}打开", "开启{r}", "把{r}开启", "开{r}", "接通{r}",
    "给{r}通电", "启动{r}", "点亮{r}", "让{r}通电", "将{r}打开",
    "将{r}置高", "把{r}置高", "把{r}设为高电平", "把{r}置1", "拉高{r}",
    "把{r}拉高", "驱动{r}为高", "置高{r}", "激活{r}", "把{r}开起来",
    "让{r}工作", "把{r}开通", "打开一下{r}", "把{r}亮起来", "{r}亮起来",
    # "都"是多目标口语里的高频副词——"把48号脚和21号脚都打开"。语料里
    # 没有"都"，保留集里的这句就回 <unknown>。
    "把{r}都打开", "{r}都打开", "把{r}全都打开",
]
ON_BARE = ["{r} 开", "{r} 高"]

OFF_T = [
    "关闭{r}", "把{r}关闭", "关掉{r}", "把{r}关掉", "关{r}", "断开{r}",
    "切断{r}的电源", "给{r}断电", "停用{r}", "熄灭{r}", "把{r}熄灭",
    "将{r}关闭", "将{r}置低", "把{r}置低", "把{r}设为低电平",
    "把{r}置0", "拉低{r}", "把{r}拉低", "关掉{r}的电源", "把{r}关了",
    "让{r}停下", "关上{r}", "把{r}关一下", "把{r}都关掉", "{r}都关掉",
    "把{r}全都关掉",
]
OFF_BARE = ["{r} 关", "{r} 低"]

TOGGLE_T = [
    "切换{r}", "把{r}切换", "反转{r}", "翻转{r}的状态", "把{r}的状态反过来",
    "换一下{r}的状态", "变换{r}", "倒换{r}", "{r}取反", "把{r}取反",
    "切换{r}的状态", "反转{r}的状态",
    # "翻个面"是口语里的切换，语料缺席时回 <unknown>。
    "把{r}翻个面", "{r}翻个面", "让{r}反过来", "把{r}反过来",
]

BLINK_T = [
    "让{r}闪烁", "闪{r}", "让{r}闪", "{r}闪烁", "使{r}闪烁",
    "让{r}闪起来", "开始闪{r}", "让{r}闪光", "给{r}开启闪烁",
    "{r}闪烁模式", "让{r}闪烁起来", "开启{r}的闪烁", "让{r}一闪一闪",
]

# "一直"类模板自带"无限次"含义，只在 count == 0 时使用，且不许再拼次数
# ——否则出来的是"一直闪两次"。中文的副词在动词前，英文版把 forever 挂
# 句尾的做法照搬过来会得到"闪一直"，所以前置模板是必需品而不是装饰。
BLINK_FOREVER_T = [
    "让{r}一直闪", "{r}一直闪", "让{r}不停地闪", "让{r}闪个不停",
    "让{r}持续闪", "让{r}一直闪下去",
]

# 频率词也在动词**前面**（"每秒五次地闪"），而且这类模板自带规范频率，
# 只在采到该周期、且次数为 0（无限）时使用，不再追加周量短语。中文里
# "闪一下/两下"带次数含义，所以这里一个都不许出现。
RATE_BLINK_T: dict[int, list[str]] = {
    100: ["{r}每秒十次地闪", "{r}一秒闪十次"],
    200: ["{r}每秒五次地闪", "{r}一秒闪五次", "{r}快一点闪", "{r}快点闪"],
    250: ["{r}每秒四次地闪"],
    500: ["{r}每秒两次地闪", "{r}每半秒闪一次"],
    1000: ["{r}每秒一次地闪", "{r}一秒闪一次", "{r}慢点闪"],
    2000: ["{r}每两秒闪一次", "{r}很慢地闪", "{r}慢一点闪"],
}

SEQ_T = [
    "让{r}依次点亮", "依次点亮{r}", "让{r}轮流点亮", "扫描{r}",
    "让{r}逐个点亮", "在{r}上跑马灯", "让{r}跑马灯", "循环点亮{r}",
    "让{r}顺序点亮", "让{r}来回扫描", "让{r}跑流水灯", "流水灯效果{r}",
    "让{r}逐个闪", "依次闪过{r}", "让{r}轮着亮",
]

# 这里的光杆动词是**完整命令**——全停不需要目标；而 negatives.TRUNCATED
# 里的光杆动词（"闪"、"打开"）是不完整的。模型只能靠很少的样本区分两者，
# 所以单字/单词形式要慷慨列出。
STOP_ALL_T = [
    "停止", "全部停止", "停下", "停", "取消", "全停", "停止一切",
    "别闪了", "不要再闪了", "够了", "让它停下", "停止所有动画",
    "停止闪烁", "终止", "中断", "取消一切", "全部停下", "停止流水灯",
    "取消流水灯", "停止跑马灯", "停止动画", "结束动画", "停掉动画",
    "停止全部", "都停下", "全部取消", "别动了", "停停停",
    "停止所有闪烁", "杀掉动画", "取消所有动画", "停止循环",
    "结束循环", "停止一切动画", "全都停下", "到此为止",
]

# 命名。`{r}` 是引脚指称，`{n}` 是要起的名字。两种语域：祈使（"把4号脚
# 叫做台灯"）和陈述（"4号脚就叫台灯"）。陈述式比它的份额更重要——它没有
# 命令动词，靠动词定动作的模型在这里没有抓手，必须真的读懂句子。
ALIAS_T = [
    "把{r}叫做{n}", "把{r}命名为{n}", "给{r}起名叫{n}", "把{r}记为{n}",
    "把{r}标记为{n}", "给{r}起别名{n}", "把{r}设为{n}", "{r}的别名是{n}",
    "以后管{r}叫{n}", "管{r}叫{n}", "把{r}叫作{n}", "重命名{r}为{n}",
    "把{r}重命名为{n}", "给{r}取名为{n}", "让{r}叫{n}", "{r}别名{n}",
    "把{n}设为{r}的名字", "给{r}挂上{n}这个名字",
]
ALIAS_DECL_T = [
    "{r}叫{n}", "{r}叫做{n}", "{r}是{n}", "{r}就是{n}", "以后{r}叫{n}",
    "从现在起{r}叫{n}", "{r}的名字是{n}", "{r}，别名{n}", "{r}={n}",
    "管{r}叫{n}了", "我把{r}叫做{n}", "{r}就叫{n}", "{r}的名字叫{n}",
]

STOP_ONE_T = [
    "停止{r}", "让{r}停止", "{r}别闪了", "停掉{r}", "取消{r}的闪烁",
    "让{r}停下", "别动{r}", "停止{r}的闪烁", "停止{r}上的动画",
    "取消{r}的动画", "结束{r}的闪烁", "停掉{r}的闪烁", "取消闪烁{r}",
    "停止闪烁{r}", "别让{r}闪了", "关掉{r}的闪烁", "停止{r}的动画",
    "结束{r}上的动画", "别闪{r}了",
]

# 祈使：配"请"、"帮我"。
READ_CMD_T = [
    "查看{r}", "读一下{r}", "读{r}", "检查{r}", "看看{r}", "查询{r}",
    "读取{r}", "测一下{r}", "探测{r}", "采样{r}", "轮询{r}",
    "告诉我{r}的状态", "给我{r}的状态", "报告{r}的状态", "读回{r}",
    "量一下{r}", "{r}的电平是多少", "把{r}的状态报给我",
]
# 疑问：本身是问句——配祈使前缀会把它弄坏。
READ_Q_T = [
    "{r}开着吗", "{r}是开的吗", "{r}是关的吗", "{r}现在什么状态",
    "{r}什么状态", "{r}状态怎么样", "{r}是高电平吗", "{r}是低电平吗",
    "{r}开着没", "{r}怎么样了", "{r}在运行吗", "{r}现在什么情况",
    "{r}的电平是什么", "{r}的状态是什么", "{r}现在是开是关",
    # 二选一问法是中文最自然的读状态句，语料里没有就整类被拒。
    "{r}是高电平还是低电平", "{r}是开着还是关着", "{r}是开还是关",
    "{r}到底什么状态", "{r}现在通着电吗",
]
# 片段：光杆名词短语，独立成句。
READ_FRAG_T = ["{r}的状态", "{r}状态", "{r}电平", "{r}的读数", "{r}读数"]

IMPERATIVE_PREFIX = ["", "", "", "", "", "请", "帮我", "麻烦", "请你",
                     "能不能", "可以", "你好，", "好的，", "现在", "先",
                     "快", "呃，", "嗯，", "哦，", "麻烦你", "帮忙",
                     "劳驾，", "拜托", "请问你", "可不可以"]
QUESTION_PREFIX = ["", "", "", "", "你好，", "呃，", "嗯，", "问一下，",
                   "请问", "打听一下，", "问个事，"]
NEUTRAL_PREFIX = ["", "", "", "", "你好，", "对了，", "记一下，",
                  "备注，", "呃，", "嗯，"]

SUFFIX = ["", "", "", "", "", "，谢谢", "，好吗", "，拜托了", "吧",
          "，现在就弄", "，谢谢啦", "，麻烦了"]
NEUTRAL_SUFFIX = ["", "", "", "", "", "，好吗", "，记住了吗", "，行吗"]


def punctuate(s: str, rng: random.Random, q: float = 0.05) -> str:
    """句末标点。

    **与 zh_negatives.py 共享，而且必须共享。**英文版的教训：只要语气装饰
    （大小写、"请"、"帮我"）只有正样本能用，它自己就成了"这是命令"的
    证据——模型据标点判断而不是据内容判断。中文没有大小写可吵，但语气词
    和标点同样会被钻空子：哪一类句子独享"吗"、"吧"、"！"，哪一类就会
    被据以分类。所以正负样本走同一个装饰函数。
    """
    if rng.random() < q:
        s += "？"
    elif rng.random() < 0.18:
        s += rng.choice(["。", "！"])
    return s


def _decorate(s: str, rng: random.Random, mood: str = "imperative") -> str:
    prefix, suffix, q = {
        "imperative": (IMPERATIVE_PREFIX, SUFFIX, 0.05),
        "question": (QUESTION_PREFIX, NEUTRAL_SUFFIX, 0.65),
        "neutral": (NEUTRAL_PREFIX, NEUTRAL_SUFFIX, 0.10),
        "bare": ([""], NEUTRAL_SUFFIX, 0.0),
        "terse": ([""], [""], 0.0),
    }[mood]

    s = rng.choice(prefix) + s + rng.choice(suffix)
    # 中文词间无空格，但 terse 语域内部有半角空格，名字里也可能有；
    # 只折叠连续空白，不增删单个空格。
    return punctuate(" ".join(s.split()), rng, q)


# 紧凑的机器式说法。第二个人写保留集时全是这种（"关 12"、"闪 4 500ms 10"、
# "流水 2 3 4 5"），上面的对话式模板一个都盖不住。
def _terse(f: Frame, rng: random.Random, sp: Speaker) -> str | None:
    a = f.action
    if a is Action.SET and f.level is not Level.TOGGLE:
        # "1 所有灯"这种数字版留给英文；中文 terse 只用开/关。
        lvl, r = ("开" if f.level is Level.HIGH else "关"), _ref(f, sp)
        return f"{lvl} {r}" if rng.random() < 0.5 else f"{r} {lvl}"
    if a is Action.SET:
        return f"翻转 {_ref(f, sp)}"
    if a is Action.READ:
        r = _ref(f, sp)
        return rng.choice([f"读 {r}", f"{r} 状态", f"{r} 状态", f"查 {r}"])
    if a is Action.BLINK:
        r = _ref(f, sp)
        if f.interval_ms is None:
            # 有次数没频率："闪 4 五次"。次数必须说出来——它是这句话里唯一
            # 的数字，而且得有标记：光秃秃的尾数（"闪 4号脚 10"）没法和目标
            # 的一部分区分，含糊的标签教模型边界靠猜。
            if f.count:
                return rng.choice([f"闪 {r} x{f.count}",
                                   f"闪 {r} {f.count}次",
                                   f"闪 {r} 次数{f.count}"])
            return f"{rng.choice(['闪', '闪烁'])} {r}"
        ct = "" if f.count == 0 else f" {f.count}"
        # "闪 4号脚 速度300ms 次数20"——带关键字标签的槽位，对话式模板给
        # 不出来的形状。
        if rng.random() < 0.3:
            k = "" if f.count == 0 else f" 次数{f.count}"
            return (f"闪 {r} {rng.choice(['速度', '间隔', '频率'])} "
                    f"{f.interval_ms}ms{k}")
        return f"闪 {r} {f.interval_ms}ms{ct}"
    if a is Action.SEQ:
        body = (" ".join(str(t.n) for t in f.targets)
                if all(isinstance(t, Pin) for t in f.targets) else _ref(f, sp))
        head = rng.choice(["流水", "跑马", "扫描", "循环"])
        if f.interval_ms is None:
            return f"{head} {body}"
        # 次数必须说出来。丢掉它就等于给"流水 38 39 40 41 50ms"贴 <cnt> 3
        # 的标签——一个文本里根本不存在的数字。
        ct = "" if f.count == 0 else f" {f.count}"
        return f"{head} {body} {f.interval_ms}ms{ct}"
    if a is Action.STOP:
        return (f"停 {_ref(f, sp)}" if f.targets
                else rng.choice(["停", "全停", "停止", "停流水"]))
    return None


def _ref(f: Frame, sp: Speaker) -> str:
    """目标短语。所有吃引脚的动作都可能点名多个引脚，一律走这里，
    不许偷懒只取 targets[0]。"""
    return (sp.target(f.targets[0]) if len(f.targets) == 1
            else sp.target_list(f.targets))


def realize(f: Frame, rng: random.Random) -> str:
    """一帧的一个表面形式。反复调用获得多样性。"""
    a = f.action

    if rng.random() < 0.26:
        t = _terse(f, rng, Speaker(rng, terse=True))
        if t is not None:
            return _decorate(t, rng, "terse")
    sp = Speaker(rng)

    if a is Action.SET:
        # 两个目标、两个分句："打开6号脚，再打开11号脚"。真实输入里很常见，
        # 语料只有"和/、/再"连接的单句时整类会被拒。
        if (len(f.targets) == 2 and f.level is not Level.TOGGLE
                and rng.random() < 0.12):
            verb = "打开" if f.level is Level.HIGH else "关掉"
            a1, a2 = sp.target(f.targets[0]), sp.target(f.targets[1])
            return _decorate(f"{verb}{a1}，再{verb}{a2}", rng, "imperative")
        if f.level is Level.TOGGLE:
            bank, mood = TOGGLE_T, "imperative"
        elif rng.random() < 0.14:
            bank = ON_BARE if f.level is Level.HIGH else OFF_BARE
            mood = "bare"
        else:
            bank = ON_T if f.level is Level.HIGH else OFF_T
            mood = "imperative"
        s = bank[rng.randrange(len(bank))].format(r=_ref(f, sp))
        return _decorate(s + sp.where(), rng, mood)

    if a is Action.READ:
        r = _ref(f, sp)
        kind = rng.random()
        if kind < 0.45:
            return _decorate(rng.choice(READ_Q_T).format(r=r) + sp.where(),
                             rng, "question")
        if kind < 0.85:
            return _decorate(rng.choice(READ_CMD_T).format(r=r) + sp.where(),
                             rng, "imperative")
        return _decorate(rng.choice(READ_FRAG_T).format(r=r), rng, "bare")

    if a is Action.BLINK:
        r = _ref(f, sp)
        if f.count == 0:
            # 无限次：要么用前置频率词模板（自带频率），要么用前置"一直"
            # 模板。两条路都不许再拼次数或周量。
            bank = RATE_BLINK_T.get(f.interval_ms or 0)
            if bank and rng.random() < 0.35:
                return _decorate(rng.choice(bank).format(r=r), rng, "imperative")
            if f.interval_ms is None and rng.random() < 0.55:
                return _decorate(rng.choice(BLINK_FOREVER_T).format(r=r), rng)
        s = rng.choice(BLINK_T).format(r=r)
        return _decorate(_with_timing(s, f, rng, "下"), rng)

    if a is Action.SEQ:
        s = rng.choice(SEQ_T).format(r=sp.target_list(f.targets))
        return _decorate(_with_timing(s, f, rng, "轮"), rng)

    if a is Action.ALIAS:
        # 名字是最后一个目标，之前全是被命名的引脚——见 frames.validate。
        # 经 Speaker.name 逐字渲染，prepare.py 才能找到片段；模板自带的
        # 配文不能让这里再加一遍指示词。
        pins = [t for t in f.targets if isinstance(t, Pin)]
        nm = next(t for t in f.targets if isinstance(t, Name)).s
        r = (sp.pin(pins[0].n) if len(pins) == 1
             else sp.target_list(list(pins)))
        decl = rng.random() < 0.42
        bank = ALIAS_DECL_T if decl else ALIAS_T
        return _decorate(rng.choice(bank).format(r=r, n=nm), rng,
                         "neutral" if decl else "imperative")

    # STOP
    s = (rng.choice(STOP_ONE_T).format(r=_ref(f, sp))
         if f.targets else rng.choice(STOP_ALL_T))
    return _decorate(s, rng)


def _with_timing(s: str, f: Frame, rng: random.Random, unit: str) -> str:
    """接上周量和次数。顺序会变，因为两种说法都自然；固定一种会让模型
    只看位置不看意思。"""
    zero = f.count == 0
    if f.interval_ms is None:
        # 没有频率。若给了次数，它是这句话里唯一的数字，必须说出来——
        # 静默的次数等于标签在让模型凭空发明。两者都没有，用设备默认值。
        if zero:
            return _forever(s, rng)
        return s if not f.count else f"{s}{count_phrase(f.count, rng, unit)}"
    iv = interval_phrase(f.interval_ms, rng)
    if zero:
        # 有频率、无限次："让4号脚每500毫秒闪一次，别停"。
        head = f"{s}，{iv}"
        return _forever(head, rng) if rng.random() < 0.5 else head + rng.choice(
            ["", "", "，别停", "，一直闪", "，不要停"])
    ct = count_phrase(f.count, rng, unit)
    # "闪烁三次"顺接自然，周量则用逗号断开更像人话；两种顺序都出。
    head = f"{s}{ct}"
    return f"{head}，{iv}" if rng.random() < 0.35 else f"{s}，{iv}{ct}"


if __name__ == "__main__":
    import frames

    rng = random.Random(1)
    for _ in range(28):
        fr = frames.sample_frame(rng)
        print(f"{realize(fr, rng):<50}  {' '.join(frames.to_symbols(fr))}")
