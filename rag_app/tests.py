import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.retrievers import BaseRetriever

from rag_app.rag_core import OllamaRerankCompressor


# ─── 测试辅助函数 ─────────────────────────────────────────────────────────────

def _make_compressor(**overrides) -> OllamaRerankCompressor:
    """创建测试用压缩器，所有参数可覆盖。"""
    defaults = dict(
        model="test-model",
        base_url="http://127.0.0.1:11434",
        top_n=3,
        timeout=5,
        ollama_client=MagicMock(),
    )
    defaults.update(overrides)
    return OllamaRerankCompressor(**defaults)


def _make_docs(n: int) -> list[Document]:
    return [Document(page_content=f"文档内容 {i}", metadata={"doc_id": str(i)}) for i in range(n)]


def _mock_urlopen(results: list[dict]):
    """构造一个返回 {results: [...]} 的 urlopen mock。"""
    body = json.dumps({"results": results}).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ─── /api/rerank 专用接口路径 ────────────────────────────────────────────────

class TestRerankAPIPath(SimpleTestCase):

    def test_正常重排并写入relevance_score(self):
        docs = _make_docs(4)
        rerank_results = [
            {"index": 2, "relevance_score": 0.99},
            {"index": 0, "relevance_score": 0.87},
            {"index": 3, "relevance_score": 0.75},
        ]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor().compress_documents(docs, "测试问题")

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].page_content, docs[2].page_content)
        self.assertEqual(result[1].page_content, docs[0].page_content)
        self.assertAlmostEqual(result[0].metadata["rerank_score"], 0.99)
        self.assertAlmostEqual(result[1].metadata["rerank_score"], 0.87)

    def test_使用score字段作为备用分数键(self):
        docs = _make_docs(2)
        rerank_results = [{"index": 1, "score": 0.88}, {"index": 0, "score": 0.6}]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor().compress_documents(docs, "测试")

        self.assertAlmostEqual(result[0].metadata["rerank_score"], 0.88)

    def test_重复索引只保留第一次出现(self):
        docs = _make_docs(3)
        rerank_results = [
            {"index": 1, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.8},  # 重复，应被忽略
            {"index": 0, "relevance_score": 0.7},
        ]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor().compress_documents(docs, "测试")

        contents = [r.page_content for r in result]
        self.assertEqual(contents.count(docs[1].page_content), 1)

    def test_越界索引被过滤(self):
        docs = _make_docs(3)
        rerank_results = [
            {"index": 99, "relevance_score": 0.99},  # 越界
            {"index": 0,  "relevance_score": 0.8},
        ]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor().compress_documents(docs, "测试")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].page_content, docs[0].page_content)

    def test_top_n限制最终返回数量(self):
        docs = _make_docs(6)
        rerank_results = [{"index": i, "relevance_score": 1.0 - i * 0.1} for i in range(6)]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor(top_n=2).compress_documents(docs, "测试")

        self.assertEqual(len(result), 2)

    def test_空文档列表直接返回空(self):
        result = _make_compressor().compress_documents([], "任意问题")
        self.assertEqual(list(result), [])


# ─── API 不可用时的降级路径 ───────────────────────────────────────────────────

class TestRerankFallbackPaths(SimpleTestCase):

    def _stub_generate(self, client: MagicMock, results: list[dict]) -> None:
        resp = MagicMock()
        resp.response = json.dumps({"results": results})
        client.generate.return_value = resp

    def test_http404时切换到兼容生成模式(self):
        docs = _make_docs(3)
        client = MagicMock()
        self._stub_generate(client, [{"index": 2, "score": 0.9}, {"index": 0, "score": 0.8}])

        with patch("rag_app.rag_core.request.urlopen", side_effect=HTTPError(None, 404, "Not Found", {}, None)):
            result = _make_compressor(ollama_client=client).compress_documents(docs, "测试")

        self.assertEqual(result[0].page_content, docs[2].page_content)
        self.assertEqual(result[1].page_content, docs[0].page_content)

    def test_网络不可达时切换到兼容生成模式(self):
        docs = _make_docs(3)
        client = MagicMock()
        self._stub_generate(client, [{"index": 1, "score": 0.95}])

        with patch("rag_app.rag_core.request.urlopen", side_effect=URLError("connection refused")):
            result = _make_compressor(ollama_client=client).compress_documents(docs, "测试")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].page_content, docs[1].page_content)

    def test_兼容模式响应非法JSON时回退候选前N条(self):
        docs = _make_docs(5)
        client = MagicMock()
        client.generate.return_value = MagicMock(response="这不是json")

        with patch("rag_app.rag_core.request.urlopen", side_effect=URLError("no")):
            result = _make_compressor(top_n=2, ollama_client=client).compress_documents(docs, "测试")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].page_content, docs[0].page_content)

    def test_重排结果全部无效时回退候选前N条(self):
        docs = _make_docs(4)
        # results 为空列表 → 无有效索引 → 回退
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen([])):
            result = _make_compressor(top_n=2).compress_documents(docs, "测试")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].page_content, docs[0].page_content)

    def test_api和兼容模式均异常时回退候选前N条(self):
        docs = _make_docs(4)
        client = MagicMock()
        client.generate.side_effect = RuntimeError("模型加载失败")

        with patch("rag_app.rag_core.request.urlopen", side_effect=URLError("no")):
            result = _make_compressor(top_n=2, ollama_client=client).compress_documents(docs, "测试")

        self.assertEqual(len(result), 2)


# ─── ContextualCompressionRetriever 装配验证 ─────────────────────────────────

class TestContextualCompressionRetrieverAssembly(SimpleTestCase):

    def test_compression_retriever将ensemble候选传给compressor并返回重排结果(self):
        seen = {}

        # 基础 retriever 返回 6 条候选（须为真正的 Runnable，故用 BaseRetriever 子类）
        class _StubRetriever(BaseRetriever):
            def _get_relevant_documents(self, query, *, run_manager=None):
                return _make_docs(6)

        # compressor 只返回前 3 条，并记录收到的候选数量
        class _StubCompressor(BaseDocumentCompressor):
            def compress_documents(self, documents, query, callbacks=None):
                seen["candidate_count"] = len(documents)
                return list(documents[:3])

        retriever = ContextualCompressionRetriever(
            base_retriever=_StubRetriever(),
            base_compressor=_StubCompressor(),
        )
        result = retriever.invoke("任意问题")

        # compressor 应拿到全部 6 条候选，最终结果由 compressor 决定
        self.assertEqual(seen["candidate_count"], 6)
        self.assertEqual(len(result), 3)

    def test_原始metadata不被compressor污染(self):
        docs = _make_docs(2)
        rerank_results = [{"index": 0, "relevance_score": 0.95}]
        with patch("rag_app.rag_core.request.urlopen", return_value=_mock_urlopen(rerank_results)):
            result = _make_compressor().compress_documents(docs, "测试")

        # 原始文档 metadata 的 doc_id 字段保留不变
        self.assertEqual(result[0].metadata["doc_id"], docs[0].metadata["doc_id"])
        # rerank_score 写入的是副本，不修改原始文档
        self.assertNotIn("rerank_score", docs[0].metadata)
