# 主线/旁支验收 9bd2ff7

范围8cc4b30..9bd2ff7，两笔、8文件。完整读189行audit、protocol/日报解释增量，当前analysis相关坐标路径再核，AST运行audit缺独立结果fixture。无新host或测量代码修复，不重复主单测。

## 主线状态

本轮仅审计/解释更新，无新有效测量。保留预注册full-alignment决策变量、不结果后换指标，方向正确；但不能把已知错误的prefix值称第二有效口径。上轮两真实评价阻断未修：map读不同输入策略的bags，prefix将run→clean变换后与GT直接比较。因此“协议下八次全失败”尚无合法数值依据。

最低主线解除：用每receipt实际消费input cloud重建map、正确healthy-prefix run→GT或clean→GT预校准变换，已有八输出重算即可。报告预注册full诊断结论和新合法prefix对照，不更换成功标准来拯救结果。此后再判断重复差异/因素，不再增加纯audit措辞提交。

## 旁支审计不能用PASS替代缺测

本机AST执行audit_independent，results含O#1而ev={}时verdict=PASS、independent=None。缺独立run/ATE应UNVERIFIABLE，缺任何8格不能宣布全复算。当前归档ev存在，未声称该路径已触发本档；把负例集中随主线修复。

audit_receipts只将disk hash匹配列字段，未将False纳入bad；只检查binary path/revision存在而非8份config/binary一致与output hash绑定，较强主张需核真实链。当前上轮本机已核input config/binary字段一致，所以不反复重跑bag；只修summary范围。

## 接受范围

不因为预注册选择不理想就结果后改判变量，但无效prefix统计必须先更正而非借“不换规则”继续引用。full diag配对不同数字方向相同仅支持阈值侧一致，不意味着全数据复现。n=2与特定interaction rule不支持通用无交互或方差统计主导。

开发侧先§10.12自检PASS/FAIL/BLOCKED/NA，主线负责真实输入/坐标重算，工程audit角色负例/summary并行。已有八run是主线进展，当前轮只是旁支，不能以audit文件新增冒充确认。今晚日报将新prefix全失败声明标未验证，不列有效结果。
