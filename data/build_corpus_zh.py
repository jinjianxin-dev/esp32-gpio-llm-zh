"""组装中文训练语料（build_corpus_zh.py）。

结构照搬 data/build_corpus.py：正样本由 frames.sample_frame 采样、经
zh_realize 渲染成中文；负样本由 zh_negatives 提供。唯一的内容差别是
NEG_MIX——英文版从 MASSIVE 取约一半负样本（真人话语），中文语料用不了
那个数据集（它的中文版不带引脚概念，且近样本过滤规则是按英文 intents
写的），所以负样本全部来自合成库 + 从正样本表面形式推导的残句。

输出 JSONL，每行一个样本：

    {"text": ..., "symbols": [...], "action": ..., "source": ..., "split": ...}

用法：
    uv run python data/build_corpus_zh.py --n 150000 --out data/corpus
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import frames
import zh_names
import zh_negatives as negatives
import zh_realize as realize
from frames import Action

# frames.py 顶层 `import names`，引脚池之外的名字槽位（Name 目标、组名、
# alias 的名字）都从它出。这里把 frames 视角里的名字池整体重定向到中文
# 模块——不改动上游 frames.py 一行，英文管线照常可用。
frames.names = zh_names

# 负样本占全语料的比例。足够高，<unknown> 才不是稀有类别；足够低，模型
# 才不会学着默认拒绝。与英文版一致（0.30）。
NEG_FRACTION = 0.30

# 英文版的负样本配比是 massive_near 0.23 / massive_far 0.26 / synthetic
# 0.34 / truncated 0.17。中文没有 MASSIVE，两份份额全部还给 synthetic 和
# truncated，按原比例（34:17 = 2:1）分配。
NEG_MIX = {"synthetic": 0.66, "truncated": 0.34}


def build(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    seen: set[str] = set()

    def add(text: str, frame: frames.Frame, source: str) -> bool:
        key = text.lower().strip()
        if not key or key in seen:
            return False
        seen.add(key)
        rows.append({
            "text": text,
            "symbols": frames.to_symbols(frame),
            "action": frame.action.value,
            "source": source,
        })
        return True

    n_neg = int(n * NEG_FRACTION)
    n_pos = n - n_neg

    # --- 正样本 ---------------------------------------------------------------
    got = tries = 0
    while got < n_pos:
        tries += 1
        if tries > n_pos * 40:
            print(f"  ! 模板空间在 {got:,} 条正样本时耗尽（{tries:,} 次抽样）")
            break
        f = frames.sample_frame(rng)
        got += add(realize.realize(f, rng), f, "template")

    # --- 负样本 ---------------------------------------------------------------
    unknown = frames.Frame(Action.UNKNOWN)
    for kind, share in NEG_MIX.items():
        want = int(n_neg * share)
        if kind == "synthetic":
            got, tries = 0, 0
            while got < want and tries < want * 60:
                tries += 1
                got += add(negatives.sample_negative(rng), unknown, "synthetic")
            continue
        if kind == "truncated":
            # 把真命令切短。半截输入曾是最大的误接受类别，切口必须从正样本
            # 用的同一批表面形式推导，否则切口落错地方。
            got, tries = 0, 0
            while got < want and tries < want * 60:
                tries += 1
                f = frames.sample_frame(rng)
                cut = negatives.truncate(realize.realize(f, rng), rng)
                if cut:
                    got += add(cut, unknown, "truncated")
            continue

    rng.shuffle(rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-frac", type=float, default=0.02)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "corpus")
    a = ap.parse_args()

    rows = build(a.n, a.seed)
    n_val = int(len(rows) * a.val_frac)
    a.out.mkdir(parents=True, exist_ok=True)

    for name, chunk in (("val", rows[:n_val]), ("train", rows[n_val:])):
        for r in chunk:
            r["split"] = name
        with (a.out / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in chunk:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    print(f"{len(rows):,} rows -> {a.out}  (train {len(rows) - n_val:,} / val {n_val:,})")
    print("\n按动作:")
    for k, v in Counter(r["action"] for r in rows).most_common():
        print(f"  {k:<9} {v:7,}  {v / len(rows):5.1%}")
    print("\n按来源:")
    for k, v in Counter(r["source"] for r in rows).most_common():
        print(f"  {k:<14} {v:7,}  {v / len(rows):5.1%}")


if __name__ == "__main__":
    main()
