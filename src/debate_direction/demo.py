"""A labeled, deterministic example. This provider makes zero model calls."""

from copy import deepcopy

from .provider import Completion

DEMO_QUESTION = "修改客服工单后台，让客服更快找到需要处理的工单。团队只有两周时间，请找出可试点的方向。"
DEMO_CONTEXT = "固定演示材料：已有工单列表和权限控制。当前没有用户任务耗时数据，也没有提供接口或代码。所有方案仍需验证。"


def proposal(revised=False):
    return {
        "needs_clarification": False, "clarification_questions": [],
        "problem_statement": "客服需要更快找到待处理工单，但具体瓶颈尚未测量。",
        "goal": "在两周内选择并验证一个可回退的改进方向。",
        "success_criteria": ["预先记录典型任务耗时与误操作，再比较试点结果。", "保留现有数据权限与工作入口。"],
        "assumptions": ["团队可以邀请代表性客服参与短期试用。", "现有接口能力尚需查看。"],
        "options": [
            {"id": "P1", "title": "重做搜索与智能推荐", "approach": "整体重做搜索，并增加推荐入口。", "tradeoffs": ["范围较大，缺少瓶颈证据。"]},
            {"id": "P2", "title": "组合筛选与个人视图试点", "approach": "先测量，再小范围增加筛选、排序和保存视图。", "tradeoffs": ["改善范围有限，需要验证接口和权限。"]},
        ],
        "recommended_option_id": "P2" if revised else "P1",
        "recommendation": "先观察典型任务，再试点组合筛选和个人视图；保留旧入口并提供回退。" if revised else "重做搜索并增加智能推荐，以减少查找工单的时间。",
        "implementation_steps": (["观察典型工单查找任务并记录基线。", "确认现有接口和权限约束。", "做组合筛选、可切换排序与个人视图的小范围试点。", "按事先约定的成功标准决定保留、调整或回退。"] if revised else ["梳理搜索字段。", "开发新搜索与推荐界面。", "邀请客服试用。"]),
        "conditions": ["试点功能使用现有服务端权限校验。", "若接口不支持所需筛选，应先调整试点范围。"],
        "validation_steps": ["测量修改前后相同任务的完成时间及误操作。", "检查角色权限、越权访问与保存视图的数据隔离。", "在真实量级数据上检查查询响应时间。"],
        "public_summary": "撤回整体重做，改为可回退的小范围试点，并把权限检查列入上线条件。" if revised else "优先重做搜索与智能推荐，同时列出小范围筛选试点备选。",
        "responses": ([
            {"issue_id": "I-001", "action": "fix", "summary": "接受范围和证据不足的异议，撤回整体重做。", "change": "改选 P2，先测量再试点。"},
            {"issue_id": "I-002", "action": "fix", "summary": "个人视图只保存筛选配置，仍由服务端按现有权限查询。", "change": "增加权限测试与失败回退条件。"},
        ] if revised else []),
    }


class DemoProvider:
    """Scripted responses solely for the built-in demonstration scenario."""

    def complete(self, *, role, phase, round_number, instructions, messages, schema, config):
        if phase in {"propose", "revise"}:
            data = proposal(revised=phase == "revise")
        elif phase == "risk_scan":
            data = {"needs_clarification": False, "clarification_questions": [],
                    "success_criteria": ["目标应以任务耗时与误操作衡量。", "两周内可回退。"],
                    "risk_areas": [
                        {"id": "R1", "severity": "high", "concern": "没有证据表明搜索是主要瓶颈。", "check": "先观察真实任务。"},
                        {"id": "R2", "severity": "high", "concern": "个人视图可能意外扩大数据权限。", "check": "服务端复用现有权限校验。"},
                    ], "public_summary": "先独立检查瓶颈证据、两周范围、权限与可回退性。"}
        elif phase == "review" and round_number == 1:
            data = {"assessment": "revise", "public_summary": "整体重做缺少瓶颈证据，且权限约束没有落实到具体设计。",
                    "clarification_questions": [],
                    "new_issues": [
                        {"id": "I-001", "severity": "high", "title": "重做范围缺少依据", "description": "没有任务数据支持重做搜索，难以证明两周内值得投入。", "target": "P1", "resolution_criterion": "缩小改动范围，并先测量基线。"},
                        {"id": "I-002", "severity": "high", "title": "个人视图权限边界不清", "description": "保存视图不能跳过服务端工单权限。", "target": "P2", "resolution_criterion": "将现有权限校验和隔离测试写入设计与上线条件。"},
                    ], "issue_evaluations": [], "conditions": ["保留旧入口。"], "next_steps": ["将改动收窄为可回退的试点。"]}
        elif phase == "review":
            data = {"assessment": "accept", "public_summary": "接受小范围试点方向；瓶颈改善与性能仍须实测。",
                    "clarification_questions": [], "new_issues": [],
                    "issue_evaluations": [
                        {"issue_id": "I-001", "status": "resolved", "rationale": "最新方案已撤回整体重做，改为先测量再试点。"},
                        {"issue_id": "I-002", "status": "resolved", "rationale": "最新设计明确复用服务端权限，并列出隔离测试及回退条件。"},
                    ], "conditions": ["接口、权限与真实性能检查通过后才开展试点。"], "next_steps": ["提供现有界面与典型工作流程，确定试点范围。"]}
        else:
            raise ValueError("Unsupported demo phase")
        if phase == "review":
            data["reviewed_version"] = round_number
        return Completion(data=deepcopy(data), model="demo-scripted", input_tokens=0,
                          output_tokens=0, response_id=f"demo-{role}-{phase}-{round_number}")
