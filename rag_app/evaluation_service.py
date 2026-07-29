import copy
import io
import json
import math
from collections.abc import Iterable
from statistics import fmean

from django.utils import timezone
from langchain_core.messages import AIMessage, HumanMessage

from .rag_core import RAGConfig


DEFAULT_RAG_CONFIG = {
    "indexing": {
        "chunk_size": RAGConfig.ChunkSize,
        "chunk_overlap": RAGConfig.ChunkOverlap,
    },
    "retrieval": {
        "vector_weight": 0.8,
        "bm25_weight": 0.2,
        "ensemble_top_k": RAGConfig.RerankCandidateCount,
        "rerank_top_k": RAGConfig.RerankTopN,
    },
}


def normalize_rag_config(value):
    """合并默认 RAG 配置，确保后续保存和比较使用完整结构。"""
    normalized = copy.deepcopy(DEFAULT_RAG_CONFIG)
    if not isinstance(value, dict):
        return normalized

    for section in ("indexing", "retrieval"):
        section_value = value.get(section)
        if isinstance(section_value, dict):
            normalized[section].update(section_value)
    return normalized


def validate_rag_config(value):
    """校验并返回完整的 RAG 配置；非法时抛出 ValueError。"""
    config = normalize_rag_config(value)
    indexing = config["indexing"]
    retrieval = config["retrieval"]

    for key in ("chunk_size", "chunk_overlap"):
        if not isinstance(indexing[key], int) or isinstance(indexing[key], bool) or indexing[key] < 0:
            raise ValueError(f"{key} 必须是非负整数")
    if indexing["chunk_size"] <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if indexing["chunk_overlap"] >= indexing["chunk_size"]:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    for key in ("vector_weight", "bm25_weight"):
        if not isinstance(retrieval[key], (int, float)) or isinstance(retrieval[key], bool) or retrieval[key] < 0:
            raise ValueError(f"{key} 必须是非负数")
    if retrieval["vector_weight"] + retrieval["bm25_weight"] <= 0:
        raise ValueError("向量检索与 BM25 权重之和必须大于 0")

    for key in ("ensemble_top_k", "rerank_top_k"):
        if not isinstance(retrieval[key], int) or isinstance(retrieval[key], bool) or retrieval[key] <= 0:
            raise ValueError(f"{key} 必须是正整数")
    if retrieval["rerank_top_k"] > retrieval["ensemble_top_k"]:
        raise ValueError("rerank_top_k 不能大于 ensemble_top_k")
    return config


def indexing_config_changed(old_value, new_value):
    """只比较会影响索引内容的分块配置。"""
    old_config = normalize_rag_config(old_value)
    new_config = normalize_rag_config(new_value)
    return old_config["indexing"] != new_config["indexing"]


def _message_content(message):
    """提取 LangChain PostgreSQL 历史消息中的文本内容。"""
    if not isinstance(message, dict):
        return ""
    data = message.get("data")
    if isinstance(data, dict):
        content = data.get("content", "")
    else:
        content = message.get("content", "")
    if isinstance(content, list):
        return "\n".join(str(item) for item in content if item)
    return str(content or "").strip()


def _message_type(message):
    if not isinstance(message, dict):
        return ""
    data = message.get("data")
    message_type = message.get("type") or (data.get("type") if isinstance(data, dict) else None)
    if message_type in ("human", "ai"):
        return message_type
    return ""


def build_evaluation_turns(messages: Iterable):
    """将历史消息标准化为可评估的完整 Human/AI 问答轮次。"""
    normalized = []
    for item in messages:
        message = getattr(item, "message", item)
        message_type = _message_type(message)
        content = _message_content(message)
        if not message_type or not content:
            continue
        if normalized and normalized[-1]["type"] == message_type:
            if message_type == "human":
                normalized[-1]["content"] = f"{normalized[-1]['content']}\n{content}"
            else:
                normalized[-1]["content"] = content
        else:
            normalized.append({"type": message_type, "content": content})

    turns = []
    history = []
    index = 0
    seen_questions = set()
    while index < len(normalized):
        current = normalized[index]
        if current["type"] != "human":
            history.append(current)
            index += 1
            continue

        question = current["content"]
        answer = ""
        next_index = index + 1
        while next_index < len(normalized) and normalized[next_index]["type"] == "ai":
            answer = normalized[next_index]["content"]
            next_index += 1

        question_key = " ".join(question.split())
        if answer and question_key not in seen_questions:
            turns.append({
                "question": question,
                "ai_answer": answer,
                "history_context": copy.deepcopy(history),
            })
            seen_questions.add(question_key)

        history.append(current)
        if answer:
            history.append({"type": "ai", "content": answer})
        index = next_index if next_index > index + 1 else index + 1
    return turns


def history_context_to_messages(history_context):
    """将数据库 JSON 历史上下文转换为 LangChain 内存消息。"""
    messages = []
    for item in history_context or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if item.get("type") == "ai":
            messages.append(AIMessage(content=content))
        elif item.get("type") == "human":
            messages.append(HumanMessage(content=content))
    return messages


def adapt_ragas_dataframe(dataframe):
    """兼容不同 Ragas 版本的列名，返回统一的评估明细列表。"""
    aliases = {
        "faithfulness": ("faithfulness",),
        "answer_relevancy": ("answer_relevancy", "answer_relevance"),
        "context_recall": ("context_recall",),
        "context_precision": ("context_precision",),
    }
    records = dataframe.to_dict(orient="records")
    adapted = []
    for record in records:
        item = dict(record)
        for target, candidates in aliases.items():
            for candidate in candidates:
                if candidate in record:
                    item[target] = record[candidate]
                    break
            else:
                item[target] = None
        adapted.append(item)
    return adapted


def aggregate_metrics(records):
    """计算四项有效平均值和固定的 context precision/recall F1。"""
    metric_names = ("faithfulness", "answer_relevancy", "context_recall", "context_precision")
    result = {}
    for name in metric_names:
        values = []
        for record in records:
            value = record.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isnan(value):
                values.append(float(value))
        if not values:
            raise ValueError(f"Ragas 未返回有效的 {name} 指标")
        result[name] = round(fmean(values), 6)
    precision = result["context_precision"]
    recall = result["context_recall"]
    result["f1_score"] = round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0
    return result


def create_excel_report(records, rag_config):
    """生成仅含 results/config 两个工作表的 Excel 二进制内容。"""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("未安装 pandas，无法生成评估报告") from exc

    output = io.BytesIO()
    config_rows = [{"rag_config": json.dumps(rag_config, ensure_ascii=False, indent=2)}]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(records).to_excel(writer, sheet_name="results", index=False)
        pd.DataFrame(config_rows).to_excel(writer, sheet_name="config", index=False)
    output.seek(0)
    return output


def parse_datetime(value):
    """解析 API 时间值，空值保持为空。"""
    if not value:
        return None
    parsed = timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
