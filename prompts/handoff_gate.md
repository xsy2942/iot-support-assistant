# Low Confidence Handoff Gate

你需要判断当前问题应该“直接回答”“建议复核”还是“转人工”。

## 输入

- 用户问题
- TopK 检索片段
- 检索相似度
- 是否命中错误码
- 是否包含风险关键词

## 判断规则

直接回答：

- Top3 中至少有 1 条片段明确覆盖问题类型或错误码。
- 问题不涉及赔偿、投诉、安全事故、法律责任、数据丢失。
- 排查动作不会扩大现场风险。

建议复核：

- 检索命中相关设备型号，但没有明确覆盖固件版本或错误码。
- 多个资料片段结论不一致。
- 用户描述缺少关键字段，例如设备型号、固件版本、错误码、最近日志。

转人工：

- 错误码未知。
- TopK 检索相似度过低。
- 涉及安全、法律、赔偿、投诉、数据全部丢失。
- 客户要求人工负责人介入。

## 输出 JSON

```json
{
  "route": "direct_answer | review | handoff",
  "confidence_reason": "判断依据",
  "missing_fields": ["device_model", "firmware_version", "error_code"],
  "ticket_required": true
}
```
