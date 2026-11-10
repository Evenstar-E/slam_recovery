# `trace_group.csv` schema v2（与 r11070-c3 对齐）

按 r11070-c3 的表为准，我只改一处、采纳两处。**改动理由写在下面，双方确认后不要再动。**

## 列

```
kind,wall_ns,lid_stamp_ns,n_items,first_stamp_ns,last_stamp_ns,stamps_sha256,extra
```

| kind | n_items | first/last | stamps_sha256 | extra |
|---|---|---|---|---|
| `ARRIVE` | 1 | 该条 header stamp | sha256(该条 ns) | `buflen=<写完后的 buffer 长度>` |
| `GROUP` | 组内 IMU 样本数 | 组内 IMU 首/末 | 组内**全部** IMU 样本 ns，按消费顺序 | `mesures=<n>;img=<n>;img_stamp=<ns>;need_init=<0/1>` |
| `IMUINIT` | 该组 IMU 数 | 该组首/末 | 同上 | `iter=<N>;max=<MAX_INI_COUNT>` |
| `STATE` | 0 | 该帧 lidar stamp | 空 | `pos=<x>|<y>|<z>;diagR=<r00>|<r11>|<r22>` |

## 与原提法的三处差异

### 1. 时间列必须是**整数纳秒**，不是 `%.9f` 秒（必须改）

原方案写「所有时间单位秒（float，`%.9f`）」。**这一点不能接受**：

- epoch 秒约 `1.6e9`，double 有约 15–16 位有效数字，在 1.6e9 量级上只能分辨约 `1e-7 s = 100 ns`；
- 也就是说 `%.9f` 打出来有 9 位小数，但**第 7–9 位是格式化出来的，不是数据里有的**；
- 这次调查的起点恰恰是 **715 ns 的边界差异**——用 double 秒记录，正好在这个量级上不可信。

所以 `wall_ns / lid_stamp_ns / first_stamp_ns / last_stamp_ns` 全部写 **int64 纳秒**：
`sec * 1_000_000_000LL + nanosec`，不经过 double。列名相应改为 `_ns`，避免有人误读单位。

### 2. 哈希拼接采纳原方案（改我的）

原方案：`sha256( concat( int64_le(ns_i) ) )`，**保持消费顺序，不排序**。
我原来的「逗号连字符串」改成这个——二进制拼接无格式歧义，且不排序是对的：
**组内顺序本身就是要观测的变量之一**，排序会把候选证据抹掉。

### 3. `extra` 里**不能出现逗号**（必须改）

原方案写 `pos=<x>,<y>,<z>`。但 `extra` 是 CSV 的最后一列，裸逗号会被 CSV 解析器当作列分隔，
`pos` 只剩第一个分量，后两个分量会散进不存在的列——**文件静默损坏，不是解析器能补救的**。

两条出路，选其一：

- **（采用）列内改用竖线**：`pos=<x>|<y>|<z>`、`diagR=<a>|<b>|<c>`；`extra` 整体不含逗号，
  写入端不需要任何引用/转义。解析器同时接受 `|` 与 `,`（后者仅为容错）。
- 或者对整个 `extra` 字段做标准 CSV 引用（`"pos=1,2,3;..."`），但 C++ 侧要自己实现引用规则，
  多一处可能出错的地方。

解析仍按分号切键值、按第一个等号切键与值。

## 解析器必须拒绝的情况

- 未知 `kind` → 报错退出，不跳过；
- `GROUP`/`IMUINIT` 缺 `stamps_sha256` → 报错（"没有样本"与"没记录"必须可区分）；
- 时间列非整数 → 报错，不静默转 float。

## 判据（与实现无关，先写死）

- `GROUP` 组成相同（`n_items + first + last + sha + mesures + img`）而 `STATE` 分歧 → **UNKNOWN**，
  不把分歧归给分组构成（S3/S4 都不宣布）；
- `GROUP` 组成不同 → `GROUP_COMPOSITION_VARIES`，是候选机制，不是原因；
- tracing OFF 的对照也分歧 → 分歧不是 tracing 造成的；
- 单对 trace 不出因果结论。
